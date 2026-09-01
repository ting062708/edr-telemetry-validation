# AccountLifecycleTest — Frozen stdout protocol

This sample follows the automation CURRENT frozen protocol:

- `[RUN-BEGIN] RunID=<id> TimeUTC=<iso>`
- `[META] TestCaseID=<id> Module=<name> Action=<action>`
- `[META] Process=<exe> PID=<pid> Hostname=<host>`
- `[SETUP-BEGIN] TimeUTC=<iso>`
- `[SETUP] Key=Value`
- `[SETUP-END] TimeUTC=<iso>`
- `[TARGET-BEGIN] TimeUTC=<iso>`
- `[TARGET] Key=Value`
- `[TARGET-END] TimeUTC=<iso>`
- `[RESULT] PASS|FAIL ExitCode=<n>`
- `[RUN-END] RunID=<id> TimeUTC=<iso>`

## Cases

| TestCaseID | Target behavior | Setup |
|---|---|---|
| `ACCOUNT-CREATE-001` | Create local account | Ensure test account is absent |
| `ACCOUNT-MODIFY-001` | Modify local account comment | Create fresh test account |
| `ACCOUNT-DELETE-001` | Delete local account | Create fresh test account |
| `ACCOUNT-LOGIN-001` | Interactive `LogonUser` | Create fresh test account |
| `ACCOUNT-LOGOFF-001` | Release final logon token | Create account and log on before TARGET |

All prerequisite behavior is outside the TARGET window. Matching should use `TARGET-BEGIN` through `TARGET-END`.

## Invocation

```bat
AccountLifecycleTest.exe --case ACCOUNT-CREATE-001
AccountLifecycleTest.exe --case ACCOUNT-MODIFY-001
AccountLifecycleTest.exe --case ACCOUNT-DELETE-001
AccountLifecycleTest.exe --case ACCOUNT-LOGIN-001
AccountLifecycleTest.exe --case ACCOUNT-LOGOFF-001
```

Administrator privileges are required.
