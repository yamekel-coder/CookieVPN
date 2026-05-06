import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
ADMIN_IDS: list[int] = [
    int(x.strip()) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()
]

# Payment
YOOKASSA_SHOP_ID: str = os.getenv("YOOKASSA_SHOP_ID", "")
YOOKASSA_SECRET_KEY: str = os.getenv("YOOKASSA_SECRET_KEY", "")
PAYMENT_METHOD: str = os.getenv("PAYMENT_METHOD", "stars")

# Bot info
BOT_USERNAME: str = os.getenv("BOT_USERNAME", "CookieVPN_bot")
SUPPORT_USERNAME: str = os.getenv("SUPPORT_USERNAME", "support")

# Реферальная система
REFERRAL_DAYS: int = 3
REFERRAL_NEED_VPN: bool = True

# Пробный период
TRIAL_DAYS: int = 3

# ─── Серверы ──────────────────────────────────────────────────────────────────
SERVERS: dict = {
    "de1": {
        "label": "🇩🇪 Германия 1",
        "emoji": "🇩🇪",
        "location": "Германия",
        "speed": "1 Гбит/с",
        "xui_host": os.getenv("XUI_HOST", "").rstrip("/"),
        "xui_username": os.getenv("XUI_USERNAME", "admin"),
        "xui_password": os.getenv("XUI_PASSWORD", "admin"),
        "xui_inbound_id": int(os.getenv("XUI_INBOUND_ID", "4")),
        "domain": os.getenv("VPN_DOMAIN", ""),
        "port": int(os.getenv("VPN_PORT", "443")),
        "sub_port": 2096,
        "premium": False,
    },
    "de2": {
        "label": "🇩🇪 Германия 2 ⚡",
        "emoji": "🇩🇪",
        "location": "Германия 2",
        "speed": "10 Гбит/с",
        "xui_host": os.getenv("XUI_HOST_2", "").rstrip("/"),
        "xui_username": os.getenv("XUI_USERNAME_2", "admin"),
        "xui_password": os.getenv("XUI_PASSWORD_2", "admin"),
        "xui_inbound_id": int(os.getenv("XUI_INBOUND_ID_2", "1")),
        "domain": os.getenv("VPN_DOMAIN_2", ""),
        "port": int(os.getenv("VPN_PORT_2", "21753")),
        "sub_port": 2096,
        "premium": True,  # Премиум сервер — чуть дороже
    },
}

# Для обратной совместимости
XUI_HOST: str = os.getenv("XUI_HOST", "").rstrip("/")
XUI_USERNAME: str = os.getenv("XUI_USERNAME", "admin")
XUI_PASSWORD: str = os.getenv("XUI_PASSWORD", "admin")
XUI_INBOUND_ID: int = int(os.getenv("XUI_INBOUND_ID", "4"))
VPN_DOMAIN: str = os.getenv("VPN_DOMAIN", "")
VPN_PORT: int = int(os.getenv("VPN_PORT", "443"))

# ─── Тарифы ───────────────────────────────────────────────────────────────────
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
        "stars": 90,
        "stars_premium": 140,
        "rub": 119,
        "emoji": "🍪",
    },
    "3months": {
        "label": "3 месяца",
        "days": 90,
        "stars": 210,
        "stars_premium": 315,
        "rub": 269,
        "emoji": "🍪🍪",
    },
    "6months": {
        "label": "6 месяцев",
        "days": 180,
        "stars": 360,
        "stars_premium": 525,
        "rub": 479,
        "emoji": "🍪🍪🍪",
    },
    "1year": {
        "label": "1 год",
        "days": 365,
        "stars": 600,
        "stars_premium": 840,
        "rub": 779,
        "emoji": "👑",
    },
}
