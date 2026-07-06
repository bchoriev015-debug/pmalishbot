"""Barcha inline tugmalar.

Ranglar (style) va tugma boshidagi animatsion emoji
custom_emoji_middleware tomonidan avtomatik qo'yiladi.
Asosiy menyu tugmalariga esa PREMIUM_EMOJI dagi ID to'g'ridan-to'g'ri beriladi.
"""
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    KeyboardButtonRequestChat,
    ChatAdministratorRights,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import PREMIUM_EMOJI

# PM (ko'rishlar) darajalari
PM_TIERS = [100, 200, 300, 400, 500, 1000]


def _menu_btn(emoji: str, label: str, cb: str, key: str) -> InlineKeyboardButton:
    """Menyu tugmasi: PREMIUM_EMOJI da ID bo'lsa animatsion emoji,
    bo'lmasa oddiy emoji (fallback) ishlatiladi."""
    emoji_id = PREMIUM_EMOJI.get(key, "")
    if emoji_id:
        return InlineKeyboardButton(text=label, callback_data=cb, icon_custom_emoji_id=emoji_id)
    return InlineKeyboardButton(text=f"{emoji} {label}", callback_data=cb)


def main_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(_menu_btn("➕", "Kanal qo'shish", "add_channel", "add"))
    builder.row(_menu_btn("📋", "Mening kanallarim", "my_channels", "list"))
    builder.row(_menu_btn("🔄", "Reklama almashish", "exchange", "exchange"))
    builder.row(_menu_btn("🛒", "Sotiladigan kanallar", "sale_list", "sale"))
    builder.row(_menu_btn("ℹ️", "Yordam", "help", "help"))
    return builder.as_markup()


def contact_button(owner: dict | None, owner_id: int) -> InlineKeyboardButton:
    """💬 Muloqot tugmasi.

    Egasining username'i bo'lsa — lichkasiga havola.
    Bo'lmasa — bot orqali suhbat ochiladi (chat_start).
    """
    if owner and owner.get("username"):
        return InlineKeyboardButton(
            text="💬 Muloqot", url=f"https://t.me/{owner['username']}")
    return InlineKeyboardButton(
        text="💬 Muloqot", callback_data=f"chat_start:{owner_id}")


def channels_list_kb(channels: list[dict], view_prefix: str) -> InlineKeyboardMarkup:
    """Kanallar ro'yxati — tanlash uchun tugmalar (almashish/sotuv bo'limlari)."""
    builder = InlineKeyboardBuilder()
    for ch in channels:
        builder.row(InlineKeyboardButton(
            text=f"📢 {ch['title']} — {ch['subscribers']} obunachi",
            callback_data=f"{view_prefix}:{ch['id']}",
        ))
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_main"))
    return builder.as_markup()


def contact_kb(owner: dict | None, owner_id: int, back_cb: str) -> InlineKeyboardMarkup:
    """Kanal kartasi: egasi bilan muloqot + orqaga."""
    builder = InlineKeyboardBuilder()
    builder.row(contact_button(owner, owner_id))
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data=back_cb))
    return builder.as_markup()


def chat_end_kb() -> InlineKeyboardMarkup:
    """Bot orqali suhbatni tugatish tugmasi."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="❌ Suhbatni tugatish", callback_data="chat_end"))
    return builder.as_markup()


def chat_reply_kb(sender_id: int) -> InlineKeyboardMarkup:
    """Kelgan xabarga javob yozish tugmasi (qabul qiluvchi uchun)."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="💬 Javob yozish", callback_data=f"chat_start:{sender_id}"))
    return builder.as_markup()


# ── Kanal qo'shish (Telegram'ning kanal tanlash oynasi) ──────────────────────

