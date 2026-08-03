# 生产部署手册（MySQL → 打包 → 上传 → Nginx）

面向 **Linux 服务器 + Nginx 反代**，不用 `.bat`。  
下文用占位符，请自行替换：

| 占位符 | 含义 | 示例 |
|--------|------|------|
| `SERVER_IP` | 服务器公网/内网 IP | `43.x.x.x` |
| `APP_DIR` | 服务器项目目录 | `/opt/product-sentiment-plus` |
| `DB_PASS` | MySQL 业务用户密码 | 自定强密码 |
| `DOMAIN` | 访问域名或 `http://SERVER_IP` | `http://43.x.x.x` |

架构：

```text
浏览器 ──► Nginx(:80)
            ├─ /              → front/dist 静态
            ├─ /jeecgboot/    → 反代本机 backend:8005（改写为 /jeecg-boot/）
            └─ （可选）/ai/   → 反代本机 AI:8001（一般不对公网开）

backend:8005 ──内网──► AI:8001
backend:8005 ──本机──► MySQL:3306 / jeecg-boot
```

默认登录：**admin / 123456**（导入 SQL 后；上线后务必改密）。

---

## 0. 服务器软件准备

以 Ubuntu 22.04 为例（CentOS 把 `apt` 换成 `yum/dnf` 即可）。

```bash
sudo apt update
sudo apt install -y nginx mysql-server python3 python3-venv python3-pip \
  build-essential git curl

# Node 18+（前端一般在本机打包后只上传 dist；若在服务器打包再装）
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
sudo npm install -g pnpm

# NVIDIA 驱动 + CUDA（AI 推理建议 ≥8GB 显存；无 GPU 可跑但极慢）
# 按机器型号自行安装 nvidia-driver / cuda toolkit
nvidia-smi   # 能出表即可
```

防火墙放行 80（以及 SSH）。**不要**把 8005 / 8001 / 3306 对公网开放。

```bash
sudo ufw allow 22
sudo ufw allow 80
sudo ufw enable
```

---

## 1. MySQL：安装、改密、建库、授权

### 1.1 初始化并设置 root

```bash
sudo mysql_secure_installation
# 按提示设 root 密码、关掉匿名用户、禁止远程 root 等
```

或：

```bash
sudo mysql
```

```sql
ALTER USER 'root'@'localhost' IDENTIFIED WITH mysql_native_password BY '你的Root强密码';
FLUSH PRIVILEGES;
EXIT;
```

### 1.2 调大导入包（约 29MB SQL，保险设大）

```bash
sudo mysql -uroot -p -e "SET GLOBAL max_allowed_packet=536870912;"
```

持久化（任选其一）：

```bash
# /etc/mysql/mysql.conf.d/mysqld.cnf 的 [mysqld] 段增加：
# max_allowed_packet = 512M
sudo systemctl restart mysql
```

### 1.3 建库 + 业务账号（推荐不用 root 跑应用）

```bash
sudo mysql -uroot -p
```

```sql
CREATE DATABASE IF NOT EXISTS `jeecg-boot`
  DEFAULT CHARACTER SET utf8mb4
  COLLATE utf8mb4_general_ci;

CREATE USER IF NOT EXISTS 'sentiment'@'localhost' IDENTIFIED BY 'DB_PASS';
GRANT ALL PRIVILEGES ON `jeecg-boot`.* TO 'sentiment'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

> 若应用与 MySQL 不在同一机，把 `'localhost'` 改成应用机 IP，并限制来源。

### 1.4 导入唯一部署 SQL

在**能访问 SQL 文件**的机器上执行（先把 `backend/sql/jeecgboot-slim.sql` 拷到服务器）：

```bash
# 方式 A：mysql 客户端直接导入
mysql -u sentiment -p'DB_PASS' \
  --default-character-set=utf8mb4 \
  --max-allowed-packet=512M \
  jeecg-boot < /path/to/jeecgboot-slim.sql

# 方式 B：用项目脚本（需已装 Python 依赖，且 backend/.env 已配好）
cd /path/to/product-sentiment-plus/backend
python -m scripts.init_slim_db \
  --host 127.0.0.1 --user sentiment --password 'DB_PASS'
