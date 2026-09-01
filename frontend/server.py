"""server.py — Flask web frontend for the EDR telemetry validation console.

Thin wrapper around the existing CLI: every action is a subprocess call to
runner/telemetry_runner.py (single case) or run_all.py (whole module). A
global serialized queue guarantees only one VM-driving task runs at a time;
console output is streamed to the browser via Server-Sent Events.
"""

from __future__ import annotations

import io
import json
import os
import zipfile
import queue as queue_mod
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

_HERE = Path(__file__).resolve().parent          # E:/EDR/frontend
ROOT = _HERE.parent / 'automation'   # E:/EDR/automation
CORE = ROOT / 'core'
TOOLS = ROOT / 'tools'
CONFIG = ROOT / 'config'
RUNS = ROOT.parent / 'results' / 'runs'
RUNNER = ROOT / 'runner' / 'telemetry_runner.py'
RUN_ALL = ROOT / 'run_all.py'

for _p in (ROOT, CORE, TOOLS):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    from flask import Flask, Response, jsonify, request, send_from_directory
except ImportError:
    Flask = None  # type: ignore

from status import collect_status
from audit_hashes import audit_and_update


app = Flask(__name__, static_folder=str(_HERE), static_url_path='')

# ── global serialized task queue (single shared VM) ────────────────────────
_task_queue: "queue_mod.Queue" = queue_mod.Queue()
_tasks: dict[str, "Task"] = {}
_tasks_lock = threading.Lock()


class Task:
    def __init__(self, command: list[str], cwd: Path):
        self.id = uuid.uuid4().hex[:12]
        self.command = command
        self.cwd = cwd
        self.state = 'queued'
        self.exit_code = None
        self.lines: list[str] = []
        self._cond = threading.Condition()
        self._done = False
        self.proc = None
        self._stopped = False

    def add_line(self, line: str):
        with self._cond:
            self.lines.append(line)
            self._cond.notify_all()

    def finish(self, exit_code: int):
        with self._cond:
            if self._done:
                return
            self.exit_code = exit_code
            self.state = 'done'
            self._done = True
            self._cond.notify_all()

    def snapshot(self, start_idx: int):
        with self._cond:
            return self.lines[start_idx:], self._done, self.exit_code

    def stop(self):
        """手动停止：杀整个进程树（python + vmrun 等子进程）并结束 SSE。"""
        with self._cond:
            if self._done:
                return
            self._stopped = True
            proc = self.proc
        if proc is not None and proc.poll() is None:
            try:
                # Windows：taskkill /T /F 杀整个进程树（含 vmrun 等子进程），
                # 只 kill python 会残留 vmrun 孤儿进程，导致「停不干净」。
                subprocess.run(
                    ['taskkill', '/PID', str(proc.pid), '/T', '/F'],
                    capture_output=True, timeout=10,
                )
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        self.add_line('── 已手动停止 ──')
        self.finish(-1)


def _worker():
    while True:
        task = _task_queue.get()
        task.state = 'running'
        try:
            # 强制子进程 UTF-8 输出：Windows 下 Python 默认按 GBK 输出非 ASCII
            # 字符（─、…、→ 等），与这里 utf-8 解码冲突会产生乱码。
            env = dict(os.environ)
            env['PYTHONIOENCODING'] = 'utf-8'
            proc = subprocess.Popen(
                task.command,
                cwd=str(task.cwd),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=1,
                env=env,
            )
            task.proc = proc
            assert proc.stdout is not None
            for line in proc.stdout:
                task.add_line(line.rstrip('\n'))
            proc.wait()
            task.finish(proc.returncode)
        except Exception as exc:  # noqa: BLE001
            task.add_line(f'[server error] {exc}')
            task.finish(-1)


_thread = threading.Thread(target=_worker, daemon=True)
_thread.start()


def _enqueue(command: list[str]) -> "Task":
    # 子进程 stdout 在非 TTY（管道）下是块缓冲：runner 的 print() 会等到进程
    # 结束才一次性 flush，导致前端 SSE「终端不实时更新」。给 Python 子进程加
    # -u（unbuffered），让 print 逐行实时流出。
    if command and command[0] == sys.executable and '-u' not in command[:2]:
        command = command[:1] + ['-u'] + command[1:]
    task = Task(command, ROOT)
    with _tasks_lock:
        _tasks[task.id] = task
    _task_queue.put(task)
    return task


