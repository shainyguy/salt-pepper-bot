"""
Воронки:
1. Приветственная  — бонус при регистрации (в start.py)
2. Пост-заказ      — через 30 мин после заказа → «Как вам?» + предложить отзыв
3. Реактивация     — 7 дней неактивности → напоминание с промо
4. День рождения   — поздравление + скидка
"""
from aiogram import Router, F
from aiogram.types import Message

import database as db
from keyboards import main_menu_kb

router = Router()


# ─── Бонусная программа (кнопка) ──────────────────────────
@router.message(F.text == "🎁 Бонусы")
async def show_loyalty(msg: Message):
    user = await db.get_user(msg.from_user.id)
    if not user:
        await msg.answer("Сначала зарегистрируйтесь: /start")
        return

    points = user["points"]
    total_orders = user["total_orders"]
    total_spent = user["total_spent"]

    # Определяем уровень
    if total_orders >= 20:
        level = "💎 Бриллиант"
        cashback = "10%"
    elif total_orders >= 10:
        level = "👑 VIP"
        cashback = "7%"
    elif total_orders >= 5:
        level = "⭐ Постоянный"
        cashback = "5%"
    else:
        level = "🌱 Новичок"
        cashback = "3%"

    text = (
        f"🎁 <b>Программа лояльности</b>\n\n"
        f"👤 {user['first_name']}\n"
        f"🏅 Уровень: {level}\n"
        f"💰 Кешбэк: {cashback}\n\n"
        f"🎁 Бонусов: <b>{points}</b>\n"
        f"📦 Всего заказов: {total_orders}\n"
        f"💵 Потрачено: {total_spent:.0f} ₽\n\n"
        f"ℹ️ 1 бонус = 1 ₽ скидки.\n"
        f"Бонусы начисляются автоматически с каждого заказа!"
    )

    # Прогресс до следующего уровня
    if total_orders < 5:
        text += f"\n\n📈 До уровня ⭐: ещё {5 - total_orders} заказов"
    elif total_orders < 10:
        text += f"\n\n📈 До уровня 👑: ещё {10 - total_orders} заказов"
    elif total_orders < 20:
        text += f"\n\n📈 До уровня 💎: ещё {20 - total_orders} заказов"

    await msg.answer(text, parse_mode="HTML")