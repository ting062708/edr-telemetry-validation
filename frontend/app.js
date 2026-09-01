/* EDR 采集验证台 · app.js
   架构铁律（DESIGN_SPEC）：数据层 → 计算层 → 渲染层 单向调用；
   渲染函数互不调用，联动统一走 refreshAll()。零外部依赖。 */
'use strict';

/* ═══════════ 工具 ═══════════ */
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s == null ? '' : s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  .replace(/"/g, '&quot;').replace(/'/g, '&#39;');

async function api(path, opts) {
  const r = await fetch(path, opts);
  if (!r.ok) {
    let msg = r.status;
    try { msg = (await r.json()).error || msg; } catch (e) { /* ignore */ }
    throw new Error(msg);
  }
  return r.json();
}
const post = (path, body) => api(path, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body || {}),
});

function toast(msg, ms) {
  const t = $('toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toast._tm);
  toast._tm = setTimeout(() => t.classList.remove('show'), ms || 2600);
}

const fmtSize = (n) => n > 1048576 ? (n / 1048576).toFixed(1) + ' MB'
  : n > 1024 ? (n / 1024).toFixed(1) + ' KB' : n + ' B';

/* ═══════════ 状态 ═══════════ */
const state = {
  overview: null,        // /api/overview
  sysmon: {},            // /api/sysmon_evidence 整份
  activeModule: null,    // 侧栏选中模块（null=全部）
  drawerCase: null,      // 当前抽屉 case 对象
  drawerTab: 'result',
  logs: [],              // 当前 case 日志候选
  selLog: null,          // 选中的日志 path
  industry: null,
  baselineTab: 'industry',
  classmate: null,
  analysis: null,        // /api/analysis 整份（人工映射笔记+采集分析）
  es: null,              // 当前 EventSource
  taskId: null,          // 当前任务 id
  pollTimer: null,       // 运行期间的进度轮询定时器
};

/* 模块中文名 */
const MODULE_CN = {
  Process: '进程', File: '文件', Account: '账号', Network: '网络', Hash: '哈希',
  Registry: '注册表', ScheduleTask: '计划任务', Service: '服务', Driver: '驱动',
  Device: '设备操作', GPO: '组策略', Pipe: '命名管道', EDRSysOps: 'EDR 运维',
  WMI: 'WMI', BIT: 'BIT 任务', PowerShell: 'PowerShell',
};

/* ═══════════ 计算层：判定派生 ═══════════ */
function badgeOf(c) {
  /* 手动 case（integrated=false）结论由人工实测直填 case_result_map，
     与自动化 case 走同一套判定，仅额外打 manual 标记用于展示「手测」标签。 */
  const v = (c.result && c.result.verdict) || '';
  let b;
  if (v === '对') b = { cls: 'ok', txt: '采集' };
  else if (v === '疑问') b = { cls: 'warn', txt: '疑问' };
  else if (v === '错') b = { cls: 'bad', txt: '缺失' };
  else if (c.binary === '采集通过') b = { cls: 'ok', txt: '采集' };
  else if (c.binary === '采集未通过') b = { cls: 'bad', txt: '缺失' };
  else b = { cls: 'muted', txt: '待测' };
  if (!c.integrated) b.manual = true;
  return b;
}

function allCases() {
  if (!state.overview) return [];
  return state.overview.modules.flatMap((m) => m.cases);
}

/* ── 变体分组（DESIGN_SPEC 十）：case_id 去掉末尾 -<序号> 即能力前缀。
   PROC-IMAGE-LOAD-001/-002 → 能力 PROC-IMAGE-LOAD 的 2 个触发方式变体。 ── */
function capKeyOf(caseId) { return String(caseId).replace(/-\d+$/, ''); }
/* 按能力前缀分组，保持原有顺序；cases.length>1 的组即变体组 */
function groupByCapability(cases) {
  const groups = [];
  const idx = {};
  cases.forEach((c) => {
    const k = capKeyOf(c.case_id);
    if (idx[k] == null) { idx[k] = groups.length; groups.push({ key: k, cases: [] }); }
    groups[idx[k]].cases.push(c);
  });
  return groups;
}
/* 能力级并集判定（四态）：
   任一变体采到 → 采集；全部变体缺失 → 缺失；
   已构建变体但还有变体未匹配（无采集）→ 疑问；单 case 待测 → 待测。 */
function unionBadge(cases) {
  const cls = cases.map((c) => badgeOf(c).cls);
  let b;
  if (cls.some((x) => x === 'ok')) b = { cls: 'ok', txt: '采集' };
  else if (cls.every((x) => x === 'bad')) b = { cls: 'bad', txt: '缺失' };
  else if (cases.length > 1) b = { cls: 'warn', txt: '疑问' };
  else b = { cls: 'muted', txt: '待测' };
  if (cases.some((c) => !c.integrated)) b.manual = true;
  return b;
}
function findCase(caseId) { return allCases().find((c) => c.case_id === caseId) || null; }
function isManualModule(m) { return m.cases.every((c) => !c.integrated); }

function countByBadge() {
  /* 按「能力」统计（DESIGN_SPEC 十）：变体组取并集，一个能力算 1 个，而非按样例数。
     53 能力 = 45 自动化能力 + 8 预留手测能力。 */
  const n = { ok: 0, warn: 0, bad: 0, muted: 0, manual: 0, total: 0 };
  groupByCapability(allCases()).forEach((g) => {
    const b = unionBadge(g.cases);
    n[b.cls]++;
    n.total++;
    if (b.manual) n.manual++;
  });
  return n;
}

/* 模块状态计数 → 堆叠条分段（侧栏/模块带共用） */
function stackBar(cnt, total) {
  if (!total) return '';
  const seg = (v, cls) => v ? `<i class="${cls}" style="width:${(v / total) * 100}%"></i>` : '';
  return seg(cnt.ok, 'ok') + seg(cnt.warn, 'warn') + seg(cnt.bad, 'bad') + seg(cnt.muted, 'muted');
}

/* ═══════════ 渲染层（互不调用，统一由 refreshAll 调度） ═══════════ */
function renderStats() {
  const n = countByBadge();
  const pct = n.total ? Math.round((n.ok / n.total) * 100) : 0;
  const seg = (v, color) => {
    const w = n.total ? (v / n.total) * 100 : 0;
    return `<i style="width:${w}%;background:${color}"></i>`;
  };
  $('statstrip').innerHTML = `
    <div class="stat ok"><div class="ico">${ICO.check}</div><div><div class="num">${n.ok}</div><div class="lab">采集</div></div></div>
    <div class="stat warn"><div class="ico">${ICO.warn}</div><div><div class="num">${n.warn}</div><div class="lab">疑问</div></div></div>
    <div class="stat bad"><div class="ico">${ICO.cross}</div><div><div class="num">${n.bad}</div><div class="lab">缺失</div></div></div>
    <div class="stat muted"><div class="ico">${ICO.clock}</div><div><div class="num">${n.muted}</div><div class="lab">待测</div></div></div>
    <div class="stat total">
      <div class="row1"><span class="lab" style="margin:0">采集覆盖率 · ${n.total} 能力${n.manual ? `（含 ${n.manual} 手测）` : ''}</span><span class="pct">${pct}%</span></div>
      <div class="pbar">${seg(n.ok, 'var(--ok)')}${seg(n.warn, 'var(--warn)')}${seg(n.bad, 'var(--bad)')}${seg(n.muted, 'var(--muted)')}</div>
    </div>`;
}

function renderSidebar() {
  if (!state.overview) return;
  const mods = state.overview.modules;
  const auto = mods.filter((m) => !isManualModule(m));
  const manual = mods.filter(isManualModule);
  const item = (m) => {
    /* 堆叠条：按 采集/疑问/缺失/待测 比例分段，一整条圆角轨道，
       取代原先的碎段红绿线（视觉噪音大、读不出比例）。 */
    const cnt = { ok: 0, warn: 0, bad: 0, muted: 0 };
    m.cases.forEach((c) => cnt[badgeOf(c).cls]++);
    const active = state.activeModule === m.module ? ' active' : '';
    return `<div class="mod${active}${isManualModule(m) ? ' is-manual' : ''}" data-mod="${esc(m.module)}">
      <div class="row"><span class="name">${esc(m.module)}</span><span class="cnt">${m.cases.length}</span></div>
      <div class="bar">${stackBar(cnt, m.cases.length)}</div></div>`;
  };
  const allActive = state.activeModule === null ? ' active' : '';
  $('sidebar').innerHTML = `
    <div class="side-label">模块 MODULES</div>
    <div class="mod${allActive}" data-mod=""><div class="row"><span class="name">全部模块</span><span class="cnt">${allCases().length}</span></div></div>
    ${auto.map(item).join('')}
    ${manual.length ? '<div class="side-sep"></div><div class="side-label">手测 MANUAL</div>' + manual.map(item).join('') : ''}`;
  $('sidebar').querySelectorAll('.mod').forEach((el) => {
    el.onclick = () => {
      const mod = el.dataset.mod || null;
      state.activeModule = mod;
      refreshAll();
    };
  });
}

function sysmonCell(c) {
  const ev = state.sysmon[c.case_id];
  if (!ev) return '<span class="st no"><i></i>无</span>';
  if (ev.captured) return '<span class="st"><i></i>已对照</span>';
  return '<span class="st warn" title="Sysmon 未采到：样本可能未触发"><i></i>未采到</span>';
}

function renderMatrix() {
  if (!state.overview) return;
  const mods = state.overview.modules.filter(
    (m) => !state.activeModule || m.module === state.activeModule);
  if (!mods.length) { $('modules').innerHTML = '<div class="empty">无数据</div>'; return; }

  $('modules').innerHTML = mods.map((m) => {
    const cnt = { ok: 0, warn: 0, bad: 0, muted: 0, manual: 0 };
    m.cases.forEach((c) => cnt[badgeOf(c).cls]++);
    const stats = [
      cnt.ok ? `<b class="g">${cnt.ok} 采集</b>` : '',
      cnt.warn ? `<b class="y">${cnt.warn} 疑问</b>` : '',
      cnt.bad ? `<b class="r">${cnt.bad} 缺失</b>` : '',
      cnt.muted ? `<b class="x">${cnt.muted} 待测</b>` : '',
    ].filter(Boolean).join('');
    const manual = isManualModule(m);
    /* 单行 case 渲染（独立行 & 变体子行共用） */
    const caseCells = (c) => {
      const b = badgeOf(c);
      const sample = c.run_state !== 'never'
        ? '<span class="st"><i></i>已投递</span>' : '<span class="st no"><i></i>未投递</span>';
      const log = c.has_match_result ? '<span class="st"><i></i>已匹配</span>'
        : c.has_stdout ? '<span class="st warn"><i></i>待匹配</span>'
        : '<span class="st no"><i></i>无</span>';
      const ops = c.integrated
        ? `<button class="btn" data-act="match" data-id="${esc(c.case_id)}" title="匹配">${ICO.checkSm}</button>
           <button class="btn" data-act="run" data-id="${esc(c.case_id)}" title="跑样本">${ICO.playSm}</button>`
        : '<span class="manual-tag">手动测定</span>';
      return { b, sample, log, ops };
    };
    const rows = groupByCapability(m.cases).map((g) => {
      /* 单 case 能力：普通行 */
      if (g.cases.length === 1) {
        const c = g.cases[0];
        const { b, sample, log, ops } = caseCells(c);
        return `<tr data-case="${esc(c.case_id)}">
        <td class="case-id">${esc(c.case_id)}</td>
        <td class="bhv">${esc(c.display)}</td>
        <td><span class="badge ${b.cls}"><i></i>${b.txt}</span>${b.manual ? '<span class="tag-manual">手测</span>' : ''}</td>
        <td>${c.integrated ? sample : '<span class="st no"><i></i>—</span>'}</td>
        <td>${c.integrated ? log : '<span class="st no"><i></i>—</span>'}</td>
        <td>${c.integrated ? sysmonCell(c) : '<span class="st no"><i></i>—</span>'}</td>
        <td class="op">${ops}</td></tr>`;
      }
      /* 变体组：能力行（并集判定，点击展开）+ 各变体子行 */
      const n = g.cases.length;
      const ub = unionBadge(g.cases);
      const nRun = g.cases.filter((c) => c.run_state !== 'never').length;
      const nMatch = g.cases.filter((c) => c.has_match_result).length;
      const nSy = g.cases.filter((c) => (state.sysmon[c.case_id] || {}).captured).length;
      const nEv = g.cases.filter((c) => state.sysmon[c.case_id]).length;
      const syCell = nEv === 0 ? '<span class="st no"><i></i>无</span>'
        : nSy === n ? '<span class="st"><i></i>已对照</span>'
        : nSy > 0 ? `<span class="st warn"><i></i>${nSy}/${n} 对照</span>`
        : '<span class="st warn"><i></i>未采到</span>';
      const subRows = g.cases.map((c) => {
        const { b, sample, log, ops } = caseCells(c);
        return `<tr class="variant-row" data-parent="${esc(g.key)}" data-case="${esc(c.case_id)}" style="display:none">
        <td class="case-id" style="padding-left:32px">${esc(c.case_id)}</td>
        <td class="bhv">${esc(c.display)}</td>
        <td><span class="badge ${b.cls}"><i></i>${b.txt}</span>${b.manual ? '<span class="tag-manual">手测</span>' : ''}</td>
        <td>${c.integrated ? sample : '<span class="st no"><i></i>—</span>'}</td>
        <td>${c.integrated ? log : '<span class="st no"><i></i>—</span>'}</td>
        <td>${c.integrated ? sysmonCell(c) : '<span class="st no"><i></i>—</span>'}</td>
        <td class="op">${ops}</td></tr>`;
      }).join('');
      return `<tr class="cap-row" data-cap="${esc(g.key)}">
        <td class="case-id"><span class="expander" data-exp="${esc(g.key)}">▸</span> ${esc(g.key)}<span class="tag-var">${n} 变体</span></td>
        <td class="bhv" style="color:var(--text-faint)">${n} 种触发方式 · 判定取并集</td>
        <td><span class="badge ${ub.cls}"><i></i>${ub.txt}</span><span class="tag-cap">并集</span></td>
        <td><span class="st${nRun ? '' : ' no'}"><i></i>${nRun}/${n} 已投递</span></td>
        <td><span class="st${nMatch ? '' : ' no'}"><i></i>${nMatch}/${n} 已匹配</span></td>
        <td>${syCell}</td>
        <td class="op">
          <button class="btn" data-gact="match" data-ids="${esc(g.cases.map((c) => c.case_id).join(','))}" title="匹配全部变体">${ICO.checkSm}</button>
          <button class="btn" data-gact="run" data-ids="${esc(g.cases.filter((c) => c.integrated).map((c) => c.case_id).join(','))}" title="跑全部变体">${ICO.playSm}</button>
        </td></tr>${subRows}`;
    }).join('');
    return `<div class="module-band">
        <span class="name">${esc(m.module)}</span><span class="cn">${esc(MODULE_CN[m.module] || m.display)}</span>
        ${manual ? '<span class="tag-manual">手测模块</span>' : ''}
        <span class="mstats">${stats}</span><span class="mbar">${stackBar(cnt, m.cases.length)}</span>
        ${manual ? '' : `<span class="actions">
          <button class="btn" data-mact="match" data-mod="${esc(m.module)}">${ICO.checkSm}匹配本模块</button>
          <button class="btn primary" data-mact="run" data-mod="${esc(m.module)}">${ICO.playSm}跑本模块</button>
        </span>`}
      </div>
      <table><thead><tr><th>CASE</th><th>行为</th><th>判定</th><th>样本</th><th>日志</th><th>SYSMON</th><th style="text-align:right">操作</th></tr></thead>
      <tbody>${rows}</tbody></table>`;
  }).join('');

  /* 事件绑定（渲染完成后） */
  $('modules').querySelectorAll('tr[data-case]').forEach((tr) => {
    tr.onclick = () => openDrawer(tr.dataset.case);
  });
  /* 能力行：点击任意位置 = 展开/收起变体子行 */
  const toggleCap = (key) => {
    const ex = $('modules').querySelector(`.expander[data-exp="${key}"]`);
    const subs = $('modules').querySelectorAll(`tr[data-parent="${key}"]`);
    const open = ex.textContent === '▸';
    ex.textContent = open ? '▾' : '▸';
    subs.forEach((s) => { s.style.display = open ? '' : 'none'; });
  };
  $('modules').querySelectorAll('tr[data-cap]').forEach((tr) => {
    tr.onclick = () => toggleCap(tr.dataset.cap);
  });
  $('modules').querySelectorAll('button[data-act]').forEach((btn) => {
    btn.onclick = (e) => {
      e.stopPropagation();
      if (btn.dataset.act === 'run') runCase(btn.dataset.id);
      else matchCase(btn.dataset.id);
    };
  });
  /* 能力组整组跑/匹配（串行队列） */
  $('modules').querySelectorAll('button[data-gact]').forEach((btn) => {
    btn.onclick = (e) => {
      e.stopPropagation();
      const ids = btn.dataset.ids.split(',').filter(Boolean);
      if (btn.dataset.gact === 'run') runGroup(ids);
      else matchGroup(ids);
    };
  });
  $('modules').querySelectorAll('button[data-mact]').forEach((btn) => {
    btn.onclick = (e) => {
      e.stopPropagation();
      if (btn.dataset.mact === 'run') runModule(btn.dataset.mod);
      else matchModule(btn.dataset.mod);
    };
  });
  $('modules').querySelectorAll('.expander').forEach((ex) => {
    ex.onclick = (e) => {
      e.stopPropagation();
      toggleCap(ex.dataset.exp);
    };
  });
}

/* 统一刷新入口（铁律 9：渲染函数不互调） */
function refreshAll() {
  renderStats();
  renderSidebar();
  renderMatrix();
}

/* ═══════════ 数据加载 ═══════════ */
async function loadOverview() {
  try {
    state.overview = await api('/api/overview');
    refreshAll();
    const c = allCases().find((x) => x.snapshot);
    if (c) $('snap-val').textContent = c.snapshot;
  } catch (e) {
    $('modules').innerHTML = `<div class="empty"><div class="big">概览加载失败</div>${esc(e.message)}<br>请确认 server.py 已启动</div>`;
  }
}
async function loadSysmon() {
  try { state.sysmon = await api('/api/sysmon_evidence'); } catch (e) { state.sysmon = {}; }
}

/* ═══════════ 详情抽屉 ═══════════ */
const DRAWER_TABS = [
  ['result', '结果'], ['sample', '样本'], ['logs', '日志'],
  ['sysmon', 'Sysmon'], ['variants', '变体'], ['analysis', '分析'],
];

function openDrawer(caseId, tab) {
  const c = findCase(caseId);
  if (!c) return;
  closeAll();
  state.drawerCase = c;
  state.drawerTab = tab || 'result';
  state.selLog = null;
  $('d-title').textContent = c.case_id;
  $('d-sub').textContent = c.display + (c.program ? ` · ${c.program}` : '');
  const b = badgeOf(c);
  $('d-badge').innerHTML = `<span class="badge ${b.cls}"><i></i>${b.txt}</span>`;
  $('d-tabs').innerHTML = DRAWER_TABS.map(([k, name]) =>
    `<div class="tab${k === state.drawerTab ? ' active' : ''}" data-tab="${k}">${name}${k === 'logs' ? '<span class="n" id="logs-n"></span>' : ''}</div>`).join('');
  $('d-tabs').querySelectorAll('.tab').forEach((t) => {
    t.onclick = () => { state.drawerTab = t.dataset.tab; renderDrawerTab(); };
  });
  $('d-foot').style.display = c.integrated ? '' : 'none';
  $('drawer').classList.add('open');
  $('mask').classList.add('open');
  renderDrawerTab();
}

function renderDrawerTab() {
  const c = state.drawerCase;
  if (!c) return;
  $('d-tabs').querySelectorAll('.tab').forEach((t) =>
    t.classList.toggle('active', t.dataset.tab === state.drawerTab));
  $('d-body').innerHTML = '<div class="loading">加载中…</div>';
  const loaders = {
    result: loadTabResult, sample: loadTabSample, logs: loadTabLogs,
    sysmon: loadTabSysmon, variants: loadTabVariants, analysis: loadTabAnalysis,
  };
  loaders[state.drawerTab](c);
}

/* ── 结果 tab ── */
async function loadTabResult(c) {
  /* 手动 case：结论人工实测直填，不走自动化流水线 */
  if (!c.integrated) {
    const b = badgeOf(c);
    const note = (c.result && c.result.note) || '';
    $('d-body').innerHTML = `
      <div class="note-box ${b.cls === 'bad' ? 'warn' : ''}">
        <b>手动测定：${esc(b.txt)}</b><br>${esc(note || '结论由人工实测得出，已归档进 case_result_map。')}</div>
      <div class="kv"><span class="k">判定方式</span><span class="v">人工实测（不参与自动化回归）</span></div>
      <div class="kv"><span class="k">结论来源</span><span class="v">config/case_result_map.json</span></div>`;
    return;
  }
  let doc = null;
  try { doc = await api(`/api/case/${c.case_id}/result`); } catch (e) { /* 无结果 */ }
  if (!doc) {
    $('d-body').innerHTML = `<div class="empty"><div class="big">尚无匹配结果</div>
      ${c.has_stdout ? '已有 stdout，点击底部「匹配」生成判定。' : '先「跑样本」再「匹配」。'}</div>`;
    return;
  }
  const ms = doc.match_stats || {};
  const icon = doc.verdict_icon || '';
  const vCls = doc.capability_detected === true ? 'ok' : doc.capability_detected === false ? 'bad' : 'warn';
  let html = `<div class="note-box"><b>${esc(icon)} ${esc(doc.verdict || '')}</b>${doc.sample_result ? ` · 样本自报 ${esc(doc.sample_result)}` : ''}<br>${esc(doc.message || '')}</div>`;
  html += `<div class="kv"><span class="k">能力判定</span><span class="v" style="color:var(--${vCls === 'ok' ? 'ok' : vCls === 'bad' ? 'bad' : 'warn'})">${
    doc.capability_detected === true ? '能力存在' : doc.capability_detected === false ? '未采到' : '未判定'}</span></div>`;
  if (doc.expected_result) html += `<div class="kv"><span class="k">期望结果</span><span class="v">${esc(doc.expected_result)} · ${doc.as_expected ? '符合预期' : '与预期不符'}</span></div>`;
  if (doc.matched_event_id) html += `<div class="kv"><span class="k">命中事件</span><span class="v">${esc(doc.matched_event_id)}</span></div>`;

  /* 字段命中 */
  const of = doc.observed_fields || {};
  const declared = of.declared || [];
  const cov = of.matched_event_coverage || {};
  if (declared.length) {
    html += `<div class="sec-t" style="margin-top:18px">字段命中 · FIELD COVERAGE（${of.filled || 0}/${of.total || declared.length}）</div>`;
    declared.forEach((f) => {
      const v = cov[f];
      html += `<div class="field-row"><span class="f">${esc(f)}</span><span class="s ${v ? 'ok' : 'bad'}">${v ? '✓ ' + esc(String(v)).slice(0, 60) : '✗ MISS'}</span></div>`;
    });
  }
  (doc.missing_required_fields || []).forEach((f) => {
    html += `<div class="field-row"><span class="f">${esc(f)}</span><span class="s bad">✗ 缺失必填</span></div>`;
  });

  /* 事件漏斗 */
  const steps = [
    ['total', ms.total_events], ['hostname', ms.after_hostname], ['time 窗口', ms.after_time],
    ['actor', ms.after_actor], ['pid', ms.after_pid], ['operation', ms.after_operation],
  ].filter((s) => typeof s[1] === 'number');
  if (steps.length && steps[0][1] > 0) {
    const base = steps[0][1];
    html += `<div class="sec-t" style="margin-top:18px">事件漏斗 · MATCH FUNNEL</div><div class="funnel">`;
    steps.forEach(([lab, n], i) => {
      const w = Math.max((n / base) * 100, n > 0 ? 2 : 0);
      const color = i === steps.length - 1 ? 'var(--ok)' : n < base * 0.5 ? 'var(--warn)' : 'var(--accent)';
      html += `<div class="step"><span class="lab">${esc(lab)}</span><span class="track"><span class="bar" style="width:${w}%;background:${color}"></span></span><span class="n">${n}</span></div>`;
    });
    html += '</div>';
    if (ms.coverage_status) html += `<div class="kv"><span class="k">日志时间窗覆盖</span><span class="v">${esc(ms.coverage_status)}</span></div>`;
  }
  $('d-body').innerHTML = html;
}

/* ── 分析 tab：人工撰写「映射笔记 + 采集分析」，存 config/case_analysis.json ── */
async function loadTabAnalysis(c) {
  if (!state.analysis) { try { state.analysis = (await api('/api/analysis')).cases || {}; } catch (e) { state.analysis = {}; } }
  const a = state.analysis[c.case_id] || {};
  let html = '';
  /* 机器 mapping 只读参考（behavior_fields：行为字段→IOA字段） */
  if (c.integrated) {
    let mapDoc = null;
    try { mapDoc = (await api(`/api/case/${c.case_id}/mapping`)).mapping; } catch (e) { /* 无 mapping */ }
    const bf = (mapDoc && mapDoc.behavior_fields) || {};
    const keys = Object.keys(bf);
    if (keys.length) {
      html += `<div class="sec-t">机器映射参考 · MAPPING（只读）</div>
        <div class="mapref">${keys.map((k) => `<div class="kv"><span class="k">${esc(k)}</span><span class="v">${esc(String(bf[k]))}</span></div>`).join('')}</div>`;
    }
  }
  html += `
    <div class="sec-t"${html ? ' style="margin-top:16px"' : ''}>能力映射名称 · MAP NAME</div>
    <input class="ainput" id="ana-mapname" type="text" placeholder="例：FileWriteClose / ProcessCreate（IOA 事件名）" value="${esc(a.map_name || '')}">
    <div class="sec-t" style="margin-top:14px">映射笔记 · 行为 → IOA 事件/字段</div>
    <textarea class="atarea" id="ana-mapping" rows="4" placeholder="例：覆盖写 → FileWriteClose，取 Child.FilePath / Child.FileMd5；TXT 不采、JSON 可采…">${esc(a.mapping || '')}</textarea>
    <div class="sec-t" style="margin-top:14px">采集分析 · 结论与限制条件</div>
    <textarea class="atarea" id="ana-analysis" rows="6" placeholder="例：仅启动期 DLL 可采，运行时 LoadLibrary 不触发；行业普遍 Yes，本产品属弱项，待补…">${esc(a.analysis || '')}</textarea>
    <div class="ana-foot">
      <span class="ana-meta">${a.updated ? `上次保存 ${esc(a.updated)}` : '尚未撰写'}</span>
      <button class="btn primary" id="btn-ana-save">${ICO.checkSm}保存分析</button>
    </div>`;
  $('d-body').innerHTML = html;
  $('btn-ana-save').onclick = () => saveAnalysis(c.case_id);
}
async function saveAnalysis(caseId) {
  const payload = {
    map_name: $('ana-mapname').value,
    mapping: $('ana-mapping').value,
    analysis: $('ana-analysis').value,
  };
  try {
    await post(`/api/case/${caseId}/analysis`, payload);
    const updated = new Date().toISOString().slice(0, 16).replace('T', ' ');
    if (payload.map_name.trim() || payload.mapping.trim() || payload.analysis.trim()) {
      state.analysis[caseId] = { ...payload, updated };
    } else {
      delete state.analysis[caseId];
    }
    document.querySelector('.ana-meta').textContent = `上次保存 ${updated}`;
    toast('分析已保存');
  } catch (e) {
    toast(`保存失败：${e.message}`);
  }
}

/* ── 样本 tab ── */
async function loadTabSample(c) {
  let info = null, stdouts = [];
  try { info = await api(`/api/case/${c.case_id}/sampleinfo`); } catch (e) { /* ignore */ }
  try { stdouts = (await api(`/api/case/${c.case_id}/stdouts`)).stdouts || []; } catch (e) { /* ignore */ }
  let html = `<div class="sec-t">样本文件 · SAMPLE</div>`;
  if (info && info.sample) {
    html += `<div class="kv"><span class="k">文件</span><span class="v">${esc(info.sample.name)}</span></div>
      <div class="kv"><span class="k">大小</span><span class="v">${fmtSize(info.sample.size)}</span></div>
      <div class="kv"><span class="k">更新</span><span class="v">${esc(info.sample.mtime)}</span></div>
      <div class="kv"><span class="k">MD5 锚点</span><span class="v">${esc((c.program && '见 test_cases.json') || '—')}</span></div>`;
  } else {
    html += `<div class="empty">样本文件未找到${c.program ? `（${esc(c.program)}）` : ''}</div>`;
  }
  if (info && info.support && info.support.length) {
    html += `<div class="sec-t" style="margin-top:16px">支撑文件 · SUPPORT</div>` +
      info.support.map((f) => `<div class="kv"><span class="k">${esc(f.name)}</span><span class="v">${fmtSize(f.size)}</span></div>`).join('');
  }
  if (c.integrated) {
    html += `<div class="upload-row">
      <input type="file" id="sample-file" multiple style="font-size:12px">
      <button class="btn" id="btn-upload-sample">${ICO.upload}上传样本</button></div>
      <div id="sample-audit"></div>`;
  }
  html += `<div class="sec-t" style="margin-top:16px">STDOUT 版本（${stdouts.length}）</div>`;
  if (!stdouts.length) html += '<div class="empty">尚无 stdout——先跑样本</div>';
  stdouts.forEach((s) => {
    html += `<div class="log-item" data-stdout="${esc(s.path)}">
      <span class="nm">${esc(s.name)}${s.latest ? ' <span class="badge ok" style="margin-left:6px"><i></i>最新</span>' : ''}</span>
      <span class="mt">${esc(s.mtime)} · ${fmtSize(s.size)}</span></div>`;
  });
  html += '<div id="stdout-preview"></div>';
  $('d-body').innerHTML = html;

  $('d-body').querySelectorAll('[data-stdout]').forEach((el) => {
    el.onclick = async () => {
      $('d-body').querySelectorAll('[data-stdout]').forEach((x) => x.classList.remove('sel'));
      el.classList.add('sel');
      const d = await api(`/api/case/${c.case_id}/stdout?path=${encodeURIComponent(el.dataset.stdout)}`);
      const lines = (d.text || '').split('\n');
      const preview = lines.slice(0, 80).join('\n');
      $('stdout-preview').innerHTML = `<div class="sec-t" style="margin-top:14px">预览（前 ${Math.min(80, lines.length)} 行）</div>
        <div class="note-box" style="font-family:var(--mono);white-space:pre-wrap;word-break:break-all;max-height:260px;overflow:auto">${esc(preview)}</div>`;
    };
  });
  const upBtn = $('btn-upload-sample');
  if (upBtn) upBtn.onclick = () => uploadSample(c);
}

async function uploadSample(c) {
  const fi = $('sample-file');
  if (!fi || !fi.files.length) { toast('先选择文件'); return; }
  const fd = new FormData();
  for (const f of fi.files) fd.append('files', f);
  try {
    const r = await api(`/api/case/${c.case_id}/sample`, { method: 'POST', body: fd });
    const a = r.audit || {};
    $('sample-audit').innerHTML = `<div class="note-box">已保存 ${r.saved.length} 个文件。MD5 校验：${esc(a.status || JSON.stringify(a))}</div>`;
  } catch (e) { toast('上传失败：' + e.message); }
}

/* ── 日志 tab ── */
async function loadTabLogs(c) {
  let logs = [];
  try { logs = (await api(`/api/case/${c.case_id}/logs`)).logs || []; } catch (e) { /* ignore */ }
  state.logs = logs;
  const nEl = $('logs-n'); if (nEl) nEl.textContent = logs.length || '';
  let html = `<div class="sec-t">IOA 日志候选（新→旧，case 名匹配优先）</div>`;
  if (!logs.length) html += '<div class="empty">logs/ 下暂无导出 JSON——从 IOA 控制台导出后上传到下面</div>';
  logs.slice(0, 30).forEach((l) => {
    html += `<div class="log-item" data-log="${esc(l.path)}">
      <span class="nm">${esc(l.name)}</span><span class="mt">${esc(l.mtime)} · ${fmtSize(l.size)}</span></div>`;
  });
  html += `<div class="upload-row">
      <input type="file" id="log-file" accept=".json,.zip" style="font-size:12px">
      <button class="btn" id="btn-upload-log">${ICO.upload}上传日志</button>
      <button class="btn primary" id="btn-match-sel" disabled>${ICO.checkSm}用选中日志匹配</button>
    </div>
    <div class="sec-t" style="margin-top:16px">归一化事件 · NORMALIZED EVENTS</div>
    <div id="ev-box"><div class="loading">加载中…</div></div>`;
  $('d-body').innerHTML = html;

  $('d-body').querySelectorAll('[data-log]').forEach((el) => {
    el.onclick = () => {
      $('d-body').querySelectorAll('[data-log]').forEach((x) => x.classList.remove('sel'));
      el.classList.add('sel');
      state.selLog = el.dataset.log;
      $('btn-match-sel').disabled = false;
    };
  });
  $('btn-upload-log').onclick = () => uploadLog(c);
  $('btn-match-sel').onclick = () => { if (state.selLog) matchCase(c.case_id, state.selLog); };

  try {
    const evs = await api(`/api/case/${c.case_id}/events`);
    const list = Array.isArray(evs) ? evs : (evs.events || []);
    if (!list.length) { $('ev-box').innerHTML = '<div class="empty">无事件</div>'; return; }
    const rows = list.slice(0, 200).map((e) => `<tr>
      <td>${esc((e.event_time_utc || '').replace('T', ' ').slice(5, 19))}</td>
      <td>${esc(e.event_category || '')}</td><td>${esc(e.operation || '')}</td>
      <td>${esc(e.actor_name || '')}</td><td>${esc(e.actor_pid == null ? '' : e.actor_pid)}</td></tr>`).join('');
    $('ev-box').innerHTML = `<div style="max-height:300px;overflow:auto;border:1px solid var(--border);border-radius:7px">
      <table class="ev-table"><thead><tr><th>时间</th><th>分类</th><th>操作</th><th>Actor</th><th>PID</th></tr></thead>
      <tbody>${rows}</tbody></table></div>
      <div style="color:var(--text-faint);font-size:11px;margin-top:6px;font-family:var(--mono)">共 ${list.length} 条，显示前 200</div>`;
  } catch (e) {
    $('ev-box').innerHTML = '<div class="empty">尚无归一化事件——匹配后生成</div>';
  }
}

async function uploadLog(c) {
  const fi = $('log-file');
  if (!fi || !fi.files.length) { toast('先选择 .json / .zip 文件'); return; }
  const fd = new FormData();
  fd.append('file', fi.files[0]);
  try {
    const r = await api(`/api/case/${c.case_id}/logupload`, { method: 'POST', body: fd });
    toast(`已上传 ${r.saved.length} 个文件`);
    loadTabLogs(c);
  } catch (e) { toast('上传失败：' + e.message); }
}

/* ── Sysmon tab ── */
function loadTabSysmon(c) {
  const ev = state.sysmon[c.case_id];
  if (!ev) {
    $('d-body').innerHTML = `<div class="empty"><div class="big">无 Sysmon 对照证据</div>
      该 case 尚未纳入 L2 对照（config/sysmon_evidence.json）。</div>`;
    return;
  }
  const ids = ev.event_ids || {};
  const idRows = Object.keys(ids).sort((a, b) => +a - +b)
    .map((k) => `<span class="badge ${ev.baseline_ids && ev.baseline_ids.includes(+k) ? 'ok' : 'muted'}" style="margin:0 4px 4px 0">EID ${k} × ${ids[k]}</span>`).join('');
  $('d-body').innerHTML = `
    <div class="note-box ${ev.captured ? '' : 'warn'}">
      <b>${ev.captured ? '✓ Sysmon 已采到该行为' : '⚠ Sysmon 未采到'}</b><br>
      ${ev.captured
        ? 'L2 参照确认行为真实发生——若 IOA 未采到，可归因为 EDR 采集盲区。'
        : 'Sysmon 也未采到——样本可能未触发该行为，需检查样本。'}
      ${ev.note ? `<br>备注：${esc(ev.note)}` : ''}</div>
    <div class="kv"><span class="k">事件总数</span><span class="v">${ev.total}</span></div>
    <div class="kv"><span class="k">基线 EventID</span><span class="v">${esc(JSON.stringify(ev.baseline_ids || []))}</span></div>
    <div class="kv"><span class="k">命中 EventID</span><span class="v">${esc(JSON.stringify(ev.matched || []))}</span></div>
    <div class="sec-t" style="margin-top:16px">事件分布 · EVENT IDS</div>
    <div style="display:flex;flex-wrap:wrap">${idRows}</div>
    <div style="color:var(--text-faint);font-size:11px;margin-top:10px">绿色为基线相关 EventID。数据来源：config/sysmon_evidence.json（人工整理，样本人工确认后入 case，前端不做自动归因）。</div>`;
}

/* ── 变体 tab（DESIGN_SPEC 十.4）：同能力前缀的变体 case 列表 + 并集判定 ── */
function loadTabVariants(c) {
  const key = capKeyOf(c.case_id);
  const siblings = allCases()
    .filter((x) => capKeyOf(x.case_id) === key)
    .sort((a, b) => a.case_id.localeCompare(b.case_id));
  if (siblings.length <= 1) {
    $('d-body').innerHTML = `
      <div class="empty" style="text-align:left;line-height:2">
        <div class="big" style="text-align:center">无变体 · 单触发方式</div>
        <div class="note-box" style="margin-top:14px">
          <b>什么是变体？</b><br>
          一个「能力」可能有多个触发方式（如注册表 Run 键 / RunOnce 键），EDR 采集有偏向性，
          需要用多个测试样例确认。每个触发方式是一个变体 case。<br><br>
          <b>命名约定</b>：<code style="font-family:var(--mono);background:var(--raised);padding:1px 6px;border-radius:5px;color:var(--accent)">&lt;模块&gt;-&lt;能力&gt;-&lt;序号&gt;</code>，
          如 REG-CREATE-001（Run 键）/ REG-CREATE-002（RunOnce 键）。case_id 前缀相同（去掉末尾序号）的
          case 自动识别为同一能力的变体，矩阵里合并为一行、判定取并集。<br><br>
          <b>并集判定</b>：全部变体采到 → 采集；部分采到 → 疑问（有偏向）；全部未采到 → 缺失。
        </div>
        <div class="sec-t">当前 CASE</div>
        <div class="log-item"><span class="nm">${esc(c.case_id)}</span><span class="mt">${esc(c.display)}</span></div>
      </div>`;
    return;
  }
  const ub = unionBadge(siblings);
  const rows = siblings.map((s) => {
    const b = badgeOf(s);
    const cur = s.case_id === c.case_id;
    const run = s.run_state !== 'never' ? '已投递' : '未投递';
    const mt = s.has_match_result ? '已匹配' : s.has_stdout ? '待匹配' : '无日志';
    return `<div class="log-item var-item${cur ? ' cur' : ''}" data-var="${esc(s.case_id)}">
      <span class="nm">${esc(s.case_id)}${cur ? ' · 当前' : ''}</span>
      <span class="mt">${esc(s.display)}<br><span style="font-size:10px">${run} · ${mt}</span></span>
      <span class="badge ${b.cls}"><i></i>${b.txt}</span></div>`;
  }).join('');
  $('d-body').innerHTML = `
    <div class="note-box">能力 <b style="font-family:var(--mono)">${esc(key)}</b> 共 ${siblings.length} 个触发方式变体，
    能力级判定取并集：<span class="badge ${ub.cls}"><i></i>${ub.txt}</span>
    （全部采到 → 采集；部分采到 → 疑问·有偏向；全部未采到 → 缺失）。点任一变体可切换查看。</div>
    <div class="sec-t">变体列表 · VARIANTS</div>${rows}`;
  $('d-body').querySelectorAll('[data-var]').forEach((el) => {
    el.onclick = () => { if (el.dataset.var !== c.case_id) openDrawer(el.dataset.var, 'variants'); };
  });
}

/* ═══════════ 滑出面板（手册 / Baseline / 报告） ═══════════ */
function openPanel(name) {
  closeAll();
  $(`panel-${name}`).classList.add('open');
  $('mask').classList.add('open');
  if (name === 'manual') loadManual();
  if (name === 'baseline') loadBaseline();
  if (name === 'report') loadReport();
}
function closeAll() {
  document.querySelectorAll('.slide').forEach((s) => s.classList.remove('open'));
  $('mask').classList.remove('open');
}

/* ── 面板向左展开（类似终端：左缘拖拽调宽 + 一键整宽，宽度存 localStorage） ── */
function initSlideExpand() {
  document.querySelectorAll('.slide').forEach((sl) => {
    const key = 'wb_edr_slide_w_' + sl.id;
    /* 恢复上次拖拽的宽度 */
    try {
      const w = parseInt(localStorage.getItem(key), 10);
      if (w >= 480) sl.style.width = w + 'px';
    } catch (e) { /* ignore */ }
    /* 左缘拖拽调宽 */
    const drag = document.createElement('div');
    drag.className = 'slide-drag';
    drag.title = '拖动调整面板宽度';
    sl.appendChild(drag);
    drag.addEventListener('pointerdown', (e) => {
      e.preventDefault();
      drag.classList.add('active');
      const startX = e.clientX;
      const startW = sl.getBoundingClientRect().width;
      const move = (ev) => {
        const w = Math.min(window.innerWidth * 0.96, Math.max(480, startW + (startX - ev.clientX)));
        sl.classList.remove('wide');
        sl.querySelector('.slide-expand').classList.remove('on');
        sl.style.width = w + 'px';
      };
      const up = () => {
        drag.classList.remove('active');
        document.removeEventListener('pointermove', move);
        document.removeEventListener('pointerup', up);
        try { localStorage.setItem(key, String(parseInt(sl.style.width, 10) || 640)); } catch (err) { /* ignore */ }
      };
      document.addEventListener('pointermove', move);
      document.addEventListener('pointerup', up);
    });
    /* 头部「展开」按钮：一键整宽 / 还原 */
    const head = sl.querySelector('.slide-head');
    if (!head) return;
    const btn = document.createElement('span');
    btn.className = 'slide-expand';
    btn.title = '展开 / 还原（整宽查看）';
    btn.innerHTML = '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>';
    btn.onclick = () => {
      const on = sl.classList.toggle('wide');
      btn.classList.toggle('on', on);
    };
    head.insertBefore(btn, head.querySelector('.close'));
  });
}

/* ── 手册 ── */
let _manualLoaded = false;
async function loadManual() {
  if (_manualLoaded) return;
  try {
    const d = await api('/api/manual');
    $('manual-body').innerHTML = mdToHtml(d.text || '');
    _manualLoaded = true;
  } catch (e) {
    $('manual-body').innerHTML = `<div class="empty">手册加载失败：${esc(e.message)}</div>`;
  }
}

/* 轻量 Markdown 渲染（标题/代码/粗体/列表/表格/分隔线） */
function mdToHtml(md) {
  const lines = md.split('\n');
  let html = '', inTable = false, inList = false;
  const inline = (s) => esc(s)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');
  const closeBlocks = () => {
    if (inTable) { html += '</tbody></table>'; inTable = false; }
    if (inList) { html += '</ul>'; inList = false; }
  };
  for (const raw of lines) {
    const line = raw.trimEnd();
    if (/^\|.*\|$/.test(line)) {
      const cells = line.slice(1, -1).split('|').map((x) => x.trim());
      if (cells.every((x) => /^[-: ]+$/.test(x))) continue;
      if (!inTable) { closeBlocks(); html += '<table class="cmp-table"><tbody>'; inTable = true; }
      html += '<tr>' + cells.map((x) => `<td>${inline(x)}</td>`).join('') + '</tr>';
      continue;
    }
    if (/^[-*] /.test(line)) {
      if (!inList) { closeBlocks(); html += '<ul>'; inList = true; }
      html += `<li>${inline(line.slice(2))}</li>`;
      continue;
    }
    closeBlocks();
    const h = line.match(/^(#{1,4})\s+(.*)/);
    if (h) { html += `<h${h[1].length}>${inline(h[2])}</h${h[1].length}>`; continue; }
    if (/^---+$/.test(line)) { html += '<hr>'; continue; }
    if (/^> /.test(line)) { html += `<div class="note-box">${inline(line.slice(2))}</div>`; continue; }
    if (/^\d+\. /.test(line)) { html += `<div style="padding-left:14px">${inline(line)}</div>`; continue; }
    if (line.trim()) html += `<div>${inline(line)}</div>`;
  }
  closeBlocks();
  return html;
}

/* ── Baseline 对比（行业基线 / 同学基线） ── */
async function loadBaseline() {
  if (!state.industry) { try { state.industry = await api('/api/industry'); } catch (e) { state.industry = {}; } }
  if (!state.classmate) { try { state.classmate = await api('/api/classmate_baseline'); } catch (e) { state.classmate = {}; } }
  if (!state.analysis) { try { state.analysis = (await api('/api/analysis')).cases || {}; } catch (e) { state.analysis = {}; } }
  renderBaseline();
}
function switchBaselineTab(tab) {
  state.baselineTab = tab;
  $('baseline-seg').querySelectorAll('button').forEach((b) =>
    b.classList.toggle('active', b.dataset.seg === tab));
  renderBaseline();
}
function renderBaseline() {
  if (state.baselineTab === 'industry') return renderIndustry();
  return renderClassmate();
}
function renderIndustry() {
  const ind = state.industry || {};
  const cats = ind.categories || {};
  const caseMap = ind.case_map || {};
  const catCn = ind.category_cn || {};
  const names = Object.keys(cats);
  if (!names.length) { $('baseline-body').innerHTML = '<div class="empty">industry_baseline.json 无数据</div>'; return; }
  /* case_map 反转：行业类目 → 本产品的 case（1 类可对多 case） */
  const cat2cases = {};
  Object.keys(caseMap).forEach((id) => {
    (cat2cases[caseMap[id]] = cat2cases[caseMap[id]] || []).push(id);
  });
  const chip = (v) => {
    const s = String(v || '').toLowerCase();
    if (s === 'yes') return '<span class="badge ok"><i></i>Yes</span>';
    if (s.startsWith('partial') || s.startsWith('via')) return '<span class="badge warn"><i></i>' + esc(v) + '</span>';
    return '<span class="badge bad"><i></i>No</span>';
  };
  const capable = (v) => {
    const s = String(v || '').toLowerCase();
    return s === 'yes' || s.startsWith('partial') || s.startsWith('via');
  };
  const products = ['Sysmon', 'MDE', 'CrowdStrike', 'SentinelOne'];
  let nWeak = 0, nStrong = 0, nAgree = 0;
  /* 模块级差异汇总：mod -> {agree, weak, strong, pending} */
  const modStats = {};
  const bumpMod = (mod, kind) => {
    if (!mod) return;
    const s = modStats[mod] = modStats[mod] || { agree: 0, weak: 0, strong: 0, pending: 0 };
    s[kind]++;
  };
  const rows = names.map((cat) => {
    const ours = (cat2cases[cat] || []).map(findCase).filter(Boolean);
    /* 本产品列：逐 case 徽章，点击跳详情 */
    const oursHtml = ours.length
      ? ours.map((c) => {
          const b = badgeOf(c);
          return `<span class="badge ${b.cls} link" data-case="${esc(c.case_id)}" title="${esc(c.case_id)}"><i></i>${b.txt}${b.manual ? '·手测' : ''}</span>`;
        }).join(' ')
      : '<span class="badge muted"><i></i>—</span>';
    /* 对照：行业多数能采（≥2/4）vs 本产品 */
    const indCap = products.filter((p) => capable(cats[cat][p])).length >= 2;
    let delta = '<span class="delta-eq">—</span>';
    const mod = ours.length ? ours[0].module : null;
    if (ours.length && !ours.every((c) => badgeOf(c).cls === 'muted')) {
      const oursCap = ours.some((c) => ['ok', 'warn'].includes(badgeOf(c).cls));
      if (oursCap && indCap) { delta = '<span class="delta-eq">= 一致</span>'; nAgree++; bumpMod(mod, 'agree'); }
      else if (oursCap && !indCap) { delta = '<span class="delta-up">↑ 强于行业</span>'; nStrong++; bumpMod(mod, 'strong'); }
      else if (!oursCap && indCap) { delta = '<span class="delta-dn">↓ 弱于行业</span>'; nWeak++; bumpMod(mod, 'weak'); }
      else { delta = '<span class="delta-eq">= 均弱</span>'; nAgree++; bumpMod(mod, 'agree'); }
    } else {
      bumpMod(mod, 'pending');
    }
    const cn = catCn[cat];
    const catCell = cn
      ? `<td class="mod-name">${esc(cn)}<div class="cat-en">${esc(cat)}</div></td>`
      : `<td class="mod-name">${esc(cat)}</td>`;
    return `<tr>${catCell}<td>${oursHtml}</td>
      ${products.map((p) => `<td>${chip(cats[cat][p])}</td>`).join('')}<td>${delta}</td></tr>`;
  }).join('');
  /* 模块级差异汇总条：按「弱于行业」降序，点击跳对应模块矩阵 */
  const modChips = Object.keys(modStats)
    .sort((a, b) => (modStats[b].weak - modStats[a].weak) || (modStats[b].agree - modStats[a].agree))
    .map((mod) => {
      const s = modStats[mod];
      const parts = [
        s.weak ? `<b class="r">↓${s.weak}</b>` : '',
        s.strong ? `<b class="g">↑${s.strong}</b>` : '',
        s.agree ? `<b class="x">=${s.agree}</b>` : '',
        s.pending ? `<b class="x">…${s.pending}</b>` : '',
      ].filter(Boolean).join(' ');
      return `<span class="mod-chip${s.weak ? ' has-weak' : ''}" data-mod="${esc(mod)}" title="点击筛选 ${esc(mod)} 模块矩阵">
        ${esc(MODULE_CN[mod] || mod)} ${parts}</span>`;
    }).join('');
  $('baseline-body').innerHTML = `
    <div class="note-box">本产品当前判定 vs 行业参照矩阵（tsale/EDR-Telemetry，行业多数 = 4 款中 ≥2 款可采）。
    一致 ${nAgree} 项 · <span class="delta-dn">↓ 弱于行业 ${nWeak} 项</span>（补齐优先级清单） · <span class="delta-up">↑ 强于行业 ${nStrong} 项</span>。
    点「本产品」列徽章可跳到对应 case 详情。</div>
    <div class="sec-t">模块级差异 · 按弱于行业排序（↓弱 ↑强 =一致 …待测）</div>
    <div class="mod-chips">${modChips}</div>
    <table class="cmp-table"><thead><tr><th>行为</th><th>本产品</th>${products.map((p) => `<th>${p}</th>`).join('')}<th>对照</th></tr></thead>
    <tbody>${rows}</tbody></table>`;
  $('baseline-body').querySelectorAll('[data-case]').forEach((el) => {
    el.onclick = () => openDrawer(el.dataset.case);
  });
  $('baseline-body').querySelectorAll('.mod-chip').forEach((el) => {
    el.onclick = () => {
      state.activeModule = el.dataset.mod;
      refreshAll();
      closeAll();
    };
  });
}
function renderClassmate() {
  const cases = (state.classmate && state.classmate.cases) || state.classmate || {};
  const ids = Object.keys(cases).filter((k) => cases[k] && typeof cases[k] === 'object');
  if (!ids.length) { $('baseline-body').innerHTML = '<div class="empty">classmate_baseline.json 无数据</div>'; return; }
  const ana = state.analysis || {};
  const rows = ids.sort().map((id) => {
    const cm = cases[id];
    const ours = findCase(id);
    const b = ours ? badgeOf(ours) : { cls: 'muted', txt: '未纳入' };
    const cv = cm.verdict || '';
    const cmBadge = cv === '有' ? '<span class="badge ok"><i></i>有</span>'
      : cv === '?' ? '<span class="badge warn"><i></i>?</span>'
      : cv === '无' ? '<span class="badge bad"><i></i>无</span>' : '<span class="badge muted"><i></i>—</span>';
    const agree = (cv === '有' || cv === '?') === (b.cls === 'ok' || b.cls === 'warn');
    const delta = b.cls === 'muted' ? '<span class="delta-eq">—</span>'
      : agree ? '<span class="delta-eq">= 一致</span>' : '<span class="delta-dn">≠ 差异</span>';
    const a = ana[id] || {};
    return `<tr><td class="mod-name" style="font-family:var(--mono);font-size:11px">${esc(id)}</td>
      <td style="color:var(--text-dim)">${esc(cm.behavior || (ours && ours.display) || '')}</td>
      <td><span class="badge ${b.cls}"><i></i>${b.txt}</span></td><td>${cmBadge}</td><td>${delta}</td>
      <td><input class="ainput cm-name" data-id="${esc(id)}" type="text" placeholder="映射名，如 FileWriteClose" value="${esc(a.map_name || '')}"></td>
      <td><textarea class="ainput cm-ana" data-id="${esc(id)}" rows="2" placeholder="采集分析（一两行）：结论、限制条件、差异原因…">${esc(a.analysis || '')}</textarea></td></tr>`;
  }).join('');
  $('baseline-body').innerHTML = `
    <div class="note-box">同学实测判定 vs 本产品当前判定（演示期兜底参照，暂时保留）；本项目复测定稿后以 case_result_map 为准。
    右侧两列可直接填写：<b>能力映射名称</b>（IOA 事件名）与<b>采集分析</b>（一两行结论），失焦自动保存，与 case 详情「分析」页互通。</div>
    <table class="cmp-table"><thead><tr><th>CASE</th><th>行为</th><th>本产品</th><th>同学</th><th>对照</th><th>能力映射名称</th><th>采集分析</th></tr></thead>
    <tbody>${rows}</tbody></table>`;
  /* 失焦自动保存（合并语义：只提交 map_name/analysis，不动映射笔记） */
  const save = async (id) => {
    const nameEl = $('baseline-body').querySelector(`.cm-name[data-id="${id}"]`);
    const anaEl = $('baseline-body').querySelector(`.cm-ana[data-id="${id}"]`);
    const payload = { map_name: nameEl.value, analysis: anaEl.value };
    const prev = ana[id] || {};
    if ((prev.map_name || '') === payload.map_name.trim()
        && (prev.analysis || '') === payload.analysis.trim()) return;
    try {
      await post(`/api/case/${id}/analysis`, payload);
      const updated = new Date().toISOString().slice(0, 16).replace('T', ' ');
      if (payload.map_name.trim() || payload.analysis.trim() || (prev.mapping || '')) {
        state.analysis[id] = { ...prev, ...payload, updated };
      } else {
        delete state.analysis[id];
      }
      toast(`${id} 分析已保存`, 1500);
    } catch (e) {
      toast(`保存失败：${e.message}`);
    }
  };
  $('baseline-body').querySelectorAll('.cm-name,.cm-ana').forEach((el) => {
    el.addEventListener('change', () => save(el.dataset.id));
  });
}

/* ── 总结报告 ── */
const SNAP_KEY = 'edr_report_snapshot';
function loadReport() { renderReport(); }
function renderReport() {
  const n = countByBadge();
  const auto = n.total - n.manual;
  const pct = n.total ? Math.round((n.ok / n.total) * 100) : 0;

  /* 较上轮 diff（localStorage 快照，历史不迁后端） */
  const cur = {};
  allCases().forEach((c) => { cur[c.case_id] = badgeOf(c).txt; });
  let added = '-', regressed = '-';
  try {
    const prev = JSON.parse(localStorage.getItem(SNAP_KEY) || 'null');
    if (prev) {
      added = 0; regressed = 0;
      Object.keys(cur).forEach((id) => {
        if (!(id in prev)) return;
        if (prev[id] !== '采集' && cur[id] === '采集') added++;
        if (prev[id] === '采集' && cur[id] !== '采集' && cur[id] !== '手动') regressed++;
      });
    }
  } catch (e) { /* ignore */ }

  /* 自动摘要 */
  const mods = (state.overview && state.overview.modules) || [];
  const strong = mods.filter((m) => !isManualModule(m) && groupByCapability(m.cases).every((g) => unionBadge(g.cases).cls === 'ok'))
    .map((m) => { const gs = groupByCapability(m.cases); return `${m.module}（${gs.length}/${gs.length}）`; });
  const concern = [];
  mods.forEach((m) => {
    if (isManualModule(m)) return;
    const bad = groupByCapability(m.cases).filter((g) => ['bad', 'warn'].includes(unionBadge(g.cases).cls));
    if (bad.length) concern.push(`${m.module}：${bad.map((g) => `${g.key}(${unionBadge(g.cases).txt})`).join('、')}`);
  });
  const manualMods = mods.filter(isManualModule).map((m) => m.module);

  $('report-body').innerHTML = `
    <div class="report-cards">
      <div class="rcard"><div class="k">总能力数</div><div class="v">${n.total}${n.manual ? `（含 ${n.manual} 手动）` : ''}</div></div>
      <div class="rcard"><div class="k">采集覆盖率</div><div class="v" style="color:var(--ok)">${pct}%</div></div>
      <div class="rcard"><div class="k">较上轮新增采集</div><div class="v" style="color:var(--ok)">${added === '-' ? '—' : '+' + added}</div></div>
      <div class="rcard"><div class="k">较上轮退化</div><div class="v" style="color:${regressed > 0 ? 'var(--bad)' : 'var(--ok)'}">${regressed}</div></div>
    </div>
    ${added === '-' ? '<div class="note-box">尚无对比基线——点击底部「存为本轮基线」后，下次打开报告即可看到新增/退化对比。</div>' : ''}
    <div class="sec-t">结论摘要 · SUMMARY</div>
    <div class="md-block">
      <h4>采集强项</h4>
      ${strong.length ? esc(strong.join('、')) + ' 全项采集。' : '暂无全项采集模块。'}
      <h4>关注项</h4>
      ${concern.length ? concern.map(esc).join('<br>') : '无。'}
      <h4>手动能力</h4>
      ${manualMods.length ? esc(manualMods.join('、')) + ' 由人工确认归档，不参与自动化回归。' : '无。'}
      <h4>状态分布</h4>
      采集 ${n.ok} · 疑问 ${n.warn} · 缺失 ${n.bad} · 待测 ${n.muted}${n.manual ? ` · 手动 ${n.manual}` : ''}
    </div>`;
}
function saveSnapshot() {
  const cur = {};
  allCases().forEach((c) => { cur[c.case_id] = badgeOf(c).txt; });
  localStorage.setItem(SNAP_KEY, JSON.stringify(cur));
  toast('已存为本轮基线');
  renderReport();
}
function exportReportMd() {
  const n = countByBadge();
  const auto = n.total - n.manual;
  const pct = n.total ? Math.round((n.ok / n.total) * 100) : 0;
  const mods = (state.overview && state.overview.modules) || [];
  const lines = [
    `# EDR 采集能力验证报告`, ``,
    `- 生成时间：${new Date().toLocaleString('zh-CN')}`,
    `- 总能力：${n.total}（自动化 ${auto}，手动 ${n.manual}）`,
    `- 采集覆盖率：${pct}%`,
    `- 状态分布：采集 ${n.ok} / 疑问 ${n.warn} / 缺失 ${n.bad} / 待测 ${n.muted}`, ``,
    `| 模块 | 采集 | 疑问 | 缺失 | 待测 |`, `|---|---|---|---|---|`,
  ];
  mods.forEach((m) => {
    const cnt = { ok: 0, warn: 0, bad: 0, muted: 0 };
    groupByCapability(m.cases).forEach((g) => { const cls = unionBadge(g.cases).cls; if (cls in cnt) cnt[cls]++; });
    lines.push(`| ${m.module} | ${cnt.ok} | ${cnt.warn} | ${cnt.bad} | ${cnt.muted} |`);
  });
  lines.push('', '## 明细', '');
  mods.forEach((m) => {
    lines.push(`### ${m.module}（${m.display}）`);
    m.cases.forEach((c) => {
      const b = badgeOf(c);
      lines.push(`- ${c.case_id} ${c.display}：**${b.txt}**${c.result && c.result.note ? ' — ' + c.result.note : ''}`);
    });
    lines.push('');
  });
  const blob = new Blob([lines.join('\n')], { type: 'text/markdown;charset=utf-8' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `edr_report_${new Date().toISOString().slice(0, 10)}.md`;
  a.click();
  URL.revokeObjectURL(a.href);
}

/* ═══════════ 终端（SSE + 拖拽 + 最大化） ═══════════ */
const TERM_H_KEY = 'edr_term_h';

function termOpen() { return $('term').classList.contains('open'); }
function termSetOpen(open) {
  if ($('terminal').classList.contains('maximized') && !open) return; // 最大化时不折叠
  $('term').classList.toggle('open', open);
  $('term-arrow').textContent = open ? '▾' : '▸';
}
function termClassify(line) {
  if (/error|fail|✗|❌|错误|失败|traceback/i.test(line)) return 'lv-err';
  if (/warn|⚠|注意|跳过|skip/i.test(line)) return 'lv-warn';
  if (/pass|✓|✅|成功|matched|完成|done/i.test(line)) return 'lv-ok';
  if (/▶|\[run-begin\]|\[target\]|\[step\]|^==|deliver/i.test(line)) return 'lv-info';
  return 'dim';
}
function termAppend(raw) {
  const body = $('term');
  const ts = new Date().toTimeString().slice(0, 8);
  const cls = termClassify(raw);
  const div = document.createElement('div');
  div.innerHTML = `<span class="ts">[${ts}]</span> <span class="${cls}">${esc(raw)}</span>`;
  const caret = body.querySelector('.caret-line');
  if (caret) caret.remove();
  body.appendChild(div);
  const nearBottom = body.scrollHeight - body.scrollTop - body.clientHeight < 60;
  if (nearBottom) body.scrollTop = body.scrollHeight;
  $('term-last').textContent = raw.slice(0, 120);
}
function termCaret(show) {
  const body = $('term');
  body.querySelectorAll('.caret-line').forEach((x) => x.remove());
  if (show) {
    const div = document.createElement('div');
    div.className = 'caret-line';
    div.innerHTML = '<span class="caret"></span>';
    body.appendChild(div);
    body.scrollTop = body.scrollHeight;
  }
}
function termClear() { $('term').innerHTML = ''; $('term-last').textContent = ''; }

function attachTask(taskId, label) {
  if (state.es) { state.es.close(); state.es = null; }
  if (state.pollTimer) { clearInterval(state.pollTimer); state.pollTimer = null; }
  state.taskId = taskId;
  termSetOpen(true);
  termAppend(`▶ ${label}（task ${taskId}）`);
  termCaret(true);
  $('term-dot').classList.remove('idle');
  // 运行期间每 5s 刷一次矩阵/侧栏：即使终端(SSE)断了、页面看不到过程，也能看投递进度
  state.pollTimer = setInterval(() => { loadOverview(); }, 5000);
  const es = new EventSource(`/api/task/${taskId}/events`);
  state.es = es;
  const stopPoll = () => { if (state.pollTimer) { clearInterval(state.pollTimer); state.pollTimer = null; } };
  es.onmessage = (ev) => {
    const d = JSON.parse(ev.data);
    if (d.line != null) { termCaret(false); termAppend(d.line); termCaret(true); }
    if (d.done) {
      es.close(); state.es = null; state.taskId = null;
      stopPoll();
      termCaret(false);
      $('term-dot').classList.add('idle');
      termAppend(d.exit_code === 0 ? '── 任务完成（exit 0）──' : `── 任务结束（exit ${d.exit_code}）──`);
      toast(d.exit_code === 0 ? '任务完成' : '任务异常结束，看终端输出');
      loadOverview().then(() => {
        if (state.drawerCase) renderDrawerTab();
      });
    }
  };
  es.onerror = () => {
    // SSE 断开：不停进度轮询（矩阵继续刷新），只标记终端连接状态
    es.close(); state.es = null;
    termCaret(false); $('term-dot').classList.add('idle');
    termAppend('── 终端连接已断开（进度仍在矩阵刷新）──');
  };
}
async function stopTask() {
  if (!state.taskId) { toast('当前无运行中任务'); return; }
  try { await post(`/api/task/${state.taskId}/stop`); termAppend('── 已请求停止 ──'); }
  catch (e) { toast('停止失败：' + e.message); }
}

/* 拖拽调高度（120px ~ 70vh，持久化） */
function initTermDrag() {
  const drag = $('term-drag');
  let startY = 0, startH = 0;
  drag.addEventListener('mousedown', (e) => {
    if (!termOpen()) termSetOpen(true);
    startY = e.clientY;
    startH = $('term').getBoundingClientRect().height;
    drag.classList.add('active');
    e.preventDefault();
    const onMove = (ev) => {
      const max = window.innerHeight * 0.7;
      const h = Math.min(Math.max(startH + (startY - ev.clientY), 120), max);
      document.documentElement.style.setProperty('--term-h', h + 'px');
    };
    const onUp = () => {
      drag.classList.remove('active');
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
      const h = $('term').getBoundingClientRect().height;
      try { localStorage.setItem(TERM_H_KEY, String(Math.round(h))); } catch (e) { /* ignore */ }
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  });
  try {
    const saved = +localStorage.getItem(TERM_H_KEY);
    if (saved >= 120) document.documentElement.style.setProperty('--term-h', saved + 'px');
  } catch (e) { /* ignore */ }
}
function termMaxToggle() {
  const t = $('terminal');
  const on = t.classList.toggle('maximized');
  $('btn-term-max').classList.toggle('on', on);
  if (on) termSetOpen(true);
}

/* ═══════════ 动作 ═══════════ */
async function runCase(id) {
  try { const r = await post(`/api/case/${id}/run`); attachTask(r.task_id, `run ${id}`); }
  catch (e) { toast('启动失败：' + e.message); }
}
async function matchCase(id, jsonPath) {
  try {
    const r = await post(`/api/case/${id}/match`, jsonPath ? { json: jsonPath } : {});
    attachTask(r.task_id, `match ${id}${jsonPath ? '（指定日志）' : ''}`);
  } catch (e) { toast('启动失败：' + e.message); }
}
/* 能力组整组跑/匹配：逐个投递（后端单 VM 串行队列），终端跟随最后一个任务 */
async function runGroup(ids) {
  let last = null, ok = 0;
  for (const id of ids) {
    try { const r = await post(`/api/case/${id}/run`); last = [r.task_id, `run ${id}（变体组）`]; ok++; }
    catch (e) { toast(`投递 ${id} 失败：${e.message}`); }
  }
  if (last) attachTask(last[0], last[1]);
  if (ok > 1) toast(`已投递 ${ok} 个变体到串行队列`);
}
async function matchGroup(ids) {
  let last = null, ok = 0;
  for (const id of ids) {
    try { const r = await post(`/api/case/${id}/match`); last = [r.task_id, `match ${id}（变体组）`]; ok++; }
    catch (e) { toast(`匹配 ${id} 失败：${e.message}`); }
  }
  if (last) attachTask(last[0], last[1]);
  if (ok > 1) toast(`已提交 ${ok} 个变体匹配`);
}
async function runModule(mod) {
  try { const r = await post(`/api/module/${mod}/deliver`); attachTask(r.task_id, `deliver --module ${mod}`); }
  catch (e) { toast('启动失败：' + e.message); }
}
async function matchModule(mod) {
  try { const r = await post(`/api/module/${mod}/match`); attachTask(r.task_id, `match --module ${mod}`); }
  catch (e) { toast('启动失败：' + e.message); }
}
async function runAll() {
  const n = allCases().filter((c) => c.integrated).length;
  if (!window.confirm(`全量投递 ${n} 个 case 到 VM 串行执行，耗时较长。确认开始？`)) return;
  try { const r = await post('/api/all/deliver'); attachTask(r.task_id, 'deliver（全量）'); }
  catch (e) { toast('启动失败：' + e.message); }
}
async function matchAll() {
  try { const r = await post('/api/all/match'); attachTask(r.task_id, 'match（全量）'); }
  catch (e) { toast('启动失败：' + e.message); }
}

/* ═══════════ 图标（内联 SVG） ═══════════ */
const ICO = {
  check: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M20 6L9 17l-5-5"/></svg>',
  warn: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M12 9v4M12 17h.01M10.3 3.9L1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z"/></svg>',
  cross: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><path d="M18 6L6 18M6 6l12 12"/></svg>',
  clock: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg>',
  checkSm: '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4"><path d="M20 6L9 17l-5-5"/></svg>',
  playSm: '<svg width="10" height="10" viewBox="0 0 24 24" fill="currentColor"><path d="M6 4l14 8-14 8z"/></svg>',
  upload: '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><path d="M17 8l-5-5-5 5"/><path d="M12 3v12"/></svg>',
};

/* ═══════════ 初始化 ═══════════ */
document.addEventListener('DOMContentLoaded', () => {
  /* 顶栏 */
  $('btn-manual').onclick = () => openPanel('manual');
  $('btn-baseline').onclick = () => openPanel('baseline');
  $('btn-report').onclick = () => openPanel('report');
  $('btn-import-log').onclick = () => {
    if (state.drawerCase && $('drawer').classList.contains('open')) {
      state.drawerTab = 'logs'; renderDrawerTab();
    } else {
      toast('先在矩阵里点一个 case，再在「日志」页上传');
    }
  };
  $('btn-match-all').onclick = matchAll;
  $('btn-run-all').onclick = runAll;

  /* Baseline seg */
  $('baseline-seg').querySelectorAll('button').forEach((b) => {
    b.onclick = () => switchBaselineTab(b.dataset.seg);
  });
  /* 报告 foot */
  $('btn-export-md').onclick = exportReportMd;
  $('btn-save-snap').onclick = saveSnapshot;
  $('btn-report-refresh').onclick = () => loadOverview().then(renderReport);

  /* 抽屉 foot */
  $('d-run').onclick = () => { if (state.drawerCase) runCase(state.drawerCase.case_id); };
  $('d-match').onclick = () => { if (state.drawerCase) matchCase(state.drawerCase.case_id); };

  /* 终端 */
  $('term-bar').onclick = (e) => {
    if (e.target.closest('.tbtn')) return;
    termSetOpen(!termOpen());
  };
  $('btn-term-clear').onclick = (e) => { e.stopPropagation(); termClear(); };
  $('btn-term-stop').onclick = (e) => { e.stopPropagation(); stopTask(); };
  $('btn-term-max').onclick = (e) => { e.stopPropagation(); termMaxToggle(); };
  $('term-dot').classList.add('idle');
  initTermDrag();

  /* 面板向左展开（拖拽 + 一键整宽） */
  initSlideExpand();

  /* 快捷键 */
  document.addEventListener('keydown', (e) => {
    if (e.key === 'F1') { e.preventDefault(); openPanel('manual'); }
    if (e.key === 'Escape') {
      if ($('terminal').classList.contains('maximized')) { termMaxToggle(); return; }
      closeAll();
    }
  });

  /* 数据加载 + 周期刷新 */
  loadSysmon().then(loadOverview);
  setInterval(loadOverview, 60000);
});
