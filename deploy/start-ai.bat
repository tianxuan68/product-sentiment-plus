@echo off
chcp 65001 >nul
title Sentiment-AI :8001
cd /d "%~dp0..\product-sentiment-ai"

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

echo [AI] 启动中 http://127.0.0.1:8001
echo 首次加载模型可能要 1~3 分钟，请勿关闭本窗口
"%PY%" -m uvicorn api.main:app --host 127.0.0.1 --port 8001
pause
