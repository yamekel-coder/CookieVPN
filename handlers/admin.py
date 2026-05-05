import logging
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import ADMIN_IDS
from database import get_stats, get_all_users, extend_subscription, get_active_subscription
from keyboards import admin_keyboard, back_main_keyboard

logger = logging.getLogger(__name__)
router = Router()


class BroadcastState(StatesGroup):
    waiting_message = State()


class GiveDaysState(StatesGroup):
    waiting_user_id = State()
    waiting_days = State()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    stats = await get_stats()
    text = (
        f"📊 <b>Статистика CookieVPN</b>\n\n"
        f"👥 Всего пользователей: <b>{stats['total_users']}</b>\n"
        f"🆕 Новых сегодня: <b>{stats['new_today']}</b>\n"
        f"✅ Активных подписок: <b>{stats['active_subs']}</b>\n"
        f"💰 Успешных платежей: <b>{stats['total_payments']}</b>\n"
        f"👥 Рефералов всего: <b>{stats['total_refs']}</b>"
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
    for u in users[:30]:
        name = u["full_name"] or "—"
        username = f"@{u['username']}" if u["username"] else "—"
        lines.append(f"• {name} ({username}) — <code>{u['tg_id']}</code>")
    if len(users) > 30:
        lines.append(f"\n...и ещё {len(users) - 30}")
    await callback.message.edit_text(
        "\n".join(lines), reply_markup=admin_keyboard(), parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    await state.set_state(BroadcastState.waiting_message)
    await callback.message.edit_text(
        "📢 <b>Рассылка</b>\n\nОтправь сообщение для рассылки.\n/cancel — отмена.",
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin:give_days")
async def admin_give_days_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа.", show_alert=True)
        return
    await state.set_state(GiveDaysState.waiting_user_id)
    await callback.message.edit_text(
        "➕ <b>Выдать дни пользователю</b>\n\nВведи Telegram ID пользователя:\n/cancel — отмена.",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(GiveDaysState.waiting_user_id)
async def give_days_get_user(message: Message, state: FSMContext) -> None:
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_keyboard())
        return
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("Введи числовой ID.")
        return
    await state.update_data(user_id=user_id)
    await state.set_state(GiveDaysState.waiting_days)
    await message.answer(f"Пользователь: <code>{user_id}</code>\nСколько дней добавить?", parse_mode="HTML")


@router.message(GiveDaysState.waiting_days)
async def give_days_apply(message: Message, state: FSMContext) -> None:
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_keyboard())
        return
    try:
        days = int(message.text.strip())
    except ValueError:
        await message.answer("Введи число дней.")
        return
    data = await state.get_data()
    user_id = data["user_id"]
    await state.clear()

    new_expires = await extend_subscription(user_id, days)
    if new_expires:
        await message.answer(
            f"✅ Пользователю <code>{user_id}</code> добавлено <b>{days} дней</b>.\n"
            f"Подписка до: <b>{new_expires[:10]}</b>",
            reply_markup=admin_keyboard(),
            parse_mode="HTML",
        )
        try:
            await message.bot.send_message(
                user_id,
                f"🎁 Администратор добавил тебе <b>{days} дней</b> к подписке!\n"
                f"Подписка продлена до: <b>{new_expires[:10]}</b>",
                parse_mode="HTML",
            )
        except Exception:
            pass
    else:
        await message.answer(
            f"❌ У пользователя <code>{user_id}</code> нет активной подписки.",
            reply_markup=admin_keyboard(),
            parse_mode="HTML",
        )


@router.message(BroadcastState.waiting_message, F.text == "/cancel")
async def broadcast_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Рассылка отменена.", reply_markup=admin_keyboard())


@router.message(BroadcastState.waiting_message)
async def broadcast_send(message: Message, state: FSMContext) -> None:
    await state.clear()
    users = await get_all_users()
    sent, failed = 0, 0
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
        f"✅ Готово! Отправлено: {sent}, ошибок: {failed}",
        reply_markup=admin_keyboard(),
    )
