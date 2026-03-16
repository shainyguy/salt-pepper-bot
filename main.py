import asyncio
import logging
from aiohttp import web
from telegram import Update, Bot
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, filters
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

import config
import database as db
from handlers.orders import handle_order_callback, notify_new_order
from handlers.reviews import handle_review_callback, notify_new_review
from handlers.funnels import process_funnel_queue, check_inactive_customers
from handlers.admin import cmd_start, cmd_orders, cmd_reviews, cmd_stats, cmd_broadcast

# Логирование
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Глобальные переменные
bot: Bot = None
scheduler: AsyncIOScheduler = None

# ============ WEBHOOK HANDLERS ============

async def handle_webhook(request):
    """Обработка вебхуков от сайта"""
    try:
        # Проверка секретного ключа
        secret = request.headers.get('X-Webhook-Secret')
        if secret != config.WEBHOOK_SECRET:
            return web.Response(status=403, text='Forbidden')
        
        data = await request.json()
        event_type = data.get('type')
        
        if event_type == 'new_order':
            await notify_new_order(bot, config.ADMIN_IDS, data.get('order', {}))
            return web.json_response({'status': 'ok', 'message': 'Order notification sent'})
        
        elif event_type == 'new_review':
            await notify_new_review(bot, config.ADMIN_IDS, data.get('review', {}))
            return web.json_response({'status': 'ok', 'message': 'Review sent for moderation'})
        
        elif event_type == 'new_banquet':
            # Уведомление о банкете
            banquet = data.get('banquet', {})
            message = f"""
🎉 <b>НОВАЯ ЗАЯВКА НА БАНКЕТ</b>

👤 {banquet.get('name')}
📱 {banquet.get('phone')}
📅 {banquet.get('date')}
👥 {banquet.get('guests')} чел.
📦 Пакет: {banquet.get('package')}
💰 Сумма: {banquet.get('total')} ₽
"""
            for admin_id in config.ADMIN_IDS:
                await bot.send_message(admin_id, message, parse_mode='HTML')
            return web.json_response({'status': 'ok'})
        
        elif event_type == 'new_contact':
            # Сообщение с формы контактов
            contact = data.get('contact', {})
            message = f"""
💬 <b>НОВОЕ СООБЩЕНИЕ</b>

👤 {contact.get('name')}
📱 {contact.get('phone')}

📝 {contact.get('message')}
"""
            for admin_id in config.ADMIN_IDS:
                await bot.send_message(admin_id, message, parse_mode='HTML')
            return web.json_response({'status': 'ok'})
        
        return web.json_response({'status': 'ok'})
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return web.Response(status=500, text=str(e))

async def health_check(request):
    """Health check endpoint"""
    return web.Response(text='OK')

# ============ SCHEDULED TASKS ============

async def scheduled_funnel_task():
    """Периодическая задача — обработка воронок"""
    await process_funnel_queue(bot, config.ADMIN_IDS)

async def scheduled_inactive_check():
    """Периодическая задача — проверка неактивных"""
    await check_inactive_customers(bot, config.ADMIN_IDS)

# ============ MAIN ============

async def main():
    global bot, scheduler
    
    # Инициализация БД
    await db.init_db()
    
    # Создаём приложение Telegram
    application = Application.builder().token(config.BOT_TOKEN).build()
    bot = application.bot
    
    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("orders", cmd_orders))
    application.add_handler(CommandHandler("reviews", cmd_reviews))
    application.add_handler(CommandHandler("stats", cmd_stats))
    application.add_handler(CommandHandler("broadcast", cmd_broadcast))
    
    # Callback handlers
    application.add_handler(CallbackQueryHandler(handle_order_callback, pattern=r'^order_'))
    application.add_handler(CallbackQueryHandler(handle_review_callback, pattern=r'^review_'))
    
    # Запускаем планировщик
    scheduler = AsyncIOScheduler()
    scheduler.add_job(scheduled_funnel_task, 'interval', minutes=5)
    scheduler.add_job(scheduled_inactive_check, 'cron', hour=10)  # Каждый день в 10:00
    scheduler.start()
    
    # Запускаем веб-сервер для вебхуков
    app = web.Application()
    app.router.add_post('/webhook', handle_webhook)
    app.router.add_get('/health', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', config.WEBHOOK_PORT)
    await site.start()
    
    logger.info(f"Webhook server started on port {config.WEBHOOK_PORT}")
    
    # Запускаем бота
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