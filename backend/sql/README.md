# 数据库部署（唯一 SQL）

只用这一个文件初始化：

```bash
mysql -u root -p --max-allowed-packet=512M < sql/jeecgboot-slim.sql
```

或在 `backend` 目录：

```bash
python -m scripts.init_slim_db
```

默认账号：`admin` / `123456`

## 内容

- 系统权限（用户/角色/菜单/部门/字典）
- 业务表：类目 / 商品 / 评价 / 关键词（含「通用」与类目专属）/ 因果结果
- **全量评论数据集**（来自 `product-sentiment-ai/data/processed/reviews.csv`）

仅迁移现库关键词类目字段（不重灌全库）时：

```bash
python -m scripts.migrate_keyword_category
```

## 重新生成 SQL

```bash
# 全量（默认）
python -m scripts.build_deploy_sql

# 若只要抽样（例如每类目 25 条）
python -m scripts.build_deploy_sql --per-category 25
```
