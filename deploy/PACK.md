# 部署打包说明（只打 3 个包）

不要再混成一个乱七八糟的 `release/`。本机只产出这些：

| 文件 | 内容 | 服务器放哪 |
|------|------|------------|
| `packages/front-dist.zip` | 前端构建产物（`front/dist`） | 解压到 `/var/www/sentiment/` |
| `packages/backend.zip` | 后端代码 + `sql/`（不含本机 `.env`） | 解压到 `/opt/product-sentiment-plus/backend/` |
| `packages/ai.zip` | AI 代码 + **模型权重** | 解压到 `/opt/product-sentiment-plus/product-sentiment-ai/` |
| `packages/requirements.txt` | Python 依赖清单 | `/opt/product-sentiment-plus/` |
| `packages/jeecgboot-slim.sql` | 初始化库 | 导库用，可放同目录 |

```text
packages/
├── front-dist.zip      # Nginx 静态
├── backend.zip         # FastAPI 业务
├── ai.zip              # 推理服务（含 bert 权重，体积最大）
├── requirements.txt
└── jeecgboot-slim.sql
```

---

## 本机怎么打

1. 先改 `front/.env.production` 里的 `VITE_GLOB_DOMAIN_URL`（如 `http://公网IP/jeecgboot`）
2. PowerShell 在项目根执行：

```powershell
cd E:\tianxuan\product-sentiment-plus
powershell -ExecutionPolicy Bypass -File deploy\pack-release.ps1
```

已 build 过、只想重打 zip：

```powershell
powershell -ExecutionPolicy Bypass -File deploy\pack-release.ps1 -SkipFrontBuild
```

---

## 上传（示例）

```powershell
scp packages\front-dist.zip packages\backend.zip packages\ai.zip `
  packages\requirements.txt packages\jeecgboot-slim.sql `
  root@公网IP:/opt/upload/
```

---

## 服务器解压

```bash
mkdir -p /opt/product-sentiment-plus /var/www/sentiment /opt/upload

# 前端 → Nginx 目录
unzip -o /opt/upload/front-dist.zip -d /var/www/sentiment

# 后端
rm -rf /opt/product-sentiment-plus/backend
mkdir -p /opt/product-sentiment-plus/backend
unzip -o /opt/upload/backend.zip -d /opt/product-sentiment-plus/backend

# AI（含模型，较大）
rm -rf /opt/product-sentiment-plus/product-sentiment-ai
mkdir -p /opt/product-sentiment-plus/product-sentiment-ai
unzip -o /opt/upload/ai.zip -d /opt/product-sentiment-plus/product-sentiment-ai

cp /opt/upload/requirements.txt /opt/product-sentiment-plus/
cp /opt/upload/jeecgboot-slim.sql /opt/product-sentiment-plus/

# 后端环境变量（在服务器上现写，不要从本机带密码）
cd /opt/product-sentiment-plus/backend
cp .env.example .env
nano .env
```

AI 包必须含（解压后检查）：

```bash
ls product-sentiment-ai/models/tagging/model/bert_hierarchical/hier_config.json
ls product-sentiment-ai/models/bert/common/model/bert_all/config.json
```

完整装库 / 启服务 / Nginx 见根目录 `DEPLOY-PRODUCTION.md`。
