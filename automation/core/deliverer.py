"""
deliverer.py

Host-side sample delivery and execution via VMware vmrun.

Workflow:
  1. Locate sample at <samples_root>/<module>/<program> (fallback: recursive search)
  2. Copy EXE to guest temp directory
  3. Run EXE with the specified action argument
  4. Capture stdout via temp file → copy back → return text
  5. Clean up guest temp files

Snapshot restore is available via restore_snapshot()/ensure_vm_ready() but is
never performed implicitly inside deliver_and_run(); the runner decides whether
to restore before delivery (e.g. via --restore-snapshot).

Config (delivery section in runner config):
  {
    "vm": {
      "vmrun_path":   "C:\\Program Files (x86)\\VMware\\..\\vmrun.exe",
      "vmx_path":     "E:\\VMs\\Win10_IOA\\Win10_IOA.vmx",
      "credentials":  { "username": "tester", "password": "xxx" },
      "guest_temp":   "C:\\Windows\\Temp",
      "timeouts": {
        "copy":       60,
        "run":        60,
        "wait_ready": 120
      }
    },
    "samples_root":   "E:\\AVtest\\samples"
  }
"""

from __future__ import annotations

import hashlib
import logging
import os
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)


def sha256_file(path: str | os.PathLike) -> str:
    """Return uppercase SHA-256 hex digest of a file."""
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest().upper()


# ── Low-level vmrun wrapper ────────────────────────────────────────────────

