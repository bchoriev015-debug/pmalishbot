"""Kanal qo'shish va "Mening kanallarim" bo'limi."""
import re

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext

from states import AddChannel
from keyboards import (
    back_kb, recheck_kb, channel_actions_kb, delete_confirm_kb,
    pick_channel_kb, after_add_kb,
)
import database as db

router = Router()
# Faqat shaxsiy chat
router.message.filter(F.chat.type == "private")
router.callback_query.filter(F.message.chat.type == "private")


# ── Yordamchi funksiyalar ────────────────────────────────────────────────────

def normalize_username(raw: str) -> str | None:
    """Kiritilgan matndan toza @username qaytaradi (yoki None)."""
    raw = raw.strip()
    for prefix in ("https://t.me/", "http://t.me/", "t.me/"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break
    raw = raw.lstrip("@").strip("/")
    if not re.fullmatch(r"[A-Za-z0-9_]{4,32}", raw):
        return None
    return "@" + raw


async def _register_channel(bot: Bot, chat, owner_id: int):
    """Kanalni (chat obyekti bo'yicha) tekshirib bazaga yozadi.
    Qaytaradi: (status, matn[, pk])."""
    if chat.type != "channel":
        return ("invalid", "❌ Bu kanal emas. Kanal tanlang.")

    # Bot o'sha kanalda admin ekanligini tekshiramiz
    try:
        me = await bot.get_me()
        member = await bot.get_chat_member(chat.id, me.id)
    except Exception:
        return ("notadmin",
                "⚠️ Bot hali kanalingizda emas.\n\n"
                "Botni kanalingizga <b>admin</b> qiling. "
                "So'ng «Qayta tekshirish» tugmasini bosing.")

    if member.status != "administrator":
        return ("notadmin",
                "⚠️ Bot kanalingizda admin emas.\n\n"
                "Botni <b>admin</b> qiling. So'ng «Qayta tekshirish» tugmasini bosing.")

    # Takror qo'shilmasin
    if await db.channel_exists(chat.id, owner_id):
        return ("dup", "✅ Bu kanal allaqachon qo'shilgan.")

    # Obunachilar soni
    try:
        count = await bot.get_chat_member_count(chat.id)
    except Exception:
        count = 0

    pk = await db.add_channel(chat.id, chat.username, chat.title, count, owner_id)
    text = (
        f"✅ <b>Kanal qo'shildi!</b>\n\n"
        f"📢 {chat.title}\n"
        f"👥 {count} obunachi"
    )
    return ("ok", text, pk)


async def _check_and_add(bot: Bot, owner_id: int, raw: str):
    """Yozib yuborilgan @username bo'yicha kanal qo'shish (zaxira usul)."""
    username = normalize_username(raw)
    if not username:
        return ("invalid",
                "❌ Noto'g'ri manzil.\n\n"
                "Pastdagi «📢 Kanalni tanlash» tugmasini bosing "
                "yoki @ bilan yozing. Masalan: <code>@mychannel</code>")

    try:
        chat = await bot.get_chat(username)
    except Exception:
        return ("notfound",
                "❌ Kanal topilmadi.\n\n"
                "Botni kanalingizga qo'shib, admin qiling. "
                "So'ng «Qayta tekshirish» tugmasini bosing.")

    return await _register_channel(bot, chat, owner_id)


def _channel_card(ch: dict) -> str:
    """Kanallarim ro'yxatidagi bitta kanal ko'rinishi."""
    uname = f"@{ch['username']}" if ch["username"] else "—"
    card = (
        f"📢 <b>{ch['title']}</b>\n"
        f"{uname}\n"
        f"👥 {ch['subscribers']} obunachi"
    )
    if ch.get("pm_tier"):
        tier = "1K" if ch["pm_tier"] == 1000 else str(ch["pm_tier"])
        card += f"\n📊 PM: {tier}"
    if ch.get("for_sale"):
        card += f"\n💰 Sotuvda: <b>{ch['sale_price']}</b>"
    return card


# ── Kanal qo'shish ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "add_channel")
async def add_channel_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AddChannel.waiting_username)
    await callback.message.answer(
        "➕ <b>Kanal qo'shish</b>\n\n"
        "Pastdagi <b>«📢 Kanalni tanlash»</b> tugmasini bosing —\n"
        "kanallaringiz ro'yxati chiqadi.\n\n"
        "Kanalni tanlasangiz, bot avtomatik admin bo'lib qo'shiladi.",
        reply_markup=pick_channel_kb(),
    )
    await callback.answer()


