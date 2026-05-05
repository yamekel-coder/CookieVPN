import aiosqlite
from datetime import datetime, timedelta
from typing import Optional

DB_PATH = "cookievpn.db"


async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id              INTEGER PRIMARY KEY,
                tg_id           INTEGER UNIQUE NOT NULL,
                username        TEXT,
                full_name       TEXT,
                referred_by     INTEGER,
                trial_used      INTEGER NOT NULL DEFAULT 0,
                bonus_days      INTEGER NOT NULL DEFAULT 0,
                created_at      TEXT NOT NULL DEFAULT (datetime('now'))
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
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promocodes (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                code            TEXT UNIQUE NOT NULL,
                type            TEXT NOT NULL,
                value           INTEGER NOT NULL,
                max_uses        INTEGER NOT NULL DEFAULT 1,
                used_count      INTEGER NOT NULL DEFAULT 0,
                expires_at      TEXT,
                active          INTEGER NOT NULL DEFAULT 1,
                created_at      TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS promocode_uses (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                code            TEXT NOT NULL,
                tg_id           INTEGER NOT NULL,
                used_at         TEXT NOT NULL DEFAULT (datetime('now')),
                UNIQUE(code, tg_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS referrals (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                inviter_id      INTEGER NOT NULL,
                invited_id      INTEGER NOT NULL UNIQUE,
                vpn_activated   INTEGER NOT NULL DEFAULT 0,
                bonus_credited  INTEGER NOT NULL DEFAULT 0,
                created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                FOREIGN KEY (inviter_id) REFERENCES users(tg_id),
                FOREIGN KEY (invited_id) REFERENCES users(tg_id)
            )
        """)
        # Миграция: добавляем колонки если их нет (для существующих БД)
        for col, definition in [
            ("referred_by", "INTEGER"),
            ("trial_used", "INTEGER NOT NULL DEFAULT 0"),
            ("bonus_days", "INTEGER NOT NULL DEFAULT 0"),
        ]:
            try:
                await db.execute(f"ALTER TABLE users ADD COLUMN {col} {definition}")
            except Exception:
                pass
        await db.commit()


async def upsert_user(
    tg_id: int,
    username: Optional[str],
    full_name: str,
    referred_by: Optional[int] = None,
) -> bool:
    """Возвращает True если пользователь новый."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id FROM users WHERE tg_id = ?", (tg_id,)) as c:
            existing = await c.fetchone()
        if existing:
            await db.execute(
                "UPDATE users SET username=?, full_name=? WHERE tg_id=?",
                (username, full_name, tg_id),
            )
            await db.commit()
            return False
        await db.execute(
            "INSERT INTO users (tg_id, username, full_name, referred_by) VALUES (?,?,?,?)",
            (tg_id, username, full_name, referred_by),
        )
        # Записываем реферала
        if referred_by and referred_by != tg_id:
            await db.execute(
                "INSERT OR IGNORE INTO referrals (inviter_id, invited_id) VALUES (?,?)",
                (referred_by, tg_id),
            )
        await db.commit()
        return True


async def get_user(tg_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE tg_id=?", (tg_id,)) as c:
            row = await c.fetchone()
            return dict(row) if row else None


async def get_active_subscription(tg_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM subscriptions
            WHERE tg_id=? AND active=1
            ORDER BY expires_at DESC LIMIT 1
        """, (tg_id,)) as c:
            row = await c.fetchone()
            return dict(row) if row else None


async def create_subscription(
    tg_id: int, xui_uuid: str, xui_email: str, plan_key: str, days: int,
) -> dict:
    now = datetime.utcnow()
    expires = now + timedelta(days=days)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO subscriptions (tg_id, xui_uuid, xui_email, plan_key, started_at, expires_at)
            VALUES (?,?,?,?,?,?)
        """, (tg_id, xui_uuid, xui_email, plan_key, now.isoformat(), expires.isoformat()))
        await db.commit()
    return {
        "tg_id": tg_id, "xui_uuid": xui_uuid, "xui_email": xui_email,
        "plan_key": plan_key, "started_at": now.isoformat(), "expires_at": expires.isoformat(),
    }


async def extend_subscription(tg_id: int, days: int) -> Optional[str]:
    """Продлевает активную подписку на N дней. Возвращает новую дату."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM subscriptions WHERE tg_id=? AND active=1 ORDER BY expires_at DESC LIMIT 1",
            (tg_id,)
        ) as c:
            sub = await c.fetchone()
        if not sub:
            return None
        sub = dict(sub)
        old_expires = datetime.fromisoformat(sub["expires_at"])
        new_expires = max(old_expires, datetime.utcnow()) + timedelta(days=days)
        await db.execute(
            "UPDATE subscriptions SET expires_at=? WHERE id=?",
            (new_expires.isoformat(), sub["id"])
        )
        await db.commit()
        return new_expires.isoformat()


async def is_trial_used(tg_id: int) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT trial_used FROM users WHERE tg_id=?", (tg_id,)) as c:
            row = await c.fetchone()
            return bool(row[0]) if row else False


async def mark_trial_used(tg_id: int) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET trial_used=1 WHERE tg_id=?", (tg_id,))
        await db.commit()


async def get_referral_stats(tg_id: int) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM referrals WHERE inviter_id=?", (tg_id,)
        ) as c:
            total = (await c.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM referrals WHERE inviter_id=? AND vpn_activated=1", (tg_id,)
        ) as c:
            activated = (await c.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM referrals WHERE inviter_id=? AND bonus_credited=1", (tg_id,)
        ) as c:
            credited = (await c.fetchone())[0]
    return {"total": total, "activated": activated, "credited": credited}


async def credit_referral_bonus(invited_id: int, referral_days: int) -> Optional[int]:
    """
    Засчитывает бонус пригласившему когда реферал активировал VPN.
    Возвращает tg_id пригласившего или None.
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM referrals WHERE invited_id=? AND bonus_credited=0", (invited_id,)
        ) as c:
            ref = await c.fetchone()
        if not ref:
            return None
        ref = dict(ref)
        inviter_id = ref["inviter_id"]
        # Помечаем vpn_activated и bonus_credited
        await db.execute(
            "UPDATE referrals SET vpn_activated=1, bonus_credited=1 WHERE id=?", (ref["id"],)
        )
        # Добавляем бонусные дни в users
        await db.execute(
            "UPDATE users SET bonus_days = bonus_days + ? WHERE tg_id=?",
            (referral_days, inviter_id)
        )
        await db.commit()
        return inviter_id


async def create_payment(
    tg_id: int, plan_key: str, amount: str, currency: str,
    payment_method: str, payment_id: Optional[str] = None,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO payments (tg_id, plan_key, amount, currency, payment_method, payment_id)
            VALUES (?,?,?,?,?,?)
        """, (tg_id, plan_key, amount, currency, payment_method, payment_id))
        await db.commit()
        return cursor.lastrowid


async def update_payment_status(payment_id: str, status: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE payments SET status=? WHERE payment_id=?", (status, payment_id))
        await db.commit()


async def get_all_users() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users ORDER BY created_at DESC") as c:
            return [dict(r) for r in await c.fetchall()]


async def get_stats() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as c:
            total_users = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM subscriptions WHERE active=1") as c:
            active_subs = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM payments WHERE status='success'") as c:
            total_payments = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM referrals") as c:
            total_refs = (await c.fetchone())[0]
        async with db.execute(
            "SELECT COUNT(*) FROM users WHERE created_at >= datetime('now', '-1 day')"
        ) as c:
            new_today = (await c.fetchone())[0]
    return {
        "total_users": total_users,
        "active_subs": active_subs,
        "total_payments": total_payments,
        "total_refs": total_refs,
        "new_today": new_today,
    }


# ─── Промокоды ────────────────────────────────────────────────────────────────

async def create_promocode(
    code: str,
    type_: str,       # "discount" | "days" | "plan"
    value: int,       # % скидки | кол-во дней | 0 (для plan)
    max_uses: int = 1,
    expires_at: Optional[str] = None,
    plan_key: Optional[str] = None,
) -> bool:
    """Создаёт промокод. Возвращает False если код уже существует."""
    async with aiosqlite.connect(DB_PATH) as db:
        try:
            await db.execute("""
                INSERT INTO promocodes (code, type, value, max_uses, expires_at)
                VALUES (?, ?, ?, ?, ?)
            """, (code.upper(), type_, value, max_uses, expires_at))
            await db.commit()
            return True
        except Exception:
            return False


async def get_promocode(code: str) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM promocodes WHERE code=? AND active=1", (code.upper(),)
        ) as c:
            row = await c.fetchone()
            return dict(row) if row else None


async def use_promocode(code: str, tg_id: int) -> tuple[bool, str]:
    """
    Применяет промокод для пользователя.
    Возвращает (успех, сообщение об ошибке или тип промокода).
    """
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM promocodes WHERE code=? AND active=1", (code.upper(),)
        ) as c:
            promo = await c.fetchone()

        if not promo:
            return False, "Промокод не найден или неактивен."

        promo = dict(promo)

        # Проверяем срок действия
        if promo["expires_at"]:
            if datetime.utcnow().isoformat() > promo["expires_at"]:
                return False, "Промокод истёк."

        # Проверяем лимит использований
        if promo["used_count"] >= promo["max_uses"]:
            return False, "Промокод уже использован максимальное количество раз."

        # Проверяем не использовал ли этот юзер
        async with db.execute(
            "SELECT 1 FROM promocode_uses WHERE code=? AND tg_id=?", (code.upper(), tg_id)
        ) as c:
            already = await c.fetchone()
        if already:
            return False, "Ты уже использовал этот промокод."

        # Применяем
        await db.execute(
            "INSERT INTO promocode_uses (code, tg_id) VALUES (?, ?)", (code.upper(), tg_id)
        )
        await db.execute(
            "UPDATE promocodes SET used_count = used_count + 1 WHERE code=?", (code.upper(),)
        )
        await db.commit()
        return True, promo["type"]


async def get_all_promocodes() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM promocodes ORDER BY created_at DESC"
        ) as c:
            return [dict(r) for r in await c.fetchall()]


async def deactivate_promocode(code: str) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE promocodes SET active=0 WHERE code=?", (code.upper(),)
        )
        await db.commit()
        return True


async def give_plan_to_user(tg_id: int, plan_key: str, days: int) -> dict:
    """Выдаёт тариф пользователю напрямую (без оплаты)."""
    from xui_client import xui
    client = await xui.add_client(tg_id=tg_id, plan_key=plan_key, expire_days=days)
    sub = await create_subscription(
        tg_id=tg_id,
        xui_uuid=client["uuid"],
        xui_email=client["email"],
        plan_key=plan_key,
        days=days,
    )
    return {**sub, "link": client["link"]}
