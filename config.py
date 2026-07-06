import os
from dotenv import load_dotenv

# .env faylni o'qiymiz
load_dotenv()

# Bot tokeni — BotFather dan olinadi va .env ga yoziladi
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

# Admin (bot egasi) Telegram ID si — ixtiyoriy, keyingi bosqichlar uchun
ADMIN_ID: int = int(os.getenv("ADMIN_ID", "0"))

# Ma'lumotlar bazasi yo'li (har bot uchun alohida bo'lgani ma'qul)
DB_PATH: str = os.getenv("DB_PATH", "pm_bot.db")

# MTProto (my.telegram.org) — kanal postlari PM (ko'rishlar) sonini
# o'qish uchun. Bo'sh bo'lsa PM sanash o'chiq turadi (bot baribir ishlaydi).
API_ID: int = int(os.getenv("API_ID", "0") or 0)
API_HASH: str = os.getenv("API_HASH", "")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN .env faylida topilmadi!")


# ─────────────────────────────────────────────────────────────────────────────
# PREMIUM EMOJI (animatsion tugma belgilari)
#
# Bot API 9.4+ da InlineKeyboardButton.icon_custom_emoji_id maydoni bor.
# Quyidagi lug'atdagi ID lar asosiy menyu tugmalariga qo'yiladi.
# ID bo'sh ("") bo'lsa — oddiy emoji ishlatiladi (fallback).
# ID kiritsangiz — premium animatsion emoji chiqadi.
# ID olish: botga premium emoji yuboring va custom_emoji_id ni oling.
# (Ishlashi uchun bot egasida Telegram Premium bo'lishi kerak.)
# ─────────────────────────────────────────────────────────────────────────────
PREMIUM_EMOJI = {
    "add":     "5030749344752468962",  # ➕ Kanal qo'shish
    "list":    "5197269100878907942",  # 📋 Mening kanallarim
    "exchange": "5470135030393090150", # 🔄 Reklama almashish
    "sale":    "5312361253610475399",  # 🛒 Sotiladigan kanallar
    "help":    "5258503720928288433",  # ℹ️ Yordam
    "back":    "5352759161945867747",  # 🔙 Orqaga
    "delete":  "5210952531676504517",  # ❌ O'chirish
    "confirm": "6296367896398399651",  # ✅ Tasdiqlash
}


# ─────────────────────────────────────────────────────────────────────────────
# EMOJI_ICONS — belgi -> custom_emoji_id.
# custom_emoji_middleware har bir chiqayotgan XABAR MATNIDAGI va TUGMADAGI
# belgini avtomatik animatsion emojiga aylantiradi + tugmalarga rang beradi.
# Yangi belgi qo'shmoqchi bo'lsangiz — shu yerga yozing (Premium kerak).
# ─────────────────────────────────────────────────────────────────────────────
EMOJI_ICONS = {
    "✅": "6296367896398399651",  # ptichka (tasdiqlash)
    "❌": "5210952531676504517",  # bekor / o'chirish
    "⚠️": "5447644880824181073",  # ogohlantirish
    "🔙": "5352759161945867747",  # orqaga
    "➕": "5030749344752468962",  # qo'shish
    "📋": "5197269100878907942",  # ro'yxat (kanallarim)
    "ℹ️": "5258503720928288433",  # ma'lumot (yordam)
    "📢": "5197304993920616826",  # karnay (reklama / e'lon)
    "🔗": "5271604874419647061",  # zanjir (havola)
    "👤": "5258011929993026890",  # shaxs (egasi)
    "👥": "6001526766714227911",  # odamlar (obunachilar)
    "📊": "5364265190353286344",  # statistika (admin)
    "🆔": "5841276284155467413",  # id (admin)
    "🔄": "5470135030393090150",  # qayta / almashish
    "📝": "5334882760735598374",  # yozuv (matnli reklama)
    "⭐": "5897920748101571572",  # yulduz (tayyor post)
    "👋": "5247133031235329609",  # salom
    "🏠": "5416041192905265756",  # uy (bosh menyu)
    "🛒": "5312361253610475399",  # savat (sotiladigan kanallar)
    "⏰": "5215394081911351762",  # soat (vaqt)
    "➡️": "5215695279377884733",  # davom etish
    "🎉": "5461151367559141950",  # tabriklash (taklif qabul qilindi)
    "💰": "5224257782013769471",  # pul (sotuvga qo'yish / narx)
    "💬": "5253742260054409879",  # xabar (muloqot)
    "🚫": "5240241223632954241",  # taqiq (sotuvdan olish)
}