```

成功标准（方式 B 会打印）：`All checks passed. Login with admin / 123456`

快速核对：

```bash
mysql -u sentiment -p'DB_PASS' -e "
SELECT COUNT(*) AS reviews FROM jeecg-boot.biz_review;
SELECT COUNT(*) AS products FROM jeecg-boot.biz_product;
SELECT username FROM jeecg-boot.sys_user WHERE username='admin';
"
```

预期：评价约 6 万+、商品约 3 万+、存在 admin。

---

## 2. 本机打包（只打 3 个 zip）

**详细说明见 [`deploy/PACK.md`](./deploy/PACK.md)。**  
不要再用混在一起的 `release/`；Windows 用脚本，产出固定三个包。

| 包 | 含义 |
|----|------|
| `packages/front-dist.zip` | 前端 `dist` → Nginx |
| `packages/backend.zip` | 后端代码（不含本机 `.env`） |
| `packages/ai.zip` | AI 代码 + 模型权重 |

另附：`requirements.txt`、`jeecgboot-slim.sql`。

### 2.1 改前端生产环境变量（打包前必改）

编辑 `front/.env.production`：

```env
VITE_GLOB_API_URL=/jeecgboot
VITE_GLOB_DOMAIN_URL=http://SERVER_IP/jeecgboot
```

### 2.2 一键打包（Windows PowerShell）

```powershell
cd E:\tianxuan\product-sentiment-plus
powershell -ExecutionPolicy Bypass -File deploy\pack-release.ps1
```

已 build 过只重打 zip：加 `-SkipFrontBuild`。

### 2.3 服务器上的 `.env`（上传后现写）

```env
DATABASE_URL=mysql+pymysql://root:DB_PASS@127.0.0.1:3306/jeecg-boot?charset=utf8mb4
# 密码含 @ 必须写成 %40
HOST=127.0.0.1
PORT=8005
DEV_RELOAD=false
FRONTEND_URL=http://SERVER_IP
CORS_ORIGINS=http://SERVER_IP,http://SERVER_IP:80
SENTIMENT_AI_BASE_URL=http://127.0.0.1:8001
SENTIMENT_AI_MOCK=false
SENTIMENT_AI_TIMEOUT=60
```

AI 包内必须有：

- `models/tagging/model/bert_hierarchical/`（打标，~0.38GB）
- `models/bert/common/model/bert_all/`（情感，~0.38GB）

---

## 3. 上传并解压（对应 3 个 zip）

```powershell
# 本机
scp packages\front-dist.zip packages\backend.zip packages\ai.zip `
  packages\requirements.txt packages\jeecgboot-slim.sql `
  root@SERVER_IP:/opt/upload/
```

```bash
# 服务器
mkdir -p /opt/product-sentiment-plus /var/www/sentiment /opt/upload

unzip -o /opt/upload/front-dist.zip -d /var/www/sentiment

rm -rf /opt/product-sentiment-plus/backend
mkdir -p /opt/product-sentiment-plus/backend
unzip -o /opt/upload/backend.zip -d /opt/product-sentiment-plus/backend

rm -rf /opt/product-sentiment-plus/product-sentiment-ai
mkdir -p /opt/product-sentiment-plus/product-sentiment-ai
unzip -o /opt/upload/ai.zip -d /opt/product-sentiment-plus/product-sentiment-ai

cp /opt/upload/requirements.txt /opt/upload/jeecgboot-slim.sql /opt/product-sentiment-plus/
cd /opt/product-sentiment-plus/backend && cp .env.example .env && nano .env
```

导库：

```bash
mysql -u root -p --max-allowed-packet=512M jeecg-boot < /opt/product-sentiment-plus/jeecgboot-slim.sql
```

---

## 4. 服务器安装 Python 依赖并启动后端 / AI

### 4.1 虚拟环境

```bash
cd APP_DIR
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip

# CUDA 11.8 示例（按机器 CUDA 版本调整；失败先装 torch 再装其余）
pip install torch==2.7.1+cu118 torchaudio==2.7.1+cu118 torchvision==0.22.1+cu118 \
  --index-url https://download.pytorch.org/whl/cu118
pip install -r requirements.txt
```

### 4.2 systemd：AI（8001）

`/etc/systemd/system/sentiment-ai.service`：

```ini
[Unit]
Description=Product Sentiment AI
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=APP_DIR/product-sentiment-ai
Environment=PATH=APP_DIR/.venv/bin
ExecStart=APP_DIR/.venv/bin/python -m uvicorn api.main:app --host 127.0.0.1 --port 8001
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 4.3 systemd：Backend（8005）

`/etc/systemd/system/sentiment-backend.service`：

```ini
[Unit]
Description=Product Sentiment Backend
After=network.target mysql.service sentiment-ai.service
Requires=mysql.service

[Service]
Type=simple
User=www-data
WorkingDirectory=APP_DIR/backend
Environment=PATH=APP_DIR/.venv/bin
ExecStart=APP_DIR/.venv/bin/python run.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

> 把上面两处所有 `APP_DIR` 换成真实路径。若用专用用户，把 `User=` 改成该用户，并 `chown -R` 项目目录。

```bash
sudo sed -i 's|APP_DIR|/opt/product-sentiment-plus|g' \
  /etc/systemd/system/sentiment-ai.service \
  /etc/systemd/system/sentiment-backend.service

# 目录权限（示例）
sudo chown -R www-data:www-data /opt/product-sentiment-plus

