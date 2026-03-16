import aiosqlite
import json
from datetime import datetime, date
from contextlib import asynccontextmanager
from config import DB_PATH


# ─── подключение ───────────────────────────────────────────
@asynccontextmanager
async def get_db():
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()


# ─── создание таблиц ──────────────────────────────────────
async def init_db():
    async with get_db() as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id     INTEGER UNIQUE,
            username        TEXT DEFAULT '',
            first_name      TEXT DEFAULT '',
            phone           TEXT DEFAULT '',
            points          INTEGER DEFAULT 0,
            total_orders    INTEGER DEFAULT 0,
            total_spent     REAL DEFAULT 0,
            birthday        TEXT DEFAULT '',
            registered_at   TEXT DEFAULT (datetime('now')),
            last_active     TEXT DEFAULT (datetime('now')),
            funnel_step     TEXT DEFAULT 'new'
        );

        CREATE TABLE IF NOT EXISTS orders (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number    TEXT UNIQUE,
            telegram_id     INTEGER,
            customer_name   TEXT DEFAULT '',
            customer_phone  TEXT DEFAULT '',
            customer_email  TEXT DEFAULT '',
            source          TEXT DEFAULT 'bot',
            items           TEXT DEFAULT '[]',
            total           REAL DEFAULT 0,
            status          TEXT DEFAULT 'new',
            delivery_type   TEXT DEFAULT 'pickup',
            address         TEXT DEFAULT '',
            payment_method  TEXT DEFAULT 'cash',
            notes           TEXT DEFAULT '',
            created_at      TEXT DEFAULT (datetime('now')),
            updated_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS menu_items (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            category    TEXT,
            name        TEXT,
            description TEXT DEFAULT '',
            price       REAL,
            available   INTEGER DEFAULT 1,
            sort_order  INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS reviews (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER,
            order_id    INTEGER,
            rating      INTEGER DEFAULT 5,
            text        TEXT DEFAULT '',
            status      TEXT DEFAULT 'pending',
            admin_reply TEXT DEFAULT '',
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS promo_codes (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            code             TEXT UNIQUE,
            discount_percent INTEGER DEFAULT 0,
            max_uses         INTEGER DEFAULT -1,
            used_count       INTEGER DEFAULT 0,
            active           INTEGER DEFAULT 1,
            expires_at       TEXT DEFAULT ''
        );
        """)
        await db.commit()
    await seed_menu()


# ─── начальное меню ────────────────────────────────────────
async def seed_menu():
    async with get_db() as db:
        cnt = await db.execute_fetchall("SELECT COUNT(*) as c FROM menu_items")
        if cnt[0]["c"] > 0:
            return
        items = [
            ("🍲 Супы", "Борщ классический", "Со сметаной и пампушками", 320),
            ("🍲 Супы", "Том Ям", "Тайский суп с креветками", 450),
            ("🍲 Супы", "Крем-суп грибной", "Из белых грибов со сливками", 380),
            ("🥗 Салаты", "Цезарь с курицей", "Романо, пармезан, соус", 420),
            ("🥗 Салаты", "Греческий", "Овощи, фета, оливки", 350),
            ("🥗 Салаты", "Оливье", "Классический рецепт", 290),
            ("🍖 Горячее", "Стейк Рибай", "300 г, medium rare", 1200),
            ("🍖 Горячее", "Паста Карбонара", "Спагетти, бекон, пармезан", 490),
            ("🍖 Горячее", "Куриная грудка гриль", "С овощами на пару", 520),
            ("🍕 Пицца", "Маргарита", "Томаты, моцарелла, базилик", 490),
            ("🍕 Пицца", "Пепперони", "Салями, моцарелла, томатный соус", 550),
            ("🍕 Пицца", "Четыре сыра", "Моцарелла, горгонзола, пармезан, чеддер", 590),
            ("🥤 Напитки", "Капучино", "200 мл", 190),
            ("🥤 Напитки", "Свежевыжатый сок", "Апельсин / яблоко", 250),
            ("🥤 Напитки", "Лимонад домашний", "Лимон-мята, 400 мл", 220),
            ("🍰 Десерты", "Тирамису", "Классический итальянский", 390),
            ("🍰 Десерты", "Чизкейк", "Нью-Йорк, ягодный соус", 350),
        ]
        await db.executemany(
            "INSERT INTO menu_items (category,name,description,price) VALUES (?,?,?,?)",
            items
        )
        await db.commit()


# ─── генерация номера заказа ───────────────────────────────
async def generate_order_number() -> str:
    today = date.today().strftime("%Y%m%d")
    async with get_db() as db:
        row = await db.execute_fetchall(
            "SELECT COUNT(*) as c FROM orders WHERE order_number LIKE ?",
            (f"SP-{today}-%",)
        )
        seq = row[0]["c"] + 1
    return f"SP-{today}-{seq:03d}"


# ═══════════════════  USERS  ═══════════════════════════════
async def upsert_user(telegram_id: int, username: str = "", first_name: str = ""):
    async with get_db() as db:
        await db.execute("""
            INSERT INTO users (telegram_id, username, first_name)
            VALUES (?, ?, ?)
            ON CONFLICT(telegram_id) DO UPDATE SET
                username=excluded.username,
                first_name=excluded.first_name,
                last_active=datetime('now')
        """, (telegram_id, username, first_name))
        await db.commit()


async def get_user(telegram_id: int):
    async with get_db() as db:
        row = await db.execute_fetchall(
            "SELECT * FROM users WHERE telegram_id=?", (telegram_id,)
        )
        return dict(row[0]) if row else None


async def update_user(telegram_id: int, **fields):
    sets = ", ".join(f"{k}=?" for k in fields)
    vals = list(fields.values()) + [telegram_id]
    async with get_db() as db:
        await db.execute(f"UPDATE users SET {sets} WHERE telegram_id=?", vals)
        await db.commit()


async def get_all_user_ids() -> list[int]:
    async with get_db() as db:
        rows = await db.execute_fetchall("SELECT telegram_id FROM users")
        return [r["telegram_id"] for r in rows]


async def get_users_count() -> int:
    async with get_db() as db:
        r = await db.execute_fetchall("SELECT COUNT(*) as c FROM users")
        return r[0]["c"]


# ═══════════════════  MENU  ════════════════════════════════
async def get_categories() -> list[str]:
    async with get_db() as db:
        rows = await db.execute_fetchall(
            "SELECT DISTINCT category FROM menu_items ORDER BY sort_order, category"
        )
        return [r["category"] for r in rows]


async def get_items_by_category(category: str):
    async with get_db() as db:
        rows = await db.execute_fetchall(
            "SELECT * FROM menu_items WHERE category=? ORDER BY sort_order, name",
            (category,)
        )
        return [dict(r) for r in rows]


async def get_menu_item(item_id: int):
    async with get_db() as db:
        rows = await db.execute_fetchall(
            "SELECT * FROM menu_items WHERE id=?", (item_id,)
        )
        return dict(rows[0]) if rows else None


async def toggle_item_available(item_id: int) -> bool:
    async with get_db() as db:
        await db.execute(
            "UPDATE menu_items SET available = NOT available WHERE id=?",
            (item_id,)
        )
        await db.commit()
        rows = await db.execute_fetchall(
            "SELECT available FROM menu_items WHERE id=?", (item_id,)
        )
        return bool(rows[0]["available"]) if rows else False


async def add_menu_item(category, name, price, description=""):
    async with get_db() as db:
        await db.execute(
            "INSERT INTO menu_items (category,name,price,description) VALUES (?,?,?,?)",
            (category, name, price, description)
        )
        await db.commit()


async def delete_menu_item(item_id: int):
    async with get_db() as db:
        await db.execute("DELETE FROM menu_items WHERE id=?", (item_id,))
        await db.commit()


# ═══════════════════  ORDERS  ══════════════════════════════
async def create_order(
    telegram_id: int | None,
    customer_name: str,
    customer_phone: str,
    items: list[dict],
    total: float,
    source: str = "bot",
    delivery_type: str = "pickup",
    address: str = "",
    payment_method: str = "cash",
    notes: str = "",
    customer_email: str = "",
) -> dict:
    order_number = await generate_order_number()
    async with get_db() as db:
        await db.execute("""
            INSERT INTO orders
            (order_number, telegram_id, customer_name, customer_phone,
             customer_email, source, items, total, delivery_type,
             address, payment_method, notes)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            order_number, telegram_id, customer_name, customer_phone,
            customer_email, source, json.dumps(items, ensure_ascii=False),
            total, delivery_type, address, payment_method, notes
        ))
        await db.commit()

    # обновить статистику пользователя
    if telegram_id:
        async with get_db() as db:
            await db.execute("""
                UPDATE users SET
                    total_orders = total_orders + 1,
                    total_spent  = total_spent + ?,
                    points       = points + ?
                WHERE telegram_id = ?
            """, (total, int(total * 0.1), telegram_id))
            await db.commit()

    return await get_order_by_number(order_number)


async def get_order_by_number(order_number: str):
    async with get_db() as db:
        rows = await db.execute_fetchall(
            "SELECT * FROM orders WHERE order_number=?", (order_number,)
        )
        if not rows:
            return None
        o = dict(rows[0])
        o["items"] = json.loads(o["items"])
        return o


async def get_order(order_id: int):
    async with get_db() as db:
        rows = await db.execute_fetchall(
            "SELECT * FROM orders WHERE id=?", (order_id,)
        )
        if not rows:
            return None
        o = dict(rows[0])
        o["items"] = json.loads(o["items"])
        return o


async def update_order_status(order_id: int, status: str):
    async with get_db() as db:
        await db.execute(
            "UPDATE orders SET status=?, updated_at=datetime('now') WHERE id=?",
            (status, order_id)
        )
        await db.commit()


async def get_user_orders(telegram_id: int, limit: int = 10):
    async with get_db() as db:
        rows = await db.execute_fetchall(
            "SELECT * FROM orders WHERE telegram_id=? ORDER BY id DESC LIMIT ?",
            (telegram_id, limit)
        )
        result = []
        for r in rows:
            o = dict(r)
            o["items"] = json.loads(o["items"])
            result.append(o)
        return result


async def get_orders_by_status(status: str | None = None, limit: int = 30):
    async with get_db() as db:
        if status:
            rows = await db.execute_fetchall(
                "SELECT * FROM orders WHERE status=? ORDER BY id DESC LIMIT ?",
                (status, limit)
            )
        else:
            rows = await db.execute_fetchall(
                "SELECT * FROM orders ORDER BY id DESC LIMIT ?", (limit,)
            )
        result = []
        for r in rows:
            o = dict(r)
            o["items"] = json.loads(o["items"])
            result.append(o)
        return result


async def get_active_orders_count() -> int:
    async with get_db() as db:
        r = await db.execute_fetchall(
            "SELECT COUNT(*) as c FROM orders WHERE status IN ('new','confirmed','cooking','ready')"
        )
        return r[0]["c"]


# ═══════════════════  REVIEWS  ═════════════════════════════
async def create_review(telegram_id: int, order_id: int, rating: int, text: str = ""):
    async with get_db() as db:
        await db.execute(
            "INSERT INTO reviews (telegram_id, order_id, rating, text) VALUES (?,?,?,?)",
            (telegram_id, order_id, rating, text)
        )
        await db.commit()


async def get_pending_reviews():
    async with get_db() as db:
        rows = await db.execute_fetchall(
            "SELECT * FROM reviews WHERE status='pending' ORDER BY id DESC"
        )
        return [dict(r) for r in rows]


async def moderate_review(review_id: int, action: str, admin_reply: str = ""):
    async with get_db() as db:
        await db.execute(
            "UPDATE reviews SET status=?, admin_reply=? WHERE id=?",
            (action, admin_reply, review_id)
        )
        await db.commit()


async def get_avg_rating() -> float:
    async with get_db() as db:
        r = await db.execute_fetchall(
            "SELECT AVG(rating) as avg FROM reviews WHERE status='approved'"
        )
        return round(r[0]["avg"] or 0, 1)


# ═══════════════════  АНАЛИТИКА  ═══════════════════════════
async def get_today_stats() -> dict:
    today = date.today().isoformat()
    async with get_db() as db:
        orders = await db.execute_fetchall(
            "SELECT COUNT(*) as c, COALESCE(SUM(total),0) as s "
            "FROM orders WHERE date(created_at)=?", (today,)
        )
        new_users = await db.execute_fetchall(
            "SELECT COUNT(*) as c FROM users WHERE date(registered_at)=?",
            (today,)
        )
        reviews = await db.execute_fetchall(
            "SELECT COUNT(*) as c FROM reviews WHERE date(created_at)=?",
            (today,)
        )
    return {
        "orders_count": orders[0]["c"],
        "revenue": orders[0]["s"],
        "new_users": new_users[0]["c"],
        "reviews": reviews[0]["c"],
    }


async def get_top_items(limit: int = 5) -> list[dict]:
    """Самые популярные позиции за всё время."""
    async with get_db() as db:
        rows = await db.execute_fetchall("SELECT items FROM orders WHERE status='completed'")
    counter: dict[str, int] = {}
    for r in rows:
        for item in json.loads(r["items"]):
            name = item.get("name", "")
            counter[name] = counter.get(name, 0) + item.get("qty", 1)
    sorted_items = sorted(counter.items(), key=lambda x: -x[1])[:limit]
    return [{"name": n, "count": c} for n, c in sorted_items]