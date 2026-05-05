import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
ADMIN_IDS: list[int] = [
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
]

# x-ui panel
XUI_HOST: str = os.getenv("XUI_HOST", "").rstrip("/")
XUI_USERNAME: str = os.getenv("XUI_USERNAME", "admin")
XUI_PASSWORD: str = os.getenv("XUI_PASSWORD", "admin")
XUI_INBOUND_ID: int = int(os.getenv("XUI_INBOUND_ID", "1"))

# Payment
YOOKASSA_SHOP_ID: str = os.getenv("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET_KEY: str = os.getenv("YOOKASSA_SECRET_KEY", "")
PAYMENT_METHOD: str = os.getenv("PAYMENT_METHOD", "stars")

# Bot info
BOT_USERNAME: str = os.getenv("BOT_USERNAME", "CookieVPN_bot")
SUPPORT_USERNAME: str = os.getenv("SUPPORT_USERNAME", "support")

# VPN
VPN_DOMAIN: str = os.getenv("VPN_DOMAIN", "")
VPN_PORT: int = int(os.getenv("VPN_PORT", "443"))

# Реферальная система
REFERRAL_DAYS: int = 3          # дней за каждого приглашённого
REFERRAL_NEED_VPN: bool = True  # засчитывать только если реферал подключил VPN

# Пробный период
TRIAL_DAYS: int = 3             # дней бесплатного пробного периода

# Subscription plans
PLANS = {
    "trial": {
        "label": "Пробный период",
        "days": TRIAL_DAYS,
        "stars": 0,
        "rub": 0,
        "emoji": "🆓",
    },
    "1month": {
        "label": "1 месяц",
        "days": 30,
        "stars": 150,
        "rub": 199,
        "emoji": "🍪",
    },
    "3months": {
        "label": "3 месяца",
        "days": 90,
        "stars": 350,
        "rub": 449,
        "emoji": "🍪🍪",
    },
    "6months": {
        "label": "6 месяцев",
        "days": 180,
        "stars": 600,
        "rub": 799,
        "emoji": "🍪🍪🍪",
    },
    "1year": {
        "label": "1 год",
        "days": 365,
        "stars": 1000,
        "rub": 1299,
        "emoji": "👑",
    },
}
