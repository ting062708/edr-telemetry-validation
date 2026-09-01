@echo off
cd /d C:\EDRTest
echo ===== LOGIN STATE ===== > login_check.txt
dir "C:\ProgramData\ZtsmEnt\Basic\CacheLoginPolicy" >> login_check.txt 2>&1
dir "C:\ProgramData\ZtsmEnt\Basic\CacheIdentityPolicy" >> login_check.txt 2>&1
dir "C:\ProgramData\ZtsmEnt\Basic\IOALic2Module.dat" >> login_check.txt 2>&1
echo ===== DONE ===== >> login_check.txt
exit /b 0
