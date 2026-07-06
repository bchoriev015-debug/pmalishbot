"""Kanal qo'shish, reklama belgilash va "Mening kanallarim" bo'limi."""
import re
import html

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.fsm.context import FSMContext

from states import AddChannel, AdInput
from keyboards import (
    back_kb, recheck_kb, ad_type_kb, channel_actions_kb, delete_confirm_kb,
    pick_channel_kb, after_add_kb,
)
import database as db

router = Router()

# Havoladan tashqarida qoldiriladigan bo'laklar:
# <tg-emoji> teglari (premium emoji) YOKI oddiy emoji belgilari
_EMOJI_SPLIT_RE = re.compile(
    r"<tg-emoji\b[^>]*>.*?</tg-emoji>"
    r"|[\U0001F000-\U0001FAFF☀-➿⬀-⯿←-⇿"
    r"\U0001F1E6-\U0001F1FF️‍⃣]+",
    re.DOTALL,
)


# ── Yordamchi funksiyalar ────────────────────────────────────────────────────


def build_link_ad(html_text: str, link: str) -> str:
    """Havolani FAQAT matnga yopishtiradi — emojilar havoladan tashqarida.

    Sabab: Telegram havola ichidagi premium emojini o'chirib tashlaydi.
    Oddiy emojilar ham havoladan chiqarilib, toza turadi.
    Natija: <a>matn</a>emoji<a>matn</a> — ko'rinishi bir xil.
    """
    href = html.escape(link, quote=True)
    out = []
    last = 0
    has_plain = False
    for m in _EMOJI_SPLIT_RE.finditer(html_text):
        seg = html_text[last:m.start()]
        if seg.strip():
            out.append(f'<a href="{href}">{seg}</a>')
            has_plain = True
        elif seg:
            out.append(seg)  # faqat bo'shliq — havolasiz qoldiramiz
        out.append(m.group(0))
        last = m.end()
    tail = html_text[last:]
    if tail.strip():
        out.append(f'<a href="{href}">{tail}</a>')
        has_plain = True
    elif tail:
        out.append(tail)

    if not has_plain:
        # Faqat emoji yuborilgan — bosiladigan matn yo'q,
        # shunda hammasini oddiy havolaga o'raymiz
        return f'<a href="{href}">{html_text}</a>'
    return "".join(out)

def normalize_username(raw: str) -> str | None:
    """Kiritilgan matndan toza @username qaytaradi (yoki None)."""
    raw = raw.strip()
    for prefix in ("https://t.me/", "http://t.me/", "t.me/"):
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break
    raw = raw.lstrip("@").strip("/")
    if not re.fullmatch(r"[A-Za-z0-9_]{4,32}", raw):
        return None
    return "@" + raw


def normalize_link(raw: str) -> str | None:
    """Havolani to'liq URL ko'rinishiga keltiradi (yoki None)."""
    raw = raw.strip()
    if raw.startswith(("http://", "https://")):
        return raw
    if raw.startswith("t.me/"):
        return "https://" + raw
    if raw.startswith("@"):
        u = raw.lstrip("@")
        if re.fullmatch(r"[A-Za-z0-9_]{4,32}", u):
            return "https://t.me/" + u
    return None


async def _register_channel(bot: Bot, chat, owner_id: int):
    """Kanalni (chat obyekti bo'yicha) tekshirib bazaga yozadi.
    Qaytaradi: (status, matn[, pk])."""
    if chat.type != "channel":
        return ("invalid", "❌ Bu kanal emas. Kanal tanlang.")

    # Bot o'sha kanalda admin ekanligini tekshiramiz
    try:
        me = await bot.get_me()
        member = await bot.get_chat_member(chat.id, me.id)
    except Exception:
        return ("notadmin",
                "⚠️ Bot hali kanalingizda emas.\n\n"
                "Botni kanalingizga <b>admin</b> qiling. "
                "So'ng «Qayta tekshirish» tugmasini bosing.")

    if member.status != "administrator":
        return ("notadmin",
                "⚠️ Bot kanalingizda admin emas.\n\n"
                "Botni <b>admin</b> qiling. So'ng «Qayta tekshirish» tugmasini bosing.")

    # Takror qo'shilmasin
    if await db.channel_exists(chat.id, owner_id):
        return ("dup", "✅ Bu kanal allaqachon qo'shilgan.")

    # Obunachilar soni
    try:
        count = await bot.get_chat_member_count(chat.id)
    except Exception:
        count = 0

    pk = await db.add_channel(chat.id, chat.username, chat.title, count, owner_id)
    text = (
        f"✅ <b>Kanal qo'shildi!</b>\n\n"
        f"📢 {chat.title}\n"
        f"👥 {count} obunachi"
    )
    return ("ok", text, pk)


