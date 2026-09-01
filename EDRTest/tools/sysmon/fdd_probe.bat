@echo off
cd /d C:\EDRTest
echo EDR_DELETE_TEST > C:\EDRTest\delete_probe.txt
del C:\EDRTest\delete_probe.txt
wevtutil epl Microsoft-Windows-Sysmon/Operational C:\EDRTest\fdd_probe.evtx
exit /b 0
