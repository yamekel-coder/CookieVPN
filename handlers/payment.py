"""
Обработчики оплаты: Telegram Stars и ЮKassa.
После успешной оплаты — автоматически создаёт клиента в x-ui и выдаёт ссылку.
"""
import logging
from aiogram import Router, F, Bot
from aiogram.types import (
    CallbackQuery,
    Message,
    LabeledPrice,
    PreCheckoutQuery,
    SuccessfulPayment,
)

from config import PLANS, PAYMENT_METHOD, YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY
from database import (
    get_active_subscription,
    create_subscription,
    create_payment,
    update_payment_status,
)
from keyboards import (
    plans_keyboard,
    payment_method_keyboard,
    confirm_payment_keyboard,
    back_main_keyboard,
    main_menu,
)
from xui_client import xui

logger = logging.getLogger(__name__)
router = Router()


# ─── Шаг 1: Показать тарифы ──────────────────────────────────────────────────

@router.callback_query(F.data == "buy")
async def show_plans(callback: CallbackQuery) -> None:
    # Если только один метод оплаты — сразу показываем тарифы с ценами
    method = "stars" if PAYMENT_METHOD == "stars" else "rub"
    text = (
        "🛒 <b>Выбери тариф CookieVPN</b>\n\n"
        "Все тарифы включают:\n"
        "• Безлимитный трафик\n"
        "• До 3 устройств одновременно\n"
        "• Поддержка 24/7\n"
    )
    await callback.message.edit_text(
        text,
        reply_markup=plans_keyboard(method),
        parse_mode="HTML",
    )
    await callback.answer()


# ─── Шаг 2: Выбор тарифа → выбор метода оплаты (если оба доступны) ──────────

@router.callback_query(F.data.startswith("plan:"))
async def select_plan(callback: CallbackQuery) -> None:
    _, plan_key, payment = callback.data.split(":")
    plan = PLANS.get(plan_key)
    if not plan:
        await callback.answer("Тариф не найден.", show_alert=True)
        return

    if PAYMENT_METHOD == "both":
        text = (
            f"💳 <b>Выбери способ оплаты</b>\n\n"
            f"Тариф: {plan['emoji']} {plan['label']}\n"
            f"• ⭐ Telegram Stars: {plan['stars']} stars\n"
            f"• 💳 Банковская карта: {plan['rub']} ₽"
        )
        await callback.message.edit_text(
            text,
            reply_markup=payment_method_keyboard(plan_key),
            parse_mode="HTML",
        )
    else:
        # Сразу к подтверждению
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
    currency_label = "⭐ Telegram Stars" if payment == "stars" else "₽ (банковская карта)"

    text = (
        f"✅ <b>Подтверждение покупки</b>\n\n"
        f"Тариф: {plan['emoji']} <b>{plan['label']}</b>\n"
        f"Цена: <b>{price} {currency_label}</b>\n\n"
        f"После оплаты ссылка для подключения будет выдана автоматически."
    )
    await callback.message.edit_text(
        text,
        reply_markup=confirm_payment_keyboard(plan_key, payment),
        parse_mode="HTML",
    )


# ─── Шаг 3: Инициировать оплату ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("confirm_pay:"))
async def initiate_payment(callback: CallbackQuery, bot: Bot) -> None:
    _, plan_key, payment = callback.data.split(":")
    plan = PLANS.get(plan_key)
    if not plan:
        await callback.answer("Тариф не найден.", show_alert=True)
        return

    if payment == "stars":
        await _pay_stars(callback, bot, plan_key, plan)
    elif payment == "yookassa":
        await _pay_yookassa(callback, bot, plan_key, plan)
    else:
        await callback.answer("Метод оплаты не поддерживается.", show_alert=True)


async def _pay_stars(callback: CallbackQuery, bot: Bot, plan_key: str, plan: dict) -> None:
    """Оплата через Telegram Stars."""
    await callback.message.delete()
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=f"CookieVPN — {plan['label']}",
        description=(
            f"VPN подписка на {plan['days']} дней. "
            "Безлимитный трафик, до 3 устройств."
        ),
        payload=f"vpn:{plan_key}:stars",
        currency="XTR",  # Telegram Stars
        prices=[LabeledPrice(label=plan["label"], amount=plan["stars"])],
        provider_token="",  # пустой для Stars
    )
    await callback.answer()


