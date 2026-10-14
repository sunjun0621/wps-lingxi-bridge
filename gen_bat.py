# -*- coding: utf-8 -*-
import os
ROOT = os.path.dirname(os.path.abspath(__file__))
bat = r'''@echo off
chcp 936 >nul
title 灵犀 Bridge（WPS 灵犀模型反代）
cd /d "%~dp0"
echo ============================================================
echo            灵犀 Bridge  -  WPS 灵犀模型反代
echo ============================================================
echo.
echo   本地服务 : http://127.0.0.1:8799
echo   访问令牌 : lingxi-bridge
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
'''
p = os.path.join(ROOT, "启动灵犀Bridge.bat")
with open(p, "w", encoding="gbk", newline="\r\n") as f:
    f.write(bat)
print("written:", p)
