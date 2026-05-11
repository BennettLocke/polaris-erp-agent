@echo off
chcp 65001 >nul
setlocal
title 肆计包装-北极星订单管理机器人

set "APP_DIR=C:\Users\chuji\Downloads\sjagent\sjagent"
set "WEB_URL=http://127.0.0.1:8081/web"
set "LOG_FILE=%APP_DIR%\logs\webui_startup.log"

cd /d "%APP_DIR%"
if errorlevel 1 (
  echo 项目目录不存在：%APP_DIR%
  pause
  exit /b 1
)

if not exist "logs" mkdir "logs"

if exist ".venv\Scripts\python.exe" (
  set "PYTHON_CMD=.venv\Scripts\python.exe"
) else (
  set "PYTHON_CMD=python"
)

echo.
echo 正在启动：肆计包装-北极星订单管理机器人
echo 项目目录：%APP_DIR%
echo Python：%PYTHON_CMD%
echo WebUI：%WEB_URL%
echo 日志：%LOG_FILE%
echo.

%PYTHON_CMD% -c "import dotenv, yaml, flask" >nul 2>nul
if errorlevel 1 (
  echo 启动失败：当前 Python 缺少依赖。
  echo.
  echo 请先在 PowerShell 里运行：
  echo Set-Location -LiteralPath "%APP_DIR%"
  echo python -m pip install -r requirements.txt
  echo.
  echo 如果你之前装过依赖，说明依赖装在另一个 Python 环境里。
  echo 当前双击脚本找到的是：
  where python
  echo.
  pause
  exit /b 1
)

echo 正在打开浏览器，请稍等几秒...
start "" powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 4; Start-Process '%WEB_URL%'"

echo [%date% %time%] start webui > "%LOG_FILE%"
%PYTHON_CMD% main.py --mode http --http-port 8081 >> "%LOG_FILE%" 2>&1

echo.
echo 服务已停止或启动失败。
echo 下面是最近的启动日志：
echo.
type "%LOG_FILE%"
echo.
pause
