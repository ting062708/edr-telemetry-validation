@echo off
cd /d C:\EDRTest
echo ===== ZtsmEnt EDRLocalData ===== > ioa_db.txt 2>&1
dir "C:\ZtsmEnt\EdrLocalData" /o-d 2>&1 >> ioa_db.txt
echo. >> ioa_db.txt
echo ===== ZtsmEnt ROOT ===== >> ioa_db.txt 2>&1
dir "C:\ZtsmEnt" /b 2>&1 >> ioa_db.txt
echo ===== DONE ===== >> ioa_db.txt 2>&1
exit /b 0
