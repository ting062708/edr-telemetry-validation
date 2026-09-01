@echo off
cd /d C:\EDRTest
copy /y C:\EDRTest\samples\File\FileLifecycleTest.exe C:\EDRTest\test_delete_exe.exe > nul
del C:\EDRTest\test_delete_exe.exe
echo test_txt > C:\EDRTest\test_delete_txt.txt
del C:\EDRTest\test_delete_txt.txt
wevtutil epl Microsoft-Windows-Sysmon/Operational C:\EDRTest\exe_del_evtx.evtx
exit /b 0
