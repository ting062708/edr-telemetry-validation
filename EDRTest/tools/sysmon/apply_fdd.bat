@echo off
cd /d C:\EDRTest
Sysmon64.exe -c C:\EDRTest\sysmonconfig.xml > apply_fdd_out.txt 2>&1
echo APPLY_EXIT=%errorlevel% >> apply_fdd_out.txt
Sysmon64.exe -c > cfg_dump2.txt 2>&1
findstr /I "FileDeleteDetected" cfg_dump2.txt >> apply_fdd_out.txt
echo FIND_EXIT=%errorlevel% >> apply_fdd_out.txt
exit /b 0
