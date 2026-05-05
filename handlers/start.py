from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command

from database import upsert_user, get_active_subscription
from keyboards import main_menu, admin_keyboard
from config import ADMIN_IDS

router = Router()

WELCOME_TEXT = """
🍪 <b>Добро пожаловать в CookieVPN!</b>

Быстрый, надёжный и безопасный VPN.

✅ Без логов и ограничений
✅ Безлимитный трафик и устройства
✅ iOS, Android, Windows, macOS, Linux
✅ Автоматическая выдача после оплаты
🆓 Пробный период — 3 дня бесплатно

Выбери действие ниже 👇
"""


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    args = message.text.split()
    referred_by = None

    # Обрабатываем реферальную ссылку (?start=ref_123456)
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referred_by = int(args[1][4:])
        except ValueError:
            pass

    is_new = await upsert_user(
        tg_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
        referred_by=referred_by,
    )

    # Уведомляем пригласившего о новом пользователе
    if is_new and referred_by and referred_by != message.from_user.id:
        try:
            await message.bot.send_message(
                referred_by,
                f"👥 По твоей реферальной ссылке зарегистрировался новый пользователь!\n"
                f"Ты получишь <b>+3 дня</b> когда он активирует VPN. 🍪",
                parse_mode="HTML",
            )
        except Exception:
            pass

    await message.answer(WELCOME_TEXT, reply_markup=main_menu(), parse_mode="HTML")


@router.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        WELCOME_TEXT, reply_markup=main_menu(), parse_mode="HTML"
    )
    await callback.answer()


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    if message.from_user.id not in ADMIN_IDS:
        await message.answer("⛔ Нет доступа.")
        return
    await message.answer(
        "🔧 <b>Панель администратора CookieVPN</b>",
        reply_markup=admin_keyboard(),
        parse_mode="HTML",
    )
