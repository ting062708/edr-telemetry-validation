# FileLifecycleTest — Frozen stdout protocol

This sample follows the CURRENT protocol consumed by `stdout_parser.py`:

```text
[RUN-BEGIN] RunID=<id> TimeUTC=<iso>
[META] TestCaseID=<id> Module=<name> Action=<action>
[META] Process=<exe> PID=<pid> Hostname=<host>
[SETUP-BEGIN] TimeUTC=<iso>
[SETUP] Key=Value
[SETUP-END] TimeUTC=<iso>
[TARGET-BEGIN] TimeUTC=<iso>
[TARGET] Key=Value
[TARGET-END] TimeUTC=<iso>
[RESULT] PASS|FAIL ExitCode=<n>
[RUN-END] RunID=<id> TimeUTC=<iso>
```

## Cases

| TestCaseID | SETUP | TARGET |
|---|---|---|
| FILE-CREATE-001 | Remove stale target files | Create `FileLifecycle_Target.txt` |
| FILE-OPEN-001 | Create baseline target file | Open/read existing target file |
| FILE-DELETE-001 | Create baseline target file | Delete existing target file |
| FILE-MODIFY-001 | Create baseline target file | Append to existing target file |
| FILE-RENAME-001 | Create source and ensure destination is absent | Rename source to destination |

The sample intentionally performs prerequisites inside the SETUP window. Telemetry correlation for the behavior under test must use `TARGET-BEGIN` through `TARGET-END`.

## Invocation

```bat
FileLifecycleTest.exe --case FILE-CREATE-001
FileLifecycleTest.exe --case FILE-OPEN-001
FileLifecycleTest.exe --case FILE-DELETE-001
FileLifecycleTest.exe --case FILE-MODIFY-001
FileLifecycleTest.exe --case FILE-RENAME-001
```

Exit codes:
- `0`: target completed successfully
- `1`: setup or target execution failed
- `2`: missing or unsupported TestCaseID
