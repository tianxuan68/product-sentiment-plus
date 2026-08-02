"""本地验证 JeecgBoot 密码算法是否与数据库哈希一致。

请在 backend 目录下运行:
    python -m scripts.verify_password
"""

# 导包
from app.core.security import encrypt_password, verify_password

if __name__ == "__main__":
    stored = "cb362cfeefbf3d8d"
    ok = verify_password("123456", "admin", "RCGTeGiH", stored)
    print("admin password verify:", ok)
    print("generated:", encrypt_password("123456", "admin", "RCGTeGiH"))