@router.message(F.chat_shared)
async def channel_picked(message: Message, state: FSMContext, bot: Bot):
    """Foydalanuvchi ro'yxatdan kanal tanladi — Telegram botni admin qilib qo'shdi."""
    chat_id = message.chat_shared.chat_id
    try:
        chat = await bot.get_chat(chat_id)
    except Exception:
        await message.answer(
            "⚠️ Kanalga kira olmadim.\n\n"
            "Botni kanalga <b>admin</b> qilib qo'shganingizga ishonch hosil qiling, "
            "keyin qayta urining.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    result = await _register_channel(bot, chat, message.from_user.id)
    status = result[0]

    if status == "ok":
        await state.clear()
        await message.answer(result[1], reply_markup=ReplyKeyboardRemove())
        await message.answer(
            "Endi nima qilamiz? 👇",
            reply_markup=after_add_kb(result[2]),
        )
    else:
        await message.answer(result[1], reply_markup=ReplyKeyboardRemove())


@router.message(AddChannel.waiting_username, F.text)
async def add_channel_username(message: Message, state: FSMContext, bot: Bot):
    # Bekor qilish tugmasi
    if message.text.strip() == "🔙 Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=ReplyKeyboardRemove())
        return

    result = await _check_and_add(bot, message.from_user.id, message.text)
    status = result[0]

    if status == "ok":
        await state.clear()
        await message.answer(result[1], reply_markup=ReplyKeyboardRemove())
        await message.answer(
            "Endi nima qilamiz? 👇",
            reply_markup=after_add_kb(result[2]),
        )
    elif status in ("notfound", "notadmin"):
        # Keyingi "qayta tekshirish" uchun username ni eslab qolamiz
        await state.update_data(pending_username=message.text)
        await message.answer(result[1], reply_markup=recheck_kb())
    elif status == "dup":
        await state.clear()
        await message.answer(result[1], reply_markup=back_kb())
    else:  # invalid — qayta kiritishga imkon beramiz
        await message.answer(result[1], reply_markup=back_kb())


@router.callback_query(F.data == "recheck")
async def recheck_channel(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    pending = data.get("pending_username")
    if not pending:
        await callback.answer("Avval kanal username ini yuboring.", show_alert=True)
        return

    result = await _check_and_add(bot, callback.from_user.id, pending)
    status = result[0]

    if status == "ok":
        await state.clear()
        await callback.message.edit_text(result[1])
        await callback.message.answer(
            "Endi nima qilamiz? 👇",
            reply_markup=after_add_kb(result[2]),
        )
    elif status == "dup":
        await state.clear()
        await callback.message.edit_text(result[1], reply_markup=back_kb())
    else:
        # Hali admin emas / topilmadi — xabarni almashtirmaymiz, alert ko'rsatamiz
        await callback.answer("⚠️ Hali admin emas yoki topilmadi. Qayta urinib ko'ring.",
                              show_alert=True)
        return
    await callback.answer()


# ── Mening kanallarim ────────────────────────────────────────────────────────

@router.callback_query(F.data == "my_channels")
async def my_channels(callback: CallbackQuery):
    chans = await db.get_user_channels(callback.from_user.id)
    if not chans:
        await callback.message.edit_text(
            "📋 <b>Mening kanallarim</b>\n\n"
            "Sizda hali kanal yo'q.\n"
            "«Kanal qo'shish» tugmasi orqali qo'shing.",
            reply_markup=back_kb(),
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        f"📋 <b>Mening kanallarim</b> — {len(chans)} ta",
        reply_markup=back_kb(),
    )
    for ch in chans:
        await callback.message.answer(
            _channel_card(ch),
            reply_markup=channel_actions_kb(ch["id"], bool(ch.get("for_sale"))),
        )
    await callback.answer()


# ── O'chirish ────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("del_channel:"))
async def del_channel_ask(callback: CallbackQuery):
    pk = int(callback.data.split(":")[1])
    ch = await db.get_channel(pk)
    if not ch or ch["owner_id"] != callback.from_user.id:
        await callback.answer("Topilmadi.", show_alert=True)
        return
    await callback.message.edit_text(
        f"❌ <b>{ch['title']}</b>\n\n"
        "Shu kanalni o'chirasizmi?",
        reply_markup=delete_confirm_kb(pk),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("del_confirm:"))
async def del_channel_do(callback: CallbackQuery):
    pk = int(callback.data.split(":")[1])
    ok = await db.delete_channel(pk, callback.from_user.id)
    if ok:
        await callback.message.edit_text("✅ Kanal o'chirildi.", reply_markup=back_kb())
    else:
        await callback.message.edit_text("⚠️ O'chirib bo'lmadi.", reply_markup=back_kb())
    await callback.answer()


@router.callback_query(F.data == "del_cancel")
async def del_cancel(callback: CallbackQuery):
    await callback.message.edit_text("Bekor qilindi.", reply_markup=back_kb())
    await callback.answer()