async def _check_and_add(bot: Bot, owner_id: int, raw: str):
    """Yozib yuborilgan @username bo'yicha kanal qo'shish (zaxira usul)."""
    username = normalize_username(raw)
    if not username:
        return ("invalid",
                "❌ Noto'g'ri manzil.\n\n"
                "Pastdagi «📢 Kanalni tanlash» tugmasini bosing "
                "yoki @ bilan yozing. Masalan: <code>@mychannel</code>")

    try:
        chat = await bot.get_chat(username)
    except Exception:
        return ("notfound",
                "❌ Kanal topilmadi.\n\n"
                "Botni kanalingizga qo'shib, admin qiling. "
                "So'ng «Qayta tekshirish» tugmasini bosing.")

    return await _register_channel(bot, chat, owner_id)


def _channel_card(ch: dict) -> str:
    """Kanallarim ro'yxatidagi bitta kanal ko'rinishi."""
    if ch["ad_type"] == "text":
        ad = "📝 Matnli reklama"
    elif ch["ad_type"] == "premium":
        ad = "⭐ Tayyor post"
    else:
        ad = "⚠️ Hali tayyor emas"
    uname = f"@{ch['username']}" if ch["username"] else "—"
    card = (
        f"📢 <b>{ch['title']}</b>\n"
        f"{uname}\n"
        f"👥 {ch['subscribers']} obunachi\n"
        f"Reklama: {ad}"
    )
    if ch.get("for_sale"):
        card += f"\n💰 Sotuvda: <b>{ch['sale_price']}</b>"
    return card


# ── Kanal qo'shish ───────────────────────────────────────────────────────────

@router.callback_query(F.data == "add_channel")
async def add_channel_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AddChannel.waiting_username)
    await callback.message.answer(
        "➕ <b>Kanal qo'shish</b>\n\n"
        "Pastdagi <b>«📢 Kanalni tanlash»</b> tugmasini bosing —\n"
        "kanallaringiz ro'yxati chiqadi.\n\n"
        "Kanalni tanlasangiz, bot avtomatik admin bo'lib qo'shiladi.",
        reply_markup=pick_channel_kb(),
    )
    await callback.answer()


@router.message(F.chat_shared)
async def channel_picked(message: Message, state: FSMContext, bot: Bot):
    """Foydalanuvchi ro'yxatdan kanal tanladi — Telegram botni admin qilib qo'shdi."""
    chat_id = message.chat_shared.chat_id
    try:
        chat = await bot.get_chat(chat_id)
    except Exception:
        await message.answer(
            "⚠️ Kanalga kira olmadim.\n\n"
            "Botni kanalga <b>admin</b> qilib qo'shganingizga ishonch hosil qiling, "
            "keyin qayta urining.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return

    result = await _register_channel(bot, chat, message.from_user.id)
    status = result[0]

    if status == "ok":
        await state.clear()
        await message.answer(result[1], reply_markup=ReplyKeyboardRemove())
        await message.answer(
            "Endi nima qilamiz? 👇",
            reply_markup=after_add_kb(result[2]),
        )
    else:
        await message.answer(result[1], reply_markup=ReplyKeyboardRemove())


@router.message(AddChannel.waiting_username, F.text)
async def add_channel_username(message: Message, state: FSMContext, bot: Bot):
    # Bekor qilish tugmasi
    if message.text.strip() == "🔙 Bekor qilish":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=ReplyKeyboardRemove())
        return

    result = await _check_and_add(bot, message.from_user.id, message.text)
    status = result[0]

    if status == "ok":
        await state.clear()
        await message.answer(result[1], reply_markup=ReplyKeyboardRemove())
        await message.answer(
            "Endi nima qilamiz? 👇",
            reply_markup=after_add_kb(result[2]),
        )
    elif status in ("notfound", "notadmin"):
        # Keyingi "qayta tekshirish" uchun username ni eslab qolamiz
        await state.update_data(pending_username=message.text)
        await message.answer(result[1], reply_markup=recheck_kb())
    elif status == "dup":
        await state.clear()
        await message.answer(result[1], reply_markup=back_kb())
    else:  # invalid — qayta kiritishga imkon beramiz
        await message.answer(result[1], reply_markup=back_kb())


