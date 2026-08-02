@echo off
chcp 65001 >nul
title Sentiment-Backend :8005
cd /d "%~dp0..\backend"

set "PY=E:\study_project\conda_envs\product-sentiment-plus\python.exe"
if not exist "%PY%" (
  where conda >nul 2>nul
  if errorlevel 1 (
    echo [错误] 找不到 Python 环境：%PY%
    echo 请先按 DEPLOY.md 安装 conda 环境 product-sentiment-plus
    pause
    exit /b 1
  )
  call conda activate product-sentiment-plus
  set "PY=python"
)

if not exist ".env" (
  echo [错误] 缺少 backend\.env，请先按 DEPLOY.md 配置数据库密码
  pause
  exit /b 1
)

echo [Backend] 启动中 http://127.0.0.1:8005
"%PY%" run.py
pause