def pick_channel_kb() -> ReplyKeyboardMarkup:
    """«Kanalni tanlash» — Telegram foydalanuvchining o'z kanallarini
    ko'rsatadi va tanlanganda botni avtomatik admin qilib qo'shadi."""
    rights = ChatAdministratorRights(
        is_anonymous=False,
        can_manage_chat=True,
        can_delete_messages=True,
        can_manage_video_chats=False,
        can_restrict_members=False,
        can_promote_members=False,
        can_change_info=False,
        can_invite_users=False,
        can_post_stories=False,
        can_edit_stories=False,
        can_delete_stories=False,
        can_post_messages=True,
        can_edit_messages=True,
    )
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(
                text="📢 Kanalni tanlash",
                request_chat=KeyboardButtonRequestChat(
                    request_id=1,
                    chat_is_channel=True,
                    # Foydalanuvchi kanalda admin bo'lishi kerak.
                    # MUHIM: bot huquqlari shu huquqlarning ichida bo'lishi shart
                    # (aks holda Telegram USER_RIGHTS_MISSING xatosi beradi)
                    user_administrator_rights=ChatAdministratorRights(
                        is_anonymous=False,
                        can_manage_chat=True,
                        can_delete_messages=True,
                        can_manage_video_chats=False,
                        can_restrict_members=False,
                        can_promote_members=True,
                        can_change_info=False,
                        can_invite_users=False,
                        can_post_stories=False,
                        can_edit_stories=False,
                        can_delete_stories=False,
                        can_post_messages=True,
                        can_edit_messages=True,
                    ),
                    # Bot shu huquqlar bilan avtomatik admin qilinadi
                    bot_administrator_rights=rights,
                ),
            )],
            [KeyboardButton(text="🔙 Bekor qilish")],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def after_add_kb(channel_pk: int) -> InlineKeyboardMarkup:
    """Kanal qo'shilgach: nima qilamiz?"""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="🔄 Reklama almashish", callback_data="exchange"))
    builder.row(InlineKeyboardButton(
        text="💰 Kanalni sotish", callback_data=f"sale_on:{channel_pk}"))
    builder.row(InlineKeyboardButton(
        text="🏠 Bosh menyu", callback_data="back_main"))
    return builder.as_markup()


# ── Reklama almashish tugmalari ──────────────────────────────────────────────

def exchange_own_kb(channels: list[dict]) -> InlineKeyboardMarkup:
    """Qaysi o'z kanali uchun almashishni tanlash."""
    builder = InlineKeyboardBuilder()
    for ch in channels:
        builder.row(InlineKeyboardButton(
            text=f"📢 {ch['title']}", callback_data=f"ex_own:{ch['id']}"))
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_main"))
    return builder.as_markup()


def pm_tiers_kb() -> InlineKeyboardMarkup:
    """PM (ko'rishlar) darajasini tanlash: 100/200/300/400/500/1k."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="100 PM", callback_data="ex_pm:100"),
        InlineKeyboardButton(text="200 PM", callback_data="ex_pm:200"),
        InlineKeyboardButton(text="300 PM", callback_data="ex_pm:300"),
    )
    builder.row(
        InlineKeyboardButton(text="400 PM", callback_data="ex_pm:400"),
        InlineKeyboardButton(text="500 PM", callback_data="ex_pm:500"),
        InlineKeyboardButton(text="1K PM", callback_data="ex_pm:1000"),
    )
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_main"))
    return builder.as_markup()


def offer_kb(exchange_id: int, proposer_id: int) -> InlineKeyboardMarkup:
    """Taklif olgan egaga: qabul / rad / muloqot."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Qabul qilish", callback_data=f"exo_acc:{exchange_id}"),
        InlineKeyboardButton(text="❌ Rad etish", callback_data=f"exo_rej:{exchange_id}"),
    )
    builder.row(InlineKeyboardButton(
        text="💬 Muloqot", callback_data=f"chat_start:{proposer_id}"))
    return builder.as_markup()


