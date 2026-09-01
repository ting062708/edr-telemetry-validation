# ServiceLifecycleTest — Frozen Protocol

Supported cases:

- `SVC-CREATE-001` — Service Creation
- `SVC-MODIFY-001` — Service Modification
- `SVC-DELETE-001` — Service Deletion

Invocation:

```bat
ServiceLifecycleTest.exe --case SVC-CREATE-001
ServiceLifecycleTest.exe --case SVC-MODIFY-001
ServiceLifecycleTest.exe --case SVC-DELETE-001
```

Each invocation emits the frozen CURRENT stdout protocol:

```text
[RUN-BEGIN] RunID=<id> TimeUTC=<iso>
[META] TestCaseID=<id> Module=Service Action=<action>
[META] Process=ServiceLifecycleTest.exe PID=<pid> Hostname=<host>
[SETUP-BEGIN] TimeUTC=<iso>
[SETUP] Key=Value
[SETUP-END] TimeUTC=<iso>
[TARGET-BEGIN] TimeUTC=<iso>
[TARGET] Key=Value
[TARGET-END] TimeUTC=<iso>
[RESULT] PASS|FAIL ExitCode=<n>
[RUN-END] RunID=<id> TimeUTC=<iso>
```

Target boundaries:

- CREATE: `CreateService` is the target operation.
- MODIFY: baseline service creation occurs in SETUP; `ChangeServiceConfig` is the target operation.
- DELETE: baseline service creation occurs in SETUP; `DeleteService` is the target operation.
- Any restoration/cleanup after a successful target is performed after `TARGET-END` so it is outside the primary correlation window.

Exit codes:

- `0` PASS
- `1` target/runtime failure
- `2` invalid arguments / CaseID
- `3` setup/precondition failure (including missing administrator privileges)