async def _pay_yookassa(callback: CallbackQuery, bot: Bot, plan_key: str, plan: dict) -> None:
    """Оплата через ЮKassa."""
    if not YOOKASSA_SHOP_ID or not YOOKASSA_SECRET_KEY:
        await callback.answer("Оплата картой временно недоступна.", show_alert=True)
        return

    await callback.message.delete()
    await bot.send_invoice(
        chat_id=callback.from_user.id,
        title=f"CookieVPN — {plan['label']}",
        description=(
            f"VPN подписка на {plan['days']} дней. "
            "Безлимитный трафик, до 3 устройств."
        ),
        payload=f"vpn:{plan_key}:yookassa",
        currency="RUB",
        prices=[LabeledPrice(label=plan["label"], amount=plan["rub"] * 100)],  # в копейках
        provider_token=f"{YOOKASSA_SHOP_ID}:{YOOKASSA_SECRET_KEY}",
    )
    await callback.answer()


# ─── Pre-checkout (обязательно подтвердить) ───────────────────────────────────

@router.pre_checkout_query()
async def pre_checkout(query: PreCheckoutQuery) -> None:
    await query.answer(ok=True)


# ─── Успешная оплата → выдача VPN ─────────────────────────────────────────────

@router.message(F.successful_payment)
async def successful_payment_handler(message: Message) -> None:
    payment: SuccessfulPayment = message.successful_payment
    payload = payment.invoice_payload  # "vpn:{plan_key}:{method}"

    try:
        _, plan_key, method = payload.split(":")
    except ValueError:
        logger.error(f"Неверный payload: {payload}")
        await message.answer("Ошибка обработки платежа. Обратитесь в поддержку.")
        return

    plan = PLANS.get(plan_key)
    if not plan:
        await message.answer("Тариф не найден. Обратитесь в поддержку.")
        return

    tg_id = message.from_user.id
    amount = str(payment.total_amount)
    currency = payment.currency

    # Сохраняем платёж
    await create_payment(
        tg_id=tg_id,
        plan_key=plan_key,
        amount=amount,
        currency=currency,
        payment_method=method,
        payment_id=payment.telegram_payment_charge_id,
    )

    # Создаём клиента в x-ui
    processing_msg = await message.answer("⏳ Оплата получена! Создаю твой VPN...")

    try:
        client = await xui.add_client(
            tg_id=tg_id,
            plan_key=plan_key,
            expire_days=plan["days"],
        )
    except Exception as e:
        logger.error(f"Ошибка создания клиента x-ui для {tg_id}: {e}")
        await processing_msg.edit_text(
            "✅ Оплата прошла, но возникла ошибка при создании VPN.\n"
            "Мы уже знаем об этом и исправим в течение 15 минут.\n"
            "Обратись в поддержку если проблема не решится."
        )
        return

    # Сохраняем подписку в БД
    await create_subscription(
        tg_id=tg_id,
        xui_uuid=client["uuid"],
        xui_email=client["email"],
        plan_key=plan_key,
        days=plan["days"],
    )

    # Обновляем статус платежа
    await update_payment_status(payment.telegram_payment_charge_id, "success")

    # Отправляем ссылку пользователю
    link = client["link"]
    text = (
        f"🎉 <b>Твой CookieVPN готов!</b>\n\n"
        f"📦 Тариф: {plan['emoji']} {plan['label']}\n"
        f"📅 Действует {plan['days']} дней\n\n"
        f"🔗 <b>Ссылка для подключения:</b>\n"
        f"<code>{link}</code>\n\n"
        f"📋 Скопируй ссылку и импортируй в приложение.\n"
        f"Нажми «📖 Инструкция» если не знаешь как подключиться."
    )
    await processing_msg.edit_text(text, reply_markup=main_menu(), parse_mode="HTML")