class _VMRun:
    def __init__(self, vmrun: str, vmx: str, user: str, pwd: str):
        self.vmrun = vmrun
        self.vmx   = vmx
        self.user  = user
        self.pwd   = pwd

    def _run(self, args: list[str], timeout: int = 30) -> tuple[bool, str]:
        cmd = [self.vmrun] + args
        try:
            r = subprocess.run(
                cmd, capture_output=True, timeout=timeout,
            )
            out = b''
            for enc in ('utf-8', 'gbk', 'mbcs'):
                try:
                    out = (r.stdout or b'').decode(enc)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                out = (r.stdout or b'').decode('utf-8', errors='replace')
            return r.returncode == 0, out.strip()
        except subprocess.TimeoutExpired:
            log.error('vmrun timeout: %s', self._desc(args))
            return False, ''
        except Exception as exc:
            log.error('vmrun error: %s', exc)
            return False, ''

    def _guest_args(self) -> list[str]:
        return ['-gu', self.user, '-gp', self.pwd, '-T', 'ws']

    def _vm_args(self) -> list[str]:
        """Args for VM-level vmrun commands (no guest credentials needed)."""
        return ['-T', 'ws']

    def _desc(self, args: list[str]) -> str:
        """Credential-safe description of a vmrun command for log messages.

        Skips the leading credential block (-gu/-gp/-T and their values) so
        usernames/passwords never reach logs, and returns only the vmrun verb
        (e.g. 'fileExistsInGuest', 'runProgramInGuest', 'revertToSnapshot').
        """
        i = 0
        while i < len(args):
            if args[i] in ('-gu', '-gp', '-T'):
                i += 2   # skip flag and its value
            else:
                break
        return args[i] if i < len(args) else '?'

    # ── VM power / snapshot management ─────────────────────────────────────

    def is_running(self, timeout: int = 15) -> bool:
        """Return True if this VMX appears in `vmrun list`."""
        ok, out = self._run(self._vm_args() + ['list'], timeout=timeout)
        if not ok:
            return False
        target = os.path.normcase(os.path.normpath(self.vmx))
        for line in out.splitlines():
            line = line.strip()
            if not line or line.lower().startswith('total'):
                continue
            if os.path.normcase(os.path.normpath(line)) == target:
                return True
        return False

    def start_vm(self, timeout: int = 60) -> bool:
        # vmrun 'start' can transiently fail right after a snapshot revert
        # ('未知错误' / 'already running') while VMware is still switching
        # state. Retry a few times; if the VM is actually running, treat it
        # as success and fall through to wait_ready().
        for attempt in range(1, 4):
            ok, out = self._run(
                self._vm_args() + ['start', self.vmx, 'nogui'],
                timeout=timeout,
            )
            if ok:
                return True
            log.warning(
                'start_vm: attempt %d returned non-zero (VM may already be '
                'starting). %s', attempt, out,
            )
            if self.is_running(timeout=15):
                log.info('start_vm: VM is running (retry after %d attempt(s)).', attempt)
                return True
            time.sleep(5)
        return self.is_running(timeout=15)

    def stop_vm(self, mode: str = 'hard', timeout: int = 30) -> bool:
        ok, out = self._run(
            self._vm_args() + ['stop', self.vmx, mode],
            timeout=timeout,
        )
        if not ok:
            log.warning('stop_vm: vmrun returned non-zero. %s', out)
        return ok

    def revert_snapshot(self, name: str, timeout: int = 120) -> bool:
        ok, out = self._run(
            self._vm_args() + ['revertToSnapshot', self.vmx, name],
            timeout=timeout,
        )
        if not ok:
            log.error('revert_snapshot(%r) failed: %s', name, out)
        return ok

    def file_exists(self, guest_path: str, timeout: int = 15) -> bool:
        ok, _ = self._run(
            self._guest_args() + ['fileExistsInGuest', self.vmx, guest_path],
            timeout=timeout,
        )
        return ok

    def create_directory(self, guest_dir: str, timeout: int = 30) -> bool:
        """Create a directory tree in the guest via vmrun createDirectoryInGuest.

        createDirectoryInGuest creates the directory and any missing parent
        directories, so it is safe for nested paths like
        C:\\EDRTest\\samples\\Process\\Support.
        """
        ok, out = self._run(
            self._guest_args() + ['createDirectoryInGuest', self.vmx, guest_dir],
            timeout=timeout,
        )
        if not ok:
            # vmrun returns non-zero when the directory already exists
            # (message like "该文件已存在" / "already exists"). That is not a
            # real failure for idempotent delivery — the directory is ready.
            lowered = (out or '').lower()
            if ('已存在' in (out or '') or 'already exist' in lowered
                    or 'file exists' in lowered):
                log.info('create_directory: %s already exists (ok)', guest_dir)
                return True
            if self.file_exists(guest_dir, timeout=15):
                log.info('create_directory: %s already exists', guest_dir)
                return True
            log.error('create_directory failed: %s  (%s)', guest_dir, out)
        return ok

    def copy_to_guest(self, host_path: str, guest_path: str, timeout: int = 120) -> bool:
        ok, out = self._run(
            self._guest_args() + ['copyFileFromHostToGuest', self.vmx,
                                  host_path, guest_path],
            timeout=timeout,
        )
        if not ok:
            log.error('copy_to_guest failed: %s → %s  (%s)', host_path, guest_path, out)
        return ok

    def copy_from_guest(self, guest_path: str, host_path: str, timeout: int = 60) -> bool:
        ok, out = self._run(
            self._guest_args() + ['copyFileFromGuestToHost', self.vmx,
                                  guest_path, host_path],
            timeout=timeout,
        )
        if not ok:
            log.warning('copy_from_guest failed: %s  (%s)', guest_path, out)
        return ok

    def run_program(self, guest_exe: str, args: str = '',
                    wait: bool = True, timeout: int = 60) -> bool:
        # NOTE: vmrun 1.17.0 rejects '-noWait'; always run synchronously.
        ok, _ = self._run(
            self._guest_args() +
            ['runProgramInGuest', self.vmx, '-activeWindow',
             guest_exe] + (args.split() if args else []),
            timeout=timeout,
        )
        return ok

    def run_via_bat(self, command: str, wait: bool = True,
                    timeout: int = 60) -> bool:
        """Write a .bat to host temp, copy to guest, run it.

        Uses the bat-relay pattern (same as the legacy framework) so that
        stdout redirection ('>') and chaining ('&') work reliably inside the
        guest — passing these directly to runProgramInGuest is what causes the
        spurious 'exit code 1'.

        NOTE: we intentionally run cmd.exe WITHOUT -activeWindow. In a locked
        or headless guest session -activeWindow frequently makes vmrun return
        a non-zero code even though the program ran fine. The sample's own
        exit code is captured separately via the stdout [RESULT] line, so we
        don't rely on vmrun's return code to judge sample success.
        """
        uid = uuid.uuid4().hex[:8]
        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.bat', delete=False,
            encoding='gbk', errors='ignore',
        ) as f:
            f.write(f'@echo off\r\n{command}\r\nexit /b %errorlevel%\r\n')
            host_bat = f.name
        guest_bat = f'C:\\Windows\\Temp\\_edr_{uid}.bat'
        try:
            if not self.copy_to_guest(host_bat, guest_bat, timeout=30):
                log.error('run_via_bat: failed to copy relay bat into guest')
                return False
            # NOTE: vmrun 1.17.0 rejects '-noWait', so always run
            # synchronously; run/delete commands are fast enough to block.
            ok, out = self._run(
                self._guest_args() +
                ['runProgramInGuest', self.vmx,
                 'C:\\Windows\\System32\\cmd.exe', '/c', guest_bat],
                timeout=timeout,
            )
            if not ok:
                # A non-zero vmrun exit here is common and not necessarily a
                # real failure (guest program exited non-zero / locked window).
                # Surface it for diagnostics but let the caller decide via stdout.
                log.warning(
                    'run_via_bat: vmrun reported non-zero (this is often benign; '
                    'the sample exit code is read from stdout). detail=%r', out,
                )
            return ok
        finally:
            try:
                Path(host_bat).unlink(missing_ok=True)
            except Exception:
                pass

    def wait_ready(self, max_wait: int = 120, interval: int = 3) -> bool:
        log.info('Waiting for guest ready (max %ds) …', max_wait)
        deadline = time.time() + max_wait
        while time.time() < deadline:
            if self.file_exists('C:\\Windows\\System32\\cmd.exe', timeout=10):
                log.info('Guest ready.')
                return True
            time.sleep(interval)
        log.error('Guest not ready after %ds', max_wait)
        return False

    def delete_file(self, guest_path: str) -> None:
        self.run_via_bat(f'del /f /q "{guest_path}" 2>nul', wait=True, timeout=10)


