from telegram import Update
from telegram.ext import ContextTypes
import database as db

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    await update.message.reply_text(
        "🍖 <b>Бот кафе «Соль и Перец»</b>\n\n"
        "Команды:\n"
        "/orders — Список заказов\n"
        "/reviews — Отзывы на модерации\n"
        "/customers — База клиентов\n"
        "/stats — Статистика\n"
        "/broadcast — Рассылка",
        parse_mode='HTML'
    )

async def cmd_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /orders — список заказов"""
    orders = await db.get_orders(limit=10)
    
    if not orders:
        await update.message.reply_text("📦 Нет заказов")
        return
    
    text = "📦 <b>Последние заказы:</b>\n\n"
    
    for order in orders:
        status_emoji = {
            'new': '🆕', 'confirmed': '✅', 'cooking': '👨‍🍳',
            'ready': '🍽️', 'delivering': '🚗', 'completed': '✔️', 'cancelled': '❌'
        }
        
        text += f"{status_emoji.get(order['status'], '❓')} #{order['order_number']} — {order['customer_name']} — {order['total']} ₽\n"
    
    await update.message.reply_text(text, parse_mode='HTML')

async def cmd_reviews(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /reviews — отзывы на модерации"""
    reviews = await db.get_pending_reviews()
    
    if not reviews:
        await update.message.reply_text("⭐ Нет отзывов на модерации")
        return
    
    text = "⭐ <b>Отзывы на модерации:</b>\n\n"
    
    for review in reviews:
        stars = '⭐' * review['rating']
        text += f"{stars}\n👤 {review['author']}\n💬 {review['text'][:100]}...\n\n"
    
    await update.message.reply_text(text, parse_mode='HTML')

async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stats — статистика"""
    orders = await db.get_orders()
    customers = await db.get_all_customers()
    
    total_revenue = sum(o.get('total', 0) for o in orders if o.get('status') != 'cancelled')
    
    text = f"""
📊 <b>Статистика</b>

📦 Всего заказов: {len(orders)}
👥 Клиентов: {len(customers)}
💰 Выручка: {total_revenue:,.0f} ₽
"""
    
    await update.message.reply_text(text, parse_mode='HTML')

async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /broadcast — рассылка"""
    context.user_data['broadcast_mode'] = True
    await update.message.reply_text(
        "📢 Отправьте сообщение для рассылки всем клиентам:\n\n"
        "(Отправьте /cancel для отмены)"
    )