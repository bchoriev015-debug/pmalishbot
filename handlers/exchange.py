"""Reklama almashish oqimi.

1. 🔄 bosiladi → (bir nechta kanali bo'lsa) o'z kanalini tanlaydi
2. PM (ko'rishlar) darajasini tanlaydi: 100/200/300/400/500/1K
3. Shu PM ni tanlagan kanallar chiqadi (bo'lmasa — hammasi, kichikdan kattaga)
4. Kanal tanlanadi → soat so'raladi → TAYYOR reklama posti so'raladi
   (havola matnga yopishtirilgan bo'ladi — bot unga TEGMAYDI)
5. Kanal egasiga so'rov boradi → u qabul qilsa, o'z reklamasini yuboradi
6. Belgilangan soatda bot IKKALA kanalga ham reklamalarni o'zi joylaydi
   (copy_message — ism yashirin, premium emoji va havolalar saqlanadi)
"""
import asyncio
import logging
import re
from datetime import datetime, timedelta

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from states import ExchangeState
from keyboards import (
    back_kb,
    exchange_own_kb,
    pm_tiers_kb,
    channels_list_kb,
    offer_kb,
    deal_kb,
)
import database as db

router = Router()
logger = logging.getLogger(__name__)
# Faqat shaxsiy chat
router.message.filter(F.chat.type == "private")
router.callback_query.filter(F.message.chat.type == "private")

_TIME_RE = re.compile(r"^([01]?\d|2[0-3]):[0-5]\d$")


def next_post_at(post_time: str) -> str:
    """HH:MM dan keyingi eng yaqin sanani (ISO) hisoblaydi."""
    hour, minute = map(int, post_time.split(":"))
    now = datetime.now()
    dt = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if dt <= now:
        dt += timedelta(days=1)
    return dt.isoformat()


async def bot_can_post(bot: Bot, channel_id: int) -> bool:
    """Bot kanalda admin va post joylay oladimi?
    (Egasi botni kanaldan chiqarib yuborgan bo'lishi mumkin.)"""
    try:
        me = await bot.get_me()
        m = await bot.get_chat_member(channel_id, me.id)
        return m.status == "administrator" and bool(
            getattr(m, "can_post_messages", False))
    except Exception:
        return False


# ── 1. Boshlash: o'z kanalini tanlash ────────────────────────────────────────