def deal_kb(exchange_id: int, peer_id: int) -> InlineKeyboardMarkup:
    """Kelishuv tayyor bo'lgach: reklama/vaqt o'zgartirish + lichka."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="✏️ Reklamani almashtirish", callback_data=f"exch_ad:{exchange_id}"))
    builder.row(InlineKeyboardButton(
        text="⏰ Vaqtni o'zgartirish", callback_data=f"exch_time:{exchange_id}"))
    builder.row(InlineKeyboardButton(
        text="💬 Lichkada gaplashish", callback_data=f"chat_start:{peer_id}"))
    return builder.as_markup()


def back_kb() -> InlineKeyboardMarkup:
    """Faqat "Orqaga" tugmasi — bosh menyuga qaytaradi."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_main"))
    return builder.as_markup()


def recheck_kb() -> InlineKeyboardMarkup:
    """Bot admin emas — qayta tekshirish + orqaga."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔄 Qayta tekshirish", callback_data="recheck"))
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_main"))
    return builder.as_markup()


def ad_type_kb(channel_pk: int) -> InlineKeyboardMarkup:
    """Kanal qo'shilgach — reklama turini tanlash."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(
        text="📝 Matnli reklama", callback_data=f"ad_text:{channel_pk}"))
    builder.row(InlineKeyboardButton(
        text="⭐ Premium post", callback_data=f"ad_premium:{channel_pk}"))
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_main"))
    return builder.as_markup()


def channel_actions_kb(channel_pk: int, has_ad: bool, for_sale: bool = False) -> InlineKeyboardMarkup:
    """Bitta kanal uchun amallar (kanallarim ro'yxatida)."""
    builder = InlineKeyboardBuilder()
    if has_ad:
        builder.row(InlineKeyboardButton(
            text="👁 Reklamani ko'rish", callback_data=f"view_ad:{channel_pk}"))
        builder.row(InlineKeyboardButton(
            text="✏️ Reklamani o'zgartirish", callback_data=f"set_ad:{channel_pk}"))
    else:
        # Reklama hali belgilanmagan — belgilash tugmasi
        builder.row(InlineKeyboardButton(
            text="➕ Reklama qo'shish", callback_data=f"set_ad:{channel_pk}"))
    if for_sale:
        builder.row(InlineKeyboardButton(
            text="🚫 Sotuvdan olish", callback_data=f"sale_off:{channel_pk}"))
    else:
        builder.row(InlineKeyboardButton(
            text="💰 Sotuvga qo'yish", callback_data=f"sale_on:{channel_pk}"))
    builder.row(InlineKeyboardButton(
        text="❌ O'chirish", callback_data=f"del_channel:{channel_pk}"))
    builder.row(InlineKeyboardButton(
        text="🏠 Bosh menyu", callback_data="back_main"))
    return builder.as_markup()


def delete_confirm_kb(channel_pk: int) -> InlineKeyboardMarkup:
    """Kanalni o'chirishdan oldin tasdiqlash."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Ha, o'chirilsin", callback_data=f"del_confirm:{channel_pk}"),
        InlineKeyboardButton(text="❌ Yo'q, bekor", callback_data="del_cancel"),
    )
    return builder.as_markup()


# ── Admin panel tugmalari ────────────────────────────────────────────────────

def admin_main_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats"),
        InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="admin_users"),
    )
    builder.row(
        InlineKeyboardButton(text="📢 Kanallar", callback_data="admin_channels"),
    )
    builder.row(
        InlineKeyboardButton(text="🔒 Majburiy obuna", callback_data="admin_subs"),
    )
    builder.row(
        InlineKeyboardButton(text="📤 Reklama yuborish", callback_data="admin_broadcast"),
    )
    return builder.as_markup()


def admin_subs_kb(subs: list[dict]) -> InlineKeyboardMarkup:
    """Majburiy obuna ro'yxati: har birini o'chirish + yangi qo'shish."""
    builder = InlineKeyboardBuilder()
    for s in subs:
        builder.row(InlineKeyboardButton(
            text=f"❌ {s['title']}", callback_data=f"fs_del:{s['id']}"))
    builder.row(InlineKeyboardButton(text="➕ Qo'shish", callback_data="fs_add"))
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_back"))
    return builder.as_markup()


def admin_back_kb() -> InlineKeyboardMarkup:
    """Admin panelga qaytish."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_back"))
    return builder.as_markup()
