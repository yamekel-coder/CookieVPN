from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import PLANS, PAYMENT_METHOD, SUPPORT_USERNAME


def main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🛒 Купить VPN", callback_data="buy"))
    builder.row(InlineKeyboardButton(text="📋 Моя подписка", callback_data="my_sub"))
    builder.row(
        InlineKeyboardButton(text="📖 Инструкция", callback_data="howto"),
        InlineKeyboardButton(text="💬 Поддержка", url=f"https://t.me/{SUPPORT_USERNAME}"),
    )
    return builder.as_markup()


def plans_keyboard(payment: str = "stars") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for key, plan in PLANS.items():
        price = plan["stars"] if payment == "stars" else plan["rub"]
        currency_label = "⭐" if payment == "stars" else "₽"
        builder.row(
            InlineKeyboardButton(
                text=f"{plan['emoji']} {plan['label']} — {price} {currency_label}",
                callback_data=f"plan:{key}:{payment}",
            )
        )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_main"))
    return builder.as_markup()


def payment_method_keyboard(plan_key: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if PAYMENT_METHOD in ("stars", "both"):
        builder.row(
            InlineKeyboardButton(
                text="⭐ Telegram Stars",
                callback_data=f"pay_method:{plan_key}:stars",
            )
        )
    if PAYMENT_METHOD in ("yookassa", "both"):
        builder.row(
            InlineKeyboardButton(
                text="💳 Банковская карта (ЮKassa)",
                callback_data=f"pay_method:{plan_key}:yookassa",
            )
        )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="buy"))
    return builder.as_markup()


def confirm_payment_keyboard(plan_key: str, payment: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text="✅ Оплатить",
            callback_data=f"confirm_pay:{plan_key}:{payment}",
        )
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="buy"))
    return builder.as_markup()


def back_main_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_main"))
    return builder.as_markup()


def howto_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📱 iOS / macOS", callback_data="howto:ios"),
        InlineKeyboardButton(text="🤖 Android", callback_data="howto:android"),
    )
    builder.row(
        InlineKeyboardButton(text="🖥 Windows", callback_data="howto:windows"),
        InlineKeyboardButton(text="🐧 Linux", callback_data="howto:linux"),
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_main"))
    return builder.as_markup()


def admin_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📊 Статистика", callback_data="admin:stats"))
    builder.row(InlineKeyboardButton(text="👥 Пользователи", callback_data="admin:users"))
    builder.row(InlineKeyboardButton(text="📢 Рассылка", callback_data="admin:broadcast"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_main"))
    return builder.as_markup()
