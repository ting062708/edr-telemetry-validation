@echo off
cd /d C:\EDRTest
Sysmon64.exe -s > schema_dump.txt 2>&1
findstr /I "FileDelete Delete" schema_dump.txt > schema_delete.txt 2>&1
exit /b 0
