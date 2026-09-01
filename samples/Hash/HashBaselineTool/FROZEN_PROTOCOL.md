# HashBaselineTool — frozen protocol mapping

This sample follows the frozen stdout contract parsed by `stdout_parser.py`:

- `[RUN-BEGIN] RunID=<id> TimeUTC=<iso>`
- `[META] TestCaseID=<id> Module=<name> Action=<action>`
- `[META] Process=<exe> PID=<pid> Hostname=<host>`
- `[SETUP-BEGIN]` / `[SETUP]` / `[SETUP-END]`
- `[TARGET-BEGIN]` / `[TARGET]` / `[TARGET-END]`
- `[RESULT] PASS|FAIL ExitCode=<n>`
- `[RUN-END] RunID=<id> TimeUTC=<iso>`

## Frozen cases

| TestCaseID | Action | TARGET behavior |
|---|---|---|
| `HASH-MD5-001` | `MD5` | Read target and calculate MD5 |
| `HASH-SHA-001` | `SHA` | Read target and calculate SHA1 + SHA256 |
| `HASH-IMPHASH-001` | `IMPHASH` | Parse PE import table and calculate import hash |

Default target: `..\Support\TestLibrary.dll` relative to the executable directory.

Examples:

```bat
HashBaselineTool.exe --case HASH-MD5-001
HashBaselineTool.exe --case HASH-SHA-001
HashBaselineTool.exe --case HASH-IMPHASH-001
HashBaselineTool.exe --case HASH-MD5-001 --target C:\Temp\EDRTest\Support\TestLibrary.dll
```

Exit codes:

- `0`: PASS
- `1`: target operation failed
- `2`: invalid arguments / unsupported CaseID
- `3`: setup prerequisite not satisfied

Legacy `[PHASE-*]`, `[TELEMETRY]`, `[TIME]`, and free-form result output are not emitted by this sample.
