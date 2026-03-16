import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN')
ADMIN_IDS = [int(id) for id in os.getenv('ADMIN_IDS', '').split(',') if id]

# Webhook от сайта
WEBHOOK_SECRET = os.getenv('WEBHOOK_SECRET', 'your-secret-key')
WEBHOOK_PORT = int(os.getenv('PORT', 8080))

# Сайт
SITE_URL = os.getenv('SITE_URL', 'https://your-site.ru')
SITE_ADMIN_URL = f"{SITE_URL}/?admin=solperecadmin2024"

# База данных
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///bot.db')