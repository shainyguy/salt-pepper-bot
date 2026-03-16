from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
from config import ADMIN_IDS
from keyboards import rating_kb, review_moderate_kb

router = Router()


class ReviewForm(StatesGroup):
    text = State()


@router.message(F.text == "⭐ Отзывы")
async def reviews_menu(msg: Message):
    orders = await db.get_user_orders(msg.from_user.id, limit=5)
    completed = [o for o in orders if o["status"] == "completed"]
    if not completed:
        avg = await db.get_avg_rating()
        await msg.answer(
            f"⭐ Средняя оценка кафе: <b>{avg}/5</b>\n\n"
            f"Оставить отзыв можно после завершения заказа.",
            parse_mode="HTML"
        )
        return
    text = "⭐ <b>Оцените свой заказ:</b>\n\n"
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = []
    for o in completed[:3]:
        items_str = ", ".join(i["name"] for i in o["items"])[:40]
        buttons.append([InlineKeyboardButton(
            text=f"{o['order_number']} — {items_str}",
            callback_data=f"rev_start:{o['id']}"
        )])
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await msg.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("rev_start:"))
async def start_review(cb: CallbackQuery):
    order_id = int(cb.data.split(":")[1])
    await cb.message.edit_text(
        "⭐ <b>Поставьте оценку:</b>",
        reply_markup=rating_kb(order_id), parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("rate:"))
async def set_rating(cb: CallbackQuery, state: FSMContext):
    parts = cb.data.split(":")
    order_id, rating = int(parts[1]), int(parts[2])
    await state.update_data(order_id=order_id, rating=rating)
    await cb.message.edit_text(
        f"{'⭐' * rating}\n\nНапишите комментарий к отзыву\n(или «—» чтобы пропустить):"
    )
    await state.set_state(ReviewForm.text)


@router.message(ReviewForm.text)
async def save_review(msg: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    text = msg.text if msg.text != "—" else ""

    await db.create_review(
        telegram_id=msg.from_user.id,
        order_id=data["order_id"],
        rating=data["rating"],
        text=text
    )
    await state.clear()
    await msg.answer("✅ Спасибо за отзыв! Он будет опубликован после модерации.")

    # Уведомить админов
    order = await db.get_order(data["order_id"])
    on = order["order_number"] if order else "?"
    admin_text = (
        f"⭐ <b>Новый отзыв</b>\n\n"
        f"Заказ: {on}\n"
        f"Оценка: {'⭐' * data['rating']}\n"
        f"Текст: {text or '(без текста)'}\n"
        f"От: {msg.from_user.first_name}"
    )
    pending = await db.get_pending_reviews()
    rev_id = pending[0]["id"] if pending else 0
    for aid in ADMIN_IDS:
        try:
            await bot.send_message(
                aid, admin_text, parse_mode="HTML",
                reply_markup=review_moderate_kb(rev_id)
            )
        except Exception:
            pass


# ─── модерация (для админов, но обработчик здесь) ─────────
@router.callback_query(F.data.startswith("rev_mod:"))
async def moderate_review(cb: CallbackQuery, bot: Bot):
    if cb.from_user.id not in ADMIN_IDS:
        await cb.answer("⛔ Нет доступа", show_alert=True)
        return
    parts = cb.data.split(":")
    review_id, action = int(parts[1]), parts[2]
    await db.moderate_review(review_id, action)
    label = "✅ Опубликован" if action == "approved" else "❌ Отклонён"
    await cb.message.edit_text(
        cb.message.text + f"\n\n<b>Статус: {label}</b>",
        parse_mode="HTML"
    )
    await cb.answer(label)