"""
Команда /config — повторно выдаёт ссылку подключения активному пользователю.
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from datetime import datetime

from database import get_active_subscription
from keyboards import main_menu

router = Router()


async def _get_config_text(tg_id: int) -> str:
    from xui_client import xui
    from config import XUI_HOST

    sub = await get_active_subscription(tg_id)
    if not sub:
        return None, "❌ У тебя нет активной подписки.\nНажми /start чтобы купить VPN."

    expires = datetime.fromisoformat(sub["expires_at"])

    # Логинимся и получаем inbound
    await xui._reset_session()
    logged = await xui.login()
    if not logged:
        return sub, "❌ Не удалось подключиться к серверу. Попробуй позже."

    inbound = await xui.get_inbound()

    # Ссылка подписки из subId (если есть в email)
    # subId хранится в x-ui, получаем через трафик клиента
    sub_link = ""
    traffic = await xui.get_client_traffic(sub["xui_email"])
    if traffic and traffic.get("subId"):
        base = XUI_HOST.rstrip("/")
        sub_link = f"{base}/sub/{traffic['subId']}"

    # Прямая ссылка
    direct_link = ""
    if inbound:
        protocol = inbound.get("protocol", "vless")
        direct_link = await xui._build_link(
            protocol, sub["xui_uuid"], sub["xui_email"], inbound,
            remark=f"🇩🇪 CookieVPN"
        )

    days_left = max((expires - datetime.utcnow()).days, 0)

    if sub_link:
        text = (
            f"🔑 <b>Твои ссылки CookieVPN</b>\n\n"
            f"📅 Подписка до: <b>{expires.strftime('%d.%m.%Y')}</b> ({days_left} дн.)\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🔗 <b>Ссылка подписки</b> (рекомендуется):\n"
            f"<code>{sub_link}</code>\n\n"
            f"📋 Автообновление серверов, показывает трафик и дату.\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"🔑 <b>Прямая ссылка:</b>\n"
            f"<code>{direct_link}</code>"
        )
    elif direct_link:
        text = (
            f"🔑 <b>Твоя ссылка подключения CookieVPN</b>\n\n"
            f"<code>{direct_link}</code>\n\n"
            f"📅 Подписка до: <b>{expires.strftime('%d.%m.%Y')}</b> ({days_left} дн.)"
        )
    else:
        text = (
            f"⚠️ Не удалось получить ссылку.\n"
            f"📅 Подписка до: <b>{expires.strftime('%d.%m.%Y')}</b>\n\n"
            f"Обратись в поддержку."
        )

    return sub, text


@router.message(Command("config"))
async def cmd_config(message: Message) -> None:
    _, text = await _get_config_text(message.from_user.id)
    await message.answer(text, parse_mode="HTML", reply_markup=main_menu())