# ── helpers ────────────────────────────────────────────────────────────────

def _find_case(case_id: str) -> dict | None:
    p = CONFIG / 'test_cases.json'
    try:
        data = json.loads(p.read_text(encoding='utf-8-sig'))
        cases = data.get('cases', []) if isinstance(data, dict) else data
    except Exception:
        return None
    for c in cases:
        if c.get('id') == case_id:
            return c
    return None


def _samples_root() -> Path:
    p = CONFIG / 'vm_config.json'
    try:
        cfg = json.loads(p.read_text(encoding='utf-8-sig'))
        if cfg.get('samples_root'):
            return Path(cfg['samples_root'])
    except Exception:
        pass
    return ROOT.parent / 'samples'


def _log_roots() -> list[Path]:
    return [ROOT.parent / 'logs']


def _list_log_candidates(module: str, case_id: str) -> list[dict]:
    """List candidate IOA JSON exports (newest first, case_id matches first)."""
    mod_dir = Path(module)
    found: dict[str, dict] = {}
    for root in _log_roots():
        for sub in (Path(),):
            d = root / sub
            if not d.is_dir():
                continue
            for p in d.glob('*.json'):
                try:
                    st = p.stat()
                except OSError:
                    continue
                key = str(p)
                if key not in found or st.st_mtime > found[key]['mtime']:
                    found[key] = {
                        'path': str(p),
                        'name': p.name,
                        'mtime': st.st_mtime,
                        'size': st.st_size,
                    }
    items = sorted(found.values(), key=lambda x: x['mtime'], reverse=True)
    items.sort(key=lambda x: 0 if case_id.lower() in x['name'].lower() else 1)
    for it in items:
        it['mtime'] = time.strftime('%Y-%m-%d %H:%M', time.localtime(it['mtime']))
    return items


# ── routes ─────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory(str(_HERE), 'index.html')


@app.route('/api/overview')
def api_overview():
    return jsonify(collect_status())


@app.route('/api/industry')
def api_industry():
    p = CONFIG / 'industry_baseline.json'
    if not p.exists():
        return jsonify({})
    try:
        return jsonify(json.loads(p.read_text(encoding='utf-8')))
    except Exception:
        return jsonify({})


@app.route('/api/classmate_baseline')
def api_classmate_baseline():
    """同学实测的『行为→IOA事件类型/字段』映射，作演示期兜底参照（暂时保留）。"""
    p = CONFIG / 'classmate_baseline.json'
    if not p.exists():
        return jsonify({})
    try:
        return jsonify(json.loads(p.read_text(encoding='utf-8')))
    except Exception:
        return jsonify({})


@app.route('/api/case/<case_id>/run', methods=['POST'])
def api_run(case_id):
    data = request.get_json(silent=True) or {}
    no_restore = bool(data.get('no_restore'))
    cmd = [sys.executable, str(RUNNER), 'run', '--case', case_id]
    if no_restore:
        cmd.append('--no-restore-snapshot')
    task = _enqueue(cmd)
    return jsonify({'task_id': task.id, 'state': task.state})


@app.route('/api/case/<case_id>/match', methods=['POST'])
def api_match(case_id):
    data = request.get_json(silent=True) or {}
    json_path = data.get('json')
    case = _find_case(case_id)
    module = (case or {}).get('module', '')
    stdout_path = RUNS / module / case_id / f'{case_id}_stdout.txt'
    cmd = [sys.executable, str(RUNNER), 'match',
           '--case', case_id, '--stdout', str(stdout_path)]
    if module and case_id:
        # 关键：结果必须写到 runs/<module>/<case>/，否则 collect_status 读不到 → 侧栏不更新
        cmd += ['--out-dir', str(RUNS / module / case_id)]
    if json_path:
        cmd += ['--json', json_path]
    else:
        cmd += ['--non-interactive']
    task = _enqueue(cmd)
    return jsonify({'task_id': task.id, 'state': task.state})


