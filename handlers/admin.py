"""
Административные команды и колбэки.
"""
import logging
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_IDS
from database import get_stats, get_all_users
from keyboards import admin_keyboard, back_main_keyboard

logger = logging.getLogger(__name__)
router = Router()


class BroadcastState(StatesGroup):
    waiting_message = State()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ─── Панель администратора ────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return

    stats = await get_stats()
    text = (
        f"📊 <b>Статистика CookieVPN</b>\n\n"
        f"👥 Всего пользователей: <b>{stats['total_users']}</b>\n"
        f"✅ Активных подписок: <b>{stats['active_subs']}</b>\n"
        f"💰 Успешных платежей: <b>{stats['total_payments']}</b>"
    )
    await callback.message.edit_text(text, reply_markup=admin_keyboard(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "admin:users")
async def admin_users(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return

    users = await get_all_users()
    if not users:
        await callback.answer("Пользователей нет.", show_alert=True)
        return

    lines = [f"👥 <b>Пользователи ({len(users)})</b>\n"]
    for u in users[:30]:  # показываем первые 30
        name = u["full_name"] or "—"
        username = f"@{u['username']}" if u["username"] else "—"
        lines.append(f"• {name} ({username}) — <code>{u['tg_id']}</code>")

    if len(users) > 30:
        lines.append(f"\n...и ещё {len(users) - 30} пользователей")

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=admin_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return

    await state.set_state(BroadcastState.waiting_message)
    await callback.message.edit_text(
        "📢 <b>Рассылка</b>\n\nОтправь сообщение для рассылки всем пользователям.\n"
        "Поддерживается текст, фото, видео.\n\n"
        "Отправь /cancel для отмены.",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(BroadcastState.waiting_message, F.text == "/cancel")
async def broadcast_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Рассылка отменена.", reply_markup=admin_keyboard())


@router.message(BroadcastState.waiting_message)
async def broadcast_send(message: Message, state: FSMContext, bot: Bot) -> None:
    await state.clear()
    users = await get_all_users()

    sent = 0
    failed = 0
    status_msg = await message.answer(f"⏳ Рассылка... 0/{len(users)}")

    for i, user in enumerate(users):
        try:
            await message.copy_to(user["tg_id"])
            sent += 1
        except Exception:
            failed += 1

        if (i + 1) % 20 == 0:
            try:
                await status_msg.edit_text(f"⏳ Рассылка... {i+1}/{len(users)}")
            except Exception:
                pass

    await status_msg.edit_text(
        f"✅ Рассылка завершена!\n"
        f"Отправлено: {sent}\n"
        f"Ошибок: {failed}",
        reply_markup=admin_keyboard(),
    )
