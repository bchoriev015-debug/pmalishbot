# PM Almashish Bot (1-bosqich)

Kanal egalari o'zaro reklama (PM) almashish uchun Telegram bot.
Bu **1-bosqich**: kanal qo'shish, bot adminligini tekshirish va reklama
(matnli yoki premium post) belgilash. Keyingi bosqichlar (almashish, vaqtli
joylash, ko'rishlarni sanash) keyinroq qo'shiladi.

## Texnologiya
- Python 3.10+ va **aiogram 3.29.0** (Bot API 9.4 — tugma `style` va
  `icon_custom_emoji_id`)
- **SQLite** (aiosqlite orqali async)
- Barcha xabarlar o'zbek tilida

## Fayllar
| Fayl | Vazifasi |
|------|----------|
| `bot.py` | Botni ishga tushiradi, routerlar va middleware ni ulaydi |
| `config.py` | `.env` dan token, `PREMIUM_EMOJI` va `EMOJI_ICONS` lug'atlari |
| `database.py` | SQLite: `users` va `channels` jadvallari |
| `states.py` | FSM holatlari (kanal/matn/link/post kutish) |
| `keyboards.py` | Barcha inline tugmalar |
| `middlewares/emoji_icons.py` | Tugma/matnga avtomatik premium emoji + rang |
| `middlewares/register_middleware.py` | Foydalanuvchini avtomatik ro'yxatga olish |
| `handlers/start.py` | /start, bosh menyu, yordam |
| `handlers/channels.py` | Kanal qo'shish, reklama, "Mening kanallarim" |

## O'rnatish

**1. Token oling.** Telegramda [@BotFather](https://t.me/BotFather) ga kiring →
`/newbot` → nom va username bering → sizga **token** beradi.

**2. `.env` faylni to'ldiring** (`.env.example` dan nusxa oling):
```
BOT_TOKEN=1234567:ABCdef...   # BotFather bergan token
ADMIN_ID=123456789            # o'z Telegram ID ingiz (ixtiyoriy)
DB_PATH=pm_bot.db
```

**3. Kutubxonalarni o'rnating:**
```bash
pip install -U -r requirements.txt
```

**4. Botni ishga tushiring:**
```bash
python bot.py
```

## Ishlatish
1. Botga `/start` yozing → bosh menyu chiqadi.
2. **➕ Kanal qo'shish** → kanal username ini (`@kanal`) yuboring.
   - Avval **botni o'sha kanalga admin qiling**, aks holda tekshiruvdan o'tmaydi.
3. Kanal qo'shilgach reklama turini tanlang:
   - **📝 Matnli reklama** — matn + havola so'raladi, matn havolaga o'raladi.
   - **⭐ Premium post** — tayyor postingizni forward qiling (emoji/format saqlanadi).
4. **📋 Mening kanallarim** → kanallar ro'yxati, reklamani ko'rish/o'chirish.

## Premium (animatsion) emoji haqida
Tugmalardagi jonli emoji va ranglar **bot egasida Telegram Premium** bo'lsa
ishlaydi. `config.py` dagi `PREMIUM_EMOJI` va `EMOJI_ICONS` lug'atlaridagi ID
larni o'zingiz to'ldirasiz/o'zgartirasiz. ID bo'sh bo'lsa oddiy emoji ishlatiladi
(bot baribir ishlayveradi).

> ID olish: botga kerakli premium emojini yuboring va uning `custom_emoji_id`
> sini oling, so'ng lug'atga qo'ying.
