import aiosqlite
import asyncio
from datetime import datetime, timedelta
from typing import Optional

DB_PATH = "cookievpn.db"


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id          INTEGER PRIMARY KEY,
                tg_id       INTEGER UNIQUE NOT NULL,
                username    TEXT,
                full_name   TEXT,
                created_at  TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS subscriptions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id       INTEGER NOT NULL,
                xui_uuid    TEXT NOT NULL,
                xui_email   TEXT NOT NULL,
                plan_key    TEXT NOT NULL,
                started_at  TEXT NOT NULL,
                expires_at  TEXT NOT NULL,
                active      INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (tg_id) REFERENCES users(tg_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_id           INTEGER NOT NULL,
                plan_key        TEXT NOT NULL,
                amount          TEXT NOT NULL,
                currency        TEXT NOT NULL,
                payment_method  TEXT NOT NULL,
                payment_id      TEXT,
                status          TEXT NOT NULL DEFAULT 'pending',
                created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (tg_id) REFERENCES users(tg_id)
            )
        """)
        await db.commit()


async def upsert_user(tg_id: int, username: Optional[str], full_name: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (tg_id, username, full_name)
            VALUES (?, ?, ?)
            ON CONFLICT(tg_id) DO UPDATE SET
                username  = excluded.username,
                full_name = excluded.full_name
        """, (tg_id, username, full_name))
        await db.commit()


async def get_active_subscription(tg_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM subscriptions
            WHERE tg_id = ? AND active = 1
            ORDER BY expires_at DESC
            LIMIT 1
        """, (tg_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def create_subscription(
    tg_id: int,
    xui_uuid: str,
    xui_email: str,
    plan_key: str,
    days: int,
) -> dict:
    now = datetime.utcnow()
    expires = now + timedelta(days=days)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO subscriptions (tg_id, xui_uuid, xui_email, plan_key, started_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            tg_id, xui_uuid, xui_email, plan_key,
            now.isoformat(), expires.isoformat(),
        ))
        await db.commit()
    return {
        "tg_id": tg_id,
        "xui_uuid": xui_uuid,
        "xui_email": xui_email,
        "plan_key": plan_key,
        "started_at": now.isoformat(),
        "expires_at": expires.isoformat(),
    }


async def deactivate_subscription(tg_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE subscriptions SET active = 0
            WHERE tg_id = ? AND active = 1
        """, (tg_id,))
        await db.commit()


async def create_payment(
    tg_id: int,
    plan_key: str,
    amount: str,
    currency: str,
    payment_method: str,
    payment_id: Optional[str] = None,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO payments (tg_id, plan_key, amount, currency, payment_method, payment_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (tg_id, plan_key, amount, currency, payment_method, payment_id))
        await db.commit()
        return cursor.lastrowid


async def update_payment_status(payment_id: str, status: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE payments SET status = ? WHERE payment_id = ?
        """, (status, payment_id))
        await db.commit()


async def get_all_users() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users ORDER BY created_at DESC") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c:
            total_users = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM subscriptions WHERE active = 1") as c:
            active_subs = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM payments WHERE status = 'success'") as c:
            total_payments = (await c.fetchone())[0]
    return {
        "total_users": total_users,
        "active_subs": active_subs,
        "total_payments": total_payments,
    }
