"""SQLite baza (aiosqlite orqali async).

Ikkita jadval:
  users    — foydalanuvchilar (user_id, username, created_at)
  channels — qo'shilgan kanallar va ularning reklamasi
"""
import aiosqlite
from datetime import datetime
from typing import Optional

from config import DB_PATH


async def init_db():
    """Jadvallarni yaratadi (agar mavjud bo'lmasa)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT,
                created_at  TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id    INTEGER NOT NULL,
                username      TEXT,
                title         TEXT,
                subscribers   INTEGER DEFAULT 0,
                owner_id      INTEGER NOT NULL,
                ad_type       TEXT,           -- 'text' yoki 'premium'
                ad_text       TEXT,           -- HTML ko'rinishidagi matnli reklama
                ad_link       TEXT,           -- havola (t.me/...)
                stored_msg_id INTEGER,        -- premium post: message_id
                stored_chat_id INTEGER,       -- premium post: from_chat_id
                created_at    TEXT NOT NULL
            )
        """)
        # Eski bazaga yangi ustunlar — bor bo'lsa xato bermaydi
        for col_sql in (
            "ALTER TABLE channels ADD COLUMN for_sale INTEGER DEFAULT 0",
            "ALTER TABLE channels ADD COLUMN sale_price TEXT",
            "ALTER TABLE channels ADD COLUMN pm_tier INTEGER",
        ):
            try:
                await db.execute(col_sql)
            except Exception:
                pass
        # Reklama almashish takliflari
        await db.execute("""
            CREATE TABLE IF NOT EXISTS exchanges (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                from_pk      INTEGER NOT NULL,   -- taklif qiluvchining kanali (channels.id)
                to_pk        INTEGER NOT NULL,   -- taklif olgan kanal (channels.id)
                post_time    TEXT NOT NULL,      -- kelishilgan soat (masalan 21:00)
                status       TEXT DEFAULT 'pending',  -- pending/accepted/ready/rejected
                created_at   TEXT NOT NULL
            )
        """)
        # Eski bazaga yangi ustunlar (avto-joylash uchun)
        for col_sql in (
            "ALTER TABLE exchanges ADD COLUMN from_msg_id INTEGER",   # taklifchi reklamasi
            "ALTER TABLE exchanges ADD COLUMN from_chat_id INTEGER",
            "ALTER TABLE exchanges ADD COLUMN to_msg_id INTEGER",     # qabul qiluvchi reklamasi
            "ALTER TABLE exchanges ADD COLUMN to_chat_id INTEGER",
            "ALTER TABLE exchanges ADD COLUMN post_at TEXT",          # aniq joylash vaqti (ISO)
            "ALTER TABLE exchanges ADD COLUMN posted INTEGER DEFAULT 0",
            "ALTER TABLE exchanges ADD COLUMN pm_target INTEGER DEFAULT 0",  # nechta PM da o'chirish
        ):
            try:
                await db.execute(col_sql)
            except Exception:
                pass
        # Kanallarga joylangan reklamalar (PM sanash va avto-o'chirish uchun)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS posted_ads (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                exchange_id INTEGER NOT NULL,
                channel_id  INTEGER NOT NULL,   -- qaysi kanalga joylangan (tg id)
                message_id  INTEGER NOT NULL,   -- kanaldagi post id
                pm_target   INTEGER NOT NULL,   -- nechta PM da o'chiriladi
                posted_at   TEXT NOT NULL,
                deleted     INTEGER DEFAULT 0
            )
        """)
        # Majburiy obuna guruh/kanallari
        await db.execute("""
            CREATE TABLE IF NOT EXISTS force_subs (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id  INTEGER NOT NULL,
                username TEXT,
                title    TEXT,
                link     TEXT NOT NULL
            )
        """)
        await db.commit()


# ── Foydalanuvchilar ─────────────────────────────────────────────────────────

async def upsert_user(user_id: int, username: Optional[str]):
    """Foydalanuvchini qo'shadi yoki username ini yangilaydi."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, username, created_at)
            VALUES (?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET username = excluded.username
        """, (user_id, username, datetime.now().isoformat()))
        await db.commit()


async def get_user(user_id: int) -> Optional[dict]:
    """Bitta foydalanuvchi (muloqot havolasi uchun username kerak)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


# ── Kanallar ─────────────────────────────────────────────────────────────────

async def channel_exists(channel_id: int, owner_id: int) -> bool:
    """Shu egada shu kanal allaqachon bormi?"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM channels WHERE channel_id = ? AND owner_id = ?",
            (channel_id, owner_id),
        ) as cursor:
            return await cursor.fetchone() is not None


async def add_channel(
    channel_id: int,
    username: Optional[str],
    title: str,
    subscribers: int,
    owner_id: int,
) -> int:
    """Yangi kanalni bazaga yozadi va uning id sini qaytaradi."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO channels
                (channel_id, username, title, subscribers, owner_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (channel_id, username, title, subscribers, owner_id,
              datetime.now().isoformat()))
        await db.commit()
        return cursor.lastrowid


async def get_channel(channel_pk: int) -> Optional[dict]:
    """id (primary key) bo'yicha bitta kanalni qaytaradi."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM channels WHERE id = ?", (channel_pk,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_user_channels(owner_id: int) -> list[dict]:
    """Foydalanuvchining barcha kanallari."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM channels WHERE owner_id = ? ORDER BY created_at DESC",
            (owner_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def set_ad_text(channel_pk: int, ad_text: str, ad_link: str):
    """Matnli reklamani saqlaydi (HTML matn + havola)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE channels
            SET ad_type = 'text', ad_text = ?, ad_link = ?,
                stored_msg_id = NULL, stored_chat_id = NULL
            WHERE id = ?
        """, (ad_text, ad_link, channel_pk))
        await db.commit()


async def set_ad_premium(channel_pk: int, msg_id: int, chat_id: int):
    """Premium postni saqlaydi (copy_message uchun manzil)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE channels
            SET ad_type = 'premium', stored_msg_id = ?, stored_chat_id = ?,
                ad_text = NULL, ad_link = NULL
            WHERE id = ?
        """, (msg_id, chat_id, channel_pk))
        await db.commit()


