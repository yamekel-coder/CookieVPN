"""
Команда /config — повторно выдаёт ссылку подключения активному пользователю.
"""
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from database import get_active_subscription
from keyboards import main_menu

router = Router()


@router.message(Command("config"))
async def cmd_config(message: Message) -> None:
    sub = await get_active_subscription(message.from_user.id)
    if not sub:
        await message.answer(
            "❌ У тебя нет активной подписки.\n"
            "Нажми /start чтобы купить VPN.",
            reply_markup=main_menu(),
        )
        return

    from xui_client import xui
    from datetime import datetime

    expires = datetime.fromisoformat(sub["expires_at"])

    # Пересобираем ссылку через x-ui
    inbound = await xui.get_inbound()
    if inbound:
        import json
        protocol = inbound.get("protocol", "vless")
        link = await xui._build_link(protocol, sub["xui_uuid"], sub["xui_email"], inbound)
    else:
        link = "Не удалось получить ссылку. Обратись в поддержку."

    text = (
        f"🔑 <b>Твоя ссылка подключения CookieVPN</b>\n\n"
        f"<code>{link}</code>\n\n"
        f"📅 Подписка до: <b>{expires.strftime('%d.%m.%Y')}</b>\n\n"
        f"Скопируй ссылку и импортируй в приложение."
    )
    await message.answer(text, parse_mode="HTML")
