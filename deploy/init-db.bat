@echo off
chcp 65001 >nul
title Sentiment-Init-DB
cd /d "%~dp0..\backend"

set "PY=E:\study_project\conda_envs\product-sentiment-plus\python.exe"
if not exist "%PY%" (
  call conda activate product-sentiment-plus
  set "PY=python"
)

if not exist ".env" (
  echo [错误] 请先复制 backend\.env.example 为 backend\.env 并改好数据库密码
  pause
  exit /b 1
)

if not exist "sql\jeecgboot-slim.sql" (
  echo [错误] 缺少 sql\jeecgboot-slim.sql
  pause
  exit /b 1
)

echo ========================================
echo  即将用 jeecgboot-slim.sql 初始化数据库
echo  注意：会重建业务相关表数据（约 30MB SQL）
echo  请确认 MySQL 已启动，且 .env 密码正确
echo ========================================
pause

echo 开始导入，请耐心等待（可能几分钟）...
"%PY%" -m scripts.init_slim_db
if errorlevel 1 (
  echo [失败] 初始化未通过，请检查 MySQL 密码与 max_allowed_packet
  pause
  exit /b 1
)

echo.
echo [成功] 可用账号 admin / 123456 登录
pause
