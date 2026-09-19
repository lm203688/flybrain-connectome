@echo off
REM Boot-time auto-start launcher for the flybrain-connectome HTTP API.
REM Registered via:  schtasks /create /tn FlyBrainConnectomeAPI /tr "<this bat>" /sc onstart /f
set FLYBRAIN_DATA_DIR=C:\Users\xing\Desktop\flybrain-connectome\male_cns
cd /d C:\Users\xing\Desktop\flybrain-connectome\flybrain-connectome-mcp
"C:\Users\xing\.workbuddy\binaries\python\envs\minimind\Scripts\pythonw.exe" run_api.py
