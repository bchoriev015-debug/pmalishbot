"""Admin panel — faqat ADMIN_ID uchun.

Bo'limlar: statistika, foydalanuvchilar, kanallar, reklama tarqatish (broadcast).
"""
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from config import ADMIN_ID
from keyboards import admin_main_kb, admin_back_kb
import database as db

router = Router()

LINE = "━━━━━━━━━━━━━━━━━━"
ADMIN_TITLE = f"🔐 <b>Admin Panel</b>\n{LINE}\nBo'lim tanlang 👇"


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID


class BroadcastState(StatesGroup):
    waiting_message = State()


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
    text_ads = await db.count_channels_by_type("text")
    premium_ads = await db.count_channels_by_type("premium")

    text = (
        f"📊 <b>Statistika</b>\n{LINE}\n"
        f"👥 Foydalanuvchilar: <b>{total_users}</b>\n"
        f"📢 Kanallar: <b>{total_channels}</b>\n{LINE}\n"
        f"📝 Matnli reklamalar: <b>{text_ads}</b>\n"
        f"⭐ Premium postlar: <b>{premium_ads}</b>"
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

    ad_label = {"text": "📝", "premium": "⭐", None: "⚠️"}
    lines = [f"📢 <b>Kanallar: {total} ta</b>\n{LINE}"]
    for ch in channels:
        uname = f"@{ch['username']}" if ch["username"] else "—"
        mark = ad_label.get(ch["ad_type"], "⚠️")
        lines.append(
            f"{mark} <b>{ch['title']}</b> ({uname})\n"
            f"   👥 {ch['subscribers']} | 👤 egasi: <code>{ch['owner_id']}</code>"
        )
    if total > 30:
        lines.append(f"\n<i>...va yana {total - 30} ta</i>")

    await callback.message.edit_text("\n".join(lines), reply_markup=admin_back_kb())
    await callback.answer()


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
