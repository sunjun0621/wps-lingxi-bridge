@echo off
chcp 936 >nul
setlocal enabledelayedexpansion
title WPS 灵犀 模型反代工具
set "PY=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
if not exist "%PY%" set "PY=python"
cd /d "%~dp0"
:menu
cls
echo ==================================
echo     WPS 灵犀 模型反代工具
echo ==================================
echo   1. 刷新 / 提取灵犀登录 Cookie
echo   2. 启动反代网关（端口 8788）
echo   3. 退出
echo ==================================
set /p choice=请输入序号：
if "%choice%"=="1" goto refresh
if "%choice%"=="2" goto serve
if "%choice%"=="3" exit
goto menu
:refresh
echo.
echo 正在从灵犀本地数据提取 Cookie（请先在灵犀客户端登录过）...
"%PY%" "08_cookies.py"
echo.
echo 完成，Cookie 已保存到 cookies_decrypted.json
pause
goto menu
:serve
echo.
echo 正在启动网关，使用期间请勿关闭本窗口...
echo 接口地址：http://127.0.0.1:8788/v1
echo.
"%PY%" -m uvicorn main:app --host 127.0.0.1 --port 8788 --app-dir "%~dp0gateway"
pause
goto menu