@router.callback_query(F.data == "recheck")
async def recheck_channel(callback: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    pending = data.get("pending_username")
    if not pending:
        await callback.answer("Avval kanal username ini yuboring.", show_alert=True)
        return

    result = await _check_and_add(bot, callback.from_user.id, pending)
    status = result[0]

    if status == "ok":
        await state.clear()
        await callback.message.edit_text(result[1])
        await callback.message.answer(
            "Endi nima qilamiz? 👇",
            reply_markup=after_add_kb(result[2]),
        )
    elif status == "dup":
        await state.clear()
        await callback.message.edit_text(result[1], reply_markup=back_kb())
    else:
        # Hali admin emas / topilmadi — xabarni almashtirmaymiz, alert ko'rsatamiz
        await callback.answer("⚠️ Hali admin emas yoki topilmadi. Qayta urinib ko'ring.",
                              show_alert=True)
        return
    await callback.answer()


# ── Reklama turini tanlash ───────────────────────────────────────────────────

@router.callback_query(F.data.startswith("set_ad:"))
async def set_ad_choose(callback: CallbackQuery):
    pk = int(callback.data.split(":")[1])
    await callback.message.edit_text(
        "📢 <b>Reklama turini tanlang</b>",
        reply_markup=ad_type_kb(pk),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("ad_text:"))
async def ad_text_start(callback: CallbackQuery, state: FSMContext):
    pk = int(callback.data.split(":")[1])
    await state.set_state(AdInput.waiting_text)
    await state.update_data(channel_pk=pk)
    await callback.message.edit_text(
        "📝 <b>Matnli reklama</b>\n\n"
        "Reklama <b>yozuvini</b> yuboring.\n"
        "Bu odamlar ko'radigan matn bo'ladi.",
        reply_markup=back_kb(),
    )
    await callback.answer()


@router.message(AdInput.waiting_text, F.text)
async def ad_text_got(message: Message, state: FSMContext):
    # html_text — foydalanuvchining premium emoji va formatlashini
    # aynan saqlaydi (<tg-emoji>, <b> va h.k.)
    await state.update_data(ad_text=message.html_text)
    await state.set_state(AdInput.waiting_link)
    await message.answer(
        "🔗 Endi <b>havolani</b> yuboring.\n"
        "Masalan: <code>https://t.me/mychannel</code>\n\n"
        "Yuqoridagi yozuv shu havolaga olib boradi.",
        reply_markup=back_kb(),
    )


@router.message(AdInput.waiting_link, F.text)
async def ad_link_got(message: Message, state: FSMContext):
    link = normalize_link(message.text)
    if not link:
        await message.answer(
            "❌ Havola noto'g'ri.\n\n"
            "Masalan: <code>https://t.me/mychannel</code>",
            reply_markup=back_kb(),
        )
        return

    data = await state.get_data()
    pk = data["channel_pk"]
    # ad_text allaqachon xavfsiz HTML (html_text dan kelgan).
    # Premium emojilar havoladan tashqarida qoladi (aks holda Telegram o'chiradi).
    ad_html = build_link_ad(data["ad_text"], link)

    await db.set_ad_text(pk, ad_html, link)
    await state.clear()
    await message.answer(
        "✅ <b>Reklama tayyor!</b>\n\n"
        "Mana shunday ko'rinadi:\n\n"
        f"{ad_html}",
        reply_markup=back_kb(),
    )


@router.callback_query(F.data.startswith("ad_premium:"))
async def ad_premium_start(callback: CallbackQuery, state: FSMContext):
    pk = int(callback.data.split(":")[1])
    await state.set_state(AdInput.waiting_post)
    await state.update_data(channel_pk=pk)
    await callback.message.edit_text(
        "⭐ <b>Tayyor post</b>\n\n"
        "Tayyor postingizni menga yuboring (forward qiling).\n"
        "Post o'zgarmasdan saqlanadi.",
        reply_markup=back_kb(),
    )
    await callback.answer()


@router.message(AdInput.waiting_post)
async def ad_premium_got(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    pk = data["channel_pk"]
    # copy_message uchun manzil: post shu suhbatda turibdi (forward bo'lsa ham).
    # Keyinchalik copy_message aynan shu xabardan nusxa oladi — emoji/format saqlanadi.
    await db.set_ad_premium(pk, message.message_id, message.chat.id)
    await state.clear()
    await message.answer(
        "✅ <b>Post saqlandi!</b>\n\n"
        "Mana shunday ko'rinadi:",
        reply_markup=back_kb(),
    )
    # Namuna: saqlangan postning nusxasini ko'rsatamiz
    try:
        await bot.copy_message(
            chat_id=message.chat.id,
            from_chat_id=message.chat.id,
            message_id=message.message_id,
        )
    except Exception:
        pass


# ── Mening kanallarim ────────────────────────────────────────────────────────

@router.callback_query(F.data == "my_channels")
async def my_channels(callback: CallbackQuery):
    chans = await db.get_user_channels(callback.from_user.id)
    if not chans:
        await callback.message.edit_text(
            "📋 <b>Mening kanallarim</b>\n\n"
            "Sizda hali kanal yo'q.\n"
            "«Kanal qo'shish» tugmasi orqali qo'shing.",
            reply_markup=back_kb(),
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        f"📋 <b>Mening kanallarim</b> — {len(chans)} ta",
        reply_markup=back_kb(),
    )
    for ch in chans:
        await callback.message.answer(
            _channel_card(ch),
            reply_markup=channel_actions_kb(
                ch["id"], bool(ch["ad_type"]), bool(ch.get("for_sale"))
            ),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("view_ad:"))
async def view_ad(callback: CallbackQuery, bot: Bot):
    pk = int(callback.data.split(":")[1])
    ch = await db.get_channel(pk)
    if not ch or ch["owner_id"] != callback.from_user.id:
        await callback.answer("Topilmadi.", show_alert=True)
        return

    if ch["ad_type"] == "text" and ch["ad_text"]:
        await callback.message.answer(
            f"📢 <b>Reklamangiz shunday ko'rinadi:</b>\n\n{ch['ad_text']}"
        )
    elif ch["ad_type"] == "premium" and ch["stored_msg_id"]:
        await callback.message.answer("📢 <b>Reklamangiz shunday ko'rinadi:</b>")
        try:
            await bot.copy_message(
                chat_id=callback.from_user.id,
                from_chat_id=ch["stored_chat_id"],
                message_id=ch["stored_msg_id"],
            )
        except Exception:
            await callback.message.answer(
                "⚠️ Postni ko'rsatib bo'lmadi (ehtimol o'chirilgan). Qayta qo'shing."
            )
    else:
        await callback.answer("Reklama hali belgilanmagan.", show_alert=True)
        return
    await callback.answer()


# ── O'chirish ────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("del_channel:"))
async def del_channel_ask(callback: CallbackQuery):
    pk = int(callback.data.split(":")[1])
    ch = await db.get_channel(pk)
    if not ch or ch["owner_id"] != callback.from_user.id:
        await callback.answer("Topilmadi.", show_alert=True)
        return
    await callback.message.edit_text(
        f"❌ <b>{ch['title']}</b>\n\n"
        "Shu kanalni o'chirasizmi?",
        reply_markup=delete_confirm_kb(pk),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("del_confirm:"))
async def del_channel_do(callback: CallbackQuery):
    pk = int(callback.data.split(":")[1])
    ok = await db.delete_channel(pk, callback.from_user.id)
    if ok:
        await callback.message.edit_text("✅ Kanal o'chirildi.", reply_markup=back_kb())
    else:
        await callback.message.edit_text("⚠️ O'chirib bo'lmadi.", reply_markup=back_kb())
    await callback.answer()


@router.callback_query(F.data == "del_cancel")
async def del_cancel(callback: CallbackQuery):
    await callback.message.edit_text("Bekor qilindi.", reply_markup=back_kb())
    await callback.answer()
