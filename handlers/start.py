"""Asosiy menyu: /start, orqaga, yordam, reklama almashish (hozircha stub)."""
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from keyboards import main_menu_kb, back_kb

router = Router()

WELCOME_TEXT = """
👋 <b>Assalomu alaykum, {name}!</b>

Bu bot kanallar o'rtasida <b>reklama almashish</b>ga yordam beradi.

Nima qila olasiz:
➕ Kanalingizni qo'shasiz
📝 Reklama tayyorlaysiz
🔄 Boshqa kanallar bilan almashasiz
🛒 Kanal sotib olasiz yoki sotasiz

Boshlash uchun pastdagi tugmani bosing.
"""

HELP_TEXT = """
ℹ️ <b>Yordam</b>

Bu bot orqali kanallar bir-biri bilan reklama almashadi.

<b>Qanday ishlaydi:</b>
1. Kanalingizni qo'shasiz (bot avtomatik admin bo'ladi).
2. 🔄 da PM ni tanlaysiz (100/200/.../1K ko'rish).
3. Kanal tanlab, soat va tayyor reklamangizni yuborasiz.
4. Egasi qabul qilsa — belgilangan soatda bot reklamalarni
   ikkala kanalga ham <b>o'zi joylaydi</b> (ism yashirin).

<b>Reklama:</b> havolani matnga o'zingiz yopishtirasiz —
bot postni qanday bo'lsa shunday joylaydi,
premium emojilar buzilmaydi.

<b>Kanal sotish:</b>
«Mening kanallarim» → «Sotuvga qo'yish» → narxini yozasiz.
🛒 bo'limida esa sotilayotgan kanallarni ko'rasiz.

Savolingiz bo'lsa, admin bilan bog'laning.
"""


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(
        WELCOME_TEXT.format(name=message.from_user.full_name),
        reply_markup=main_menu_kb(),
    )


@router.callback_query(F.data == "sub_check")
async def sub_check(callback: CallbackQuery, state: FSMContext):
    """Majburiy obuna: «Tekshirish» tugmasi."""
    from middlewares.force_sub import get_missing_subs
    missing = await get_missing_subs(callback.bot, callback.from_user.id)
    if missing:
        await callback.answer(
            "❌ Hali qo'shilmagansiz! Avval guruhga qo'shiling.",
            show_alert=True,
        )
        return
    await state.clear()
    await callback.message.edit_text(
        WELCOME_TEXT.format(name=callback.from_user.full_name),
        reply_markup=main_menu_kb(),
    )
    await callback.answer("✅ Rahmat! Xush kelibsiz!")


@router.message(F.text == "🔙 Bekor qilish")
async def cancel_reply_kb(message: Message, state: FSMContext):
    """Pastki klaviaturadagi bekor qilish tugmasi."""
    await state.clear()
    await message.answer("Bekor qilindi.", reply_markup=ReplyKeyboardRemove())
    await message.answer(
        WELCOME_TEXT.format(name=message.from_user.full_name),
        reply_markup=main_menu_kb(),
    )


@router.callback_query(F.data == "back_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        WELCOME_TEXT.format(name=callback.from_user.full_name),
        reply_markup=main_menu_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "help")
async def show_help(callback: CallbackQuery):
    await callback.message.edit_text(HELP_TEXT, reply_markup=back_kb())
    await callback.answer()


# "exchange" va "sale_list" tugmalari handlers/market.py da ishlanadi
