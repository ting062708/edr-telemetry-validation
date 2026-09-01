# NetworkActivityTest - Frozen Protocol

This project follows the current frozen stdout protocol used by the telemetry runner/parser.

## Invocation

```bat
NetworkActivityTest.exe --case <TestCaseID>
```

Supported cases:

| TestCaseID | Module | Action | Target behavior |
|---|---|---|---|
| `NET-TCP-001` | Network | TCPConnection | Establish a TCP connection using `System.Net.Sockets.Socket` |
| `NET-UDP-001` | Network | UDPConnection | Send and receive a UDP datagram using `Socket` |
| `NET-URL-001` | Network | URL | Perform an HTTPS GET using WinINet |
| `NET-DNS-001` | Network | DNSQuery | Query an A record using `DnsQuery_W` with cache bypass |
| `NET-DOWNLOAD-001` | Network | FileDownloaded | Download a file using WinHTTP and write it to disk |

## Stdout contract

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

No new sample should emit legacy `[PHASE-*]`, `[TELEMETRY]`, or old free-form test headers.

## SETUP / TARGET boundary

- TCP, UDP, URL and DNS require no mutating setup and emit `[SETUP] Required=None`.
- Download setup creates `C:\Temp\EDRTest` if needed and removes a previous deterministic target file.
- All behavior intended for EDR correlation occurs strictly after `[TARGET-BEGIN]` and before `[TARGET-END]`.
- Download output is intentionally not deleted after the target window; the next run removes it during SETUP. This avoids generating an extra deletion inside the current target window.

## Exit codes

- `0`: PASS
- `1`: target operation failed
- `2`: invalid/missing CaseID
- `3`: precondition not satisfied

## Original implementation preserved

The uploaded legacy samples used five separate executables. Their underlying mechanisms are preserved here:

- TCP: `Socket`
- UDP: `Socket`
- URL: WinINet (`InternetOpenUrl`)
- DNS: `DnsQuery_W`
- File Downloaded: WinHTTP (`WinHttp*`)

Only orchestration, protocol output, and case selection were consolidated into one executable.
