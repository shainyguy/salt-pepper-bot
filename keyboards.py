from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)

# ═══════════════════  REPLY  ═══════════════════════════════
def main_menu_kb(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text="📋 Меню"), KeyboardButton(text="🛒 Корзина")],
        [KeyboardButton(text="📦 Мои заказы"), KeyboardButton(text="⭐ Отзывы")],
        [KeyboardButton(text="🎁 Бонусы"), KeyboardButton(text="ℹ️ О нас")],
    ]
    if is_admin:
        rows.append([KeyboardButton(text="🔧 Админ-панель")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📱 Отправить номер", request_contact=True)]],
        resize_keyboard=True, one_time_keyboard=True
    )


def location_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📍 Отправить геолокацию", request_location=True)],
            [KeyboardButton(text="✏️ Ввести адрес вручную")],
        ],
        resize_keyboard=True, one_time_keyboard=True
    )


# ═══════════════════  INLINE  ══════════════════════════════
def categories_kb(categories: list[str]) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton(text=c, callback_data=f"cat:{c}")] for c in categories]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def items_kb(items: list[dict], category: str) -> InlineKeyboardMarkup:
    buttons = []
    for it in items:
        status = "" if it["available"] else " ❌"
        buttons.append([InlineKeyboardButton(
            text=f"{it['name']} — {it['price']:.0f} ₽{status}",
            callback_data=f"item:{it['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def item_detail_kb(item_id: int, available: bool) -> InlineKeyboardMarkup:
    buttons = []
    if available:
        buttons.append([InlineKeyboardButton(
            text="🛒 В корзину", callback_data=f"add:{item_id}"
        )])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="menu_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def cart_kb(cart: list) -> InlineKeyboardMarkup:
    buttons = []
    for i, item in enumerate(cart):
        buttons.append([
            InlineKeyboardButton(text=f"❌ {item['name']}", callback_data=f"cart_del:{i}")
        ])
    buttons.append([
        InlineKeyboardButton(text="🗑 Очистить", callback_data="cart_clear"),
        InlineKeyboardButton(text="✅ Оформить", callback_data="checkout"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def delivery_type_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏃 Самовывоз", callback_data="dtype:pickup")],
        [InlineKeyboardButton(text="🚗 Доставка", callback_data="dtype:delivery")],
    ])


def confirm_order_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Подтвердить", callback_data="order_confirm"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="order_cancel"),
        ]
    ])


def order_actions_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔁 Повторить заказ", callback_data=f"repeat:{order_id}")],
        [InlineKeyboardButton(text="⭐ Оставить отзыв", callback_data=f"rev_start:{order_id}")],
    ])


def rating_kb(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"{'⭐' * i}", callback_data=f"rate:{order_id}:{i}")
        for i in range(1, 6)
    ]])


# ─── ADMIN ─────────────────────────────────────────────────
STATUS_LABELS = {
    "new": "🆕 Новый",
    "confirmed": "✅ Подтверждён",
    "cooking": "🍳 Готовится",
    "ready": "📦 Готов",
    "delivering": "🚗 Доставляется",
    "completed": "✔️ Завершён",
    "cancelled": "❌ Отменён",
}

STATUS_FLOW = ["new", "confirmed", "cooking", "ready", "delivering", "completed"]


def admin_main_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Новые заказы", callback_data="a_orders:new")],
        [InlineKeyboardButton(text="🍳 В работе", callback_data="a_orders:cooking")],
        [InlineKeyboardButton(text="📦 Все заказы", callback_data="a_orders:all")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="a_stats")],
        [InlineKeyboardButton(text="🍽 Меню (стоп-лист)", callback_data="a_menu")],
        [InlineKeyboardButton(text="⭐ Отзывы", callback_data="a_reviews")],
        [InlineKeyboardButton(text="📣 Рассылка", callback_data="a_broadcast")],
        [InlineKeyboardButton(text="👥 Пользователи", callback_data="a_users")],
    ])


def admin_order_kb(order_id: int, current_status: str) -> InlineKeyboardMarkup:
    buttons = []
    for st in STATUS_FLOW:
        if st == current_status:
            continue
        buttons.append([InlineKeyboardButton(
            text=f"→ {STATUS_LABELS[st]}",
            callback_data=f"a_st:{order_id}:{st}"
        )])
    if current_status != "cancelled":
        buttons.append([InlineKeyboardButton(
            text="❌ Отменить", callback_data=f"a_st:{order_id}:cancelled"
        )])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="a_orders:all")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def admin_stoplist_kb(items: list[dict]) -> InlineKeyboardMarkup:
    buttons = []
    for it in items:
        icon = "✅" if it["available"] else "🚫"
        buttons.append([InlineKeyboardButton(
            text=f"{icon} {it['name']} — {it['price']:.0f}₽",
            callback_data=f"a_toggle:{it['id']}"
        )])
    buttons.append([InlineKeyboardButton(text="➕ Добавить блюдо", callback_data="a_add_item")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="a_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def review_moderate_kb(review_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"rev_mod:{review_id}:approved"),
        InlineKeyboardButton(text="❌ Отклонить", callback_data=f"rev_mod:{review_id}:rejected"),
    ]])