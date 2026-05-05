from aiogram import Router, F
from aiogram.types import CallbackQuery
from datetime import datetime

from database import get_active_subscription
from keyboards import main_menu, back_main_keyboard, howto_keyboard
from xui_client import xui

router = Router()

HOWTO_TEXTS = {
    "ios": """
📱 <b>Установка на iOS / macOS</b>

1. Скачай приложение <b>Streisand</b> или <b>V2Box</b> из App Store
2. Нажми «+» → «Импорт из буфера обмена»
3. Вставь свою ссылку подключения
4. Нажми «Подключить»

🔗 <a href="https://apps.apple.com/app/streisand/id6450534064">Streisand в App Store</a>
""",
    "android": """
🤖 <b>Установка на Android</b>

1. Скачай <b>v2rayNG</b> из Google Play или GitHub
2. Нажми «+» → «Импорт из буфера обмена»
3. Вставь свою ссылку подключения
4. Нажми на профиль → «Подключить»

🔗 <a href="https://play.google.com/store/apps/details?id=com.v2ray.ang">v2rayNG в Google Play</a>
""",
    "windows": """
🖥 <b>Установка на Windows</b>

1. Скачай <b>Hiddify</b> или <b>v2rayN</b>
2. Нажми «+» → «Добавить из буфера обмена»
3. Вставь свою ссылку подключения
4. Нажми «Подключить»

🔗 <a href="https://github.com/hiddify/hiddify-next/releases">Hiddify на GitHub</a>
""",
    "linux": """
🐧 <b>Установка на Linux</b>

1. Скачай <b>Hiddify</b> или используй <b>v2ray-core</b>
2. Импортируй свою ссылку подключения
3. Запусти и подключись

🔗 <a href="https://github.com/hiddify/hiddify-next/releases">Hiddify на GitHub</a>
""",
}


@router.callback_query(F.data == "my_sub")
async def my_subscription(callback: CallbackQuery) -> None:
    sub = await get_active_subscription(callback.from_user.id)

    if not sub:
        text = (
            "❌ <b>У тебя нет активной подписки.</b>\n\n"
            "Нажми «🛒 Купить VPN» чтобы оформить подписку."
        )
        await callback.message.edit_text(text, reply_markup=main_menu(), parse_mode="HTML")
        await callback.answer()
        return

    expires = datetime.fromisoformat(sub["expires_at"])
    now = datetime.utcnow()
    days_left = (expires - now).days

    # Получаем трафик из x-ui
    traffic_info = ""
    traffic = await xui.get_client_traffic(sub["xui_email"])
    if traffic:
        up_gb = round(traffic.get("up", 0) / (1024 ** 3), 2)
        down_gb = round(traffic.get("down", 0) / (1024 ** 3), 2)
        traffic_info = f"\n📊 Трафик: ↑{up_gb} GB / ↓{down_gb} GB"

    text = (
        f"✅ <b>Активная подписка CookieVPN</b>\n\n"
        f"📅 Истекает: <b>{expires.strftime('%d.%m.%Y')}</b>\n"
        f"⏳ Осталось дней: <b>{max(days_left, 0)}</b>\n"
        f"🔑 Email: <code>{sub['xui_email']}</code>"
        f"{traffic_info}\n\n"
        f"Используй команду /config чтобы получить ссылку подключения."
    )
    await callback.message.edit_text(text, reply_markup=back_main_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "howto")
async def howto_menu(callback: CallbackQuery) -> None:
    text = (
        "📖 <b>Инструкция по подключению</b>\n\n"
        "Выбери свою платформу:"
    )
    await callback.message.edit_text(text, reply_markup=howto_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("howto:"))
async def howto_platform(callback: CallbackQuery) -> None:
    platform = callback.data.split(":")[1]
    text = HOWTO_TEXTS.get(platform, "Инструкция не найдена.")
    await callback.message.edit_text(
        text,
        reply_markup=back_main_keyboard(),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    await callback.answer()
