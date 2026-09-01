# Sample inventory and migration order

## Existing source projects received

| Module | Current executable | Current form | Planned actions | Snapshot |
| --- | --- | --- | --- | --- |
| Registry | RegistryLifecycleTest.exe | Lifecycle | create, modify, delete, cleanup | ioa |
| Process | ProcessLifecycleTest.exe | Lifecycle | create, access, tamper, remotethread, terminate, cleanup | ioa |
| File | FileLifecycleTest.exe | Lifecycle | create, open, modify, rename, delete, cleanup | ioa |
| Account | AccountLifecycleTest.exe | Lifecycle | create, modify, delete, login, logoff, cleanup | ioa |
| Scheduled Task | ScheduledTaskLifecycleTest.exe | Lifecycle | create, modify, delete, cleanup | ioa |
| Service | ServiceLifecycleTest.exe | Lifecycle | create, modify, delete, cleanup | ioa |
| Driver | DriverLifecycleTest.exe | Lifecycle | load, modify, unload, cleanup | Baseline_Driver |
| Named Pipe | PipeLifecycleTest.exe | mixed phases | create, connect, readwrite, cleanup | ioa |
| Virtual Disk | VirtualDiskMountTest.exe | setup + target | mount, unmount, cleanup | ioa |
| Group Policy | GroupPolicyModificationTest.exe | setup + target | modify, cleanup | ioa |
| Image Load | ImageLoadTest.exe | single behavior | load | ioa |
| Hash | HashBaselineTool.exe | argument driven tool | md5, sha256, imphash | ioa |
| DNS | DnsTest.exe | single behavior | resolve | ioa |
| TCP | TcpTest.exe | single behavior | connect | ioa |
| UDP | UdpTest.exe | single behavior | connect | ioa |
| URL | UrlTest.exe | single behavior | request | ioa |
| Download | DownloadTest.exe | single behavior | download | ioa |

## Support projects and files

- ProcessTarget.exe
- TestLibrary.dll
- nonpnp.sys
- Network endpoints or URLs configured by the network samples

## New module projects

| Module executable | Actions |
| --- | --- |
| EDRAgentTest.exe | start, stop, install, uninstall, keepalive, error |
| WmiTest.exe | filter, consumer, bind, cleanup |
| BitsTest.exe | create, transfer, cancel, cleanup |
| PowerShellTest.exe | block |
| UsbTest.exe | pending exact capability definition |

## Migration gate

An Action is ready only when all of the following are true:

1. It accepts a non-interactive command-line Action.
2. SETUP creates only prerequisites.
3. TARGET contains one telemetry behavior.
4. UTC target timestamps and PID are emitted.
5. It exits with 0 for success, 1 for execution failure, and 2 for invalid usage.
6. Cleanup is idempotent or the assigned snapshot provides deterministic reset.
7. Release x64 builds on .NET Framework 4.7.2.
