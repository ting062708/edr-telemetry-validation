@echo off
cd /d C:\EDRTest
echo ===== FILE-DELETE RULE CHECK ===== > cfg_check.txt 2>&1
Sysmon64.exe -c > cfg_dump.txt 2>&1
findstr /C:"FileDelete" cfg_dump.txt >> cfg_check.txt 2>&1
findstr /C:"EDRTelemetrySample" cfg_dump.txt >> cfg_check.txt 2>&1
echo ===== C:\EDRTest RULES ===== >> cfg_check.txt 2>&1
findstr /C:"C:\EDRTest" cfg_dump.txt >> cfg_check.txt 2>&1
echo ===== DONE ===== >> cfg_check.txt
exit /b 0
