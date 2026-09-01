# EDR Telemetry Validation

This project validates whether IOA cloud telemetry records expected Windows
behaviors. It reuses VMware delivery primitives from the previous AV project,
but uses a new telemetry-oriented execution and verdict pipeline.

## Frozen environment

- VMware Workstation 16 Pro 16.1.0
- vmrun 1.17.0
- VMX: `D:\Program Files (x86)\Windows 10 x64.vmx`
- Normal snapshot: `ioa`
- Driver snapshot: `Baseline_Driver`
- Guest: Windows 10 Pro 22H2 (19045.3803)
- VMware Tools: running
- Samples: .NET Framework 4.7.2, Release x64, elevated administrator

## Sample contract

Each module owns one executable and exposes one behavior per Action:

```text
RegistryLifecycleTest.exe create
RegistryLifecycleTest.exe modify
RegistryLifecycleTest.exe delete
RegistryLifecycleTest.exe cleanup
```

`SETUP` may create prerequisites. Only behavior between `TARGET-BEGIN` and
`TARGET-END` is evaluated. Every run emits a RunID, TestCaseID, PID, hostname,
UTC timestamps, target object, result, and exit code.

## Result states

- PASS
- FAIL_EVENT_MISSING
- FAIL_FIELD_MISSING
- AMBIGUOUS
- ERROR_SAMPLE
- ERROR_LOG_INPUT
- KNOWN_GAP

## First smoke test

Run in an elevated guest command prompt:

```bat
RegistryLifecycleTest.exe modify
```

Save stdout, export the matching IOA time range as CSV, then run:

```bat
python runner\telemetry_runner.py inspect-csv C:\EDRTest\CloudLogs\export.csv
```