@app.route('/api/module/<module>/deliver', methods=['POST'])
def api_module_deliver(module):
    data = request.get_json(silent=True) or {}
    no_restore = bool(data.get('no_restore'))
    cmd = [sys.executable, str(RUN_ALL), 'deliver', '--module', module]
    if no_restore:
        cmd.append('--no-restore')
    task = _enqueue(cmd)
    return jsonify({'task_id': task.id, 'state': task.state})


@app.route('/api/all/deliver', methods=['POST'])
def api_all_deliver():
    """全量投递：run_all.py deliver（不带 --module）。"""
    data = request.get_json(silent=True) or {}
    no_restore = bool(data.get('no_restore'))
    cmd = [sys.executable, str(RUN_ALL), 'deliver']
    if no_restore:
        cmd.append('--no-restore')
    task = _enqueue(cmd)
    return jsonify({'task_id': task.id, 'state': task.state})


@app.route('/api/module/<module>/match', methods=['POST'])
def api_module_match(module):
    """匹配本模块：run_all.py match --module <module>。"""
    data = request.get_json(silent=True) or {}
    json_path = data.get('json')
    cmd = [sys.executable, str(RUN_ALL), 'match', '--module', module]
    if json_path:
        cmd += ['--json', json_path]
    task = _enqueue(cmd)
    return jsonify({'task_id': task.id, 'state': task.state})


@app.route('/api/all/match', methods=['POST'])
def api_all_match():
    """一键匹配全部能力：run_all.py match（不带 --module，自动跳过无 stdout 的 USB/预留项）。"""
    data = request.get_json(silent=True) or {}
    json_path = data.get('json')
    cmd = [sys.executable, str(RUN_ALL), 'match']
    if json_path:
        cmd += ['--json', json_path]
    task = _enqueue(cmd)
    return jsonify({'task_id': task.id, 'state': task.state})


