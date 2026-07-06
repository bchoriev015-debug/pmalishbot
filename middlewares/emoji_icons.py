"""Avtomatik animatsion (custom) emoji + tugma ranglari.

Bu session middleware har bir chiqayotgan so'rovni ushlaydi va:
  * tugma matnining boshidagi belgini -> InlineKeyboardButton.icon_custom_emoji_id
  * xabar matnidagi belgini          -> <tg-emoji emoji-id="..."> tegi
  * tugmaning ma'nosiga qarab rang    -> InlineKeyboardButton.style
ga aylantiradi (config.EMOJI_ICONS jadvaliga ko'ra).

Shunday qilib butun botdagi tugma va matnlar avtomatik chiroyli bo'ladi —
har bir faylni alohida bezash shart emas.
Ishlashi uchun bot egasida Telegram Premium bo'lishi kerak (Bot API 9.4+).
"""
import re

from config import EMOJI_ICONS

# Allaqachon mavjud <tg-emoji ...>...</tg-emoji> teglarini ajratib olish uchun
_TG_EMOJI_RE = re.compile(r"<tg-emoji\b[^>]*>.*?</tg-emoji>", re.DOTALL)

# Faqat HTML matnni qo'llab-quvvatlaydigan metodlarda matnni qayta ishlaymiz
_TEXT_METHODS = {
    "SendMessage",
    "EditMessageText",
    "EditMessageCaption",
    "SendPhoto",
    "SendDocument",
    "SendAnimation",
    "SendVideo",
}


def emojify_text(text: str | None) -> str | None:
    """Matndagi tanish belgilarni animatsion emojiga o'raydi (HTML)."""
    if not text:
        return text

    def _wrap(segment: str) -> str:
        for char, emoji_id in EMOJI_ICONS.items():
            if char in segment:
                segment = segment.replace(char, f'<tg-emoji emoji-id="{emoji_id}">{char}</tg-emoji>')
        return segment

    # Mavjud <tg-emoji> teglarini tegmasdan qoldiramiz (ikki marta o'ramaslik uchun)
    out = []
    last = 0
    for m in _TG_EMOJI_RE.finditer(text):
        out.append(_wrap(text[last:m.start()]))
        out.append(m.group(0))
        last = m.end()
    out.append(_wrap(text[last:]))
    return "".join(out)


def _style_for(button):
    """Tugma ma'nosiga qarab rang (style) tanlaydi (avvalgi botlar uslubi).

    yashil (success) — navigatsiya (Orqaga/Bosh menyu) + tasdiqlash/qo'shish
    qizil  (danger)  — o'chirish / bekor / rad etish
    ko'k   (primary) — qolgan barcha amallar
    """
    cb = button.callback_data or ""
    text = button.text or ""

    # Yashil — navigatsiya (avvalgi botlardagidek)
    if "Orqaga" in text or "Bosh menyu" in text:
        return "success"

    # Yashil — qo'shish / tasdiqlash / rozilik / sotuvga qo'yish / qabul qilish
    if (
        cb.startswith(("add_channel", "ad_text", "ad_premium", "del_confirm",
                       "sale_on", "exo_acc"))
        or "Tasdiqlash" in text
        or "Qabul qilish" in text
        or "qo'shish" in text.lower()
        or text.startswith("Ha")
    ):
        return "success"

    # Qizil — o'chirish / bekor / rad etish / sotuvdan olish / suhbatni tugatish
    if (
        cb.startswith(("del_channel", "del_cancel", "sale_off", "chat_end"))
        or "O'chirish" in text
        or "Bekor" in text
        or "Rad etish" in text
        or "tugatish" in text
    ):
        return "danger"

    # Ko'k — qolgan asosiy amallar (almashish, qayta tekshirish, ko'rish...)
    return "primary"


def decorate_markup(markup) -> None:
    """Tugma matni belgi bilan boshlansa icon_custom_emoji_id ga ko'chiradi + rang beradi."""
    rows = getattr(markup, "inline_keyboard", None)
    if not rows:
        return
    for row in rows:
        for button in row:
            text = button.text or ""
            head, _, rest = text.partition(" ")
            if head in EMOJI_ICONS and not button.icon_custom_emoji_id:
                button.icon_custom_emoji_id = EMOJI_ICONS[head]
                button.text = rest if rest else head
            if not button.style:
                style = _style_for(button)
                if style:
                    button.style = style


async def custom_emoji_middleware(make_request, bot, method):
    markup = getattr(method, "reply_markup", None)
    if markup is not None:
        decorate_markup(markup)

    if type(method).__name__ in _TEXT_METHODS:
        if getattr(method, "text", None):
            method.text = emojify_text(method.text)
        if getattr(method, "caption", None):
            method.caption = emojify_text(method.caption)

    return await make_request(bot, method)
