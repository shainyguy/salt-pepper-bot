import aiosqlite
from datetime import datetime
from typing import Optional, List, Dict, Any

DATABASE_FILE = 'bot.db'

async def init_db():
    """Инициализация базы данных"""
    async with aiosqlite.connect(DATABASE_FILE) as db:
        # Таблица клиентов
        await db.execute('''
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT UNIQUE NOT NULL,
                name TEXT,
                telegram_id INTEGER,
                loyalty_points INTEGER DEFAULT 0,
                total_spent REAL DEFAULT 0,
                orders_count INTEGER DEFAULT 0,
                last_order_date TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                funnel_step TEXT,
                funnel_updated_at TEXT
            )
        ''')
        
        # Таблица заказов
        await db.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_number INTEGER UNIQUE,
                customer_phone TEXT,
                customer_name TEXT,
                items TEXT,
                total REAL,
                status TEXT DEFAULT 'new',
                delivery_type TEXT,
                address TEXT,
                payment_method TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT,
                notes TEXT,
                telegram_message_id INTEGER
            )
        ''')
        
        # Таблица отзывов
        await db.execute('''
            CREATE TABLE IF NOT EXISTS reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                author TEXT,
                phone TEXT,
                rating INTEGER,
                text TEXT,
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                admin_comment TEXT,
                telegram_message_id INTEGER
            )
        ''')
        
        # Таблица банкетов
        await db.execute('''
            CREATE TABLE IF NOT EXISTS banquets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT,
                customer_phone TEXT,
                event_date TEXT,
                guests_count INTEGER,
                package TEXT,
                extras TEXT,
                total REAL,
                status TEXT DEFAULT 'new',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                notes TEXT
            )
        ''')
        
        # Таблица сообщений воронок
        await db.execute('''
            CREATE TABLE IF NOT EXISTS funnel_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_phone TEXT,
                message_type TEXT,
                message_text TEXT,
                scheduled_at TEXT,
                sent_at TEXT,
                status TEXT DEFAULT 'pending'
            )
        ''')
        
        await db.commit()

# ============ CUSTOMERS ============

async def get_customer(phone: str) -> Optional[Dict]:
    async with aiosqlite.connect(DATABASE_FILE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            'SELECT * FROM customers WHERE phone = ?', (phone,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

async def create_or_update_customer(phone: str, name: str = None, 
                                    order_total: float = 0, telegram_id: int = None):
    async with aiosqlite.connect(DATABASE_FILE) as db:
        customer = await get_customer(phone)
        
        if customer:
            await db.execute('''
                UPDATE customers SET
                    name = COALESCE(?, name),
                    telegram_id = COALESCE(?, telegram_id),
                    total_spent = total_spent + ?,
                    orders_count = orders_count + 1,
                    loyalty_points = loyalty_points + ?,
                    last_order_date = ?
                WHERE phone = ?
            ''', (name, telegram_id, order_total, int(order_total * 0.05), 
                  datetime.now().isoformat(), phone))
        else:
            await db.execute('''
                INSERT INTO customers (phone, name, telegram_id, total_spent, 
                                       orders_count, loyalty_points, last_order_date)
                VALUES (?, ?, ?, ?, 1, ?, ?)
            ''', (phone, name, telegram_id, order_total, 
                  int(order_total * 0.05), datetime.now().isoformat()))
        
        await db.commit()

async def get_all_customers() -> List[Dict]:
    async with aiosqlite.connect(DATABASE_FILE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('SELECT * FROM customers ORDER BY created_at DESC')
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

# ============ ORDERS ============

async def create_order(order_data: Dict) -> int:
    async with aiosqlite.connect(DATABASE_FILE) as db:
        cursor = await db.execute('SELECT MAX(order_number) FROM orders')
        result = await cursor.fetchone()
        next_number = (result[0] or 1000) + 1
        
        await db.execute('''
            INSERT INTO orders (order_number, customer_phone, customer_name, items,
                               total, delivery_type, address, payment_method, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            next_number,
            order_data.get('phone'),
            order_data.get('name'),
            str(order_data.get('items', [])),
            order_data.get('total', 0),
            order_data.get('delivery_type', 'pickup'),
            order_data.get('address'),
            order_data.get('payment_method', 'cash'),
            datetime.now().isoformat()
        ))
        await db.commit()
        return next_number

async def update_order_status(order_number: int, status: str):
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute('''
            UPDATE orders SET status = ?, updated_at = ? WHERE order_number = ?
        ''', (status, datetime.now().isoformat(), order_number))
        await db.commit()

async def get_orders(status: str = None, limit: int = 50) -> List[Dict]:
    async with aiosqlite.connect(DATABASE_FILE) as db:
        db.row_factory = aiosqlite.Row
        if status:
            cursor = await db.execute(
                'SELECT * FROM orders WHERE status = ? ORDER BY created_at DESC LIMIT ?',
                (status, limit)
            )
        else:
            cursor = await db.execute(
                'SELECT * FROM orders ORDER BY created_at DESC LIMIT ?', (limit,)
            )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

# ============ REVIEWS ============

async def create_review(review_data: Dict) -> int:
    async with aiosqlite.connect(DATABASE_FILE) as db:
        cursor = await db.execute('''
            INSERT INTO reviews (author, phone, rating, text, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            review_data.get('author'),
            review_data.get('phone'),
            review_data.get('rating'),
            review_data.get('text'),
            datetime.now().isoformat()
        ))
        await db.commit()
        return cursor.lastrowid

async def update_review_status(review_id: int, status: str, admin_comment: str = None):
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute('''
            UPDATE reviews SET status = ?, admin_comment = ? WHERE id = ?
        ''', (status, admin_comment, review_id))
        await db.commit()

async def get_pending_reviews() -> List[Dict]:
    async with aiosqlite.connect(DATABASE_FILE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM reviews WHERE status = 'pending' ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

# ============ FUNNELS ============

async def add_to_funnel_queue(phone: str, message_type: str, 
                              message_text: str, scheduled_at: datetime):
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute('''
            INSERT INTO funnel_queue (customer_phone, message_type, message_text, scheduled_at)
            VALUES (?, ?, ?, ?)
        ''', (phone, message_type, message_text, scheduled_at.isoformat()))
        await db.commit()

async def get_pending_funnel_messages() -> List[Dict]:
    async with aiosqlite.connect(DATABASE_FILE) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute('''
            SELECT * FROM funnel_queue 
            WHERE status = 'pending' AND scheduled_at <= ?
            ORDER BY scheduled_at
        ''', (datetime.now().isoformat(),))
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def mark_funnel_message_sent(message_id: int):
    async with aiosqlite.connect(DATABASE_FILE) as db:
        await db.execute('''
            UPDATE funnel_queue SET status = 'sent', sent_at = ? WHERE id = ?
        ''', (datetime.now().isoformat(), message_id))
        await db.commit()