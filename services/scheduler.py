"""
Планировщик:
- ежедневный отчёт для админов (21:00)
- реактивация неактивных (раз в день)
- проверка непросмотренных отзывов (каждый час)
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot
from datetime import datetime, timedelta

import database as db
from config import ADMIN_IDS
from keyboards import STATUS_LABELS


def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

    # ── ежедневный отчёт в 21:00 ──
    scheduler.add_job(daily_report, "cron", hour=21, minute=0, args=[bot])

    # ── реактивация каждый день в 12:00 ──
    scheduler.add_job(reactivation, "cron", hour=12, minute=0, args=[bot])

    # ── напоминание о непросмотренных отзывах каждые 2 часа ──
    scheduler.add_job(review_reminder, "interval", hours=2, args=[bot])

    return scheduler


async def daily_report(bot: Bot):
    stats = await db.get_today_stats()
    top = await db.get_top_items(3)
    avg = await db.get_avg_rating()
    top_text = "\n".join(f"  {i+1}. {t['name']} ({t['count']})" for i, t in enumerate(top))

    text = (
        f"📊 <b>Дневной отчёт</b> ({datetime.now().strftime('%d.%m.%Y')})\n\n"
        f"📦 Заказов: {stats['orders_count']}\n"
        f"💰 Выручка: {stats['revenue']:.0f} ₽\n"
        f"👤 Новых клиентов: {stats['new_users']}\n"
        f"⭐ Отзывов: {stats['reviews']}\n"
        f"⭐ Средний рейтинг: {avg}\n\n"
        f"🏆 Топ блюд сегодня:\n{top_text or '  нет данных'}"
    )
    for aid in ADMIN_IDS:
        try:
            await bot.send_message(aid, text, parse_mode="HTML")
        except Exception:
            pass


async def reactivation(bot: Bot):
    """Отправить напоминание пользователям, неактивным 7+ дней."""
    cutoff = (datetime.now() - timedelta(days=7)).isoformat()
    async with db.get_db() as conn:
        rows = await conn.execute_fetchall(
            "SELECT telegram_id, first_name FROM users "
            "WHERE last_active < ? AND funnel_step != 'reactivated'",
            (cutoff,)
        )
    sent = 0
    for r in rows:
        try:
            await bot.send_message(
                r["telegram_id"],
                f"👋 {r['first_name']}, мы скучаем!\n\n"
                f"Давно не виделись. Специально для вас — "
                f"<b>скидка 15%</b> на следующий заказ! 🎁\n\n"
                f"Промокод: <code>COMEBACK15</code>\n"
                f"Действует 3 дня.",
                parse_mode="HTML"
            )
            await db.update_user(r["telegram_id"], funnel_step="reactivated")
            sent += 1
        except Exception:
            pass
    if sent > 0:
        for aid in ADMIN_IDS:
            try:
                await bot.send_message(aid, f"🔄 Реактивация: отправлено {sent} сообщений")
            except Exception:
                pass


async def review_reminder(bot: Bot):
    """Напомнить админам о непросмотренных отзывах."""
    pending = await db.get_pending_reviews()
    if not pending:
        return
    cnt = len(pending)
    for aid in ADMIN_IDS:
        try:
            await bot.send_message(
                aid,
                f"⭐ Непросмотренных отзывов: <b>{cnt}</b>\n"
                f"Зайдите в Админ-панель → Отзывы",
                parse_mode="HTML"
            )
        except Exception:
            pass