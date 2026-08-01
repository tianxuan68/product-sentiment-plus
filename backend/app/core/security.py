import base64
import hashlib
import re
from datetime import datetime, timedelta, timezone
from typing import Optional

from Crypto.Cipher import AES, DES
from jose import jwt

from app.core.config import settings

AES_KEY = b"1234567890adbcde"
AES_IV = b"1234567890hjlkew"
_AES_CIPHER_RE = re.compile(r"^[A-Za-z0-9+/]+=*$")


# ---------------------------------------------------------------------------
# 密码统一规范（登录 / 注册 / 改密 必须一致）
# 1. 前端传输：encryptPasswordForTransmit(明文) → AES-CBC Base64
# 2. 后端入口：parse_client_password(密文) → 明文
# 3. 数据库存储：hash_password(明文, username, salt) → JeecgBoot PBE 哈希
# 4. 登录校验：verify_password(明文, username, salt, 哈希)
# ---------------------------------------------------------------------------

def decode_client_password(cipher_or_plain: str) -> str:
    """解码前端 AES 传输密码；非密文格式则原样返回（兼容明文）。"""
    if not cipher_or_plain:
        return cipher_or_plain
    if len(cipher_or_plain) < 16 or not _AES_CIPHER_RE.match(cipher_or_plain):
        return cipher_or_plain
    try:
        raw = base64.b64decode(cipher_or_plain)
        if not raw or len(raw) % 16 != 0:
            return cipher_or_plain
        cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
        decrypted = cipher.decrypt(raw)
        pad = decrypted[-1]
        if pad < 1 or pad > 16:
            return cipher_or_plain
        text = decrypted[:-pad].decode("utf-8")
        return text if text else cipher_or_plain
    except Exception:
        return cipher_or_plain


def parse_client_password(raw: str) -> str:
    """统一入口：解析前端提交的 password / oldpassword 等字段。"""
    return decode_client_password((raw or "").strip())


def decrypt_login_password(cipher_or_plain: str) -> str:
    return parse_client_password(cipher_or_plain)


def resolve_password(cipher_or_plain: str) -> str:
    return parse_client_password(cipher_or_plain)


def _pbe_derive_key_iv(pbe_password: str, salt: str, iterations: int = 1000) -> tuple[bytes, bytes]:
    """JeecgBoot PasswordUtil — PBEWithMD5AndDES 密钥派生。"""
    password_bytes = pbe_password.encode("utf-8")
    salt_bytes = salt.encode("utf-8")
    derived = b""
    block = b""
    while len(derived) < 16:
        block = hashlib.md5(block + password_bytes + salt_bytes).digest()
        for _ in range(1, iterations):
            block = hashlib.md5(block).digest()
        derived += block
    return derived[:8], derived[8:16]


def _des_encrypt_hex(plaintext: str, pbe_password: str, salt: str) -> str:
    key, iv = _pbe_derive_key_iv(pbe_password, salt)
    data = plaintext.encode("utf-8")
    pad_len = 8 - (len(data) % 8)
    data = data + bytes([pad_len] * pad_len)
    cipher = DES.new(key, DES.MODE_CBC, iv)
    return cipher.encrypt(data).hex()


def _legacy_derive_des_key_iv(username: str, salt: str, iterations: int = 1000) -> tuple[bytes, bytes]:
    """旧版误实现：用 username+salt 派生密钥后加密 password 字段（仅兼容历史数据）。"""
    pwd = username.encode("utf-8")
    slt = salt.encode("utf-8")
    digest = hashlib.md5(pwd + slt).digest()
    for _ in range(1, iterations):
        digest = hashlib.md5(digest).digest()
    return digest[:8], digest[8:16]


def _legacy_encrypt_password(plain: str, username: str, salt: str) -> str:
    key, iv = _legacy_derive_des_key_iv(username, salt)
    data = plain.encode("utf-8")
    pad_len = 8 - (len(data) % 8)
    data = data + bytes([pad_len] * pad_len)
    cipher = DES.new(key, DES.MODE_CBC, iv)
    return cipher.encrypt(data).hex()


def encrypt_password(plain: str, username: str, salt: str) -> str:
    """JeecgBoot 标准：用用户密码加密用户名后存库。plain 必须是明文密码。"""
    return _des_encrypt_hex(username, plain, salt)


def hash_password(plain: str, username: str, salt: str) -> str:
    """encrypt_password 别名，强调存库哈希。"""
    return encrypt_password(plain, username, salt)


def verify_password(plain: str, username: str, salt: str, stored_hash: str) -> bool:
    if not stored_hash or not plain:
        return False
    if encrypt_password(plain, username, salt) == stored_hash:
        return True
    return _legacy_encrypt_password(plain, username, salt) == stored_hash


def create_token(username: str, password_hash: str, client_type: str = "PC") -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    payload = {
        "username": username,
        "clientType": client_type,
        "exp": expire,
    }
    return jwt.encode(payload, password_hash, algorithm="HS256")


def decode_username(token: str) -> Optional[str]:
    try:
        payload = jwt.get_unverified_claims(token)
        return payload.get("username")
    except Exception:
        return None


def verify_token(token: str, username: str, password_hash: str) -> bool:
    try:
        payload = jwt.decode(token, password_hash, algorithms=["HS256"])
        return payload.get("username") == username
    except Exception:
        return False


def md5_hex(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def is_http_url(url: str) -> bool:
    return bool(url and (url.startswith("http://") or url.startswith("https://") or url.startswith("{{")))


def url_to_route_name(url: str) -> Optional[str]:
    if not url:
        return None
    if url.startswith("/"):
        url = url[1:]
    url = url.replace("/", "-").replace(":", "@")
    return url
