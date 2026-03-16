from datetime import datetime, timedelta
from telegram import Bot
import database as db

# Настройки воронок
FUNNELS = {
    # После заказа
    'after_order': [
        {
            'delay_hours': 1,
            'message': """🙏 Спасибо за заказ в «Соль и Перец»!

Надеемся, вам понравилось! 

⭐ Оставьте отзыв на нашем сайте и получите 100 бонусных баллов!

{site_url}#reviews"""
        },
        {
            'delay_hours': 24,
            'message': """📝 Как вам наши блюда?

Ваше мнение важно для нас! 

Оставьте отзыв и получите:
🎁 100 баллов на счёт
🎁 Скидку 10% на следующий заказ!"""
        }
    ],
    
    # Брошенная корзина (если интегрировать с сайтом)
    'abandoned_cart': [
        {
            'delay_hours': 1,
            'message': """👋 Вы что-то забыли!

Ваша корзина ждёт вас в «Соль и Перец»

🎁 Закажите в течение часа — доставка бесплатно!

Промокод: FREESHIP"""
        }
    ],
    
    # Неактивные клиенты
    'inactive': [
        {
            'delay_days': 14,
            'message': """👋 Давно не виделись!

Соскучились по нашему фирменному шашлыку?

🔥 Специально для вас — скидка 15% на любой заказ!

Промокод: COMEBACK15
Действует 3 дня"""
        }
    ]
}

async def schedule_funnel_messages(phone: str, funnel_type: str, site_url: str):
    """Запланировать сообщения воронки"""
    funnel = FUNNELS.get(funnel_type, [])
    
    for step in funnel:
        delay_hours = step.get('delay_hours', 0)
        delay_days = step.get('delay_days', 0)
        
        scheduled_at = datetime.now() + timedelta(hours=delay_hours, days=delay_days)
        message_text = step['message'].format(site_url=site_url)
        
        await db.add_to_funnel_queue(
            phone=phone,
            message_type=funnel_type,
            message_text=message_text,
            scheduled_at=scheduled_at
        )

async def process_funnel_queue(bot: Bot, admin_ids: list):
    """Обработать очередь сообщений воронки"""
    messages = await db.get_pending_funnel_messages()
    
    for msg in messages:
        # В реальности здесь отправка SMS/WhatsApp
        # Для демо — уведомляем админов
        for admin_id in admin_ids:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=f"📤 <b>Воронка — отправить клиенту:</b>\n\n"
                         f"📱 {msg['customer_phone']}\n\n"
                         f"{msg['message_text']}",
                    parse_mode='HTML'
                )
            except Exception as e:
                print(f"Error: {e}")
        
        await db.mark_funnel_message_sent(msg['id'])

async def check_inactive_customers(bot: Bot, admin_ids: list):
    """Проверить неактивных клиентов"""
    customers = await db.get_all_customers()
    
    for customer in customers:
        if not customer.get('last_order_date'):
            continue
            
        last_order = datetime.fromisoformat(customer['last_order_date'])
        days_inactive = (datetime.now() - last_order).days
        
        # Если не заказывал 14+ дней
        if days_inactive >= 14 and customer.get('funnel_step') != 'inactive_sent':
            await schedule_funnel_messages(
                phone=customer['phone'],
                funnel_type='inactive',
                site_url='https://your-site.ru'
            )
