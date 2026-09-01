@echo off
cd /d C:\EDRTest
echo ===== EDR DIR CONTENT ===== > ioa_edr.txt 2>&1
dir "C:\ProgramData\ZtsmEnt\Basic\edr" /s /o-d 2>&1 >> ioa_edr.txt
echo ===== EdrLocalData ===== >> ioa_edr.txt 2>&1
dir "C:\ProgramData\ZtsmEnt\Basic\EdrLocalData" /s /o-d 2>&1 >> ioa_edr.txt
echo ===== EdrTasks ===== >> ioa_edr.txt 2>&1
dir "C:\ProgramData\ZtsmEnt\Basic\EdrTasks" /s /o-d 2>&1 >> ioa_edr.txt
echo ===== LOG DIR ===== >> ioa_edr.txt 2>&1
dir "C:\ProgramData\ZtsmEnt\Log" /s /o-d 2>&1 >> ioa_edr.txt
echo ===== DONE ===== >> ioa_edr.txt 2>&1
exit /b 0
