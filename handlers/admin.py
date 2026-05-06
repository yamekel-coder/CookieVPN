import logging
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

from config import ADMIN_IDS, PLANS, SERVERS
from database import (
    get_stats, get_all_users, extend_subscription,
    create_promocode, get_all_promocodes, deactivate_promocode,
)
from keyboards import admin_keyboard, promocodes_keyboard, promo_type_keyboard

logger = logging.getLogger(__name__)
router = Router()


class BroadcastState(StatesGroup):
    waiting_message = State()

class GiveDaysState(StatesGroup):
    waiting_user_id = State()
    waiting_days = State()

class GivePlanState(StatesGroup):
    waiting_server = State()
    waiting_plan = State()
    waiting_user_id = State()

class PromoCreateState(StatesGroup):
    waiting_type = State()
    waiting_code = State()
    waiting_value = State()
    waiting_uses = State()
    waiting_server = State()
    waiting_plan = State()

class PromoDeleteState(StatesGroup):
    waiting_code = State()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def server_select_keyboard(callback_prefix: str) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    for key, srv in SERVERS.items():
        builder.row(InlineKeyboardButton(
            text=f"{srv['label']} | {srv['speed']}",
            callback_data=f"{callback_prefix}:{key}",
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:back"))
    return builder.as_markup()


def plan_select_keyboard(callback_prefix: str, server_key: str) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    for key, plan in PLANS.items():
        if key == "trial":
            continue
        builder.row(InlineKeyboardButton(
            text=f"{plan['emoji']} {plan['label']}",
            callback_data=f"{callback_prefix}:{server_key}:{key}",
        ))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:give_plan"))
    return builder.as_markup()


# ─── Назад в админку ──────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:back")
async def admin_back(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text(
        "🔧 <b>Панель администратора CookieVPN</b>",
        reply_markup=admin_keyboard(), parse_mode="HTML"
    )
    await callback.answer()


# ─── Статистика ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    stats = await get_stats()
    text = (
        f"📊 <b>Статистика CookieVPN</b>\n\n"
        f"👥 Всего пользователей: <b>{stats['total_users']}</b>\n"
        f"🆕 Новых сегодня: <b>{stats['new_today']}</b>\n"
        f"✅ Активных подписок: <b>{stats['active_subs']}</b>\n"
        f"💰 Успешных платежей: <b>{stats['total_payments']}</b>\n"
        f"👥 Рефералов всего: <b>{stats['total_refs']}</b>\n\n"
        f"🖥 <b>Серверы:</b>\n"
    )
    for key, srv in SERVERS.items():
        text += f"• {srv['label']} — {srv['speed']}\n"
    await callback.message.edit_text(text, reply_markup=admin_keyboard(), parse_mode="HTML")
    await callback.answer()


# ─── Пользователи ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:users")
async def admin_users(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
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


# ─── Рассылка ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    await state.set_state(BroadcastState.waiting_message)
    await callback.message.edit_text(
        "📢 <b>Рассылка</b>\n\nОтправь сообщение.\n/cancel — отмена.",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(BroadcastState.waiting_message, F.text == "/cancel")
async def broadcast_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Отменено.", reply_markup=admin_keyboard())


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


# ─── Выдать дни ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:give_days")
async def admin_give_days_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    await state.set_state(GiveDaysState.waiting_user_id)
    await callback.message.edit_text(
        "➕ <b>Выдать дни</b>\n\nВведи Telegram ID:\n/cancel — отмена.",
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
    await message.answer(f"ID: <code>{user_id}</code>\nСколько дней?", parse_mode="HTML")


@router.message(GiveDaysState.waiting_days)
async def give_days_apply(message: Message, state: FSMContext) -> None:
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_keyboard())
        return
    try:
        days = int(message.text.strip())
    except ValueError:
        await message.answer("Введи число.")
        return
    data = await state.get_data()
    user_id = data["user_id"]
    await state.clear()

    new_expires = await extend_subscription(user_id, days)
    if new_expires:
        await message.answer(
            f"✅ <code>{user_id}</code> +<b>{days} дней</b>. До: <b>{new_expires[:10]}</b>",
            reply_markup=admin_keyboard(), parse_mode="HTML",
        )
        try:
            await message.bot.send_message(
                user_id,
                f"🎁 Тебе добавили <b>{days} дней</b>!\nПодписка до: <b>{new_expires[:10]}</b>",
                parse_mode="HTML",
            )
        except Exception:
            pass
    else:
        await message.answer(
            f"❌ У <code>{user_id}</code> нет активной подписки.",
            reply_markup=admin_keyboard(), parse_mode="HTML",
        )


# ─── Выдать тариф ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:give_plan")
async def admin_give_plan(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    await state.set_state(GivePlanState.waiting_server)
    await callback.message.edit_text(
        "🎁 <b>Выдать тариф</b>\n\nВыбери сервер:",
        reply_markup=server_select_keyboard("admin:give_plan_srv"),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:give_plan_srv:"), GivePlanState.waiting_server)
async def give_plan_server_selected(callback: CallbackQuery, state: FSMContext) -> None:
    server_key = callback.data.split(":")[2]
    await state.update_data(server_key=server_key)
    await state.set_state(GivePlanState.waiting_plan)
    srv = SERVERS.get(server_key, {})
    await callback.message.edit_text(
        f"🎁 Сервер: <b>{srv.get('label', server_key)}</b>\n\nВыбери тариф:",
        reply_markup=plan_select_keyboard("admin:give_plan_sel", server_key),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("admin:give_plan_sel:"), GivePlanState.waiting_plan)
async def give_plan_plan_selected(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":")
    server_key, plan_key = parts[2], parts[3]
    await state.update_data(plan_key=plan_key)
    await state.set_state(GivePlanState.waiting_user_id)
    plan = PLANS[plan_key]
    srv = SERVERS.get(server_key, {})
    await callback.message.edit_text(
        f"🎁 Сервер: <b>{srv.get('label', server_key)}</b>\n"
        f"Тариф: <b>{plan['emoji']} {plan['label']}</b>\n\n"
        f"Введи Telegram ID пользователя:\n/cancel — отмена.",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(GivePlanState.waiting_user_id)
async def give_plan_apply(message: Message, state: FSMContext) -> None:
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_keyboard())
        return
    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("Введи числовой ID.")
        return

    data = await state.get_data()
    plan_key = data["plan_key"]
    server_key = data["server_key"]
    plan = PLANS[plan_key]
    srv = SERVERS.get(server_key, {})
    await state.clear()

    processing = await message.answer(
        f"⏳ Создаю VPN на <b>{srv.get('label', server_key)}</b> для <code>{user_id}</code>...",
        parse_mode="HTML"
    )
    try:
        from xui_client import get_xui_client
        from database import create_subscription
        xui_client = get_xui_client(server_key)
        client = await xui_client.add_client(user_id, plan_key, plan["days"])
        await create_subscription(
            tg_id=user_id, xui_uuid=client["uuid"], xui_email=client["email"],
            plan_key=plan_key, days=plan["days"], xui_sub_id=client.get("sub_id"),
        )
        sub_link = client.get("sub_link", "")
        link = client["link"]
        await processing.edit_text(
            f"✅ Тариф <b>{plan['emoji']} {plan['label']}</b> выдан!\n"
            f"Сервер: <b>{srv.get('label', server_key)}</b>\n"
            f"Пользователь: <code>{user_id}</code>",
            reply_markup=admin_keyboard(), parse_mode="HTML",
        )
        try:
            await message.bot.send_message(
                user_id,
                f"🎉 <b>Тебе выдан тариф {plan['emoji']} {plan['label']}!</b>\n\n"
                f"🌍 Сервер: <b>{srv.get('label', server_key)}</b>\n"
                f"📅 Действует {plan['days']} дней\n\n"
                f"📡 <b>Ссылка подписки:</b>\n<code>{sub_link}</code>\n\n"
                f"🔑 <b>Прямая ссылка:</b>\n<code>{link}</code>",
                parse_mode="HTML",
            )
        except Exception:
            pass
    except Exception as e:
        await processing.edit_text(f"❌ Ошибка: {e}", reply_markup=admin_keyboard())


# ─── Промокоды ────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin:promocodes")
async def admin_promocodes(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    await callback.message.edit_text(
        "🎟 <b>Управление промокодами</b>",
        reply_markup=promocodes_keyboard(), parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin:promo_list")
async def admin_promo_list(callback: CallbackQuery) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    promos = await get_all_promocodes()
    if not promos:
        await callback.answer("Промокодов нет.", show_alert=True)
        return

    lines = ["🎟 <b>Промокоды</b>\n"]
    for p in promos:
        status = "✅" if p["active"] else "❌"
        type_label = {
            "discount": f"скидка {p['value']}%",
            "days": f"+{p['value']} дней",
            "plan": "тариф",
        }.get(p["type"], p["type"])
        expires = p["expires_at"][:10] if p["expires_at"] else "∞"
        lines.append(
            f"{status} <code>{p['code']}</code> — {type_label} | "
            f"{p['used_count']}/{p['max_uses']} | до {expires}"
        )
    await callback.message.edit_text(
        "\n".join(lines), reply_markup=promocodes_keyboard(), parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "admin:promo_create")
async def admin_promo_create_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    await state.set_state(PromoCreateState.waiting_type)
    await callback.message.edit_text(
        "🎟 <b>Создать промокод</b>\n\nВыбери тип:",
        reply_markup=promo_type_keyboard(), parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("promo_type:"))
async def promo_type_selected(callback: CallbackQuery, state: FSMContext) -> None:
    promo_type = callback.data.split(":")[1]
    await state.update_data(promo_type=promo_type)

    if promo_type == "plan":
        # Выбор сервера для бесплатного тарифа
        await state.set_state(PromoCreateState.waiting_server)
        await callback.message.edit_text(
            "🎁 Выбери сервер для промокода:",
            reply_markup=server_select_keyboard("promo_srv"),
        )
    elif promo_type == "discount":
        # Выбор сервера для скидки (или все серверы)
        await state.set_state(PromoCreateState.waiting_server)
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🌍 Все серверы", callback_data="promo_srv:all"))
        for key, srv in SERVERS.items():
            builder.row(InlineKeyboardButton(
                text=srv["label"], callback_data=f"promo_srv:{key}",
            ))
        builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="admin:promocodes"))
        await callback.message.edit_text(
            "💰 На какой сервер скидка?",
            reply_markup=builder.as_markup(),
        )
    else:
        # Для days — сервер не нужен
        await state.update_data(server_key="all")
        await state.set_state(PromoCreateState.waiting_code)
        await callback.message.edit_text(
            "Введи <b>код промокода</b> (латиница, например WEEK7):\n/cancel — отмена.",
            parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(F.data.startswith("promo_srv:"))
async def promo_server_selected(callback: CallbackQuery, state: FSMContext) -> None:
    server_key = callback.data.split(":")[1]
    await state.update_data(server_key=server_key)
    data = await state.get_data()

    if data["promo_type"] == "plan":
        await state.set_state(PromoCreateState.waiting_plan)
        await callback.message.edit_text(
            "🎁 Выбери тариф для промокода:",
            reply_markup=plan_select_keyboard("promo_plan", server_key),
        )
    else:
        await state.set_state(PromoCreateState.waiting_code)
        await callback.message.edit_text(
            "Введи <b>код промокода</b> (латиница, например COOKIE20):\n/cancel — отмена.",
            parse_mode="HTML",
        )
    await callback.answer()


@router.callback_query(F.data.startswith("promo_plan:"))
async def promo_plan_selected(callback: CallbackQuery, state: FSMContext) -> None:
    parts = callback.data.split(":")
    plan_key = parts[2]
    await state.update_data(plan_key=plan_key)
    await state.set_state(PromoCreateState.waiting_code)
    await callback.message.edit_text(
        "Введи <b>код промокода</b> (латиница, например FREEVPN):\n/cancel — отмена.",
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(PromoCreateState.waiting_code)
async def promo_code_entered(message: Message, state: FSMContext) -> None:
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_keyboard())
        return
    code = message.text.strip().upper()
    if not code.replace("-", "").replace("_", "").isalnum():
        await message.answer("Код должен содержать только буквы и цифры.")
        return
    await state.update_data(code=code)
    data = await state.get_data()

    if data["promo_type"] == "plan":
        await state.set_state(PromoCreateState.waiting_uses)
        await message.answer(f"Код: <b>{code}</b>\nСколько раз можно использовать?", parse_mode="HTML")
    else:
        await state.set_state(PromoCreateState.waiting_value)
        hint = "процент скидки (1-99)" if data["promo_type"] == "discount" else "количество дней"
        await message.answer(f"Код: <b>{code}</b>\nВведи {hint}:", parse_mode="HTML")


@router.message(PromoCreateState.waiting_value)
async def promo_value_entered(message: Message, state: FSMContext) -> None:
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_keyboard())
        return
    try:
        value = int(message.text.strip())
    except ValueError:
        await message.answer("Введи число.")
        return
    await state.update_data(value=value)
    await state.set_state(PromoCreateState.waiting_uses)
    await message.answer("Сколько раз можно использовать? (например 1 или 1000):")


@router.message(PromoCreateState.waiting_uses)
async def promo_uses_entered(message: Message, state: FSMContext) -> None:
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_keyboard())
        return
    try:
        max_uses = int(message.text.strip())
    except ValueError:
        await message.answer("Введи число.")
        return

    data = await state.get_data()
    await state.clear()

    promo_type = data["promo_type"]
    code = data["code"]
    value = data.get("value", 0)
    server_key = data.get("server_key", "all")
    plan_key = data.get("plan_key", "1month")

    success = await create_promocode(
        code=code,
        type_=promo_type,
        value=value if promo_type != "plan" else 0,
        max_uses=max_uses,
        plan_key=plan_key if promo_type == "plan" else None,
    )

    if success:
        srv_label = SERVERS.get(server_key, {}).get("label", "Все серверы") if server_key != "all" else "Все серверы"
        type_label = {
            "discount": f"скидка {value}%",
            "days": f"+{value} дней",
            "plan": f"тариф {PLANS.get(plan_key, {}).get('label', plan_key)}",
        }.get(promo_type, promo_type)

        await message.answer(
            f"✅ <b>Промокод создан!</b>\n\n"
            f"🎟 Код: <code>{code}</code>\n"
            f"📦 Тип: {type_label}\n"
            f"🌍 Сервер: {srv_label}\n"
            f"🔢 Использований: {max_uses}",
            reply_markup=admin_keyboard(), parse_mode="HTML",
        )
    else:
        await message.answer(
            f"❌ Промокод <code>{code}</code> уже существует.",
            reply_markup=admin_keyboard(), parse_mode="HTML",
        )


@router.callback_query(F.data == "admin:promo_delete")
async def admin_promo_delete_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔", show_alert=True)
        return
    await state.set_state(PromoDeleteState.waiting_code)
    await callback.message.edit_text("❌ Введи код промокода для удаления:\n/cancel — отмена.")
    await callback.answer()


@router.message(PromoDeleteState.waiting_code)
async def promo_delete_apply(message: Message, state: FSMContext) -> None:
    if message.text == "/cancel":
        await state.clear()
        await message.answer("Отменено.", reply_markup=admin_keyboard())
        return
    code = message.text.strip().upper()
    await state.clear()
    await deactivate_promocode(code)
    await message.answer(
        f"✅ Промокод <code>{code}</code> деактивирован.",
        reply_markup=admin_keyboard(), parse_mode="HTML",
    )
