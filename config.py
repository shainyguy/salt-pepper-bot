import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
API_SECRET = os.getenv("API_SECRET", "change-me-secret")
PORT = int(os.getenv("PORT", 8080))
DB_PATH = os.getenv("DB_PATH", "cafe.db")

CAFE_NAME = "Соль и Перец 🧂🌶"
CAFE_ADDRESS = os.getenv("CAFE_ADDRESS", "ул. Примерная, 1")
CAFE_PHONE = os.getenv("CAFE_PHONE", "+7 (999) 123-45-67")
SITE_URL = os.getenv("SITE_URL", "https://salt-pepper.example.com")
WORK_HOURS = os.getenv("WORK_HOURS", "10:00–22:00")
POINTS_PER_RUBLE = 0.1          # 1 бонус за каждые 10 ₽
POINTS_TO_RUBLE = 1.0           # 1 бонус = 1 ₽ скидки