# RegistryLifecycleTest - Telemetry Action Version

Target: `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\EDRTelemetryRunTest`

Actions:
- `create`: SETUP removes stale test value; TARGET creates `EDRTelemetryRunTest = C:\Windows\System32\notepad.exe`.
- `modify`: SETUP writes notepad; TARGET changes it to `C:\Windows\System32\calc.exe`.
- `delete`: SETUP writes calc; TARGET deletes the value.
- `cleanup`: removes only the `EDRTelemetryRunTest` value. It never deletes the Windows `Run` key.

Build: Release | x64 | .NET Framework 4.7.2

Primary validation command:
`RegistryLifecycleTest.exe modify > registry_modify_stdout.txt 2>&1`
