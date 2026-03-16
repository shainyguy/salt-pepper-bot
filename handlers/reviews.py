from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
import database as db

def get_review_keyboard(review_id: int):
    """Клавиатура модерации отзыва"""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f"review_approve:{review_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"review_reject:{review_id}")
        ],
        [
            InlineKeyboardButton("✏️ Редактировать", callback_data=f"review_edit:{review_id}")
        ]
    ])

async def notify_new_review(bot, admin_ids: list, review_data: dict):
    """Отправить отзыв на модерацию"""
    review_id = await db.create_review(review_data)
    
    stars = '⭐' * review_data.get('rating', 5)
    
    message = f"""
📝 <b>НОВЫЙ ОТЗЫВ</b>

{stars}

👤 <b>Автор:</b> {review_data.get('author')}
📱 <b>Телефон:</b> {review_data.get('phone')}

💬 <i>"{review_data.get('text')}"</i>
"""
    
    keyboard = get_review_keyboard(review_id)
    
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
    
    return review_id

async def handle_review_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка модерации отзыва"""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split(':')
    action = data[0]
    review_id = int(data[1])
    
    if action == 'review_approve':
        await db.update_review_status(review_id, 'approved')
        await query.edit_message_text(
            text=query.message.text + "\n\n✅ <b>ОДОБРЕН</b>",
            parse_mode='HTML'
        )
        
    elif action == 'review_reject':
        await db.update_review_status(review_id, 'rejected')
        await query.edit_message_text(
            text=query.message.text + "\n\n❌ <b>ОТКЛОНЁН</b>",
            parse_mode='HTML'
        )
        
    elif action == 'review_edit':
        context.user_data['editing_review'] = review_id
        await query.message.reply_text(
            "✏️ Отправьте отредактированный текст отзыва:"
        )