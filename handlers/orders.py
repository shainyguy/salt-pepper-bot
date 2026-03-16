from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

import database as db
from config import ADMIN_IDS
from keyboards import (
    categories_kb, items_kb, item_detail_kb, cart_kb,
    delivery_type_kb, confirm_order_kb, order_actions_kb,
    main_menu_kb, location_kb, STATUS_LABELS
)

router = Router()

# ── корзины хранятся в памяти (dict: telegram_id → list) ──
user_carts: dict[int, list[dict]] = {}


class OrderForm(StatesGroup):
    delivery_type = State()
    address = State()
    notes = State()
    confirm = State()


# ════════════════  МЕНЮ  ═══════════════════════════════════
@router.message(F.text == "📋 Меню")
async def show_menu(msg: Message):
    cats = await db.get_categories()
    await msg.answer("🍽 <b>Выберите категорию:</b>",
                     reply_markup=categories_kb(cats), parse_mode="HTML")


@router.callback_query(F.data == "menu_back")
async def menu_back(cb: CallbackQuery):
    cats = await db.get_categories()
    await cb.message.edit_text("🍽 <b>Выберите категорию:</b>",
                               reply_markup=categories_kb(cats), parse_mode="HTML")


@router.callback_query(F.data.startswith("cat:"))
async def show_category(cb: CallbackQuery):
    cat = cb.data.split(":", 1)[1]
    items = await db.get_items_by_category(cat)
    await cb.message.edit_text(
        f"<b>{cat}</b>\nВыберите блюдо:",
        reply_markup=items_kb(items, cat), parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("item:"))
async def show_item(cb: CallbackQuery):
    item_id = int(cb.data.split(":")[1])
    item = await db.get_menu_item(item_id)
    if not item:
        await cb.answer("Блюдо не найдено", show_alert=True)
        return
    avail = "✅ В наличии" if item["available"] else "❌ Нет в наличии"
    text = (
        f"<b>{item['name']}</b>\n\n"
        f"{item['description']}\n\n"
        f"💰 <b>{item['price']:.0f} ₽</b>\n"
        f"{avail}"
    )
    await cb.message.edit_text(
        text,
        reply_markup=item_detail_kb(item_id, bool(item["available"])),
        parse_mode="HTML"
    )


# ════════════════  КОРЗИНА  ════════════════════════════════
@router.callback_query(F.data.startswith("add:"))
async def add_to_cart(cb: CallbackQuery):
    item_id = int(cb.data.split(":")[1])
    item = await db.get_menu_item(item_id)
    if not item or not item["available"]:
        await cb.answer("❌ Блюдо недоступно", show_alert=True)
        return
    uid = cb.from_user.id
    if uid not in user_carts:
        user_carts[uid] = []
    # проверяем, есть ли уже в корзине
    for c in user_carts[uid]:
        if c["id"] == item_id:
            c["qty"] += 1
            await cb.answer(f"✅ {item['name']} × {c['qty']}")
            return
    user_carts[uid].append({
        "id": item_id, "name": item["name"],
        "price": item["price"], "qty": 1
    })
    await cb.answer(f"✅ {item['name']} добавлен в корзину!")


@router.message(F.text == "🛒 Корзина")
async def show_cart(msg: Message):
    uid = msg.from_user.id
    cart = user_carts.get(uid, [])
    if not cart:
        await msg.answer("🛒 Корзина пуста.\nОткройте 📋 Меню, чтобы добавить блюда!")
        return
    text = "🛒 <b>Ваша корзина:</b>\n\n"
    total = 0
    for item in cart:
        line_total = item["price"] * item["qty"]
        total += line_total
        text += f"• {item['name']} × {item['qty']} — {line_total:.0f} ₽\n"
    text += f"\n💰 <b>Итого: {total:.0f} ₽</b>"
    await msg.answer(text, reply_markup=cart_kb(cart), parse_mode="HTML")


