@echo off
REM 启动果蝇连接组 HTTP API 服务（apikey 鉴权，供其他项目调用）
REM 数据在基地文件夹 C:\Users\xing\Desktop\flybrain-connectome\male_cns
REM 也可用 run_api.py（默认自动指向 ..\male_cns，并把日志写进 api_runtime.log）
set PY=C:\Users\xing\.workbuddy\binaries\python\envs\minimind\Scripts\python.exe
set FLYBRAIN_DATA_DIR=C:\Users\xing\Desktop\flybrain-connectome\male_cns
"%PY%" "%~dp0mcp_connectome\api_server.py"