async def delete_channel(channel_pk: int, owner_id: int) -> bool:
    """Kanalni o'chiradi (faqat egasi o'chira oladi)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM channels WHERE id = ? AND owner_id = ?",
            (channel_pk, owner_id),
        )
        await db.commit()
        return cursor.rowcount > 0


# ── Reklama almashish va sotuv ───────────────────────────────────────────────

async def get_other_channels(owner_id: int, limit: int = 30) -> list[dict]:
    """Boshqa foydalanuvchilarning kanallari (almashish ro'yxati uchun)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM channels WHERE owner_id != ? ORDER BY subscribers DESC LIMIT ?",
            (owner_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def set_for_sale(channel_pk: int, price: str):
    """Kanalni sotuvga qo'yadi (narxi bilan)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE channels SET for_sale = 1, sale_price = ? WHERE id = ?",
            (price, channel_pk),
        )
        await db.commit()


async def unset_for_sale(channel_pk: int):
    """Kanalni sotuvdan olib tashlaydi."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE channels SET for_sale = 0, sale_price = NULL WHERE id = ?",
            (channel_pk,),
        )
        await db.commit()


async def get_sale_channels(limit: int = 30) -> list[dict]:
    """Sotuvga qo'yilgan barcha kanallar."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM channels WHERE for_sale = 1 ORDER BY subscribers DESC LIMIT ?",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


# ── Almashish takliflari ─────────────────────────────────────────────────────

async def create_exchange(
    from_pk: int, to_pk: int, post_time: str,
    from_msg_id: int, from_chat_id: int, pm_target: int = 0,
) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO exchanges
                (from_pk, to_pk, post_time, from_msg_id, from_chat_id,
                 pm_target, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (from_pk, to_pk, post_time, from_msg_id, from_chat_id,
              pm_target, datetime.now().isoformat()))
        await db.commit()
        return cursor.lastrowid


async def get_exchange(exchange_id: int) -> Optional[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM exchanges WHERE id = ?", (exchange_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def set_exchange_status(exchange_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE exchanges SET status = ? WHERE id = ?",
            (status, exchange_id),
        )
        await db.commit()


async def set_exchange_to_ad(exchange_id: int, msg_id: int, chat_id: int,
                             post_at: str):
    """Qabul qiluvchining reklamasi keldi — kelishuv tayyor."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE exchanges
            SET to_msg_id = ?, to_chat_id = ?, post_at = ?, status = 'ready'
            WHERE id = ?
        """, (msg_id, chat_id, post_at, exchange_id))
        await db.commit()


async def set_exchange_from_ad(exchange_id: int, msg_id: int, chat_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE exchanges SET from_msg_id = ?, from_chat_id = ? WHERE id = ?",
            (msg_id, chat_id, exchange_id),
        )
        await db.commit()


async def update_exchange_ad(exchange_id: int, side: str, msg_id: int, chat_id: int):
    """side: 'from' yoki 'to' — o'sha tomon reklamasini yangilaydi."""
    col_msg = "from_msg_id" if side == "from" else "to_msg_id"
    col_chat = "from_chat_id" if side == "from" else "to_chat_id"
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE exchanges SET {col_msg} = ?, {col_chat} = ? WHERE id = ?",
            (msg_id, chat_id, exchange_id),
        )
        await db.commit()


