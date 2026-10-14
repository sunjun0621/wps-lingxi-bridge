@echo off
chcp 936 >nul
title 灵犀 Bridge（WPS 灵犀模型反代）
cd /d "%~dp0"
where python >nul 2>nul
if errorlevel 1 (
  echo ============================================================
  echo [错误] 未找到 python 命令：请先安装 Python 3.11+ 并在安装时勾选
  echo        "Add python.exe to PATH"，然后重新双击本文件。
  echo        若已安装但仍报错，可在本窗口手动执行：python bridge_gateway.py
  echo        （缺依赖包不用怕：启动窗口会给出中文安装命令）
  echo ============================================================
  pause
  exit /b 1
)
echo ============================================================
echo            灵犀 Bridge  -  WPS 灵犀模型反代
echo ============================================================
echo.
echo   本地服务 : http://127.0.0.1:8799
echo   访问令牌 : lingxi-bridge
echo   （改过 bridge-runtime\gateway.json 时，以启动窗口打印的地址/令牌为准）
echo.
echo   控制台将在约 4 秒后自动打开，请稍候……
echo.
echo   关闭本窗口即停止服务。
echo.
rem 延迟 4 秒后用默认浏览器打开可视化控制台（最小化窗口执行，不打扰）
start "openconsole" /min cmd /c "ping 127.0.0.1 -n 5 >nul & start """" http://127.0.0.1:8799/?token=lingxi-bridge"
rem 前台运行网关（关闭窗口即停止）
python bridge_gateway.py
echo.
echo 服务已退出。
pause
