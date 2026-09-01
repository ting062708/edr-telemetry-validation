@echo off
cd /d C:\EDRTest
echo ===== APPLY ===== > apply_cfg_out.txt 2>&1
Sysmon64.exe -c C:\EDRTest\sysmonconfig.xml >> apply_cfg_out.txt 2>&1
echo EXIT=%errorlevel% >> apply_cfg_out.txt
echo ===== VERIFY FILEDELETE ===== >> apply_cfg_out.txt 2>&1
Sysmon64.exe -c > cfg_dump2.txt 2>&1
findstr /C:"FileDelete" cfg_dump2.txt >> apply_cfg_out.txt 2>&1
findstr /C:"EDRTelemetrySample" cfg_dump2.txt >> apply_cfg_out.txt 2>&1
echo ===== DONE ===== >> apply_cfg_out.txt
exit /b 0
