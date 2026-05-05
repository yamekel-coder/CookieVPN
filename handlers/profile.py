"""
Профиль пользователя и реферальная система.
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from datetime import datetime

from database import get_user, get_active_subscription, get_referral_stats
from keyboards import profile_keyboard, referral_keyboard, back_main_keyboard, main_menu
from config import BOT_USERNAME, REFERRAL_DAYS

router = Router()


@router.callback_query(F.data == "profile")
async def show_profile(callback: CallbackQuery) -> None:
    tg_id = callback.from_user.id
    user = await get_user(tg_id)
    sub = await get_active_subscription(tg_id)
    ref_stats = await get_referral_stats(tg_id)

    name = callback.from_user.full_name
    username = f"@{callback.from_user.username}" if callback.from_user.username else "не задан"

    # Статус подписки
    if sub:
        expires = datetime.fromisoformat(sub["expires_at"])
        days_left = max((expires - datetime.utcnow()).days, 0)
        sub_status = f"✅ Активна до {expires.strftime('%d.%m.%Y')} ({days_left} дн.)"
        plan = sub["plan_key"]
    else:
        sub_status = "❌ Нет активной подписки"
        plan = "—"

    bonus_days = user.get("bonus_days", 0) if user else 0
    reg_date = user["created_at"][:10] if user else "—"

    text = (
        f"👤 <b>Профиль</b>\n\n"
        f"🏷 Имя: {name}\n"
        f"📎 Username: {username}\n"
        f"🆔 ID: <code>{tg_id}</code>\n"
        f"📅 Регистрация: {reg_date}\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📡 Подписка: {sub_status}\n"
        f"📦 Тариф: {plan}\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👥 Рефералов приглашено: {ref_stats['total']}\n"
        f"✅ Активировали VPN: {ref_stats['activated']}\n"
        f"🎁 Бонусных дней накоплено: {bonus_days}\n"
    )

    await callback.message.edit_text(text, reply_markup=profile_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "referral")
async def show_referral(callback: CallbackQuery) -> None:
    tg_id = callback.from_user.id
    ref_stats = await get_referral_stats(tg_id)
    user = await get_user(tg_id)
    bonus_days = user.get("bonus_days", 0) if user else 0

    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{tg_id}"

    text = (
        f"👥 <b>Реферальная программа</b>\n\n"
        f"Приглашай друзей и получай <b>+{REFERRAL_DAYS} дня</b> за каждого!\n\n"
        f"📌 Условие: друг должен зарегистрироваться по твоей ссылке "
        f"и активировать VPN (хотя бы пробный период).\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👥 Приглашено: <b>{ref_stats['total']}</b>\n"
        f"✅ Активировали VPN: <b>{ref_stats['activated']}</b>\n"
        f"🎁 Бонусных дней: <b>{bonus_days}</b>\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"🔗 Твоя ссылка:\n"
        f"<code>{ref_link}</code>"
    )

    await callback.message.edit_text(
        text,
        reply_markup=referral_keyboard(BOT_USERNAME, tg_id),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("copy_ref:"))
async def copy_ref_link(callback: CallbackQuery) -> None:
    tg_id = int(callback.data.split(":")[1])
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref_{tg_id}"
    await callback.answer(f"Ссылка: {ref_link}", show_alert=True)


@router.callback_query(F.data == "get_config")
async def get_config_callback(callback: CallbackQuery) -> None:
    from database import get_active_subscription
    from xui_client import xui
    import json

    sub = await get_active_subscription(callback.from_user.id)
    if not sub:
        await callback.answer("❌ Нет активной подписки.", show_alert=True)
        return

    expires = datetime.fromisoformat(sub["expires_at"])
    inbound = await xui.get_inbound()
    if inbound:
        protocol = inbound.get("protocol", "vless")
        link = await xui._build_link(protocol, sub["xui_uuid"], sub["xui_email"], inbound)
    else:
        link = "Не удалось получить ссылку. Обратись в поддержку."

    text = (
        f"🔑 <b>Твоя ссылка подключения</b>\n\n"
        f"<code>{link}</code>\n\n"
        f"📅 Подписка до: <b>{expires.strftime('%d.%m.%Y')}</b>\n\n"
        f"Скопируй и импортируй в приложение."
    )
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()
