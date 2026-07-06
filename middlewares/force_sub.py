"""Majburiy obuna.

Foydalanuvchi botdan foydalanishdan oldin admin belgilagan
guruh/kanallarga qo'shilgan bo'lishi shart. Qo'shilmagan bo'lsa —
qo'shilish tugmalari chiqadi, boshqa hech narsa ishlamaydi.
Admin tekshiruvdan ozod.
"""
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot
from aiogram.types import (
    TelegramObject, Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import ADMIN_ID
import database as db

PROMPT_TEXT = (
    "🔒 <b>Botdan foydalanish uchun avval\n"
    "guruhimizga qo'shiling!</b>\n\n"
    "Quyidagi tugma orqali qo'shiling,\n"
    "so'ng «✅ Tekshirish» ni bosing 👇"
)


async def get_missing_subs(bot: Bot, user_id: int) -> list[dict]:
    """Foydalanuvchi hali qo'shilmagan guruh/kanallar ro'yxati."""
    subs = await db.get_force_subs()
    missing = []
    for s in subs:
        try:
            m = await bot.get_chat_member(s["chat_id"], user_id)
            if m.status in ("left", "kicked"):
                missing.append(s)
        except Exception:
            # Bot guruhdan chiqarilgan bo'lsa — foydalanuvchini bloklamaymiz
            continue
    return missing


def subs_kb(missing: list[dict]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for s in missing:
        builder.row(InlineKeyboardButton(
            text=f"➕ {s['title']}", url=s["link"]))
    builder.row(InlineKeyboardButton(
        text="✅ Tekshirish", callback_data="sub_check"))
    return builder.as_markup()


class ForceSubMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = data.get("event_from_user")
        if not user or user.is_bot or user.id == ADMIN_ID:
            return await handler(event, data)

        # Faqat shaxsiy chatdagi harakatlarni tekshiramiz
        if isinstance(event, Message):
            if event.chat.type != "private":
                return await handler(event, data)
        elif isinstance(event, CallbackQuery):
            # «Tekshirish» tugmasining o'zi o'tishi kerak
            if event.data == "sub_check":
                return await handler(event, data)
        else:
            return await handler(event, data)

        bot: Bot = data["bot"]
        missing = await get_missing_subs(bot, user.id)
        if not missing:
            return await handler(event, data)

        # Qo'shilmagan — bloklaymiz va tugmalarni ko'rsatamiz
        if isinstance(event, Message):
            await event.answer(PROMPT_TEXT, reply_markup=subs_kb(missing))
        else:
            await event.answer()
            await event.message.answer(PROMPT_TEXT, reply_markup=subs_kb(missing))
        return None
