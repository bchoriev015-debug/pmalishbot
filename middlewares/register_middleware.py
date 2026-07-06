"""Har bir so'rovda foydalanuvchini bazaga avtomatik ro'yxatga oladi."""
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

import database as db


class RegisterMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user: User | None = data.get("event_from_user")
        if user and not user.is_bot:
            await db.upsert_user(user_id=user.id, username=user.username)
        return await handler(event, data)
