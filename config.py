import os
import json
import base64
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))

# Tự động giải mã cấu hình khi chạy trên Cloud VPS 24/7 (cloud_env.dat)
_CLOUD_DAT = os.path.join(BASE_DIR, "cloud_env.dat")
if not os.getenv("BOT_TOKEN") and os.path.exists(_CLOUD_DAT):
    try:
        _raw = base64.b64decode(open(_CLOUD_DAT, "r", encoding="ascii").read().strip())
        _key = b"HUPSMS_CLOUD_VPS_KEY_2026"
        _dec = json.loads(bytes(b ^ _key[i % len(_key)] for i, b in enumerate(_raw)).decode("utf-8"))
        for _k, _v in _dec.items():
            if _k and _v is not None and not os.getenv(_k):
                os.environ[_k] = str(_v)
    except Exception:
        pass

def _get(key: str, default: str = "") -> str:
    return os.getenv(key, default).strip()

def _int(key: str, default: int) -> int:
    val = _get(key, str(default))
    return int(val) if val.isdigit() else default

# Bot & Admin Settings
BOT_TOKEN = _get("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in _get("ADMIN_IDS", "8754685711,8669804848").replace(" ", "").split(",") if x.isdigit()]
ADMIN_USERNAMES = [x.strip().lstrip("@").lower() for x in _get("ADMIN_USERNAMES", "roxie_usa1998,useralex199").split(",") if x.strip()]
SUPPORT_USERNAME = _get("SUPPORT_USERNAME", "roxie_usa1998").lstrip("@")

def is_admin(user_id: int, username: str = None) -> bool:
    if user_id in ADMIN_IDS:
        return True
    if username and username.lstrip("@").lower() in ADMIN_USERNAMES:
        return True
    return False

# HupSMS API Settings
HUPSMS_API_KEY = _get("HUPSMS_API_KEY")
HUPSMS_BASE_URL = _get("HUPSMS_BASE_URL", "https://hupsms.com/api/v1")
# Secondary fallback URL
HUPSMS_FALLBACK_URL = _get("HUPSMS_FALLBACK_URL", "https://hupsms.com/api")

# Business & Markup Pricing
# Mặc định cộng 1.500đ đến 2.000đ mỗi tin nhắn theo yêu cầu đề bài
DEFAULT_MARKUP = _int("DEFAULT_MARKUP", 1500)
ROUND_STEP = _int("ROUND_STEP", 100) # Làm tròn lên hàng 100đ

# Timeout cấu hình cho mỗi phiên nhận OTP (Mặc định 300s = 5 phút chuẩn HupSMS)
ORDER_TIMEOUT_SECONDS = _int("ORDER_TIMEOUT_SECONDS", 300)
POLL_INTERVAL_SECONDS = _int("POLL_INTERVAL_SECONDS", 3) # Polling ngầm mỗi 3 giây

# Ngân hàng nạp tiền mặc định
DEFAULT_BANK_NAME = _get("DEFAULT_BANK_NAME", "MBBANK")
DEFAULT_BANK_ACC = _get("DEFAULT_BANK_ACC", "0987654321")
DEFAULT_BANK_OWNER = _get("DEFAULT_BANK_OWNER", "NGUYEN VAN A")

# Database & Storage
DB_PATH = os.path.join(BASE_DIR, _get("DB_PATH", "hupsms_otp.db"))
CACHE_DIR = os.path.join(BASE_DIR, "storage")
os.makedirs(CACHE_DIR, exist_ok=True)
