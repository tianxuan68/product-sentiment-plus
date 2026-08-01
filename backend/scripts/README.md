# 运维脚本

| 脚本 | 用途 |
|------|------|
| `init_slim_db.py` | 初始化精简库（执行 `sql/jeecgboot-slim.sql`） |
| `check_db.py` | 检查数据库连通与基础表 |
| `reset_users.py` | 重置默认用户密码（`admin` / `123456` 等） |

## 调试脚本（按需）

| 脚本 | 用途 |
|------|------|
| `verify_password.py` | 校验密码哈希 |
| `diagnose_hash.py` | 排查加密/盐值问题 |
| `inspect_user.py` | 查看用户记录 |
| `test_auth_chain.py` | 本地鉴权链路自检 |
| `test_register_login_api.py` | 注册/登录 API 冒烟 |

日常开发优先使用前三张表中的脚本；调试脚本用完可不保留在交付清单里。
