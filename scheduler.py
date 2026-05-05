"""
Планировщик задач:
- Каждый час проверяет истёкшие подписки и удаляет клиентов из x-ui
- За 3 дня до истечения отправляет напоминание
"""
import asyncio
import logging
from datetime import datetime, timedelta

import aiosqlite
from aiogram import Bot

from database import DB_PATH
from xui_client import xui

logger = logging.getLogger(__name__)


async def check_expired_subscriptions(bot: Bot) -> None:
    """Деактивирует истёкшие подписки и удаляет клиентов из x-ui."""
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM subscriptions
            WHERE active = 1 AND expires_at <= ?
        """, (now,)) as cursor:
            expired = await cursor.fetchall()

        for sub in expired:
            sub = dict(sub)
            # Удаляем из x-ui
            deleted = await xui.delete_client(sub["xui_uuid"])
            logger.info(f"Удалён клиент {sub['xui_email']}: {deleted}")

            # Деактивируем в БД
            await db.execute(
                "UPDATE subscriptions SET active = 0 WHERE id = ?",
                (sub["id"],),
            )

            # Уведомляем пользователя
            try:
                await bot.send_message(
                    sub["tg_id"],
                    "⚠️ <b>Твоя подписка CookieVPN истекла.</b>\n\n"
                    "Для продления нажми /start и выбери тариф.",
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.warning(f"Не удалось уведомить {sub['tg_id']}: {e}")

        await db.commit()


async def send_expiry_reminders(bot: Bot) -> None:
    """Отправляет напоминание за 3 дня до истечения подписки."""
    remind_before = (datetime.utcnow() + timedelta(days=3)).isoformat()
    now = datetime.utcnow().isoformat()

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM subscriptions
            WHERE active = 1
              AND expires_at <= ?
              AND expires_at > ?
        """, (remind_before, now)) as cursor:
            expiring = await cursor.fetchall()

        for sub in expiring:
            sub = dict(sub)
            expires = datetime.fromisoformat(sub["expires_at"])
            days_left = (expires - datetime.utcnow()).days

            # Проверяем, не отправляли ли уже напоминание сегодня
            today = datetime.utcnow().date().isoformat()
            async with db.execute("""
                SELECT 1 FROM payments
                WHERE tg_id = ? AND status = 'reminder_sent' AND DATE(created_at) = ?
            """, (sub["tg_id"], today)) as c:
                already_sent = await c.fetchone()

            if already_sent:
                continue

            try:
                await bot.send_message(
                    sub["tg_id"],
                    f"⏰ <b>Напоминание CookieVPN</b>\n\n"
                    f"Твоя подписка истекает через <b>{days_left} дн.</b>\n"
                    f"Не забудь продлить, чтобы не потерять доступ!\n\n"
                    f"Нажми /start для продления.",
                    parse_mode="HTML",
                )
                # Помечаем что напоминание отправлено
                await db.execute("""
                    INSERT INTO payments (tg_id, plan_key, amount, currency, payment_method, status)
                    VALUES (?, 'reminder', '0', 'NONE', 'system', 'reminder_sent')
                """, (sub["tg_id"],))
                await db.commit()
            except Exception as e:
                logger.warning(f"Не удалось отправить напоминание {sub['tg_id']}: {e}")


async def run_scheduler(bot: Bot) -> None:
    """Запускает планировщик в фоне."""
    logger.info("Планировщик запущен")
    while True:
        try:
            await check_expired_subscriptions(bot)
            await send_expiry_reminders(bot)
        except Exception as e:
            logger.error(f"Ошибка планировщика: {e}")
        await asyncio.sleep(3600)  # каждый час