@app.route('/api/task/<task_id>/events')
def api_events(task_id):
    task = _tasks.get(task_id)
    if task is None:
        return jsonify({'error': 'unknown task'}), 404

    def gen():
        idx = 0
        while True:
            lines, done, exit_code = task.snapshot(idx)
            for line in lines:
                yield f'data: {json.dumps({"line": line}, ensure_ascii=False)}\n\n'
                idx += 1
            if done:
                yield f'data: {json.dumps({"done": True, "exit_code": exit_code})}\n\n'
                break
            time.sleep(0.25)

    return Response(gen(), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@app.route('/api/task/<task_id>/stop', methods=['POST'])
def api_stop(task_id):
    task = _tasks.get(task_id)
    if task is None:
        return jsonify({'error': 'unknown task'}), 404
    task.stop()
    return jsonify({'ok': True})


@app.route('/api/case/<case_id>/stdout')
def api_stdout(case_id):
    case = _find_case(case_id)
    module = (case or {}).get('module', '')
    base = RUNS / module / case_id
    # ?path= 指定历史版本，否则读最新指针
    req_path = (request.args.get('path') or '').strip()
    stdout_path = base / req_path if req_path else base / f'{case_id}_stdout.txt'
    if not stdout_path.exists() or not stdout_path.is_file():
        return jsonify({'error': 'stdout not found'}), 404
    return jsonify({'text': stdout_path.read_text(encoding='utf-8', errors='replace')})


@app.route('/api/case/<case_id>/mapping')
def api_mapping(case_id):
    """该 case 的映射（behavior_fields + observed_fields），供前端展示。"""
    case = _find_case(case_id)
    module = (case or {}).get('module', '')
    if not module:
        return jsonify({'error': 'case has no module field'}), 404
    mpath = CONFIG / 'mappings' / module.lower() / f'{case_id}.json'
    if not mpath.exists():
        return jsonify({'mapping': None, 'error': 'mapping not found'}), 404
    data = json.loads(mpath.read_text(encoding='utf-8', errors='replace'))
    return jsonify({'mapping': data})


ANALYSIS = CONFIG / 'case_analysis.json'


def _load_analysis() -> dict:
    """人工撰写的映射笔记 + 采集分析：case_id -> {mapping, analysis, updated}。"""
    if not ANALYSIS.exists():
        return {}
    try:
        data = json.loads(ANALYSIS.read_text(encoding='utf-8-sig'))
    except Exception:
        return {}
    return data.get('cases', {}) if isinstance(data, dict) else {}


@app.route('/api/analysis')
def api_analysis():
    """全部 case 的人工分析（映射笔记 + 采集分析）。"""
    return jsonify({'cases': _load_analysis()})


@app.route('/api/case/<case_id>/analysis', methods=['POST'])
def api_save_analysis(case_id):
    """保存单个 case 的人工分析。空内容视为删除该条。"""
    data = request.get_json(silent=True) or {}
    mapping = str(data.get('mapping', '')).strip()
    analysis = str(data.get('analysis', '')).strip()
    cases = _load_analysis()
    if mapping or analysis:
        cases[case_id] = {
            'mapping': mapping,
            'analysis': analysis,
            'updated': time.strftime('%Y-%m-%d %H:%M'),
        }
    else:
        cases.pop(case_id, None)
    ANALYSIS.write_text(
        json.dumps({'_meta': {'purpose': '人工撰写的行为→IOA字段映射笔记与采集分析'}, 'cases': cases},
                   ensure_ascii=False, indent=2),
        encoding='utf-8')
    return jsonify({'ok': True})


@app.route('/api/case/<case_id>/stdouts')
def api_stdouts(case_id):
    """stdout 版本列表（历史 + 最新指针），新版本在前。"""
    case = _find_case(case_id)
    module = (case or {}).get('module', '')
    d = RUNS / module / case_id
    items = []
    if d.is_dir():
        for p in d.glob('*_stdout.txt'):
            try:
                st = p.stat()
            except OSError:
                continue
            items.append({
                'name': p.name,
                'path': p.name,
                'mtime': time.strftime('%Y-%m-%d %H:%M', time.localtime(st.st_mtime)),
                'size': st.st_size,
                'latest': p.name == f'{case_id}_stdout.txt',
            })
    items.sort(key=lambda x: (not x['latest'], x['name']), reverse=False)
    items.sort(key=lambda x: 0 if x['latest'] else 1)
    return jsonify({'stdouts': items})


@app.route('/api/case/<case_id>/logupload', methods=['POST'])
def api_logupload(case_id):
    """上传本地 IOA 导出 JSON 到 log/<module>/，进入自动探测候选。"""
    case = _find_case(case_id)
    if not case:
        return jsonify({'error': 'unknown case'}), 404
    module = case.get('module', '')
    if not module:
        return jsonify({'error': 'case has no module field'}), 400
    saved = []
    for root in _log_roots():
        target = root / module
        target.mkdir(parents=True, exist_ok=True)
        for field, f in request.files.items():
            fname = Path(f.filename or field).name
            low = fname.lower()
            if low.endswith('.zip'):
                # IOA 全量导出常为 .zip，解压出里面的 .json
                try:
                    with zipfile.ZipFile(io.BytesIO(f.read()), 'r') as zf:
                        for name in zf.namelist():
                            if name.lower().endswith('.json'):
                                dest = target / Path(name).name
                                dest.write_bytes(zf.read(name))
                                saved.append(str(dest))
                except Exception:
                    continue
            elif low.endswith('.json'):
                dest = target / fname
                f.save(str(dest))
                saved.append(str(dest))
        if saved:
            break
    if not saved:
        return jsonify({'error': 'no json file uploaded'}), 400
    return jsonify({'saved': saved})


@app.route('/api/case/<case_id>/sampleinfo')
def api_sampleinfo(case_id):
    """样本文件信息（文件名/大小/更新时间），用于右键查看。"""
    case = _find_case(case_id)
    if not case:
        return jsonify({'error': 'unknown case'}), 404
    module = case.get('module', '')
    program = case.get('program', '')
    root = _samples_root()
    target_dir = root / module
    support_dir = target_dir / 'Support'
    info = {'module': module, 'program': program}
    p = target_dir / program if program else None
    if p and p.exists():
        st = p.stat()
        info['sample'] = {
            'name': p.name,
            'path': str(p),
            'size': st.st_size,
            'mtime': time.strftime('%Y-%m-%d %H:%M', time.localtime(st.st_mtime)),
        }
    else:
        info['sample'] = None
    info['support'] = []
    if support_dir.is_dir():
        for f in sorted(support_dir.iterdir()):
            if f.is_file():
                st = f.stat()
                info['support'].append({
                    'name': f.name,
                    'size': st.st_size,
                    'mtime': time.strftime('%Y-%m-%d %H:%M', time.localtime(st.st_mtime)),
                })
    return jsonify(info)


@app.route('/api/case/<case_id>/result')
def api_result(case_id):
    case = _find_case(case_id)
    module = (case or {}).get('module', '')
    match_path = RUNS / module / case_id / 'match_result.json'
    if not match_path.exists():
        return jsonify({'error': 'match_result not found'}), 404
    doc = json.loads(match_path.read_text(encoding='utf-8-sig'))
    return jsonify(doc)


@app.route('/api/case/<case_id>/events')
def api_case_events(case_id):
    """归一化后的 IOA 事件列表（normalized_events.json），供前端「样本日志」展示。"""
    case = _find_case(case_id)
    module = (case or {}).get('module', '')
    p = RUNS / module / case_id / 'normalized_events.json'
    if not p.exists():
        return jsonify({'error': 'normalized_events not found'}), 404
    return jsonify(json.loads(p.read_text(encoding='utf-8-sig')))


@app.route('/api/case/<case_id>/logs')
def api_logs(case_id):
    case = _find_case(case_id)
    module = (case or {}).get('module', '')
    return jsonify({'logs': _list_log_candidates(module, case_id)})


@app.route('/api/case/<case_id>/variants')
def api_variants(case_id):
    """多用例变体（占位）。

    一个能力可有多个触发方式（如注册表 Run 键 / RunOnce 键），每个触发方式
    是一个变体 case，命名 <模块>-<能力>-<序号>（REG-CREATE-001 / -002）。
    case 行判定 = 各变体判定的并集（任一命中即能力存在，见 docs/chain/04_conclusion.md）。
    当前一个 case = 一个触发方式，故返回空列表；后续接入变体数据源时在此填充。
    """
    return jsonify({'case_id': case_id, 'variants': []})


@app.route('/api/sysmon_evidence')
def api_sysmon_evidence():
    """整份 Sysmon（L2）对照证据：{case_id: {total, event_ids, baseline_ids,
    matched, captured, note}}。矩阵 SYSMON 列与详情 Sysmon tab 共用。"""
    p = CONFIG / 'sysmon_evidence.json'
    if not p.exists():
        return jsonify({})
    try:
        return jsonify(json.loads(p.read_text(encoding='utf-8-sig')))
    except Exception:
        return jsonify({})


@app.route('/api/manual')
def api_manual():
    """使用手册（docs/USER_MANUAL.md），前端手册面板渲染。"""
    p = ROOT.parent / 'docs' / 'USER_MANUAL.md'
    if not p.exists():
        return jsonify({'error': 'manual not found', 'text': ''}), 404
    return jsonify({'text': p.read_text(encoding='utf-8-sig', errors='replace')})


@app.route('/api/case/<case_id>/sample', methods=['POST'])
def api_sample(case_id):
    case = _find_case(case_id)
    if not case:
        return jsonify({'error': 'unknown case'}), 404
    module = case.get('module', '')
    program = case.get('program', '')
    if not program:
        return jsonify({'error': 'case has no program field'}), 400

    root = _samples_root()
    target_dir = root / module
    support_dir = target_dir / 'Support'
    saved = []
    for field, f in request.files.items():
        fname = Path(f.filename or field).name
        if fname == program:
            dest = target_dir / fname
        else:
            support_dir.mkdir(parents=True, exist_ok=True)
            dest = support_dir / fname
        dest.parent.mkdir(parents=True, exist_ok=True)
        f.save(str(dest))
        saved.append(str(dest))

    if not saved:
        return jsonify({'error': 'no files uploaded'}), 400

    report = audit_and_update(update=True, programs=[program])
    return jsonify({'saved': saved, 'audit': report['programs'].get(program, {})})


if __name__ == '__main__':
    if Flask is None:
        print('Flask is not installed. Install with: pip install flask')
        sys.exit(1)
    app.run(host='127.0.0.1', port=8000, threaded=True)
