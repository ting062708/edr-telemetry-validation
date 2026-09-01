@echo off
cd /d E:\EDR\EDRTest\automation
for %%m in (Process Network Hash ScheduledTask Service) do (
  echo ===== MODULE %%m START %date% %time% =====
  python run_all.py deliver --module %%m
  echo ===== MODULE %%m END %date% %time% exit=%ERRORLEVEL% =====
)
echo ===== ALL DONE =====
