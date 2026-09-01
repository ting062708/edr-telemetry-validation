@echo off
cd /d C:\EDRTest
echo === UNINSTALL === > reinstall_fdd_out.txt 2>&1
Sysmon64.exe -u >> reinstall_fdd_out.txt 2>&1
echo UNINSTALL_EXIT=%errorlevel% >> reinstall_fdd_out.txt
echo === INSTALL === >> reinstall_fdd_out.txt
Sysmon64.exe -i C:\EDRTest\sysmonconfig.xml -accepteula >> reinstall_fdd_out.txt 2>&1
echo INSTALL_EXIT=%errorlevel% >> reinstall_fdd_out.txt
echo === VERIFY === >> reinstall_fdd_out.txt
Sysmon64.exe -c > cfg_dump3.txt 2>&1
findstr /I "FileDeleteDetected" cfg_dump3.txt >> reinstall_fdd_out.txt
echo VERIFY_EXIT=%errorlevel% >> reinstall_fdd_out.txt
exit /b 0
