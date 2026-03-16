from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db

ORDER_STATUSES = {
    'new': '🆕 Новый',
    'confirmed': '✅ Подтверждён',
    'cooking': '👨‍🍳 Готовится',
    'ready': '🍽️ Готов',
    'delivering': '🚗 В доставке',
    'completed': '✔️ Завершён',
    'cancelled': '❌ Отменён'
}

def get_order_keyboard(order_number: int, current_status: str):
    """Клавиатура управления заказом"""
    buttons = []
    
    status_flow = ['new', 'confirmed', 'cooking', 'ready', 'delivering', 'completed']
    current_index = status_flow.index(current_status) if current_status in status_flow else 0
    
    # Следующий статус
    if current_index < len(status_flow) - 1:
        next_status = status_flow[current_index + 1]
        buttons.append([
            InlineKeyboardButton(
                f"➡️ {ORDER_STATUSES[next_status]}", 
                callback_data=f"order_status:{order_number}:{next_status}"
            )
        ])
    
    # Отмена
    if current_status not in ['completed', 'cancelled']:
        buttons.append([
            InlineKeyboardButton(
                "❌ Отменить", 
                callback_data=f"order_status:{order_number}:cancelled"
            )
        ])
    
    # Позвонить
    buttons.append([
        InlineKeyboardButton("📞 Позвонить клиенту", callback_data=f"order_call:{order_number}")
    ])
    
    return InlineKeyboardMarkup(buttons)

async def notify_new_order(bot, admin_ids: list, order_data: dict):
    """Отправить уведомление о новом заказе всем админам"""
    order_number = await db.create_order(order_data)
    
    # Создаём/обновляем клиента
    await db.create_or_update_customer(
        phone=order_data.get('phone'),
        name=order_data.get('name'),
        order_total=order_data.get('total', 0)
    )
    
    # Формируем сообщение
    items_text = "\n".join([
        f"  • {item['name']} × {item['quantity']} = {item['price'] * item['quantity']} ₽"
        for item in order_data.get('items', [])
    ])
    
    message = f"""
🆕 <b>НОВЫЙ ЗАКАЗ #{order_number}</b>

👤 <b>Клиент:</b> {order_data.get('name')}
📱 <b>Телефон:</b> {order_data.get('phone')}

📦 <b>Тип:</b> {'🚗 Доставка' if order_data.get('delivery_type') == 'delivery' else '🏪 Самовывоз'}
{f"📍 <b>Адрес:</b> {order_data.get('address')}" if order_data.get('address') else ""}

🛒 <b>Состав заказа:</b>
{items_text}

💰 <b>Итого:</b> {order_data.get('total', 0)} ₽
💳 <b>Оплата:</b> {order_data.get('payment_method', 'Наличные')}
"""
    
    keyboard = get_order_keyboard(order_number, 'new')
    
    # Отправляем всем админам
    for admin_id in admin_ids:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text=message,
                parse_mode='HTML',
                reply_markup=keyboard
            )
        except Exception as e:
            print(f"Error sending to admin {admin_id}: {e}")
    
    return order_number

async def handle_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатий кнопок заказа"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split(':')
    action = data[0]
    
    if action == 'order_status':
        order_number = int(data[1])
        new_status = data[2]
        
        await db.update_order_status(order_number, new_status)
        
        # Обновляем сообщение
        await query.edit_message_text(
            text=query.message.text + f"\n\n✅ <b>Статус изменён:</b> {ORDER_STATUSES[new_status]}",
            parse_mode='HTML',
            reply_markup=get_order_keyboard(order_number, new_status) if new_status not in ['completed', 'cancelled'] else None
        )
        
    elif action == 'order_call':
        order_number = int(data[1])
        orders = await db.get_orders()
        order = next((o for o in orders if o['order_number'] == order_number), None)
        
        if order:
            await query.message.reply_text(
                f"📞 Позвоните клиенту:\n\n"
                f"👤 {order['customer_name']}\n"
                f"📱 <a href='tel:{order['customer_phone']}'>{order['customer_phone']}</a>",
                parse_mode='HTML'
            )