@echo off
cd /d C:\EDRTest\samples\File
FileLifecycleTest.exe --case FILE-DELETE-001 > C:\EDRTest\fdel_manual_stdout.txt 2>&1
wevtutil epl Microsoft-Windows-Sysmon/Operational C:\EDRTest\fdel_evtx.evtx
exit /b 0
