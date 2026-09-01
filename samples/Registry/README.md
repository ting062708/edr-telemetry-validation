# RegistryLifecycleTest — Full Lifecycle Frozen Candidate

## Purpose

This project is the frozen-candidate EDR registry lifecycle sample for Windows 10 x64 / .NET Framework 4.7.2.

One normal run performs exactly three test phases in order:

1. `REG-CREATE-001` — create one test registry value.
2. `REG-MODIFY-001` — modify that same value once.
3. `REG-DELETE-001` — delete that same value once.

Test target:

```text
HKCU\Software\Microsoft\Windows\CurrentVersion\Run
ValueName = EDRTelemetryRunTest
```

Lifecycle values:

```text
CREATE = C:\Windows\System32\notepad.exe
MODIFY = C:\Windows\System32\calc.exe
DELETE = remove EDRTelemetryRunTest
```

The program never launches `notepad.exe` or `calc.exe`; these paths are registry test data only.

## Frozen behavior rules

- SETUP is read-only validation.
- No automatic pre-clean occurs during a formal full-cycle run.
- Each TARGET contains only the intended registry mutation for that TestCase.
- Each TARGET is followed by read-only verification.
- There is a 10-second delay between phases for telemetry separation.
- A successful run ends with the test value absent, so the normal lifecycle is self-cleaning.
- If a previous interrupted run left the value behind, the formal run FAILs instead of silently deleting it.
- `cleanup` is a separate recovery command and is not part of any formal TestCase.

## Build

Requirements:

```text
Windows 10/11 x64
Visual Studio 2022
.NET Framework 4.7.2 Developer Pack / targeting pack
```

Open:

```text
RegistryLifecycleTest.sln
```

Build exactly:

```text
Configuration = Release
Platform      = x64
```

Expected executable:

```text
RegistryLifecycleTest\bin\x64\Release\RegistryLifecycleTest.exe
```

## Formal test

Use the same Windows user account that is monitored by the EDR. Administrator rights are not required for this HKCU test.

Before the run, verify the test value is absent:

```bat
reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v EDRTelemetryRunTest
```

Expected before a clean run:

```text
ERROR: The system was unable to find the specified registry value or key.
```

Run:

```bat
cd /d C:\Users\tester\Desktop
RegistryLifecycleTest.exe > registry_fullcycle_stdout.txt 2>&1
echo ExitCode=%ERRORLEVEL%
type registry_fullcycle_stdout.txt
```

Expected result:

```text
[PHASE-END] TestCaseID=REG-CREATE-001 Status=PASS ...
[PHASE-END] TestCaseID=REG-MODIFY-001 Status=PASS ...
[PHASE-END] TestCaseID=REG-DELETE-001 Status=PASS ...
[RESULT] PASS ExitCode=0
```

After the run, verify the test value is absent again:

```bat
reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v EDRTelemetryRunTest
```

Expected: value not found.

## Recovery cleanup

Only use this after a failed/interrupted test or before restoring a baseline:

```bat
RegistryLifecycleTest.exe cleanup > registry_cleanup_stdout.txt 2>&1
echo ExitCode=%ERRORLEVEL%
type registry_cleanup_stdout.txt
```

Do not include cleanup telemetry in the formal test result window.

## EDR export window

Use the UTC timestamps printed by stdout. Export a window beginning roughly 30 seconds before `[RUN-BEGIN]` and ending roughly 30 seconds after `[RUN-END]`.

Correlate using:

```text
Process = RegistryLifecycleTest.exe
PID     = [META] PID
RunID   = [META] RunID
Value   = EDRTelemetryRunTest
Path    = HKCU\Software\Microsoft\Windows\CurrentVersion\Run
```

Expected target operations:

```text
REG-CREATE-001  RegSetValue     -> notepad.exe
REG-MODIFY-001  RegSetValue     -> calc.exe
REG-DELETE-001  RegDeleteValue  -> value absent
```

## Acceptance checklist

- [ ] `Release | x64` build succeeds.
- [ ] `Environment.Is64BitProcess=True` in stdout.
- [ ] Before run, `EDRTelemetryRunTest` is absent.
- [ ] Create SETUP PASS and TARGET writes `notepad.exe` once.
- [ ] Modify SETUP sees `notepad.exe`, TARGET writes `calc.exe` once.
- [ ] Delete SETUP sees `calc.exe`, TARGET deletes the value once.
- [ ] All three phase endings report `Status=PASS`.
- [ ] Final output is `[RESULT] PASS ExitCode=0`.
- [ ] After run, `EDRTelemetryRunTest` is absent.
- [ ] EDR JSON is exported for the same PID/time window before judging telemetry support.

## Freeze note

Treat this package as a **frozen candidate** until both behavior and EDR telemetry have been independently verified. Once accepted, record the source ZIP SHA256 and the final Release EXE SHA256 and do not replace either file without incrementing the version.
