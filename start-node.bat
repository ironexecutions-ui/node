@echo off
set PATH=%PATH%;C:\Users\elder\AppData\Local\Programs\Python\Launcher
cd /d C:\DocumentosIronExecutions\IronExecutions\node
py -m uvicorn main:app --host 0.0.0.0 --port 8888
pause
