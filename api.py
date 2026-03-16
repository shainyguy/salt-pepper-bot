"""
FastAPI-сервер: принимает заказы с сайта, отдаёт статус.
Сайт отправляет POST /api/orders с заголовком X-API-Key.
"""
from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel
import database as db
from config import API_SECRET, ADMIN_IDS

app = FastAPI(title="Salt & Pepper Bot API")

# ── Telegram-бот будет подключён в main.py ──
# app.state.bot  — проставляется снаружи


# ─── Модели ────────────────────────────────────────────────
class OrderItem(BaseModel):
    name: str
    qty: int = 1
    price: float


class NewOrder(BaseModel):
    customer_name: str
    customer_phone: str
    customer_email: str = ""
    items: list[OrderItem]
    total: float
    delivery_type: str = "pickup"        # pickup / delivery
    address: str = ""
    payment_method: str = "cash"         # cash / card / online
    notes: str = ""
    telegram_id: int | None = None       # если клиент привязал Telegram


class OrderResponse(BaseModel):
    success: bool = True
    order_number: str
    estimated_minutes: int


# ─── проверка ключа ───────────────────────────────────────
def verify_key(key: str | None):
    if key != API_SECRET:
        raise HTTPException(401, "Invalid API key")


# ─── создать заказ (с сайта) ──────────────────────────────
@app.post("/api/orders", response_model=OrderResponse)
async def create_order_api(body: NewOrder, x_api_key: str = Header(None)):
    verify_key(x_api_key)

    items = [i.model_dump() for i in body.items]

    active = await db.get_active_orders_count()
    est_minutes = 15 + active * 5           # простая оценка времени

    order = await db.create_order(
        telegram_id=body.telegram_id,
        customer_name=body.customer_name,
        customer_phone=body.customer_phone,
        customer_email=body.customer_email,
        items=items,
        total=body.total,
        source="website",
        delivery_type=body.delivery_type,
        address=body.address,
        payment_method=body.payment_method,
        notes=body.notes,
    )

    # ── уведомить админов в Telegram ──
    bot = app.state.bot
    text = (
        f"🌐 <b>Новый заказ с сайта!</b>\n\n"
        f"📋 <b>{order['order_number']}</b>\n"
        f"👤 {body.customer_name}\n"
        f"📞 {body.customer_phone}\n"
        f"🚚 {'Доставка' if body.delivery_type == 'delivery' else 'Самовывоз'}\n"
    )
    if body.address:
        text += f"📍 {body.address}\n"
    text += "\n"
    for it in items:
        text += f"  • {it['name']} × {it['qty']} — {it['price'] * it['qty']:.0f} ₽\n"
    text += f"\n💰 <b>Итого: {body.total:.0f} ₽</b>"
    if body.notes:
        text += f"\n📝 {body.notes}"

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, parse_mode="HTML")
        except Exception:
            pass

    # ── уведомить клиента, если есть telegram_id ──
    if body.telegram_id:
        try:
            await bot.send_message(
                body.telegram_id,
                f"✅ Ваш заказ <b>{order['order_number']}</b> принят!\n"
                f"⏱ Примерное время: ~{est_minutes} мин.\n"
                f"Отслеживайте статус: /status_{order['order_number']}",
                parse_mode="HTML"
            )
        except Exception:
            pass

    return OrderResponse(
        order_number=order["order_number"],
        estimated_minutes=est_minutes
    )


# ─── статус заказа (для сайта) ────────────────────────────
@app.get("/api/orders/{order_number}")
async def get_order_status_api(order_number: str, x_api_key: str = Header(None)):
    verify_key(x_api_key)
    order = await db.get_order_by_number(order_number)
    if not order:
        raise HTTPException(404, "Order not found")
    return {
        "order_number": order["order_number"],
        "status": order["status"],
        "items": order["items"],
        "total": order["total"],
        "created_at": order["created_at"],
        "updated_at": order["updated_at"],
    }


# ─── получить меню (для сайта) ────────────────────────────
@app.get("/api/menu")
async def get_menu_api(x_api_key: str = Header(None)):
    verify_key(x_api_key)
    categories = await db.get_categories()
    result = {}
    for cat in categories:
        items = await db.get_items_by_category(cat)
        result[cat] = [
            {"id": i["id"], "name": i["name"], "description": i["description"],
             "price": i["price"], "available": bool(i["available"])}
            for i in items
        ]
    return result


# ─── healthcheck ───────────────────────────────────────────
@app.get("/health")
async def health():
    return {"status": "ok"}