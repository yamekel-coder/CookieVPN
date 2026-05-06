"""
Команда /config — выдаёт ссылку подписки и прямую ссылку.
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from datetime import datetime

from database import get_active_subscription
from keyboards import main_menu
from config import XUI_HOST

router = Router()


async def _get_config_text(tg_id: int) -> tuple:
    from xui_client import xui

    sub = await get_active_subscription(tg_id)
    if not sub:
        return None, "❌ У тебя нет активной подписки.\nНажми /start чтобы купить VPN."

    expires = datetime.fromisoformat(sub["expires_at"])
    days_left = max((expires - datetime.utcnow()).days, 0)

    # Ссылка подписки из сохранённого sub_id
    sub_id = sub.get("xui_sub_id")
    sub_link = ""
    if sub_id:
        base = XUI_HOST.rstrip("/")
        sub_link = f"{base}/sub/{sub_id}"

    # Прямая ссылка — логинимся и получаем inbound
    direct_link = ""
    try:
        await xui._reset_session()
        await xui.login()
        inbound = await xui.get_inbound()
        if inbound:
            protocol = inbound.get("protocol", "vless")
            direct_link = await xui._build_link(
                protocol, sub["xui_uuid"], sub["xui_email"], inbound,
                remark="🇩🇪 CookieVPN"
            )
    except Exception as e:
        print(f"[config_cmd] Error getting direct link: {e}")

    if sub_link:
        text = (
            f"🔑 <b>Твои ссылки CookieVPN</b>\n\n"
            f"📅 Подписка до: <b>{expires.strftime('%d.%m.%Y')}</b> ({days_left} дн.)\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"📡 <b>Ссылка подписки</b> (рекомендуется):\n"
            f"<code>{sub_link}</code>\n\n"
            f"✅ Показывает трафик, дату истечения, автообновляется.\n\n"
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