# ── Sample discovery ───────────────────────────────────────────────────────

def discover_sample(samples_root: Path, sample_file: str) -> Optional[Path]:
    """
    Search samples_root recursively for <sample_file> inside any
    build_output directory.  Returns the first match or None.

    Search order: developing → (frozen) → legacy
    """
    for priority in ('developing', 'frozen', 'legacy'):
        for p in sorted(samples_root.rglob(f'{priority}/**/build_output/{sample_file}')):
            log.info('Discovered sample: %s', p)
            return p
    # Fallback: any build_output anywhere
    for p in sorted(samples_root.rglob(f'build_output/{sample_file}')):
        log.info('Discovered sample (fallback): %s', p)
        return p
    # Fallback: flat EXE directly under samples_root (post-migration layout)
    for p in sorted(samples_root.rglob(sample_file)):
        log.info('Discovered sample (flat): %s', p)
        return p
    return None


# ── Deliverer ──────────────────────────────────────────────────────────────

class Deliverer:
    """
    Copy a sample EXE from the host into the guest VM and run it,
    capturing stdout.  No snapshot management; call restore_snapshot
    manually before using this class if needed.
    """

    def __init__(self, config: dict):
        vm_cfg   = config['vm']
        self._vm = _VMRun(
            vmrun = vm_cfg['vmrun_path'],
            vmx   = vm_cfg['vmx_path'],
            user  = vm_cfg['credentials']['username'],
            pwd   = vm_cfg['credentials']['password'],
        )
        self._guest_temp    = vm_cfg.get('guest_temp', 'C:\\Windows\\Temp')
        self._timeouts      = vm_cfg.get('timeouts', {})
        self._samples_root  = Path(config['samples_root'])
        self._guest_samples_root = config.get('guest_samples_root', '') or ''

    # ── Public API ─────────────────────────────────────────────────────────

    def ensure_guest_ready(self) -> bool:
        return self._vm.wait_ready(
            max_wait=self._timeouts.get('wait_ready', 120),
        )

    # ── Snapshot / VM lifecycle ────────────────────────────────────────────

    def restore_snapshot(self, snapshot_name: str) -> bool:
        """Power off (if running), revert to snapshot, then start the VM."""
        if self._vm.is_running():
            log.info('VM is running; powering off before snapshot restore …')
            self._vm.stop_vm('hard')

        if not self._vm.revert_snapshot(snapshot_name):
            return False

        log.info('Snapshot %r restored; starting VM …', snapshot_name)
        if not self._vm.start_vm():
            log.error('Failed to start VM after snapshot restore.')
            return False
        return True

    def ensure_vm_ready(self, snapshot_name=None) -> bool:
        """Bring the VM to a guest-ready state.

        If snapshot_name is provided, restore it (which also starts the VM);
        otherwise ensure the VM is started if not running, then wait for
        VMware Tools / guest file access to become ready.
        """
        if snapshot_name:
            if not self.restore_snapshot(snapshot_name):
                return False
        elif not self._vm.is_running():
            log.info('VM is not running; starting …')
            self._vm.start_vm()

        return self.ensure_guest_ready()

    def shutdown_after(self, mode: str = 'soft', timeout: int = 90) -> bool:
        """Soft-power-off the VM after a run.

        Used by --shutdown-after to clear persistent sample behavior
        (services / scheduled tasks / drivers) for modules whose snapshot
        policy is 'never'. Soft mode lets the guest shut down cleanly so
        persistent objects are released instead of being force-killed.
        """
        if not self._vm.is_running():
            log.info('VM already powered off; nothing to shut down.')
            return True
        log.info('Powering off VM (mode=%s) to clear persistent behavior …', mode)
        if self._vm.stop_vm(mode, timeout=timeout):
            return True
        # Soft shutdown timed out / failed — force a hard stop so the next
        # case doesn't inherit a half-shutdown VM (which makes
        # runProgramInGuest fail with "VMware Tools not running").
        log.warning('Soft shutdown failed/timed out; forcing hard stop.')
        return self._vm.stop_vm('hard', timeout=60)

    def _ensure_guest_dir(self, guest_dir: str) -> bool:
        """Ensure a directory tree exists in the guest.

        Prefer vmrun createDirectoryInGuest (creates parents automatically);
        fall back to the bat-relay mkdir if that command is unavailable.
        """
        if self._vm.create_directory(guest_dir):
            return True
        cmd = f'if not exist "{guest_dir}" mkdir "{guest_dir}"'
        self._vm.run_via_bat(cmd, wait=True, timeout=20)
        return self._vm.file_exists(guest_dir, timeout=15)

    def deliver_and_run(
        self,
        test_case: dict,
        wait_s_after_run: int = 5,
        strict_fingerprint: bool = False,
    ) -> Optional[str]:
        """
        Locate the sample under <samples_root>/<module>/, deliver the whole
        module directory (preserving relative sub-directories such as
        Support\\TestLibrary.dll or Support\\nonpnp.sys), then run the
        program with the action argument and capture stdout.

        Returns the stdout text, or None on delivery/execution failure.
        """
        program: str = test_case.get('program') or test_case.get('sample_file', '')
        module:  str = test_case.get('module', '')
        action:  str = test_case.get('action', '')
        case_id: str = test_case.get('id', 'UNKNOWN')

        if not program:
            log.error('[%s] test_case missing program', case_id)
            return None

        # 1. Locate host module directory.
        #    Primary: <samples_root>/<module>/ contains the program.
        #    Fallback: recursive discovery (legacy build_output / flat layouts).
        host_module_dir: Optional[Path] = None
        host_program:    Optional[Path] = None
        if module:
            d = self._samples_root / module
            candidate = d / program
            if candidate.is_file():
                host_module_dir = d
                host_program = candidate
                log.info('[%s] Sample located: %s', case_id, candidate)
        if host_program is None:
            legacy = discover_sample(self._samples_root, program)
            if legacy is not None:
                host_program = legacy
                host_module_dir = legacy.parent
        if host_program is None:
            log.error(
                '[%s] Sample %r not found under %s',
                case_id, program, self._samples_root,
            )
            return None

        # 1.5. Host-side SHA-256 fingerprint verification.
        #      Warn (and optionally abort) when the host EXE differs from the
        #      declared sample_sha256. A mismatch usually means the sample was
        #      rebuilt without updating test_cases.json — abort only in strict
        #      mode, otherwise warn and proceed so stdout still flows.
        expected_sha = (test_case.get('sample_sha256') or '').strip().upper()
        if expected_sha:
            actual_sha = sha256_file(str(host_program))
            if actual_sha != expected_sha:
                if strict_fingerprint:
                    log.error(
                        '[%s] Sample fingerprint mismatch (aborting): '
                        'expected=%s actual=%s (%s)',
                        case_id, expected_sha, actual_sha, host_program,
                    )
                    return None
                log.warning(
                    '[%s] Sample fingerprint mismatch (continuing): '
                    'expected=%s actual=%s (%s)',
                    case_id, expected_sha, actual_sha, host_program,
                )
            else:
                log.info('[%s] Sample fingerprint OK', case_id)
        else:
            log.info(
                '[%s] No sample_sha256 configured, skipping fingerprint check',
                case_id,
            )

        # 2. Enumerate all files under the module dir (preserve relative paths).
        payload: list[tuple[Path, str]] = []
        if host_module_dir is not None:
            for p in sorted(host_module_dir.rglob('*')):
                if p.is_file():
                    rel = p.relative_to(host_module_dir)
                    payload.append((p, rel.as_posix()))
        if not payload:
            # Degenerate case: only the program file, no module dir scan.
            payload = [(host_program, host_program.name)]

        # 3. Guest destination root.
        #    Deterministic per-module dir under guest_samples_root when
        #    configured, otherwise fall back to a uid-tagged temp dir.
        uid = uuid.uuid4().hex[:8]
        if self._guest_samples_root:
            guest_base = f'{self._guest_samples_root}\\{module}'
        else:
            guest_base = f'{self._guest_temp}\\{uid}_{module}'

        # 4. Create guest directory tree for every payload sub-directory.
        subdirs = set()
        for _, rel in payload:
            parent = str(Path(rel).parent)
            if parent and parent != '.':
                subdirs.add(parent)
        self._ensure_guest_dir(guest_base)
        for sd in sorted(subdirs, key=lambda s: s.count('/')):
            self._ensure_guest_dir(f'{guest_base}\\{sd.replace("/", "\\")}')

        # 4.5. Kill a lingering pre_start target from a previous case before
        #      copying, otherwise the still-running EXE locks the file and
        #      copyFileFromHostToGuest fails with "access denied".
        pre_start = (test_case.get('pre_start') or '').strip()
        if pre_start:
            self._vm.run_via_bat(
                f'taskkill /F /IM "{pre_start}" 2>nul', wait=True, timeout=15,
            )
            time.sleep(1)

        # 5. Copy each file to guest.
        copied: list[str] = []
        for host_file, rel in payload:
            guest_dst = f'{guest_base}\\{rel.replace("/", "\\")}'
            # pre_start target: skip re-copy when it already exists in the
            # guest. A still-running instance holds the file open, making
            # copyFileFromHostToGuest fail with "access denied"; the EXE is
            # identical across cases (MD5-verified), so re-copying is unneeded.
            if pre_start and rel == pre_start and self._vm.file_exists(guest_dst, timeout=15):
                log.info('[%s] Skip re-copy (already in guest): %s', case_id, rel)
                copied.append(guest_dst)
                continue
            log.info('[%s] Copying %s → %s', case_id, rel, guest_dst)
            if not self._vm.copy_to_guest(
                str(host_file), guest_dst,
                timeout=self._timeouts.get('copy', 120),
            ):
                log.error('[%s] copy failed: %s', case_id, rel)
                return None
            copied.append(guest_dst)

        # 5.5. Pre-start a prerequisite process (e.g. ProcessTarget.exe for
        #      terminate/access/remotethread/tamper) so the sample acts on an
        #      already-running target.
        pre_start = (test_case.get('pre_start') or '').strip()
        if pre_start:
            guest_ps = f'{guest_base}\\{pre_start}'
            log.info('[%s] Pre-starting prerequisite %s', case_id, pre_start)
            # `start ""` launches it detached so the target keeps running.
            self._vm.run_via_bat(
                f'start "" "{guest_ps}"', wait=True,
                timeout=self._timeouts.get('run', 30),
            )
            time.sleep(2)  # let the target finish initializing

        # 6. Run the program with the action argument.
        guest_exe = f'{guest_base}\\{program}'
        uid_out   = f'{self._guest_temp}\\{uid}_stdout.txt'
        cmd = f'"{guest_exe}" {action} > "{uid_out}" 2>&1'
        log.info('[%s] Running: %s', case_id, cmd)
        self._vm.run_via_bat(
            cmd, wait=True,
            timeout=self._timeouts.get('run', 90),
        )

        # Brief pause to allow file flush
        time.sleep(wait_s_after_run)

        # 7. Copy stdout back.
        with tempfile.NamedTemporaryFile(
            suffix='.txt', delete=False,
        ) as tmp:
            local_out = tmp.name

        stdout_text: Optional[str] = None
        if self._vm.copy_from_guest(
            uid_out, local_out,
            timeout=self._timeouts.get('copy', 60),
        ):
            try:
                stdout_text = Path(local_out).read_text(
                    encoding='utf-8', errors='replace'
                )
                log.info('[%s] stdout captured (%d chars)', case_id, len(stdout_text))
            except Exception as exc:
                log.warning('[%s] reading local stdout: %s', case_id, exc)
        else:
            log.warning('[%s] Could not retrieve stdout from guest', case_id)

        # 8. Cleanup: delete the uid stdout temp only. The deployed module dir
        #    is left in place under guest_samples_root (deterministic, idempotent
        #    re-delivery on the next run).
        try:
            Path(local_out).unlink(missing_ok=True)
        except Exception:
            pass
        self._vm.delete_file(uid_out)

        return stdout_text

    def export_sysmon_log(self, out_dir: Path, case_id: str) -> Optional[Path]:
        """Export the guest Sysmon operational log to
        <out_dir>/sysmon_<case_id>.evtx (L2 baseline evidence).

        MUST be called while the VM is still running and BEFORE any snapshot
        revert — reverting discards the guest-local event log. Best-effort:
        failures log a warning and return None instead of aborting the run
        (e.g. when Sysmon is not installed in the current snapshot).
        """
        if not self._vm.is_running():
            log.warning('[%s] VM not running; Sysmon export skipped', case_id)
            return None
        evtx = f'{self._guest_temp}\\sysmon_{case_id}.evtx'
        self._vm.delete_file(evtx)  # stale-file guard
        cmd = (
            f'wevtutil epl Microsoft-Windows-Sysmon/Operational '
            f'"{evtx}" >nul 2>&1'
        )
        self._vm.run_via_bat(cmd, wait=True, timeout=60)
        if not self._vm.file_exists(evtx, timeout=15):
            log.warning(
                '[%s] Sysmon evtx export unavailable in guest '
                '(Sysmon not installed?); skipped', case_id,
            )
            return None
        out_dir.mkdir(parents=True, exist_ok=True)
        local = out_dir / f'sysmon_{case_id}.evtx'
        if self._vm.copy_from_guest(evtx, str(local), timeout=120):
            log.info('[%s] Sysmon evtx exported: %s', case_id, local)
            self._vm.delete_file(evtx)
            return local
        return None

    def save_stdout(self, stdout_text: str, out_dir: Path, case_id: str) -> Path:
        """Persist stdout to out_dir/<case_id>_stdout.txt and return the path."""
        out_dir.mkdir(parents=True, exist_ok=True)
        p = out_dir / f'{case_id}_stdout.txt'
        p.write_text(stdout_text, encoding='utf-8')
        log.info('stdout saved: %s', p)
        return p