@router.callback_query(F.data.startswith("cart_del:"))
async def cart_remove(cb: CallbackQuery):
    idx = int(cb.data.split(":")[1])
    uid = cb.from_user.id
    cart = user_carts.get(uid, [])
    if 0 <= idx < len(cart):
        removed = cart.pop(idx)
        await cb.answer(f"❌ {removed['name']} удалён")
    if not cart:
        await cb.message.edit_text("🛒 Корзина пуста.")
        return
    text = "🛒 <b>Ваша корзина:</b>\n\n"
    total = 0
    for item in cart:
        lt = item["price"] * item["qty"]
        total += lt
        text += f"• {item['name']} × {item['qty']} — {lt:.0f} ₽\n"
    text += f"\n💰 <b>Итого: {total:.0f} ₽</b>"
    await cb.message.edit_text(text, reply_markup=cart_kb(cart), parse_mode="HTML")


@router.callback_query(F.data == "cart_clear")
async def cart_clear(cb: CallbackQuery):
    user_carts.pop(cb.from_user.id, None)
    await cb.message.edit_text("🗑 Корзина очищена.")


# ════════════════  ОФОРМЛЕНИЕ  ═════════════════════════════
@router.callback_query(F.data == "checkout")
async def checkout_start(cb: CallbackQuery, state: FSMContext):
    uid = cb.from_user.id
    cart = user_carts.get(uid, [])
    if not cart:
        await cb.answer("Корзина пуста!", show_alert=True)
        return
    user = await db.get_user(uid)
    if not user or not user["phone"]:
        await cb.message.answer("Сначала зарегистрируйтесь: /start")
        return
    total = sum(i["price"] * i["qty"] for i in cart)
    await state.update_data(cart=cart, total=total)
    await cb.message.edit_text(
        "🚚 <b>Как хотите получить заказ?</b>",
        reply_markup=delivery_type_kb(), parse_mode="HTML"
    )
    await state.set_state(OrderForm.delivery_type)


@router.callback_query(OrderForm.delivery_type, F.data.startswith("dtype:"))
async def set_delivery(cb: CallbackQuery, state: FSMContext):
    dtype = cb.data.split(":")[1]
    await state.update_data(delivery_type=dtype)
    if dtype == "delivery":
        await cb.message.edit_text(
            "📍 <b>Укажите адрес доставки:</b>",
            parse_mode="HTML"
        )
        await cb.message.answer("Отправьте адрес или геолокацию 👇",
                                 reply_markup=location_kb())
        await state.set_state(OrderForm.address)
    else:
        await state.update_data(address="Самовывоз")
        await cb.message.edit_text(
            "📝 Комментарий к заказу?\n(или отправьте «—» чтобы пропустить)"
        )
        await state.set_state(OrderForm.notes)


@router.message(OrderForm.address, F.location)
async def got_location(msg: Message, state: FSMContext):
    loc = msg.location
    addr = f"📍 geo:{loc.latitude},{loc.longitude}"
    await state.update_data(address=addr)
    is_admin = msg.from_user.id in ADMIN_IDS
    await msg.answer(
        "📝 Комментарий к заказу?\n(или «—» чтобы пропустить)",
        reply_markup=main_menu_kb(is_admin)
    )
    await state.set_state(OrderForm.notes)


@router.message(OrderForm.address, F.text)
async def got_address(msg: Message, state: FSMContext):
    await state.update_data(address=msg.text)
    is_admin = msg.from_user.id in ADMIN_IDS
    await msg.answer(
        "📝 Комментарий к заказу?\n(или «—» чтобы пропустить)",
        reply_markup=main_menu_kb(is_admin)
    )
    await state.set_state(OrderForm.notes)


