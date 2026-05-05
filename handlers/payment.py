"""
Оплата: Telegram Stars, ЮKassa, пробный период, реферальные бонусы.
"""
import logging
from aiogram import Router, F, Bot
from aiogram.types import (
    CallbackQuery, Message, LabeledPrice,
    PreCheckoutQuery, SuccessfulPayment,
)

from config import PLANS, PAYMENT_METHOD, YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY, REFERRAL_DAYS
from database import (
    get_active_subscription, create_subscription, create_payment,
    update_payment_status, is_trial_used, mark_trial_used,
    credit_referral_bonus, extend_subscription, get_user,
)
from keyboards import plans_keyboard, payment_method_keyboard, back_main_keyboard, main_menu
from xui_client import xui

logger = logging.getLogger(__name__)
router = Router()


# ─── Показать магазин ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "buy")
async def show_plans(callback: CallbackQuery) -> None:
    trial_used = await is_trial_used(callback.from_user.id)
    method = "stars" if PAYMENT_METHOD != "yookassa" else "rub"
    text = (
        "🛒 <b>Выбери тариф CookieVPN</b>\n\n"
        "• Безлимитный трафик и устройства\n"
        "• Автовыдача сразу после оплаты\n"
        "• Поддержка 24/7\n"
    )
    await callback.message.edit_text(
        text,
        reply_markup=plans_keyboard(method, show_trial=not trial_used),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "trial")
async def trial_shortcut(callback: CallbackQuery) -> None:
    trial_used = await is_trial_used(callback.from_user.id)
    if trial_used:
        await callback.answer("❌ Пробный период уже использован.", show_alert=True)
        return
    sub = await get_active_subscription(callback.from_user.id)
    if sub:
        await callback.answer("У тебя уже есть активная подписка.", show_alert=True)
        return
    await _activate_free(callback)


# ─── Выбор тарифа ─────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("plan:"))
async def select_plan(callback: CallbackQuery) -> None:
    _, plan_key, payment = callback.data.split(":")
    plan = PLANS.get(plan_key)
    if not plan:
        await callback.answer("Тариф не найден.", show_alert=True)
        return
    if PAYMENT_METHOD == "both":
        text = (
            f"💳 <b>Способ оплаты</b>\n\n"
            f"Тариф: {plan['emoji']} {plan['label']}\n"
            f"• ⭐ Stars: {plan['stars']}\n"
            f"• 💳 Карта: {plan['rub']} ₽"
        )
        await callback.message.edit_text(
            text, reply_markup=payment_method_keyboard(plan_key), parse_mode="HTML"
        )
    else:
        await _show_confirm(callback, plan_key, payment)
    await callback.answer()


@router.callback_query(F.data.startswith("pay_method:"))
async def select_payment_method(callback: CallbackQuery) -> None:
    _, plan_key, payment = callback.data.split(":")
    await _show_confirm(callback, plan_key, payment)
    await callback.answer()


async def _show_confirm(callback: CallbackQuery, plan_key: str, payment: str) -> None:
    plan = PLANS[plan_key]
    price = plan["stars"] if payment == "stars" else plan["rub"]
    currency_label = "⭐ Stars" if payment == "stars" else "₽"
    text = (
        f"✅ <b>Подтверждение</b>\n\n"
        f"Тариф: {plan['emoji']} <b>{plan['label']}</b>\n"
        f"Цена: <b>{price} {currency_label}</b>\n\n"
        f"Ссылка выдаётся автоматически после оплаты."
    )
    from keyboards import confirm_payment_keyboard
    await callback.message.edit_text(
        text, reply_markup=confirm_payment_keyboard(plan_key, payment), parse_mode="HTML"
    )


# ─── Инициировать оплату ──────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("confirm_pay:"))
async def initiate_payment(callback: CallbackQuery, bot: Bot) -> None:
    parts = callback.data.split(":")
    plan_key, payment = parts[1], parts[2]
    plan = PLANS.get(plan_key)
    if not plan:
        await callback.answer("Тариф не найден.", show_alert=True)
        return

    if payment == "free":
        await _activate_free(callback)
        return
    elif payment == "stars":
        await _pay_stars(callback, bot, plan_key, plan)
    elif payment == "yookassa":
        await _pay_yookassa(callback, bot, plan_key, plan)


async def _activate_free(callback: CallbackQuery) -> None:
    """Активация пробного периода."""
    tg_id = callback.from_user.id
    if await is_trial_used(tg_id):
        await callback.answer("❌ Пробный период уже использован.", show_alert=True)
        return
    if await get_active_subscription(tg_id):
        await callback.answer("У тебя уже есть активная подписка.", show_alert=True)
        return

    await callback.message.edit_text("⏳ Активирую пробный период...")
    await mark_trial_used(tg_id)
    await _issue_vpn(callback.message, tg_id, "trial", PLANS["trial"], is_free=True)
    await callback.answer()