sudo systemctl daemon-reload
sudo systemctl enable --now sentiment-ai
sudo systemctl enable --now sentiment-backend

sudo systemctl status sentiment-ai sentiment-backend
# AI 首次加载模型可能要 30～90 秒
curl -s http://127.0.0.1:8001/health
curl -s http://127.0.0.1:8005/jeecg-boot/sys/randomImage/0   # 或打开 /docs
```

---

## 5. Nginx 部署（具体配置）

### 5.1 静态目录

```bash
sudo mkdir -p /var/www/sentiment
sudo rsync -a APP_DIR/front/dist/ /var/www/sentiment/
# 若 dist 已单独上传到 /var/www/sentiment 可跳过
sudo chown -R www-data:www-data /var/www/sentiment
```

### 5.2 站点配置

`/etc/nginx/sites-available/sentiment`（Debian/Ubuntu）：

```nginx
server {
    listen 80;
    server_name SERVER_IP;   # 或你的域名

    client_max_body_size 50m;

    root /var/www/sentiment;
    index index.html;

    # 前端 SPA
    location / {
        try_files $uri $uri/ /index.html;
    }

    # 前端请求 /jeecgboot/* → 后端真实路径 /jeecg-boot/*
    location /jeecgboot/ {
        proxy_pass http://127.0.0.1:8005/jeecg-boot/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
        proxy_send_timeout 120s;
    }

    # 无尾斜杠时也进反代
    location = /jeecgboot {
        return 301 /jeecgboot/;
    }

    # 可选：仅内网调试 AI，生产建议删掉整段
    # location /ai/ {
    #     proxy_pass http://127.0.0.1:8001/;
    #     proxy_set_header Host $host;
    # }
}
```

启用并重载：

```bash
sudo ln -sf /etc/nginx/sites-available/sentiment /etc/nginx/sites-enabled/sentiment
# 若有 default 冲突可先禁用：sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx
```

CentOS/RHEL 把文件放到 `/etc/nginx/conf.d/sentiment.conf`，然后 `nginx -t && systemctl reload nginx`。

### 5.3 HTTPS（有域名时）

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your.domain.com
```

同时把 `front/.env.production` 的 `VITE_GLOB_DOMAIN_URL`、`backend/.env` 的 `FRONTEND_URL` / `CORS_ORIGINS` 改成 `https://your.domain.com`，**重新 `pnpm build` 并覆盖** `/var/www/sentiment`。

---

## 6. 验收清单

| # | 命令 / 操作 | 期望 |
|---|-------------|------|
| 1 | 浏览器打开 `http://SERVER_IP` | 登录页 |
| 2 | `admin` / `123456` 登录 | 进入系统 |
| 3 | `curl -I http://127.0.0.1/jeecgboot/sys/randomImage/x` | 非 502 |
| 4 | 评价管理列表 | 约 6 万+ 条 |
| 5 | 评价 → 更多 → 评价分析 | 出标签/情绪（AI 已 ready） |
| 6 | `journalctl -u sentiment-ai -n 50` | 无反复崩溃；有模型加载日志 |

---

## 7. 日常运维命令

```bash
# 看日志
sudo journalctl -u sentiment-backend -f
sudo journalctl -u sentiment-ai -f

# 重启
sudo systemctl restart sentiment-ai sentiment-backend
sudo systemctl reload nginx

# 更新前端（本机重新 pnpm build 后）
rsync -avz front/dist/ root@SERVER_IP:/var/www/sentiment/

# 更新后端代码后
sudo systemctl restart sentiment-backend

# 更新 AI 权重后
sudo systemctl restart sentiment-ai
```

---

## 8. 常见坑

1. **502 / 登录接口失败**  
   Nginx 写了 `/jeecgboot` 但 `proxy_pass` 没改成 `/jeecg-boot/`；或 backend 没起来。

2. **跨域**  
   生产应走同源 `/jeecgboot`，不要让浏览器直连 `:8005`。检查 `CORS_ORIGINS` 与真实访问地址一致。

3. **密码里的 `@`**  
   `DATABASE_URL` 里必须写成 `%40`。

4. **评价分析失败**  
   AI 未启动或模型目录缺失；权重在 `.gitignore`，上传时漏拷是最常见原因。

5. **显存不够**  
   双 BERT 建议 ≥8GB；不够会 OOM 重启，可考虑只开一层或换更大卡。

6. **改了 `.env.production` 但页面还是旧接口**  
   必须重新 `pnpm build` 并覆盖 `dist`，环境变量是打进静态资源的。

---

## 9. 与本地开发文档的关系

- 本机一键调试（`.bat`）：见 `DEPLOY.md`
- 服务器 Nginx 生产：以本文为准
- 数据库唯一 SQL：`backend/sql/jeecgboot-slim.sql`
