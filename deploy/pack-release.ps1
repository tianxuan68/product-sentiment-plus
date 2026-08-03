# 本机一键打 3 个部署包（PowerShell）
# 用法（在项目根目录）:
#   powershell -ExecutionPolicy Bypass -File deploy\pack-release.ps1
#   powershell -ExecutionPolicy Bypass -File deploy\pack-release.ps1 -SkipFrontBuild
#
# 产出目录: packages/
#   front-dist.zip   → 解压到服务器 /var/www/sentiment
#   backend.zip      → 解压到服务器 /opt/product-sentiment-plus/backend
#   ai.zip           → 解压到服务器 /opt/product-sentiment-plus/product-sentiment-ai
#   jeecgboot-slim.sql（顺带复制，导库用）
#   requirements.txt（顺带复制）

param(
    [switch]$SkipFrontBuild,
    [switch]$SkipAi
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path (Join-Path $Root "requirements.txt"))) {
    $Root = (Get-Location).Path
}
$Out = Join-Path $Root "packages"
$Stage = Join-Path $Out "_stage"

Write-Host "==> root: $Root"
Write-Host "==> out : $Out"

# 清理旧包
if (Test-Path $Out) {
    Remove-Item $Out -Recurse -Force
}
New-Item -ItemType Directory -Path $Stage | Out-Null

function Assert-Exists([string]$Path, [string]$Hint) {
    if (-not (Test-Path $Path)) {
        throw "缺少: $Path`n$Hint"
    }
}

# ---------- 1) 前端 dist ----------
$FrontDir = Join-Path $Root "front"
$DistDir = Join-Path $FrontDir "dist"
if (-not $SkipFrontBuild) {
    Write-Host "==> pnpm build front..."
    Push-Location $FrontDir
    try {
        if (-not (Test-Path "node_modules")) {
            pnpm install
        }
        pnpm build
        if ($LASTEXITCODE -ne 0) { throw "pnpm build 失败" }
    }
    finally {
        Pop-Location
    }
}
Assert-Exists (Join-Path $DistDir "index.html") "请先在 front 目录执行 pnpm build，或去掉 -SkipFrontBuild"

$FrontStage = Join-Path $Stage "front-dist"
New-Item -ItemType Directory -Path $FrontStage | Out-Null
robocopy $DistDir $FrontStage /E /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null
$FrontZip = Join-Path $Out "front-dist.zip"
Compress-Archive -Path (Join-Path $FrontStage "*") -DestinationPath $FrontZip -Force
Write-Host "OK  front-dist.zip"

# ---------- 2) 后端 backend.zip ----------
$BackendSrc = Join-Path $Root "backend"
$BackendStage = Join-Path $Stage "backend"
New-Item -ItemType Directory -Path $BackendStage | Out-Null
robocopy $BackendSrc $BackendStage /E `
    /XD __pycache__ .venv uploads .pytest_cache `
    /XF *.pyc .env .env.local `
    /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null

# 服务器环境模板（勿带本机密码）
Copy-Item (Join-Path $BackendSrc ".env.example") (Join-Path $BackendStage ".env.example") -Force
$BackendZip = Join-Path $Out "backend.zip"
Compress-Archive -Path (Join-Path $BackendStage "*") -DestinationPath $BackendZip -Force
Write-Host "OK  backend.zip"

# ---------- 3) AI ai.zip（代码 + 推理权重；日常前后端更新可 -SkipAi）----------
if ($SkipAi) {
    Write-Host "SKIP ai.zip (-SkipAi)"
} else {
    $AiSrc = Join-Path $Root "product-sentiment-ai"
    Assert-Exists (Join-Path $AiSrc "models\tagging\model\bert_hierarchical\hier_config.json") `
        "缺少打标模型权重，无法打包 AI"
    Assert-Exists (Join-Path $AiSrc "models\bert\common\model\bert_all\config.json") `
        "缺少情感模型权重，无法打包 AI"

    $AiStage = Join-Path $Stage "ai"
    New-Item -ItemType Directory -Path $AiStage | Out-Null
    robocopy $AiSrc $AiStage /E `
        /XD __pycache__ .venv .git `
        /XF *.pyc `
        /NFL /NDL /NJH /NJS /nc /ns /np | Out-Null

    $AiZip = Join-Path $Out "ai.zip"
    Compress-Archive -Path (Join-Path $AiStage "*") -DestinationPath $AiZip -Force
    Write-Host "OK  ai.zip"
}

# ---------- 附带：SQL + 依赖清单（仅全量打包时带上大 SQL）----------
Copy-Item (Join-Path $Root "requirements.txt") $Out -Force
if (-not $SkipAi) {
    Copy-Item (Join-Path $Root "backend\sql\jeecgboot-slim.sql") $Out -Force
} else {
    Write-Host "SKIP jeecgboot-slim.sql (-SkipAi 日常增量不带大 SQL)"
}

# 清理临时目录
Remove-Item $Stage -Recurse -Force

Write-Host ""
Write-Host "======= 打包完成（上传 packages/ 里这些文件）======="
Get-ChildItem $Out | ForEach-Object {
    "{0,10:N1} MB  {1}" -f ($_.Length / 1MB), $_.Name
}
Write-Host ""
Write-Host "服务器建议布局:"
Write-Host "  /var/www/sentiment/              ← front-dist.zip 解压"
Write-Host "  /opt/product-sentiment-plus/backend/                 ← backend.zip 解压"
Write-Host "  /opt/product-sentiment-plus/product-sentiment-ai/    ← ai.zip 解压"
Write-Host "  /opt/product-sentiment-plus/requirements.txt"
Write-Host "  /opt/product-sentiment-plus/jeecgboot-slim.sql"
