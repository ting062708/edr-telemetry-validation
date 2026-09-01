@echo off
cd /d C:\EDRTest
Sysmon64.exe -c > cfg_dump3.txt 2>&1
exit /b 0
