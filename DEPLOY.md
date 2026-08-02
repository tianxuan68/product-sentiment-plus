# 傻瓜式部署手册（Windows）

按顺序做。**不要跳步**。做完一步再做下一步。

> 本机已验证通过的关键结果：  
> MySQL 有评价约 **61494** 条、商品 **32424**、类目 **15**、关键词 **85**；  
> 登录 `admin / 123456` 成功；前端 `3100`、后端 `8005` 可访问。

---

## 你最终会看到什么

| 服务 | 地址 | 作用 |
|------|------|------|
| 前端 | http://127.0.0.1:3100 | 网页 |
| 后端 | http://127.0.0.1:8005 | 业务接口 |
| AI | http://127.0.0.1:8001 | 评价分析 / 打标 |
| MySQL | 127.0.0.1:3306 | 数据 |

登录账号：**admin**  
登录密码：**123456**

---

## 第 0 步：准备软件（只装一次）

1. 安装 **MySQL 8**（本机要能连上 `127.0.0.1:3306`）
2. 安装 **Node.js 18+**（能在命令行运行 `node -v`）
3. 安装 **pnpm**（管理员 CMD 执行一次）：

```bat
npm install -g pnpm
```

4. 安装 **Anaconda / Miniconda**，并准备好环境（推荐名：`product-sentiment-plus`）

> 本项目默认 Python 路径：  
> `E:\study_project\conda_envs\product-sentiment-plus\python.exe`  
> 若你的路径不同，请改 `deploy\start-ai.bat` / `start-backend.bat` / `init-db.bat` 里的 `PY=` 那一行。

5. 安装 Python 依赖（在项目根目录打开 CMD）：

```bat
cd /d E:\tianxuan\product-sentiment-plus
E:\study_project\conda_envs\product-sentiment-plus\python.exe -m pip install -r requirements.txt
```

若 `torch` 装不上，先执行 README 里那条 CUDA 安装命令，再重跑上面这句。

6. 前端依赖（只装一次）：

```bat
cd /d E:\tianxuan\product-sentiment-plus\front
pnpm install
```

---

## 第 1 步：配置数据库密码（只做一次）

1. 打开文件：`backend\.env`  
   （没有就复制 `backend\.env.example` 改名为 `.env`）

2. 改这一行（把密码换成你的 MySQL root 密码）：

```env
DATABASE_URL=mysql+pymysql://root:你的密码@127.0.0.1:3306/jeecg-boot?charset=utf8mb4
```

**重要**：密码里如果有 `@`，必须写成 `%40`  
例如密码是 `Zpg1314521@`，应写成：

```env
DATABASE_URL=mysql+pymysql://root:Zpg1314521%40@127.0.0.1:3306/jeecg-boot?charset=utf8mb4
```

3. 保存文件。

---

## 第 2 步：初始化数据库（只做一次，或你要重装库时再做）

> 会导入约 30MB 的 `backend\sql\jeecgboot-slim.sql`（全量评论数据）。  
> MySQL 必须已启动。

**方式 A（推荐，双击）**

1. 双击：`deploy\init-db.bat`
2. 按提示按任意键继续
3. 等到出现：`All checks passed. Login with admin / 123456`

**方式 B（命令行）**

```bat
cd /d E:\tianxuan\product-sentiment-plus\backend
E:\study_project\conda_envs\product-sentiment-plus\python.exe -m scripts.init_slim_db
```

若报错 `max_allowed_packet`，用管理员登录 MySQL 执行：

```sql
SET GLOBAL max_allowed_packet=536870912;
```

然后再跑一遍初始化。

---

## 第 3 步：每天怎么启动（三选一）

### 方式 A：一键启动（最省事）

双击：

```text
deploy\start-all.bat
```

会弹出 **3 个黑窗口**（AI / 后端 / 前端），**不要关**。

等约 30～60 秒（AI 第一次更久），浏览器打开：

→ http://127.0.0.1:3100

### 方式 B：分开启动（排查问题时用）

按顺序双击（每个都留着窗口）：

1. `deploy\start-ai.bat`　　→ 等到出现 `Application startup complete`
2. `deploy\start-backend.bat`
3. `deploy\start-front.bat`

### 方式 C：命令行

```bat
:: 窗口1 AI
cd /d E:\tianxuan\product-sentiment-plus\product-sentiment-ai
E:\study_project\conda_envs\product-sentiment-plus\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8001

:: 窗口2 后端
cd /d E:\tianxuan\product-sentiment-plus\backend
E:\study_project\conda_envs\product-sentiment-plus\python.exe run.py

:: 窗口3 前端
cd /d E:\tianxuan\product-sentiment-plus\front
pnpm dev
```

---

## 第 4 步：怎么确认部署成功（请照着勾）

在浏览器或本机逐项检查：

| # | 检查 | 期望结果 |
|---|------|----------|
| 1 | 打开 http://127.0.0.1:8001/docs | 能打开 AI 文档页 |
| 2 | 打开 http://127.0.0.1:8005/docs | 能打开后端文档页 |
| 3 | 打开 http://127.0.0.1:3100 | 出现登录页 |
| 4 | 用 `admin` / `123456` 登录 | 能进系统（默认进前台 `/home`） |
| 5 | 后台 → 评价管理 | 总条数约 6 万+ |
| 6 | 评价「更多 → 评价分析」 | 能出标签/情绪（需 AI 窗口已就绪） |

---

## 常见问题（照着修）

### 1）登录提示用户名或密码错误

- 先确认数据库已用 `init-db.bat` 初始化成功  
- 默认就是 `admin` / `123456`（不是 MySQL 密码）  
- 浏览器别自动填错密码，建议手动输入

### 2）评价分析失败 / AI 502 / 连接被拒绝

- AI 窗口没开，或模型还在加载  
- 重新双击 `deploy\start-ai.bat`  
- 等到窗口里出现 `Application startup complete` 再点分析

### 3）前端能开，接口全红

- 后端没开：双击 `deploy\start-backend.bat`  
- 检查 `backend\.env` 的 `DATABASE_URL` 密码是否正确（`@` → `%40`）

### 4）端口被占用

| 端口 | 占用时 |
|------|--------|
| 3100 | 关掉旧前端窗口，或结束占用进程后重启 |
| 8005 | 关掉旧后端窗口 |
| 8001 | 关掉旧 AI 窗口 |

### 5）`pnpm` 不是内部命令

```bat
npm install -g pnpm
```

然后重新开一个 CMD 窗口再启动前端。

### 6）只想更新关键词，不想整库重装

```bat
cd /d E:\tianxuan\product-sentiment-plus\backend
E:\study_project\conda_envs\product-sentiment-plus\python.exe -m scripts.migrate_keyword_category
```

---

## 目录对照（怕找错时看）

```text
product-sentiment-plus/
├── DEPLOY.md                 ← 你正在看的文档
├── requirements.txt          ← Python 依赖
├── deploy/
│   ├── start-all.bat         ← 日常一键启动
│   ├── start-ai.bat
│   ├── start-backend.bat
│   ├── start-front.bat
│   └── init-db.bat           ← 只在装库时用
├── backend/                  ← 业务后端（8005）
│   ├── .env                  ← 数据库密码在这里
│   ├── run.py
│   └── sql/jeecgboot-slim.sql
├── front/                    ← 网页（3100）
└── product-sentiment-ai/     ← AI（8001）
```

---

## 最短路径（你已经装过依赖时）

1. 确认 MySQL 已开  
2. 双击 `deploy\start-all.bat`  
3. 打开 http://127.0.0.1:3100  
4. 登录 `admin` / `123456`
