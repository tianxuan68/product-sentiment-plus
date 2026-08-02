"""Diagnose whether a stored hash matches correct or buggy password pipeline.

请在 backend 目录下运行:
    python -m scripts.diagnose_hash
"""

# 导包
import base64

from Crypto.Cipher import AES

from app.core.security import AES_IV, AES_KEY, encrypt_password, parse_client_password, verify_password


def aes_encrypt(plain: str) -> str:
    data = plain.encode("utf-8")
    pad_len = 16 - (len(data) % 16)
    data = data + bytes([pad_len] * pad_len)
    cipher = AES.new(AES_KEY, AES.MODE_CBC, AES_IV)
    return base64.b64encode(cipher.encrypt(data)).decode()


def diagnose(username: str, salt: str, stored: str, candidates: list[str]) -> None:
    print(f"user={username} salt={salt} stored={stored}")
    for pwd in candidates:
        enc = aes_encrypt(pwd)
        dec = parse_client_password(enc)
        correct_hash = encrypt_password(pwd, username, salt)
        dec_hash = encrypt_password(dec, username, salt)
        buggy_hash = encrypt_password(enc, username, salt)
        if stored == correct_hash:
            print(f"  CORRECT pipeline password={pwd!r}")
        if stored == buggy_hash and enc != pwd:
            print(f"  BUGGY (hash AES ciphertext) password={pwd!r} enc={enc[:24]}...")
        if dec != pwd:
            print(f"  parse mismatch for {pwd!r}: dec={dec!r}")


if __name__ == "__main__":
    diagnose(
        "gousan",
        "53bc0d16",
        "8b2e2eacd1219831",
        [
            "123456",
            "gousan",
            "Gousan123",
            "Gousan@123",
            "Test@123",
            "Aa123456",
            "Abc12345",
            "Password1",
            "password123",
            "19857027644",
            "Gousan1234",
            "gousan123",
            "GoUsan123",
        ],
    )
