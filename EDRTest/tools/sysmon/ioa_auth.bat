@echo off
cd /d C:\EDRTest
echo ===== LIC MODULE ===== > ioa_auth.txt 2>&1
dir "C:\ProgramData\ZtsmEnt\Basic\IOALic2Module.dat" 2>&1 >> ioa_auth.txt
echo. >> ioa_auth.txt
echo ===== LOGIN POLICY ===== >> ioa_auth.txt 2>&1
dir "C:\ProgramData\ZtsmEnt\Basic\CacheLoginPolicy" /s /o-d 2>&1 >> ioa_auth.txt
echo. >> ioa_auth.txt
echo ===== IDENTITY POLICY ===== >> ioa_auth.txt 2>&1
dir "C:\ProgramData\ZtsmEnt\Basic\CacheIdentityPolicy" /s /o-d 2>&1 >> ioa_auth.txt
echo. >> ioa_auth.txt
echo ===== EdrQueryResult ===== >> ioa_auth.txt 2>&1
dir "C:\ZtsmEnt\EdrLocalData\EdrQueryResult" /s /o-d 2>&1 >> ioa_auth.txt
echo. >> ioa_auth.txt
echo ===== DONE ===== >> ioa_auth.txt 2>&1
exit /b 0
