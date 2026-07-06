"""FSM holatlari — foydalanuvchi ma'lumot kiritayotganda ishlatiladi."""
from aiogram.fsm.state import StatesGroup, State


class AddChannel(StatesGroup):
    # Kanal username sini kutish (@kanal ko'rinishida)
    waiting_username = State()


class AdInput(StatesGroup):
    # Matnli reklama: avval matn, keyin havola
    waiting_text = State()
    waiting_link = State()
    # Premium post: forward qilingan postni kutish
    waiting_post = State()


class SaleInput(StatesGroup):
    # Kanalni sotuvga qo'yish: narx kutish
    waiting_price = State()


class ChatState(StatesGroup):
    # Bot orqali muloqot (username yo'q egalar bilan yozishish)
    active = State()


class ExchangeState(StatesGroup):
    # Reklama almashish oqimi
    waiting_time = State()        # soat kutish (taklifchi)
    waiting_ad = State()          # tayyor reklama posti kutish (taklifchi)
    waiting_accept_ad = State()   # qabul qiluvchining reklamasi kutish
    waiting_new_ad = State()      # reklamani almashtirish
    waiting_new_time = State()    # vaqtni o'zgartirish
