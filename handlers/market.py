"""Sotiladigan kanallar bo'limi.

Kanal tanlanadi va kanal egasi bilan 💬 Muloqot tugmasi
orqali yozishish mumkin. (Reklama almashish — handlers/exchange.py da.)
"""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from states import SaleInput
from keyboards import (
    back_kb,
    channels_list_kb,
    contact_kb,
)
import database as db

router = Router()
# Faqat shaxsiy chat
router.message.filter(F.chat.type == "private")
router.callback_query.filter(F.message.chat.type == "private")


# ── Sotiladigan kanallar ─────────────────────────────────────────────────────

@router.callback_query(F.data == "sale_list")
async def sale_list(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    channels = await db.get_sale_channels()
    if not channels:
        await callback.message.edit_text(
            "🛒 <b>Sotiladigan kanallar</b>\n\n"
            "Hozircha sotuvda kanal yo'q.\n\n"
            "O'z kanalingizni sotmoqchimisiz?\n"
            "«Mening kanallarim» bo'limida "
            "«Sotuvga qo'yish» tugmasini bosing.",
            reply_markup=back_kb(),
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        "🛒 <b>Sotiladigan kanallar</b>\n\n"
        "Kanalni tanlang:",
        reply_markup=channels_list_kb(channels, "sale_view"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sale_view:"))
async def sale_view(callback: CallbackQuery):
    pk = int(callback.data.split(":")[1])
    ch = await db.get_channel(pk)
    if not ch or not ch.get("for_sale"):
        await callback.answer("Bu kanal endi sotuvda emas.", show_alert=True)
        return

    uname = f"@{ch['username']}" if ch["username"] else "—"
    owner = await db.get_user(ch["owner_id"])

    await callback.message.edit_text(
        f"📢 <b>{ch['title']}</b>\n"
        f"{uname}\n"
        f"👥 {ch['subscribers']} obunachi\n"
        f"💰 Narxi: <b>{ch['sale_price']}</b>\n\n"
        "Sotib olish uchun egasi bilan yozishing:",
        reply_markup=contact_kb(owner, ch["owner_id"], "sale_list"),
    )
    await callback.answer()


# ── O'z kanalini sotuvga qo'yish / olish ─────────────────────────────────────

@router.callback_query(F.data.startswith("sale_on:"))
async def sale_on_start(callback: CallbackQuery, state: FSMContext):
    pk = int(callback.data.split(":")[1])
    ch = await db.get_channel(pk)
    if not ch or ch["owner_id"] != callback.from_user.id:
        await callback.answer("Topilmadi.", show_alert=True)
        return

    await state.set_state(SaleInput.waiting_price)
    await state.update_data(sale_pk=pk)
    await callback.message.answer(
        f"💰 <b>{ch['title']}</b> kanalini sotuvga qo'yish\n\n"
        "Narxini yozib yuboring.\n"
        "Masalan: <code>500 000 so'm</code>",
        reply_markup=back_kb(),
    )
    await callback.answer()


@router.message(SaleInput.waiting_price, F.text)
async def sale_price_got(message: Message, state: FSMContext):
    price = message.text.strip()
    if len(price) > 50:
        await message.answer(
            "❌ Narx juda uzun. Qisqaroq yozing.\n"
            "Masalan: <code>500 000 so'm</code>",
            reply_markup=back_kb(),
        )
        return

    data = await state.get_data()
    pk = data["sale_pk"]
    await db.set_for_sale(pk, price)
    await state.clear()

    ch = await db.get_channel(pk)
    await message.answer(
        f"✅ <b>{ch['title']}</b> sotuvga qo'yildi!\n\n"
        f"💰 Narxi: <b>{price}</b>\n\n"
        "Endi u «Sotiladigan kanallar» bo'limida ko'rinadi.",
        reply_markup=back_kb(),
    )


@router.callback_query(F.data.startswith("sale_off:"))
async def sale_off(callback: CallbackQuery):
    pk = int(callback.data.split(":")[1])
    ch = await db.get_channel(pk)
    if not ch or ch["owner_id"] != callback.from_user.id:
        await callback.answer("Topilmadi.", show_alert=True)
        return

    await db.unset_for_sale(pk)
    await callback.answer("✅ Kanal sotuvdan olindi.", show_alert=True)
    # Kartadagi tugmalarni yangilaymiz
    from keyboards import channel_actions_kb
    try:
        await callback.message.edit_reply_markup(
            reply_markup=channel_actions_kb(pk, for_sale=False)
        )
    except Exception:
        pass
