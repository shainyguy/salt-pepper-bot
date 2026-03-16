from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, Contact
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
from config import ADMIN_IDS, CAFE_NAME, CAFE_ADDRESS, CAFE_PHONE, WORK_HOURS, SITE_URL
from keyboards import main_menu_kb, phone_kb

router = Router()


class Registration(StatesGroup):
    phone = State()


@router.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext):
    await state.clear()
    user = await db.upsert_user(
        msg.from_user.id,
        msg.from_user.username or "",
        msg.from_user.first_name or ""
    )
    is_admin = msg.from_user.id in ADMIN_IDS

    existing = await db.get_user(msg.from_user.id)
    if existing and existing["phone"]:
        await msg.answer(
            f"С возвращением в <b>{CAFE_NAME}</b>! 🎉\n"
            f"Выберите действие 👇",
            reply_markup=main_menu_kb(is_admin),
            parse_mode="HTML"
        )
        return

    await msg.answer(
        f"Добро пожаловать в <b>{CAFE_NAME}</b>! 🎉\n\n"
        f"Я помогу вам:\n"
        f"🍽 Сделать заказ\n"
        f"📦 Отследить статус\n"
        f"⭐ Оставить отзыв\n"
        f"🎁 Копить бонусы\n\n"
        f"Для начала поделитесь номером телефона 👇",
        reply_markup=phone_kb(),
        parse_mode="HTML"
    )
    await state.set_state(Registration.phone)


@router.message(Registration.phone, F.contact)
async def got_contact(msg: Message, state: FSMContext):
    phone = msg.contact.phone_number
    await db.update_user(msg.from_user.id, phone=phone)
    is_admin = msg.from_user.id in ADMIN_IDS
    await state.clear()
    await msg.answer(
        f"✅ Отлично! Номер сохранён.\n"
        f"Теперь вы можете делать заказы и копить бонусы!",
        reply_markup=main_menu_kb(is_admin),
        parse_mode="HTML"
    )
    # Приветственный бонус
    await db.update_user(msg.from_user.id, points=50, funnel_step="welcome_done")
    await msg.answer("🎁 Вам начислено <b>50 приветственных бонусов</b>!", parse_mode="HTML")


@router.message(Registration.phone, F.text)
async def got_phone_text(msg: Message, state: FSMContext):
    phone = msg.text.strip()
    if len(phone) < 7:
        await msg.answer("Пожалуйста, отправьте корректный номер или нажмите кнопку 👇",
                         reply_markup=phone_kb())
        return
    await db.update_user(msg.from_user.id, phone=phone)
    is_admin = msg.from_user.id in ADMIN_IDS
    await state.clear()
    await msg.answer(
        "✅ Номер сохранён! Добро пожаловать!",
        reply_markup=main_menu_kb(is_admin)
    )
    await db.update_user(msg.from_user.id, points=50, funnel_step="welcome_done")
    await msg.answer("🎁 Вам начислено <b>50 приветственных бонусов</b>!", parse_mode="HTML")


@router.message(F.text == "ℹ️ О нас")
async def about(msg: Message):
    rating = await db.get_avg_rating()
    stars = "⭐" * int(rating) if rating else "пока нет оценок"
    await msg.answer(
        f"🏠 <b>{CAFE_NAME}</b>\n\n"
        f"📍 {CAFE_ADDRESS}\n"
        f"📞 {CAFE_PHONE}\n"
        f"🕐 {WORK_HOURS}\n"
        f"🌐 {SITE_URL}\n\n"
        f"Рейтинг: {rating} {stars}\n\n"
        f"Мы готовим с любовью! ❤️",
        parse_mode="HTML"
    )