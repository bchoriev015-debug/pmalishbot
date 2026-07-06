"""Admin panel — faqat ADMIN_ID uchun.

Bo'limlar: statistika, foydalanuvchilar, kanallar, reklama tarqatish (broadcast).
"""
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from config import ADMIN_ID
from keyboards import admin_main_kb, admin_back_kb, admin_subs_kb
import database as db

router = Router()
# Faqat shaxsiy chat
router.message.filter(F.chat.type == "private")
router.callback_query.filter(F.message.chat.type == "private")

LINE = "━━━━━━━━━━━━━━━━━━"
ADMIN_TITLE = f"🔐 <b>Admin Panel</b>\n{LINE}\nBo'lim tanlang 👇"


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


class BroadcastState(StatesGroup):
    waiting_message = State()


class ForceSubState(StatesGroup):
    waiting_chat = State()


# ── Panelni ochish ───────────────────────────────────────────────────────────

@router.message(Command("admin"))
async def admin_open(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("❌ Sizda ruxsat yo'q!")
        return
    await state.clear()
    await message.answer(ADMIN_TITLE, reply_markup=admin_main_kb())


@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!", show_alert=True)
        return
    await state.clear()
    await callback.message.edit_text(ADMIN_TITLE, reply_markup=admin_main_kb())
    await callback.answer()


# ── Statistika ───────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_stats")
async def admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!", show_alert=True)
        return

    total_users = await db.count_users()
    total_channels = await db.count_channels()
    for_sale = await db.count_for_sale()
    total_ex = await db.count_exchanges()
    ready_ex = await db.count_exchanges("ready")
    posted_ex = await db.count_posted_exchanges()

    text = (
        f"📊 <b>Statistika</b>\n{LINE}\n"
        f"👥 Foydalanuvchilar: <b>{total_users}</b>\n"
        f"📢 Kanallar: <b>{total_channels}</b>\n"
        f"💰 Sotuvda: <b>{for_sale}</b>\n{LINE}\n"
        f"🔄 Kelishuvlar (jami): <b>{total_ex}</b>\n"
        f"⏳ Joylanishini kutmoqda: <b>{ready_ex}</b>\n"
        f"✅ Joylangan: <b>{posted_ex}</b>"
    )
    await callback.message.edit_text(text, reply_markup=admin_back_kb())
    await callback.answer()


# ── Foydalanuvchilar ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_users")
async def admin_users(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!", show_alert=True)
        return

    total = await db.count_users()
    users = await db.get_all_users(limit=30)

    lines = [f"👥 <b>Foydalanuvchilar: {total} ta</b>\n{LINE}"]
    for u in users:
        uname = f"@{u['username']}" if u["username"] else "—"
        lines.append(f"🆔 <code>{u['user_id']}</code> — {uname}")
    if total > 30:
        lines.append(f"\n<i>...va yana {total - 30} ta</i>")

    await callback.message.edit_text("\n".join(lines), reply_markup=admin_back_kb())
    await callback.answer()


# ── Kanallar ─────────────────────────────────────────────────────────────────

@router.callback_query(F.data == "admin_channels")
async def admin_channels(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!", show_alert=True)
        return

    total = await db.count_channels()
    channels = await db.get_all_channels(limit=30)

    if not channels:
        await callback.message.edit_text(
            f"📢 <b>Kanallar</b>\n{LINE}\nHali kanal qo'shilmagan.",
            reply_markup=admin_back_kb(),
        )
        await callback.answer()
        return

    lines = [f"📢 <b>Kanallar: {total} ta</b>\n{LINE}"]
    for ch in channels:
        uname = f"@{ch['username']}" if ch["username"] else "—"
        mark = "💰" if ch.get("for_sale") else "📢"
        lines.append(
            f"{mark} <b>{ch['title']}</b> ({uname})\n"
            f"   👥 {ch['subscribers']} | 👤 egasi: <code>{ch['owner_id']}</code>"
        )
    if total > 30:
        lines.append(f"\n<i>...va yana {total - 30} ta</i>")

    await callback.message.edit_text("\n".join(lines), reply_markup=admin_back_kb())
    await callback.answer()


# ── Majburiy obuna boshqaruvi ────────────────────────────────────────────────

SUBS_TITLE = (
    f"🔒 <b>Majburiy obuna</b>\n{LINE}\n"
    "Foydalanuvchilar botdan foydalanish uchun\n"
    "shu guruh/kanallarga qo'shilishi shart.\n\n"
    "O'chirish uchun nomini bosing 👇"
)


@router.callback_query(F.data == "admin_subs")
async def admin_subs(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!", show_alert=True)
        return
    await state.clear()
    subs = await db.get_force_subs()
    text = SUBS_TITLE if subs else (
        f"🔒 <b>Majburiy obuna</b>\n{LINE}\n"
        "Hozircha majburiy obuna yo'q.\n"
        "«➕ Qo'shish» tugmasini bosing."
    )
    await callback.message.edit_text(text, reply_markup=admin_subs_kb(subs))
    await callback.answer()


@router.callback_query(F.data == "fs_add")
async def fs_add_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!", show_alert=True)
        return
    await state.set_state(ForceSubState.waiting_chat)
    await callback.message.edit_text(
        f"➕ <b>Majburiy obuna qo'shish</b>\n{LINE}\n"
        "Guruh yoki kanal manzilini yuboring:\n"
        "• <code>@guruhusername</code> yoki\n"
        "• <code>-100...</code> ID (yopiq guruh uchun)\n\n"
        "⚠️ Bot o'sha guruh/kanalda <b>admin</b> bo'lishi shart\n"
        "(a'zolikni tekshira olishi uchun).",
        reply_markup=admin_back_kb(),
    )
    await callback.answer()


@router.message(ForceSubState.waiting_chat, F.text)
async def fs_add_got(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return

    raw = message.text.strip()
    for prefix in ("https://t.me/", "http://t.me/", "t.me/"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break
    ident = int(raw) if raw.lstrip("-").isdigit() else "@" + raw.lstrip("@")

    try:
        chat = await bot.get_chat(ident)
    except Exception:
        await message.answer(
            "❌ Guruh/kanal topilmadi.\n\n"
            "Avval botni o'sha guruhga qo'shib admin qiling, "
            "keyin qayta yuboring.",
            reply_markup=admin_back_kb(),
        )
        return

    # Bot a'zo/admin ekanini tekshiramiz
    try:
        me = await bot.get_me()
        m = await bot.get_chat_member(chat.id, me.id)
        if m.status not in ("administrator", "member", "creator"):
            raise ValueError
    except Exception:
        await message.answer(
            "❌ Bot bu guruhda yo'q.\n\n"
            "Botni guruhga qo'shib <b>admin</b> qiling, keyin qayta yuboring.",
            reply_markup=admin_back_kb(),
        )
        return

    # Qo'shilish havolasi
    if chat.username:
        link = f"https://t.me/{chat.username}"
    else:
        try:
            invite = await bot.create_chat_invite_link(chat.id)
            link = invite.invite_link
        except Exception:
            await message.answer(
                "❌ Taklif havolasini olib bo'lmadi.\n\n"
                "Botga guruhda <b>«Foydalanuvchilarni taklif qilish»</b> "
                "huquqini bering, keyin qayta yuboring.",
                reply_markup=admin_back_kb(),
            )
            return

    await state.clear()
    await db.add_force_sub(chat.id, chat.username, chat.title, link)
    subs = await db.get_force_subs()
    await message.answer(
        f"✅ <b>{chat.title}</b> majburiy obunaga qo'shildi!\n\n"
        "Endi foydalanuvchilar botdan foydalanish uchun\n"
        "shu yerga qo'shilishi shart bo'ladi.",
        reply_markup=admin_subs_kb(subs),
    )


@router.callback_query(F.data.startswith("fs_del:"))
async def fs_del(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!", show_alert=True)
        return
    sub_id = int(callback.data.split(":")[1])
    await db.del_force_sub(sub_id)
    subs = await db.get_force_subs()
    text = SUBS_TITLE if subs else (
        f"🔒 <b>Majburiy obuna</b>\n{LINE}\n"
        "Hozircha majburiy obuna yo'q."
    )
    await callback.message.edit_text(text, reply_markup=admin_subs_kb(subs))
    await callback.answer("O'chirildi.")


# ── Reklama yuborish (broadcast) ─────────────────────────────────────────────

@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!", show_alert=True)
        return
    await state.set_state(BroadcastState.waiting_message)
    await callback.message.edit_text(
        f"📤 <b>Reklama yuborish</b>\n{LINE}\n"
        "Barcha foydalanuvchilarga yuboriladigan xabarni yuboring.\n\n"
        "<i>Matn, rasm, video, stiker — hammasi bo'ladi.</i>",
        reply_markup=admin_back_kb(),
    )
    await callback.answer()


@router.message(BroadcastState.waiting_message)
async def admin_broadcast_send(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id):
        return
    await state.clear()

    user_ids = await db.get_all_user_ids()
    status_msg = await message.answer(f"📤 Yuborilmoqda... 0/{len(user_ids)}")

    sent = 0
    failed = 0
    for uid in user_ids:
        try:
            await message.copy_to(uid)
            sent += 1
        except Exception:
            failed += 1

    await status_msg.edit_text(
        f"✅ <b>Reklama yuborildi!</b>\n{LINE}\n"
        f"👥 Jami: <b>{len(user_ids)}</b>\n"
        f"✅ Yuborildi: <b>{sent}</b>\n"
        f"❌ Xato (bloklagan): <b>{failed}</b>",
        reply_markup=admin_back_kb(),
    )
