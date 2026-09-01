@echo off
cd /d C:\EDRTest
echo === UNINSTALL === > sysmon_reinstall.txt 2>&1
Sysmon64.exe -u >> sysmon_reinstall.txt 2>&1
echo UNINSTALL_EXIT=%errorlevel% >> sysmon_reinstall.txt
echo === INSTALL === >> sysmon_reinstall.txt
Sysmon64.exe -i C:\EDRTest\sysmonconfig.xml -accepteula >> sysmon_reinstall.txt 2>&1
echo INSTALL_EXIT=%errorlevel% >> sysmon_reinstall.txt
echo === VERIFY === >> sysmon_reinstall.txt
Sysmon64.exe -c > cfg_dump.txt 2>&1
findstr /I "FileDelete" cfg_dump.txt >> sysmon_reinstall.txt
echo VERIFY_EXIT=%errorlevel% >> sysmon_reinstall.txt
exit /b 0
