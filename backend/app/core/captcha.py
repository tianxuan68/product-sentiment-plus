import io
import random
import string
import time
from typing import Dict, Tuple

from PIL import Image, ImageDraw, ImageFont

from app.core.config import settings
from app.core.security import md5_hex

_store: Dict[str, Tuple[str, float]] = {}
CAPTCHA_TTL = 60


def generate_captcha_image(code: str) -> str:
    width, height = 105, 35
    image = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)
    for _ in range(3):
        draw.line(
            [(random.randint(0, width), random.randint(0, height)),
             (random.randint(0, width), random.randint(0, height))],
            fill=(random.randint(0, 200), random.randint(0, 200), random.randint(0, 200)),
        )
    try:
        font = ImageFont.truetype("arial.ttf", 24)
    except Exception:
        font = ImageFont.load_default()
    draw.text((10, 5), code, fill=(0, 0, 0), font=font)
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    import base64
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def create_captcha(check_key: str) -> Tuple[str, str]:
    code = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    key_prefix = md5_hex(check_key + settings.signature_secret)
    real_key = key_prefix + code.lower()
    _store[real_key] = (code.lower(), time.time() + CAPTCHA_TTL)
    return code, generate_captcha_image(code)


def validate_captcha(check_key: str, captcha: str) -> bool:
    if not settings.enable_login_captcha:
        return True
    if not captcha:
        return False
    key_prefix = md5_hex(check_key + settings.signature_secret)
    real_key = key_prefix + captcha.lower()
    item = _store.get(real_key)
    if not item:
        return False
    expected, expire_at = item
    if time.time() > expire_at:
        _store.pop(real_key, None)
        return False
    _store.pop(real_key, None)
    return expected == captcha.lower()
