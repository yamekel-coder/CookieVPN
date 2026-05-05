from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command

from database import upsert_user, get_active_subscription
from keyboards import main_menu, back_main_keyboard
from config import ADMIN_IDS

router = Router()

WELCOME_TEXT = """
🍪 <b>Добро пожаловать в CookieVPN!</b>

Быстрый, надёжный и безопасный VPN.

✅ Без логов
✅ Безлимитный трафик
✅ Работает везде — iOS, Android, Windows, macOS, Linux
✅ Протокол VLESS / VMess (xray-core)
✅ Автоматическая выдача после оплаты

Выбери действие ниже 👇
"""


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await upsert_user(
        tg_id=message.from_user.id,
        username=message.from_user.username,
        full_name=message.from_user.full_name,
    )
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
    from keyboards import admin_keyboard
    await message.answer("🔧 <b>Панель администратора</b>", reply_markup=admin_keyboard(), parse_mode="HTML")
