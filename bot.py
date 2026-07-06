"""PM (o'zaro reklama) almashish boti — 1-bosqich.

Ishga tushirish:  python bot.py
"""
import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    BotCommand,
    BotCommandScopeDefault,
    BotCommandScopeChat,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeAllGroupChats,
)

from config import BOT_TOKEN, ADMIN_ID
from database import init_db
from middlewares.register_middleware import RegisterMiddleware
from middlewares.emoji_icons import custom_emoji_middleware
from middlewares.force_sub import ForceSubMiddleware
from handlers import start, channels, market, exchange, chat, admin

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def set_commands(bot: Bot):
    # Komandalar FAQAT shaxsiy chatda ko'rinadi
    await bot.set_my_commands(
        [BotCommand(command="start", description="🔄 Botni ishga tushirish")],
        scope=BotCommandScopeAllPrivateChats(),
    )
    # Guruhlarda va umumiy ro'yxatda komandalar bo'lmasin ("/" bosganda chiqmaydi)
    await bot.delete_my_commands(scope=BotCommandScopeDefault())
    await bot.delete_my_commands(scope=BotCommandScopeAllGroupChats())
    # Admin uchun: /start + /admin (admin hali /start bosmagan bo'lsa xato
    # bermasligi uchun try/except — /admin komandasi baribir ishlayveradi)
    if ADMIN_ID:
        try:
            await bot.set_my_commands(
                [
                    BotCommand(command="start", description="🔄 Botni ishga tushirish"),
                    BotCommand(command="admin", description="🔐 Admin panel"),
                ],
                scope=BotCommandScopeChat(chat_id=ADMIN_ID),
            )
        except Exception:
            logger.info("Admin menyu komandasi keyinroq o'rnatiladi (admin hali /start bosmagan).")


async def main():
    # Bazani tayyorlaymiz
    await init_db()
    logger.info("Ma'lumotlar bazasi tayyor.")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            # Havolalarning katta oldindan ko'rish oynasini o'chiramiz
            link_preview_is_disabled=True,
        ),
    )
    # Barcha chiqayotgan tugma/matnga avtomatik animatsion emoji + rang
    bot.session.middleware(custom_emoji_middleware)

    dp = Dispatcher(storage=MemoryStorage())
    # Foydalanuvchini avtomatik ro'yxatga olish
    dp.update.middleware(RegisterMiddleware())
    # Majburiy obuna tekshiruvi (admin belgilagan guruh/kanallar)
    dp.message.middleware(ForceSubMiddleware())
    dp.callback_query.middleware(ForceSubMiddleware())

    # Routerlar
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(channels.router)
    dp.include_router(market.router)
    dp.include_router(exchange.router)
    dp.include_router(chat.router)

    await set_commands(bot)
    logger.info("Bot ishga tushmoqda...")
    await bot.delete_webhook(drop_pending_updates=True)

    # Avto-joylash rejalashtiruvchisi (belgilangan soatda kanallarga joylaydi)
    asyncio.create_task(exchange.scheduler(bot))
    # PM (ko'rishlar) kuzatuvchisi — belgilangan PM da postni o'chiradi
    asyncio.create_task(exchange.views_watcher(bot))

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
