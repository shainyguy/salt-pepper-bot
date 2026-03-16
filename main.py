# main.py
import asyncio
import logging
from aiohttp import web
from telegram import Update, Bot
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
import database as db  # должен быть async SQLAlchemy setup
from handlers.orders import handle_order_callback
from handlers.reviews import handle_review_callback
from handlers.funnels import process_funnel_queue, check_inactive_customers
from handlers.admin import cmd_start, cmd_reviews, cmd_stats, cmd_broadcast

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Глобальные переменные
bot: Bot = None
scheduler: AsyncIOScheduler = None
orders_cache = []  # кэш заказов


# ============ WEBHOOK HANDLERS ============

async def notify_new_order(order_data: dict):
    """Сохраняем заказ в БД и шлём уведомление админам"""
    global orders_cache
    async with db.async_session() as session:
        from database.models import Order  # импорт модели заказа
        # Проверка на дубли
        existing = await session.get(Order, order_data.get('external_id'))
        if existing:
            return

        order = Order(
            external_id=str(order_data['id']),
            customer_name=order_data['customer_name'],
            status='new'
        )
        session.add(order)
        await session.commit()
        orders_cache.append(order)  # обновляем кэш

    # Отправляем уведомление
    message = f"📦 Новый заказ: {order.customer_name}\nID: {order.external_id}"
    for admin_id in config.ADMIN_IDS:
        await bot.send_message(admin_id, message)


async def handle_webhook(request):
    """Обработка вебхуков от сайта"""
    try:
        secret = request.headers.get('X-Webhook-Secret')
        if secret != config.WEBHOOK_SECRET:
            return web.Response(status=403, text='Forbidden')

        data = await request.json()
        event_type = data.get('type')

        if event_type == 'new_order':
            await notify_new_order(data.get('order', {}))
            return web.json_response({'status': 'ok', 'message': 'Order saved & notification sent'})

        # остальные типы событий (отзывы, банкет, контакты)
        return web.json_response({'status': 'ok'})

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return web.Response(status=500, text=str(e))


async def health_check(request):
    return web.Response(text='OK')


# ============ BOT COMMANDS ============

async def cmd_orders(update: Update, context):
    """Показываем все заказы из кэша"""
    global orders_cache
    # Если кэш пустой, грузим из БД
    if not orders_cache:
        async with db.async_session() as session:
            from database.models import Order
            orders = await session.execute(db.select(Order))
            orders_cache = orders.scalars().all()

    if not orders_cache:
        await update.message.reply_text("Заказов нет.")
        return

    text = "\n".join([f"{o.id} | {o.external_id} | {o.customer_name} | {o.status}" 
                      for o in orders_cache])
    await update.message.reply_text(text)


# ============ SCHEDULED TASKS ============

async def scheduled_funnel_task():
    await process_funnel_queue(bot, config.ADMIN_IDS)

async def scheduled_inactive_check():
    await check_inactive_customers(bot, config.ADMIN_IDS)


# ============ MAIN ============

async def main():
    global bot, scheduler

    # Инициализация БД
    await db.init_db()

    # Создаём Telegram Application
    application = Application.builder().token(config.BOT_TOKEN).build()
    bot = application.bot

    # Команды
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("orders", cmd_orders))
    application.add_handler(CommandHandler("reviews", cmd_reviews))
    application.add_handler(CommandHandler("stats", cmd_stats))
    application.add_handler(CommandHandler("broadcast", cmd_broadcast))

    # Callback handlers
    application.add_handler(CallbackQueryHandler(handle_order_callback, pattern=r'^order_'))
    application.add_handler(CallbackQueryHandler(handle_review_callback, pattern=r'^review_'))

    # Планировщик
    scheduler = AsyncIOScheduler()
    scheduler.add_job(scheduled_funnel_task, 'interval', minutes=5)
    scheduler.add_job(scheduled_inactive_check, 'cron', hour=10)
    scheduler.start()

    # Вебсервер для webhook
    app = web.Application()
    app.router.add_post('/webhook', handle_webhook)
    app.router.add_get('/health', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', config.WEBHOOK_PORT)
    await site.start()
    logger.info(f"Webhook server started on port {config.WEBHOOK_PORT}")

    # Запуск бота
    await application.initialize()
    await application.start()
    await application.updater.start_polling()
    logger.info("Bot started!")

    # Ждём завершения
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        scheduler.shutdown()
        await application.stop()
        await runner.cleanup()


if __name__ == '__main__':
    asyncio.run(main())
