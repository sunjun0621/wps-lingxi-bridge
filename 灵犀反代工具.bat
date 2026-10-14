@echo off
chcp 936 >nul
title 灵犀 Bridge 工具
cd /d "%~dp0"

where python >nul 2>nul
if errorlevel 1 (
  echo [错误] 未找到 python 命令：请先安装 Python 3.11+ 并勾选 "Add python.exe to PATH"。
  pause
  exit /b 1
)

:menu
cls
echo ==================================
echo     灵犀 Bridge 工具
echo ==================================
echo   1. 打开控制台
echo   2. 状态速查（网关 / 灵犀 / 登录）
echo   3. 依赖体检
echo   4. 启动网关（前台运行）
echo   5. 退出
echo ==================================
set /p choice=请输入序号：
if "%choice%"=="1" goto console
if "%choice%"=="2" goto status
if "%choice%"=="3" goto deps
if "%choice%"=="4" goto serve
if "%choice%"=="5" exit
goto menu

:console
start "" http://127.0.0.1:8799/?token=lingxi-bridge
echo 已用浏览器打开控制台（若改过端口/令牌，以启动窗口打印的地址为准）。
timeout /t 2 >nul
goto menu

:status
echo.
python check_deps.py --status
echo.
pause
goto menu

:deps
echo.
python check_deps.py
echo.
pause
goto menu

:serve
echo.
python bridge_gateway.py
echo.
pause
goto menu
