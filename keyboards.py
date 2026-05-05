from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from config import PLANS, PAYMENT_METHOD, SUPPORT_USERNAME, BOT_USERNAME


def main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🛒 Купить VPN", callback_data="buy"))
    builder.row(
        InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
        InlineKeyboardButton(text="📋 Подписка", callback_data="my_sub"),
    )
    builder.row(
        InlineKeyboardButton(text="👥 Рефералы", callback_data="referral"),
        InlineKeyboardButton(text="🆓 Пробный период", callback_data="trial"),
    )
    builder.row(
        InlineKeyboardButton(text="📖 Инструкция", callback_data="howto"),
        InlineKeyboardButton(text="💬 Поддержка", url=f"https://t.me/{SUPPORT_USERNAME}"),
    )
    return builder.as_markup()


def plans_keyboard(payment: str = "stars", show_trial: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if show_trial:
        builder.row(
            InlineKeyboardButton(
                text="🆓 Пробный период (3 дня) — Бесплатно",
                callback_data="confirm_pay:trial:free",
            )
        )
    for key, plan in PLANS.items():
        if key == "trial":
            continue
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
        builder.row(InlineKeyboardButton(
            text="⭐ Telegram Stars",
            callback_data=f"pay_method:{plan_key}:stars",
        ))
    if PAYMENT_METHOD in ("yookassa", "both"):
        builder.row(InlineKeyboardButton(
            text="💳 Банковская карта",
            callback_data=f"pay_method:{plan_key}:yookassa",
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="buy"))
    return builder.as_markup()


def confirm_payment_keyboard(plan_key: str, payment: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="✅ Оплатить" if payment != "free" else "✅ Активировать",
        callback_data=f"confirm_pay:{plan_key}:{payment}",
    ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="buy"))
    return builder.as_markup()


def back_main_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_main"))
    return builder.as_markup()


def profile_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📋 Моя подписка", callback_data="my_sub"))
    builder.row(InlineKeyboardButton(text="👥 Рефералы", callback_data="referral"))
    builder.row(InlineKeyboardButton(text="🔑 Получить конфиг", callback_data="get_config"))
    builder.row(InlineKeyboardButton(text="🏠 Главное меню", callback_data="back_main"))
    return builder.as_markup()


def referral_keyboard(bot_username: str, tg_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    ref_link = f"https://t.me/{bot_username}?start=ref_{tg_id}"
    builder.row(InlineKeyboardButton(text="📤 Поделиться ссылкой", url=f"https://t.me/share/url?url={ref_link}&text=🍪+Попробуй+CookieVPN+бесплатно!"))
    builder.row(InlineKeyboardButton(text="🔗 Скопировать ссылку", callback_data=f"copy_ref:{tg_id}"))
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
    builder.row(InlineKeyboardButton(text="➕ Выдать дни", callback_data="admin:give_days"))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="back_main"))
    return builder.as_markup()
