@echo off
REM EDR 采集验证台 · 一键启动
REM 系统 Python 无 Flask，固定用 Anaconda 的解释器。
cd /d "%~dp0"
echo Starting EDR console at http://127.0.0.1:8000 ...
start "" http://127.0.0.1:8000
"D:\Anaconda3\python.exe" server.py
pause
