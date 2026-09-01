# NetworkActivityTest

Build the `NetworkActivityTest/NetworkActivityTest.csproj` project with Visual Studio targeting .NET Framework 4.7.2.

Examples:

```bat
NetworkActivityTest.exe --case NET-TCP-001
NetworkActivityTest.exe --case NET-UDP-001
NetworkActivityTest.exe --case NET-URL-001
NetworkActivityTest.exe --case NET-DNS-001
NetworkActivityTest.exe --case NET-DOWNLOAD-001
```

The source package intentionally contains no `.vs`, `bin`, or `obj` directories so an older executable cannot be mistaken for the frozen-protocol build.