@router.callback_query(F.data == "exchange")
async def exchange_start(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    my_channels = await db.get_user_channels(callback.from_user.id)

    if not my_channels:
        await callback.message.edit_text(
            "🔄 <b>Reklama almashish</b>\n\n"
            "Avval kanalingizni qo'shing.",
            reply_markup=back_kb(),
        )
        await callback.answer()
        return

    if len(my_channels) == 1:
        await state.update_data(own_pk=my_channels[0]["id"])
        await callback.message.edit_text(
            "🔄 <b>Reklama almashish</b>\n\n"
            "Nechta PM (ko'rish) ga almashasiz?",
            reply_markup=pm_tiers_kb(),
        )
    else:
        await callback.message.edit_text(
            "🔄 <b>Reklama almashish</b>\n\n"
            "Qaysi kanalingiz uchun almashasiz?",
            reply_markup=exchange_own_kb(my_channels),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("ex_own:"))
async def exchange_own_chosen(callback: CallbackQuery, state: FSMContext):
    pk = int(callback.data.split(":")[1])
    ch = await db.get_channel(pk)
    if not ch or ch["owner_id"] != callback.from_user.id:
        await callback.answer("Topilmadi.", show_alert=True)
        return
    await state.update_data(own_pk=pk)
    await callback.message.edit_text(
        "🔄 <b>Reklama almashish</b>\n\n"
        "Nechta PM (ko'rish) ga almashasiz?",
        reply_markup=pm_tiers_kb(),
    )
    await callback.answer()


# ── 2. PM darajasi va kanal tanlash ──────────────────────────────────────────

@router.callback_query(F.data.startswith("ex_pm:"))
async def pm_tier_chosen(callback: CallbackQuery, state: FSMContext):
    tier = int(callback.data.split(":")[1])
    data = await state.get_data()
    own_pk = data.get("own_pk")
    if not own_pk:
        await callback.answer("Avval boshidan boshlang.", show_alert=True)
        return

    # O'z kanaliga PM darajasini yozamiz (boshqalar topishi uchun)
    await db.set_pm_tier(own_pk, tier)
    await state.update_data(tier=tier)

    tier_label = "1K" if tier == 1000 else str(tier)
    channels = await db.get_channels_by_tier(tier, callback.from_user.id)

    if channels:
        text = (f"🔄 <b>{tier_label} PM ga almashadigan kanallar:</b>\n\n"
                "Kanalni tanlang:")
    else:
        # Hech kim bu PM ni tanlamagan — hamma kanallar (kichikdan kattaga)
        channels = await db.get_other_channels_asc(callback.from_user.id)
        if not channels:
            await callback.message.edit_text(
                "🔄 Hozircha boshqa kanallar yo'q.\n"
                "Keyinroq qayta kirib ko'ring.",
                reply_markup=back_kb(),
            )
            await callback.answer()
            return
        text = (f"🔄 <b>{tier_label} PM ni hali hech kim tanlamagan.</b>\n\n"
                "Barcha kanallar (kichikdan kattaga):")

    await callback.message.edit_text(
        text, reply_markup=channels_list_kb(channels, "ex_pick"))
    await callback.answer()


@router.callback_query(F.data.startswith("ex_pick:"))
async def target_chosen(callback: CallbackQuery, state: FSMContext, bot: Bot):
    pk = int(callback.data.split(":")[1])
    ch = await db.get_channel(pk)
    if not ch:
        await callback.answer("Kanal topilmadi.", show_alert=True)
        return

    # Bot o'sha kanalda hali ham admin ekanini tekshiramiz
    if not await bot_can_post(bot, ch["channel_id"]):
        await callback.answer(
            "⚠️ Bu kanalga joylab bo'lmaydi — bot u yerdan chiqarilgan. "
            "Boshqa kanal tanlang.",
            show_alert=True,
        )
        return

    # O'z kanalimizda ham bot adminligini tekshiramiz
    data = await state.get_data()
    own = await db.get_channel(data.get("own_pk", 0))
    if own and not await bot_can_post(bot, own["channel_id"]):
        await callback.answer(
            "⚠️ Botni avval o'z kanalingizga qayta admin qiling "
            "(bot kanalingizdan chiqarilgan).",
            show_alert=True,
        )
        return

    await state.update_data(target_pk=pk)
    await state.set_state(ExchangeState.waiting_time)
    await callback.message.edit_text(
        f"📢 <b>{ch['title']}</b> — {ch['subscribers']} obunachi\n\n"
        "⏰ <b>Soat nechida almashamiz?</b>\n"
        "Vaqtni yozing. Masalan: <code>21:00</code>",
        reply_markup=back_kb(),
    )
    await callback.answer()


# ── 3. Soat va tayyor reklama ────────────────────────────────────────────────

@router.message(ExchangeState.waiting_time, F.text)
async def time_got(message: Message, state: FSMContext):
    post_time = message.text.strip()
    if not _TIME_RE.match(post_time):
        await message.answer(
            "❌ Vaqt noto'g'ri.\n\nMasalan: <code>21:00</code>",
            reply_markup=back_kb(),
        )
        return

    await state.update_data(post_time=post_time)
    await state.set_state(ExchangeState.waiting_ad)
    await message.answer(
        "📝 <b>Endi tayyor reklamangizni yuboring.</b>\n\n"
        "Havolani matnning ichiga <b>o'zingiz</b> yopishtiring\n"
        "(matnni belgilab → «Havola qo'shish»).\n\n"
        "Bot postingizni <b>qanday bo'lsa shunday</b>, ismingizni\n"
        "yashirib, kanalga joylaydi — premium emoji buzilmaydi.",
        reply_markup=back_kb(),
    )


@router.message(ExchangeState.waiting_ad)
async def ad_got(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    own_pk = data.get("own_pk")
    target_pk = data.get("target_pk")
    post_time = data.get("post_time")
    await state.clear()

    my_ch = await db.get_channel(own_pk)
    target = await db.get_channel(target_pk)
    if not my_ch or not target:
        await message.answer("❌ Kanal topilmadi.", reply_markup=back_kb())
        return

    exchange_id = await db.create_exchange(
        own_pk, target_pk, post_time,
        from_msg_id=message.message_id, from_chat_id=message.chat.id,
        pm_target=data.get("tier", 0),
    )

    sender = message.from_user
    who = f"@{sender.username}" if sender.username else sender.full_name
    uname = f"@{my_ch['username']}" if my_ch["username"] else "—"

    try:
        # Taklif kartasi
        await bot.send_message(
            target["owner_id"],
            "🔄 <b>Reklama almashish taklifi!</b>\n\n"
            f"👤 Kimdan: <b>{who}</b>\n"
            f"📢 Kanali: <b>{my_ch['title']}</b> ({uname})\n"
            f"👥 {my_ch['subscribers']} obunachi\n"
            f"⏰ Vaqt: <b>{post_time}</b>\n\n"
            "Reklamasi 👇",
        )
        # Reklama namunasi (aynan o'zi)
        await bot.copy_message(
            chat_id=target["owner_id"],
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )
        await bot.send_message(
            target["owner_id"],
            f"Qabul qilsangiz, bot soat <b>{post_time}</b> da\n"
            f"shu reklamani <b>{target['title']}</b> kanalingizga,\n"
            "sizning reklamangizni esa ularning kanaliga\n"
            "<b>avtomatik</b> joylaydi.\n\n"
            "Qabul qilasizmi?",
            reply_markup=offer_kb(exchange_id, sender.id),
        )
    except Exception:
        await message.answer(
            "❌ Taklif yetib bormadi — kanal egasi botni hali "
            "ishga tushirmagan.\n\n"
            "«Sotiladigan kanallar» yoki keyinroq qayta urining.",
            reply_markup=back_kb(),
        )
        return

    await message.answer(
        f"✅ <b>Taklif yuborildi!</b>\n\n"
        f"📢 {target['title']} egasining javobini kutamiz — "
        "xabar beraman.",
        reply_markup=back_kb(),
    )


# ── 4. Qabul qilish / rad etish ──────────────────────────────────────────────

@router.callback_query(F.data.startswith("exo_acc:"))
async def offer_accept(callback: CallbackQuery, state: FSMContext):
    exchange_id = int(callback.data.split(":")[1])
    ex = await db.get_exchange(exchange_id)
    if not ex or ex["status"] != "pending":
        await callback.answer("Bu taklifga allaqachon javob berilgan.", show_alert=True)
        return

    to_ch = await db.get_channel(ex["to_pk"])
    if not to_ch or to_ch["owner_id"] != callback.from_user.id:
        await callback.answer("Bu taklif sizga emas.", show_alert=True)
        return

    # Bot kanalingizda hali ham admin bo'lishi shart (joylash uchun)
    if not await bot_can_post(callback.bot, to_ch["channel_id"]):
        await callback.answer(
            "⚠️ Bot kanalingizda admin emas!\n\n"
            "Avval botni kanalingizga qayta admin qiling, "
            "keyin qabul qiling.",
            show_alert=True,
        )
        return

    await db.set_exchange_status(exchange_id, "accepted")
    await state.set_state(ExchangeState.waiting_accept_ad)
    await state.update_data(exchange_id=exchange_id)

    await callback.message.edit_text(
        "✅ <b>Qabul qildingiz!</b>\n\n"
        "📝 Endi <b>o'z reklamangizni</b> yuboring —\n"
        "havolani matnga o'zingiz yopishtiring.\n\n"
        "Bot uni ularning kanaliga avtomatik joylaydi."
    )
    await callback.answer()


@router.message(ExchangeState.waiting_accept_ad)
async def accept_ad_got(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    exchange_id = data.get("exchange_id")
    await state.clear()

    ex = await db.get_exchange(exchange_id) if exchange_id else None
    if not ex or ex["status"] != "accepted":
        await message.answer("❌ Kelishuv topilmadi.", reply_markup=back_kb())
        return

    from_ch = await db.get_channel(ex["from_pk"])
    to_ch = await db.get_channel(ex["to_pk"])
    post_at = next_post_at(ex["post_time"])
    await db.set_exchange_to_ad(
        exchange_id, message.message_id, message.chat.id, post_at)

    pm_line = ""
    if ex.get("pm_target"):
        pm_line = (f"\n📊 Har bir reklama <b>{ex['pm_target']} PM</b> ga "
                   "yetganda avtomatik o'chiriladi.")
    deal_text = (
        "🤝 <b>Kelishuv tayyor!</b>\n\n"
        f"📢 {from_ch['title']} ⇄ {to_ch['title']}\n"
        f"⏰ Soat <b>{ex['post_time']}</b> da bot reklamalarni\n"
        "ikkala kanalga <b>avtomatik</b> joylaydi."
        + pm_line
    )

    # Qabul qiluvchiga
    await message.answer(
        deal_text, reply_markup=deal_kb(exchange_id, from_ch["owner_id"]))

    # Taklif qiluvchiga: sherik reklamasi + kelishuv
    try:
        await bot.send_message(
            from_ch["owner_id"],
            f"🎉 <b>{to_ch['title']}</b> taklifingizni qabul qildi!\n\n"
            "Ularning reklamasi 👇",
        )
        await bot.copy_message(
            chat_id=from_ch["owner_id"],
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )
        await bot.send_message(
            from_ch["owner_id"],
            deal_text,
            reply_markup=deal_kb(exchange_id, to_ch["owner_id"]),
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith("exo_rej:"))
async def offer_reject(callback: CallbackQuery, bot: Bot):
    exchange_id = int(callback.data.split(":")[1])
    ex = await db.get_exchange(exchange_id)
    if not ex or ex["status"] != "pending":
        await callback.answer("Bu taklifga allaqachon javob berilgan.", show_alert=True)
        return

    from_ch = await db.get_channel(ex["from_pk"])
    to_ch = await db.get_channel(ex["to_pk"])
    if not to_ch or to_ch["owner_id"] != callback.from_user.id:
        await callback.answer("Bu taklif sizga emas.", show_alert=True)
        return

    await db.set_exchange_status(exchange_id, "rejected")
    await callback.message.edit_text("❌ Taklif rad etildi.")

    if from_ch:
        try:
            await bot.send_message(
                from_ch["owner_id"],
                f"❌ <b>{to_ch['title']}</b> taklifingizni rad etdi.",
            )
        except Exception:
            pass
    await callback.answer("Rad etildi.")


# ── 5. Kelishuvni boshqarish: reklama / vaqt o'zgartirish ────────────────────

async def _check_participant(callback: CallbackQuery, exchange_id: int):
    """Foydalanuvchi kelishuv qatnashchisimi? (ex, side) qaytaradi."""
    ex = await db.get_exchange(exchange_id)
    if not ex:
        await callback.answer("Kelishuv topilmadi.", show_alert=True)
        return None, None
    if ex.get("posted"):
        await callback.answer("Reklamalar allaqachon joylangan.", show_alert=True)
        return None, None

    from_ch = await db.get_channel(ex["from_pk"])
    to_ch = await db.get_channel(ex["to_pk"])
    uid = callback.from_user.id
    if from_ch and from_ch["owner_id"] == uid:
        return ex, "from"
    if to_ch and to_ch["owner_id"] == uid:
        return ex, "to"
    await callback.answer("Bu kelishuv sizniki emas.", show_alert=True)
    return None, None


@router.callback_query(F.data.startswith("exch_ad:"))
async def change_ad_start(callback: CallbackQuery, state: FSMContext):
    exchange_id = int(callback.data.split(":")[1])
    ex, side = await _check_participant(callback, exchange_id)
    if not ex:
        return
    await state.set_state(ExchangeState.waiting_new_ad)
    await state.update_data(exchange_id=exchange_id, side=side)
    await callback.message.answer(
        "✏️ <b>Yangi reklamangizni yuboring</b>\n\n"
        "Havolani matnga o'zingiz yopishtiring.",
        reply_markup=back_kb(),
    )
    await callback.answer()


@router.message(ExchangeState.waiting_new_ad)
async def new_ad_got(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    exchange_id = data.get("exchange_id")
    side = data.get("side")
    if not exchange_id or not side:
        await message.answer("❌ Kelishuv topilmadi.", reply_markup=back_kb())
        return

    await db.update_exchange_ad(
        exchange_id, side, message.message_id, message.chat.id)
    await message.answer("✅ <b>Reklama yangilandi!</b>", reply_markup=back_kb())


@router.callback_query(F.data.startswith("exch_time:"))
async def change_time_start(callback: CallbackQuery, state: FSMContext):
    exchange_id = int(callback.data.split(":")[1])
    ex, side = await _check_participant(callback, exchange_id)
    if not ex:
        return
    await state.set_state(ExchangeState.waiting_new_time)
    await state.update_data(exchange_id=exchange_id)
    await callback.message.answer(
        "⏰ <b>Yangi vaqtni yozing.</b>\n\nMasalan: <code>22:30</code>",
        reply_markup=back_kb(),
    )
    await callback.answer()


@router.message(ExchangeState.waiting_new_time, F.text)
async def new_time_got(message: Message, state: FSMContext, bot: Bot):
    post_time = message.text.strip()
    if not _TIME_RE.match(post_time):
        await message.answer(
            "❌ Vaqt noto'g'ri.\n\nMasalan: <code>22:30</code>",
            reply_markup=back_kb(),
        )
        return

    data = await state.get_data()
    await state.clear()
    exchange_id = data.get("exchange_id")
    ex = await db.get_exchange(exchange_id) if exchange_id else None
    if not ex:
        await message.answer("❌ Kelishuv topilmadi.", reply_markup=back_kb())
        return

    post_at = next_post_at(post_time) if ex["status"] == "ready" else None
    await db.set_exchange_time(exchange_id, post_time, post_at)
    await message.answer(
        f"✅ Vaqt <b>{post_time}</b> ga o'zgartirildi!",
        reply_markup=back_kb(),
    )

    # Ikkinchi tomonga xabar beramiz
    from_ch = await db.get_channel(ex["from_pk"])
    to_ch = await db.get_channel(ex["to_pk"])
    uid = message.from_user.id
    other = None
    if from_ch and from_ch["owner_id"] != uid:
        other = from_ch["owner_id"]
    elif to_ch and to_ch["owner_id"] != uid:
        other = to_ch["owner_id"]
    if other:
        try:
            await bot.send_message(
                other,
                f"⏰ Kelishuv vaqti <b>{post_time}</b> ga o'zgartirildi.",
            )
        except Exception:
            pass


# ── 6. Avto-joylash (rejalashtiruvchi) ───────────────────────────────────────

async def _post_exchange(bot: Bot, ex: dict):
    """Vaqti kelgan kelishuvni ikkala kanalga joylaydi."""
    from_ch = await db.get_channel(ex["from_pk"])
    to_ch = await db.get_channel(ex["to_pk"])
    if not from_ch or not to_ch:
        await db.mark_exchange_posted(ex["id"])
        return

    pm_target = ex.get("pm_target") or 0
    failed = []
    # Taklifchining reklamasi -> qabul qiluvchining kanaliga
    try:
        posted = await bot.copy_message(
            chat_id=to_ch["channel_id"],
            from_chat_id=ex["from_chat_id"],
            message_id=ex["from_msg_id"],
        )
        if pm_target:
            await db.add_posted_ad(
                ex["id"], to_ch["channel_id"], posted.message_id, pm_target)
    except Exception:
        failed.append(to_ch["title"])
    # Qabul qiluvchining reklamasi -> taklifchining kanaliga
    try:
        posted = await bot.copy_message(
            chat_id=from_ch["channel_id"],
            from_chat_id=ex["to_chat_id"],
            message_id=ex["to_msg_id"],
        )
        if pm_target:
            await db.add_posted_ad(
                ex["id"], from_ch["channel_id"], posted.message_id, pm_target)
    except Exception:
        failed.append(from_ch["title"])

    await db.mark_exchange_posted(ex["id"])

    # Egalariga xabar
    if not failed:
        text = (
            "✅ <b>Reklamalar kanallarga joylandi!</b>\n\n"
            f"📢 {from_ch['title']} ⇄ {to_ch['title']}"
        )
    else:
        text = (
            "⚠️ <b>Joylab bo'lmadi:</b> " + ", ".join(failed) + "\n\n"
            "Bot o'sha kanal(lar)da <b>admin emas</b>. "
            "Botni qayta admin qilib, yangi kelishuv tuzing."
        )
    for owner in (from_ch["owner_id"], to_ch["owner_id"]):
        try:
            await bot.send_message(owner, text)
        except Exception:
            pass


async def scheduler(bot: Bot):
    """Har 30 soniyada vaqti kelgan kelishuvlarni tekshiradi."""
    while True:
        try:
            due = await db.get_due_exchanges(datetime.now().isoformat())
            for ex in due:
                await _post_exchange(bot, ex)
        except Exception:
            logger.exception("Rejalashtiruvchida xato")
        await asyncio.sleep(30)


# ── 7. PM (ko'rishlar) kuzatuvi va avto-o'chirish ────────────────────────────

async def _notify_ad_deleted(bot: Bot, ad: dict, views: int, ok: bool):
    """Reklama o'chirilgani haqida ikkala tomonga xabar."""
    ex = await db.get_exchange(ad["exchange_id"])
    if not ex:
        return
    ch = await db.get_channel_by_tg_id(ad["channel_id"])
    title = ch["title"] if ch else "kanal"
    if ok:
        text = (f"📊 <b>{title}</b> dagi reklama <b>{views} PM</b> ga "
                f"yetdi va avtomatik o'chirildi ✅")
    else:
        text = (f"⚠️ <b>{title}</b> dagi reklama {views} PM ga yetdi, "
                "lekin o'chira olmadim — bot admin huquqini tekshiring.")

    from_ch = await db.get_channel(ex["from_pk"])
    to_ch = await db.get_channel(ex["to_pk"])
    for c in (from_ch, to_ch):
        if c:
            try:
                await bot.send_message(c["owner_id"], text)
            except Exception:
                pass


async def views_watcher(bot: Bot):
    """Har 3 daqiqada joylangan reklamalar PM ini tekshiradi.
    Belgilangan PM ga yetganda postni kanaldan o'chiradi.
    MTProto (Telethon) orqali ishlaydi — API_ID/API_HASH kerak."""
    from config import API_ID, API_HASH, BOT_TOKEN

    if not API_ID or not API_HASH:
        logger.warning("API_ID/API_HASH yo'q — PM kuzatuvi o'chiq.")
        return

    from telethon import TelegramClient

    client = TelegramClient("pm_views", API_ID, API_HASH)
    await client.start(bot_token=BOT_TOKEN)
    logger.info("PM kuzatuvchisi ishga tushdi (MTProto).")

    while True:
        try:
            ads = await db.get_active_posted_ads()
            for ad in ads:
                try:
                    msg = await client.get_messages(
                        ad["channel_id"], ids=ad["message_id"])
                except Exception:
                    continue

                if msg is None:
                    # Post qo'lda o'chirilgan — kuzatuvdan chiqaramiz
                    await db.mark_ad_deleted(ad["id"])
                    continue

                views = getattr(msg, "views", None) or 0
                if views >= ad["pm_target"]:
                    # PM ga yetdi — postni o'chiramiz
                    try:
                        await bot.delete_message(
                            ad["channel_id"], ad["message_id"])
                        ok = True
                    except Exception:
                        ok = False
                    await db.mark_ad_deleted(ad["id"])
                    await _notify_ad_deleted(bot, ad, views, ok)
        except Exception:
            logger.exception("PM kuzatuvchisida xato")
        await asyncio.sleep(180)
