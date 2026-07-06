"""Bot orqali muloqot.

Kanal egasining username'i bo'lmasa, «Muloqot» tugmasi bot ichida
suhbat ochadi: yozilgan xabarni bot egasiga yetkazadi, ega esa
«Javob yozish» tugmasi bilan javob qaytaradi.
"""
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from states import ChatState
from keyboards import back_kb, chat_end_kb, chat_reply_kb

router = Router()
# Faqat shaxsiy chat
router.message.filter(F.chat.type == "private")
router.callback_query.filter(F.message.chat.type == "private")


@router.callback_query(F.data.startswith("chat_start:"))
async def chat_start(callback: CallbackQuery, state: FSMContext):
    peer_id = int(callback.data.split(":")[1])
    if peer_id == callback.from_user.id:
        await callback.answer("Bu sizning kanalingiz 🙂", show_alert=True)
        return

    await state.set_state(ChatState.active)
    await state.update_data(peer_id=peer_id)
    await callback.message.answer(
        "💬 <b>Suhbat boshlandi!</b>\n\n"
        "Xabaringizni yozing — men egasiga yetkazaman.\n"
        "Rasm, video ham yuborsangiz bo'ladi.\n\n"
        "Tugatish uchun pastdagi tugmani bosing.",
        reply_markup=chat_end_kb(),
    )
    await callback.answer()


@router.callback_query(F.data == "chat_end")
async def chat_end(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer(
        "✅ Suhbat tugadi.",
        reply_markup=back_kb(),
    )
    await callback.answer()


@router.message(ChatState.active)
async def chat_relay(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    peer_id = data.get("peer_id")
    if not peer_id:
        await state.clear()
        await message.answer("❌ Suhbat topilmadi. Qaytadan urinib ko'ring.",
                             reply_markup=back_kb())
        return

    sender = message.from_user
    who = f"@{sender.username}" if sender.username else sender.full_name

    try:
        # Xabarning o'zini nusxalaymiz (rasm/video/format saqlanadi)
        await message.copy_to(peer_id)
        # Kimdan kelganini va javob tugmasini yuboramiz
        await bot.send_message(
            peer_id,
            f"👆 Bu xabarni <b>{who}</b> yubordi.\n"
            "Javob berish uchun tugmani bosing:",
            reply_markup=chat_reply_kb(sender.id),
        )
    except Exception:
        await message.answer(
            "❌ Xabar yetib bormadi.\n\n"
            "Ega botni hali ishga tushirmagan bo'lishi mumkin.",
            reply_markup=back_kb(),
        )
        await state.clear()
        return

    await message.answer("✅ Yuborildi", reply_markup=chat_end_kb())