async def _pay_stars(callback: CallbackQuery, bot: Bot, plan_key: str, plan: dict) -> None:
    await callback.message.delete()
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=f"CookieVPN — {plan['label']}",
        description=f"VPN на {plan['days']} дней. Безлимит, автовыдача.",
        payload=f"vpn:{plan_key}:stars",
        currency="XTR",
        prices=[LabeledPrice(label=plan["label"], amount=plan["stars"])],
        provider_token="",
    )
    await callback.answer()


async def _pay_yookassa(callback: CallbackQuery, bot: Bot, plan_key: str, plan: dict) -> None:
    if not YOOKASSA_SHOP_ID or not YOOKASSA_SECRET_KEY:
        await callback.answer("Оплата картой временно недоступна.", show_alert=True)
        return
    await callback.message.delete()
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=f"CookieVPN — {plan['label']}",
        description=f"VPN на {plan['days']} дней. Безлимит, автовыдача.",
        payload=f"vpn:{plan_key}:yookassa",
        currency="RUB",
        prices=[LabeledPrice(label=plan["label"], amount=plan["rub"] * 100)],
        provider_token=f"{YOOKASSA_SHOP_ID}:{YOOKASSA_SECRET_KEY}",
    )
    await callback.answer()


# ─── Pre-checkout ─────────────────────────────────────────────────────────────

@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    await query.answer(ok=True)


# ─── Успешная оплата ──────────────────────────────────────────────────────────

@router.message(F.successful_payment)
async def successful_payment_handler(message: Message) -> None:
    payment: SuccessfulPayment = message.successful_payment
    payload = payment.invoice_payload

    try:
        _, plan_key, method = payload.split(":")
    except ValueError:
        await message.answer("Ошибка обработки платежа. Обратитесь в поддержку.")
        return

    plan = PLANS.get(plan_key)
    if not plan:
        await message.answer("Тариф не найден. Обратитесь в поддержку.")
        return

    tg_id = message.from_user.id
    await create_payment(
        tg_id=tg_id, plan_key=plan_key,
        amount=str(payment.total_amount), currency=payment.currency,
        payment_method=method, payment_id=payment.telegram_payment_charge_id,
    )

    processing_msg = await message.answer("⏳ Оплата получена! Создаю твой VPN...")
    await _issue_vpn(processing_msg, tg_id, plan_key, plan, payment_charge_id=payment.telegram_payment_charge_id)


async def _issue_vpn(
    msg, tg_id: int, plan_key: str, plan: dict,
    is_free: bool = False,
    payment_charge_id: str = None,
) -> None:
    """Создаёт клиента в x-ui и отправляет ссылку."""
    try:
        client = await xui.add_client(tg_id=tg_id, plan_key=plan_key, expire_days=plan["days"])
    except Exception as e:
        logger.error(f"Ошибка x-ui для {tg_id}: {e}")
        await msg.edit_text(
            "✅ Оплата прошла, но возникла ошибка при создании VPN.\n"
            "Обратись в поддержку — исправим в течение 15 минут."
        )
        return

    await create_subscription(
        tg_id=tg_id, xui_uuid=client["uuid"], xui_email=client["email"],
        plan_key=plan_key, days=plan["days"],
    )

    if payment_charge_id:
        await update_payment_status(payment_charge_id, "success")

    # Начисляем реферальный бонус пригласившему
    inviter_id = await credit_referral_bonus(tg_id, REFERRAL_DAYS)
    if inviter_id:
        # Продлеваем подписку пригласившего
        new_expires = await extend_subscription(inviter_id, REFERRAL_DAYS)
        try:
            exp_str = new_expires[:10] if new_expires else ""
            await msg.bot.send_message(
                inviter_id,
                f"🎉 <b>Реферальный бонус!</b>\n\n"
                f"Твой друг активировал CookieVPN.\n"
                f"Тебе начислено <b>+{REFERRAL_DAYS} дня</b> к подписке! 🍪\n"
                f"Подписка продлена до: <b>{exp_str}</b>",
                parse_mode="HTML",
            )
        except Exception:
            pass

    link = client["link"]
    prefix = "🆓 <b>Пробный период активирован!</b>" if is_free else "🎉 <b>Твой CookieVPN готов!</b>"
    text = (
        f"{prefix}\n\n"
        f"📦 Тариф: {plan['emoji']} {plan['label']}\n"
        f"📅 Действует {plan['days']} дней\n\n"
        f"🔗 <b>Ссылка для подключения:</b>\n"
        f"<code>{link}</code>\n\n"
        f"📋 Скопируй и импортируй в приложение.\n"
        f"Нажми «📖 Инструкция» если не знаешь как."
    )
    await msg.edit_text(text, reply_markup=main_menu(), parse_mode="HTML")
