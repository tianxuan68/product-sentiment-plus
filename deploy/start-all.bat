@echo off
chcp 65001 >nul
title Sentiment-Start-All
cd /d "%~dp0"

echo ========================================
echo   一键启动（会打开 3 个黑窗口，勿关）
echo   1) AI      :8001
echo   2) Backend :8005
echo   3) Front   :3100
echo ========================================
echo.

start "Sentiment-AI" "%~dp0start-ai.bat"
timeout /t 3 /nobreak >nul
start "Sentiment-Backend" "%~dp0start-backend.bat"
timeout /t 3 /nobreak >nul
start "Sentiment-Front" "%~dp0start-front.bat"

echo.
echo 已启动。约 30~60 秒后浏览器打开：
echo   http://127.0.0.1:3100
echo 账号：admin   密码：123456
echo.
echo 若「评价分析」报 AI 错误，等 AI 窗口出现
echo   Application startup complete  后再试。
echo.
pause