async def set_exchange_time(exchange_id: int, post_time: str, post_at: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE exchanges SET post_time = ?, post_at = ? WHERE id = ?",
            (post_time, post_at, exchange_id),
        )
        await db.commit()


async def get_due_exchanges(now_iso: str) -> list[dict]:
    """Vaqti kelgan, hali joylanmagan kelishuvlar."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM exchanges
            WHERE status = 'ready' AND posted = 0 AND post_at <= ?
        """, (now_iso,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def mark_exchange_posted(exchange_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE exchanges SET posted = 1 WHERE id = ?", (exchange_id,)
        )
        await db.commit()


# ── Joylangan reklamalar (PM sanash uchun) ───────────────────────────────────

async def add_posted_ad(exchange_id: int, channel_id: int, message_id: int,
                        pm_target: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO posted_ads
                (exchange_id, channel_id, message_id, pm_target, posted_at)
            VALUES (?, ?, ?, ?, ?)
        """, (exchange_id, channel_id, message_id, pm_target,
              datetime.now().isoformat()))
        await db.commit()


async def get_active_posted_ads() -> list[dict]:
    """Hali o'chirilmagan, PM kuzatuvidagi reklamalar."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM posted_ads WHERE deleted = 0 AND pm_target > 0"
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def mark_ad_deleted(ad_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE posted_ads SET deleted = 1 WHERE id = ?", (ad_id,)
        )
        await db.commit()


async def get_channel_by_tg_id(channel_id: int) -> Optional[dict]:
    """Telegram channel_id bo'yicha kanalni topadi."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM channels WHERE channel_id = ? LIMIT 1", (channel_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


# ── PM darajasi (100/200/... ko'rish) ────────────────────────────────────────

async def set_pm_tier(channel_pk: int, tier: int):
    """Kanal egasi almashmoqchi bo'lgan PM (ko'rishlar) darajasi."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE channels SET pm_tier = ? WHERE id = ?", (tier, channel_pk)
        )
        await db.commit()


async def get_channels_by_tier(tier: int, exclude_owner: int) -> list[dict]:
    """Shu PM darajasini tanlagan boshqa kanallar (kichikdan kattaga)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM channels
            WHERE pm_tier = ? AND owner_id != ?
            ORDER BY subscribers ASC
        """, (tier, exclude_owner)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_other_channels_asc(owner_id: int, limit: int = 30) -> list[dict]:
    """Boshqalarning kanallari — kichikdan kattaga."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM channels WHERE owner_id != ? ORDER BY subscribers ASC LIMIT ?",
            (owner_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


# ── Majburiy obuna ───────────────────────────────────────────────────────────

async def add_force_sub(chat_id: int, username: Optional[str], title: str,
                        link: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO force_subs (chat_id, username, title, link)
            VALUES (?, ?, ?, ?)
        """, (chat_id, username, title, link))
        await db.commit()
        return cursor.lastrowid


async def get_force_subs() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM force_subs") as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def del_force_sub(sub_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM force_subs WHERE id = ?", (sub_id,))
        await db.commit()


# ── Admin panel uchun ────────────────────────────────────────────────────────

async def count_users() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def get_all_users(limit: int = 100) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM users ORDER BY created_at DESC LIMIT ?", (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_all_user_ids() -> list[int]:
    """Broadcast uchun barcha foydalanuvchi ID lari."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            rows = await cursor.fetchall()
            return [r[0] for r in rows]


async def count_channels() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM channels") as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def count_channels_by_type(ad_type: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM channels WHERE ad_type = ?", (ad_type,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def get_all_channels(limit: int = 50) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM channels ORDER BY created_at DESC LIMIT ?", (limit,)
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