@router.message(OrderForm.notes)
async def got_notes(msg: Message, state: FSMContext):
    notes = msg.text if msg.text != "—" else ""
    await state.update_data(notes=notes)
    data = await state.get_data()
    cart = data["cart"]
    total = data["total"]
    dtype = "Доставка" if data["delivery_type"] == "delivery" else "Самовывоз"
    user = await db.get_user(msg.from_user.id)

    text = (
        f"📋 <b>Подтвердите заказ:</b>\n\n"
    )
    for it in cart:
        text += f"• {it['name']} × {it['qty']} — {it['price'] * it['qty']:.0f} ₽\n"
    text += f"\n💰 Итого: <b>{total:.0f} ₽</b>"
    if user and user["points"] > 0:
        text += f"\n🎁 Доступно бонусов: {user['points']}"
    text += f"\n🚚 {dtype}"
    if data.get("address") and data["delivery_type"] == "delivery":
        text += f"\n📍 {data['address']}"
    if notes:
        text += f"\n📝 {notes}"

    await msg.answer(text, reply_markup=confirm_order_kb(), parse_mode="HTML")
    await state.set_state(OrderForm.confirm)


@router.callback_query(OrderForm.confirm, F.data == "order_confirm")
async def order_confirm(cb: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    user = await db.get_user(cb.from_user.id)

    order = await db.create_order(
        telegram_id=cb.from_user.id,
        customer_name=user["first_name"],
        customer_phone=user["phone"],
        items=data["cart"],
        total=data["total"],
        source="bot",
        delivery_type=data["delivery_type"],
        address=data.get("address", ""),
        notes=data.get("notes", ""),
    )

    user_carts.pop(cb.from_user.id, None)
    await state.clear()

    active = await db.get_active_orders_count()
    est = 15 + active * 5

    await cb.message.edit_text(
        f"✅ <b>Заказ оформлен!</b>\n\n"
        f"📋 Номер: <code>{order['order_number']}</code>\n"
        f"⏱ Примерное время: ~{est} мин.\n\n"
        f"Отслеживайте статус в разделе «📦 Мои заказы»",
        parse_mode="HTML"
    )

    # Уведомить админов
    admin_text = (
        f"🔔 <b>Новый заказ из бота!</b>\n\n"
        f"📋 {order['order_number']}\n"
        f"👤 {user['first_name']} (@{user['username']})\n"
        f"📞 {user['phone']}\n"
    )
    for it in data["cart"]:
        admin_text += f"  • {it['name']} × {it['qty']}\n"
    admin_text += f"\n💰 <b>{data['total']:.0f} ₽</b>"

    from keyboards import admin_order_kb
    for aid in ADMIN_IDS:
        try:
            await bot.send_message(
                aid, admin_text, parse_mode="HTML",
                reply_markup=admin_order_kb(order["id"], "new")
            )
        except Exception:
            pass


@router.callback_query(OrderForm.confirm, F.data == "order_cancel")
async def order_abort(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("❌ Оформление отменено. Корзина сохранена.")


# ════════════════  МОИ ЗАКАЗЫ  ═════════════════════════════
@router.message(F.text == "📦 Мои заказы")
async def my_orders(msg: Message):
    orders = await db.get_user_orders(msg.from_user.id)
    if not orders:
        await msg.answer("У вас пока нет заказов.\nОткройте 📋 Меню!")
        return
    text = "📦 <b>Ваши заказы:</b>\n\n"
    for o in orders[:10]:
        st = STATUS_LABELS.get(o["status"], o["status"])
        items_str = ", ".join(f"{i['name']}×{i['qty']}" for i in o["items"])
        text += (
            f"<b>{o['order_number']}</b> | {st}\n"
            f"  {items_str}\n"
            f"  💰 {o['total']:.0f} ₽ | {o['created_at'][:16]}\n\n"
        )
    await msg.answer(text, parse_mode="HTML")


# ─── повтор заказа ─────────────────────────────────────────
@router.callback_query(F.data.startswith("repeat:"))
async def repeat_order(cb: CallbackQuery):
    order_id = int(cb.data.split(":")[1])
    order = await db.get_order(order_id)
    if not order:
        await cb.answer("Заказ не найден", show_alert=True)
        return
    uid = cb.from_user.id
    user_carts[uid] = []
    for it in order["items"]:
        user_carts[uid].append({
            "id": it.get("id", 0),
            "name": it["name"],
            "price": it["price"],
            "qty": it.get("qty", 1),
        })
    await cb.answer("🔁 Товары добавлены в корзину!")
    await cb.message.answer("🛒 Корзина обновлена! Нажмите «🛒 Корзина» для оформления.")