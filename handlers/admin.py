from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
from config import ADMIN_IDS
from keyboards import (
    admin_main_kb, admin_order_kb, admin_stoplist_kb,
    STATUS_LABELS, main_menu_kb
)

router = Router()


class BroadcastForm(StatesGroup):
    message = State()
    confirm = State()


class AddItemForm(StatesGroup):
    category = State()
    name = State()
    price = State()
    description = State()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ════════════════  ПАНЕЛЬ  ═════════════════════════════════
@router.message(F.text == "🔧 Админ-панель")
async def admin_panel(msg: Message):
    if not is_admin(msg.from_user.id):
        return
    await msg.answer("🔧 <b>Админ-панель</b>", reply_markup=admin_main_kb(), parse_mode="HTML")


@router.callback_query(F.data == "a_main")
async def admin_main(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    await cb.message.edit_text("🔧 <b>Админ-панель</b>",
                                reply_markup=admin_main_kb(), parse_mode="HTML")


# ════════════════  ЗАКАЗЫ  ═════════════════════════════════
@router.callback_query(F.data.startswith("a_orders:"))
async def admin_orders(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    filter_val = cb.data.split(":")[1]
    status = None if filter_val == "all" else filter_val
    orders = await db.get_orders_by_status(status, limit=20)

    if not orders:
        await cb.message.edit_text(
            "📋 Заказов не найдено.",
            reply_markup=admin_main_kb()
        )
        return

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    text = f"📋 <b>Заказы ({filter_val}):</b>\n\n"
    buttons = []
    for o in orders[:15]:
        st = STATUS_LABELS.get(o["status"], o["status"])
        src = "🌐" if o["source"] == "website" else "🤖"
        text += f"{src} <b>{o['order_number']}</b> | {st} | {o['total']:.0f}₽\n"
        buttons.append([InlineKeyboardButton(
            text=f"{src} {o['order_number']} — {o['total']:.0f}₽",
            callback_data=f"a_order:{o['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="a_main")])
    await cb.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
                               parse_mode="HTML")


@router.callback_query(F.data.startswith("a_order:"))
async def admin_order_detail(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    order_id = int(cb.data.split(":")[1])
    o = await db.get_order(order_id)
    if not o:
        await cb.answer("Заказ не найден", show_alert=True)
        return
    st = STATUS_LABELS.get(o["status"], o["status"])
    src = "🌐 Сайт" if o["source"] == "website" else "🤖 Бот"
    dtype = "🚗 Доставка" if o["delivery_type"] == "delivery" else "🏃 Самовывоз"

    text = (
        f"📋 <b>Заказ {o['order_number']}</b>\n\n"
        f"📌 Статус: {st}\n"
        f"📡 Источник: {src}\n"
        f"👤 {o['customer_name']}\n"
        f"📞 {o['customer_phone']}\n"
        f"{dtype}\n"
    )
    if o["address"]:
        text += f"📍 {o['address']}\n"
    text += "\n"
    for it in o["items"]:
        qty = it.get("qty", 1)
        text += f"  • {it['name']} × {qty} — {it['price'] * qty:.0f} ₽\n"
    text += f"\n💰 <b>Итого: {o['total']:.0f} ₽</b>"
    if o["notes"]:
        text += f"\n📝 {o['notes']}"
    text += f"\n\n🕐 {o['created_at'][:16]}"

    await cb.message.edit_text(
        text, reply_markup=admin_order_kb(order_id, o["status"]), parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("a_st:"))
async def admin_change_status(cb: CallbackQuery, bot: Bot):
    if not is_admin(cb.from_user.id):
        return
    parts = cb.data.split(":")
    order_id, new_status = int(parts[1]), parts[2]
    await db.update_order_status(order_id, new_status)

    order = await db.get_order(order_id)
    st_label = STATUS_LABELS.get(new_status, new_status)
    await cb.answer(f"Статус изменён → {st_label}")

    # Обновить сообщение админа
    await admin_order_detail(cb)

    # Уведомить клиента
    if order and order["telegram_id"]:
        status_messages = {
            "confirmed": "✅ Ваш заказ подтверждён и скоро начнём готовить!",
            "cooking": "🍳 Ваш заказ готовится! Ожидайте...",
            "ready": "📦 Ваш заказ готов! Можете забирать.",
            "delivering": "🚗 Ваш заказ в пути!",
            "completed": "✔️ Заказ завершён! Спасибо, приходите ещё! 😊",
            "cancelled": "❌ К сожалению, ваш заказ отменён. Свяжитесь с нами для деталей.",
        }
        msg_text = (
            f"🔔 <b>Обновление заказа {order['order_number']}</b>\n\n"
            f"{status_messages.get(new_status, f'Статус: {st_label}')}"
        )
        try:
            if new_status == "completed":
                from keyboards import order_actions_kb
                await bot.send_message(
                    order["telegram_id"], msg_text, parse_mode="HTML",
                    reply_markup=order_actions_kb(order_id)
                )
            else:
                await bot.send_message(order["telegram_id"], msg_text, parse_mode="HTML")
        except Exception:
            pass


# ════════════════  СТОП-ЛИСТ  ══════════════════════════════
@router.callback_query(F.data == "a_menu")
async def admin_menu_mgmt(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    cats = await db.get_categories()
    # Показываем по категориям
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    buttons = []
    for cat in cats:
        buttons.append([InlineKeyboardButton(
            text=f"📂 {cat}", callback_data=f"a_menu_cat:{cat}"
        )])
    buttons.append([InlineKeyboardButton(text="➕ Добавить блюдо", callback_data="a_add_item")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="a_main")])
    await cb.message.edit_text(
        "🍽 <b>Управление меню</b>\nВыберите категорию:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("a_menu_cat:"))
async def admin_menu_category(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    cat = cb.data.split(":", 1)[1]
    items = await db.get_items_by_category(cat)
    await cb.message.edit_text(
        f"🍽 <b>{cat}</b>\n(нажмите для вкл/выкл):",
        reply_markup=admin_stoplist_kb(items),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("a_toggle:"))
async def admin_toggle(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    item_id = int(cb.data.split(":")[1])
    new_state = await db.toggle_item_available(item_id)
    item = await db.get_menu_item(item_id)
    icon = "✅" if new_state else "🚫"
    await cb.answer(f"{icon} {item['name']}: {'доступно' if new_state else 'СТОП'}")
    # Обновить список
    items = await db.get_items_by_category(item["category"])
    await cb.message.edit_reply_markup(reply_markup=admin_stoplist_kb(items))


# ════════════════  ДОБАВИТЬ БЛЮДО  ═════════════════════════
@router.callback_query(F.data == "a_add_item")
async def add_item_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    cats = await db.get_categories()
    cats_text = "\n".join(f"  • {c}" for c in cats)
    await cb.message.edit_text(
        f"➕ <b>Добавление блюда</b>\n\nВведите категорию:\n{cats_text}\n\n"
        f"(или введите новую)",
        parse_mode="HTML"
    )
    await state.set_state(AddItemForm.category)


@router.message(AddItemForm.category)
async def add_item_category(msg: Message, state: FSMContext):
    await state.update_data(category=msg.text.strip())
    await msg.answer("Введите название блюда:")
    await state.set_state(AddItemForm.name)


@router.message(AddItemForm.name)
async def add_item_name(msg: Message, state: FSMContext):
    await state.update_data(name=msg.text.strip())
    await msg.answer("Введите цену (число):")
    await state.set_state(AddItemForm.price)


@router.message(AddItemForm.price)
async def add_item_price(msg: Message, state: FSMContext):
    try:
        price = float(msg.text.strip())
    except ValueError:
        await msg.answer("❌ Введите число!")
        return
    await state.update_data(price=price)
    await msg.answer("Введите описание (или «—»):")
    await state.set_state(AddItemForm.description)


@router.message(AddItemForm.description)
async def add_item_desc(msg: Message, state: FSMContext):
    desc = msg.text.strip() if msg.text.strip() != "—" else ""
    data = await state.get_data()
    await db.add_menu_item(data["category"], data["name"], data["price"], desc)
    await state.clear()
    await msg.answer(
        f"✅ Блюдо добавлено!\n\n"
        f"📂 {data['category']}\n"
        f"🍽 {data['name']}\n"
        f"💰 {data['price']:.0f} ₽\n"
        f"📝 {desc or '—'}"
    )


# ════════════════  СТАТИСТИКА  ═════════════════════════════
@router.callback_query(F.data == "a_stats")
async def admin_stats(cb: CallbackQuery):
    if not is_admin(cb.from_user.id):
        return
    stats = await db.get_today_stats()
    users = await db.get_users_count()
    avg_rating = await db.get_avg_rating()
    active = await db.get_active_orders_count()
    top = await db.get_top_items(5)

    top_text = ""
    for i, t in enumerate(top, 1):
        top_text += f"  {i}. {t['name']} — {t['count']} шт.\n"

    text = (
        f"📊 <b>Статистика</b>\n\n"
        f"📅 <b>Сегодня:</b>\n"
        f"  📦 Заказов: {stats['orders_count']}\n"
        f"  💰 Выручка: {stats['revenue']:.0f} ₽\n"
        f"  👤 Новых клиентов: {stats['new_users']}\n"
        f"  ⭐ Отзывов: {stats['reviews']}\n\n"
        f"📈 <b>Общее:</b>\n"
        f"  👥 Всего клиентов: {users}\n"
        f"  ⭐ Средний рейтинг: {avg_rating}/5\n"
        f"  🔄 Активных заказов: {active}\n\n"
        f"🏆 <b>Топ блюд:</b>\n{top_text or '  нет данных'}"
    )
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="a_main")]
    ])
    await cb.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


# ════════════════  РАССЫЛКА  ═══════════════════════════════
@router.callback_query(F.data == "a_broadcast")
async def broadcast_start(cb: CallbackQuery, state: FSMContext):
    if not is_admin(cb.from_user.id):
        return
    users = await db.get_users_count()
    await cb.message.edit_text(
        f"📣 <b>Рассылка</b>\n\n"
        f"Получателей: {users} чел.\n\n"
        f"Отправьте текст сообщения (поддерживается HTML).\n"
        f"Для отмены: /cancel",
        parse_mode="HTML"
    )
    await state.set_state(BroadcastForm.message)


@router.message(BroadcastForm.message)
async def broadcast_preview(msg: Message, state: FSMContext):
    if msg.text == "/cancel":
        await state.clear()
        await msg.answer("❌ Рассылка отменена.")
        return
    await state.update_data(broadcast_text=msg.text)
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Отправить", callback_data="bcast_send"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="bcast_cancel"),
        ]
    ])
    await msg.answer(
        f"📣 <b>Превью рассылки:</b>\n\n{msg.text}\n\n"
        f"Отправить?", reply_markup=kb, parse_mode="HTML"
    )
    await state.set_state(BroadcastForm.confirm)


@router.callback_query(BroadcastForm.confirm, F.data == "bcast_send")
async def broadcast_send(cb: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    text = data["broadcast_text"]
    await state.clear()

    user_ids = await db.get_all_user_ids()
    sent, failed = 0, 0

    await cb.message.edit_text("📣 Рассылка запущена...")

    for uid in user_ids:
        try:
            await bot.send_message(uid, text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1

    await cb.message.edit_text(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"✉️ Отправлено: {sent}\n"
        f"❌ Ошибки: {failed}",
        parse_mode="HTML"
    