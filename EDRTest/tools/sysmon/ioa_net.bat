@echo off
cd /d C:\EDRTest
echo ===== config.json ===== > ioa_net.txt 2>&1
type "C:\ProgramData\ZtsmEnt\Basic\EdrLocalData\config.json" >> ioa_net.txt 2>&1
echo. >> ioa_net.txt
echo ===== policy files ===== >> ioa_net.txt 2>&1
for %%f in ("C:\ProgramData\ZtsmEnt\Basic\EdrTasks\*.txt") do (
  echo --- %%f --- >> ioa_net.txt 2>&1
  type "%%f" >> ioa_net.txt 2>&1
  echo. >> ioa_net.txt
)
echo ===== IsolateBlockTasks ===== >> ioa_net.txt 2>&1
type "C:\ProgramData\ZtsmEnt\Basic\EdrTasks\IsolateBlockTasks.dat" >> ioa_net.txt 2>&1
echo. >> ioa_net.txt
echo ===== PING TEST ===== >> ioa_net.txt 2>&1
ping -n 1 223.5.5.5 >> ioa_net.txt 2>&1
ping -n 1 www.qq.com >> ioa_net.txt 2>&1
echo ===== DONE ===== >> ioa_net.txt 2>&1
exit /b 0
