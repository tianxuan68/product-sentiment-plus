@echo off
chcp 65001 >nul
title Sentiment-Front :3100
cd /d "%~dp0..\front"

where pnpm >nul 2>nul
if errorlevel 1 (
  echo [错误] 未安装 pnpm。请先执行: npm install -g pnpm
  pause
  exit /b 1
)

if not exist "node_modules" (
  echo [Front] 首次安装依赖，请稍候...
  call pnpm install
  if errorlevel 1 (
    echo [错误] pnpm install 失败
    pause
    exit /b 1
  )
)

echo [Front] 启动中 http://127.0.0.1:3100
call pnpm dev
pause
