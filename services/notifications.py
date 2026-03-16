"""
Универсальные уведомления.
Можно расширять: SMS, WhatsApp, email через внешние API.
"""
from aiogram import Bot
from config import ADMIN_IDS


async def notify_admins(bot: Bot, text: str, **kwargs):
    for aid in ADMIN_IDS:
        try:
            await bot.send_message(aid, text, parse_mode="HTML", **kwargs)
        except Exception:
            pass


async def notify_user(bot: Bot, telegram_id: int, text: str, **kwargs):
    try:
        await bot.send_message(telegram_id, text, parse_mode="HTML", **kwargs)
        return True
    except Exception:
        return False


# ── заглушки для SMS/WhatsApp ──────────────────────────────
async def send_sms(phone: str, text: str):
    """
    Подключите Twilio, SMS.ru или любой SMS-сервис.
    Пример для SMS.ru:
        import httpx
        async with httpx.AsyncClient() as client:
            await client.get("https://sms.ru/sms/send", params={
                "api_id": SMS_API_KEY,
                "to": phone,
                "msg": text,
                "json": 1
            })
    """
    print(f"[SMS → {phone}]: {text}")


async def send_whatsapp(phone: str, text: str):
    """
    Подключите WhatsApp Business API (WABA) или сервис типа
    Green-API, Chat-API и т.д.
    """
    print(f"[WhatsApp → {phone}]: {text}")