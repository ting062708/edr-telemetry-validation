@echo off
cd /d C:\EDRTest
echo ===== ZTSM PROGRAMDATA ===== > ioa_probe.txt 2>&1
dir "C:\ProgramData\ZtsmEnt" /b >> ioa_probe.txt 2>&1
echo ===== ZTSM EDR DIR ===== >> ioa_probe.txt 2>&1
dir "C:\ProgramData\ZtsmEnt\Edr" /b >> ioa_probe.txt 2>&1
echo ===== ZTSM BASIC DIR ===== >> ioa_probe.txt 2>&1
dir "C:\ProgramData\ZtsmEnt\Basic" /b >> ioa_probe.txt 2>&1
echo ===== EDR LOG FILES (recent) ===== >> ioa_probe.txt 2>&1
dir "C:\ProgramData\ZtsmEnt\Edr" /s /o-d /b 2>&1 | findstr /i ".log .db .dat" >> ioa_probe.txt 2>&1
echo ===== SERVICES ===== >> ioa_probe.txt 2>&1
sc query state= all 2>&1 | findstr /i "ztsm qm ioa tencent" >> ioa_probe.txt 2>&1
echo ===== DONE ===== >> ioa_probe.txt 2>&1
exit /b 0
