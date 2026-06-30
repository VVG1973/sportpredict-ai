# Version: 2.0 - with favorites_router
import asyncio
import logging
import sys
import random
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Dispatcher
from config import settings

logging.basicConfig(
level=getattr(logging, settings.LOG_LEVEL),
format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
stream=sys.stdout
)
logger = logging.getLogger(__name__)

from data_collectors.real_sports_parser import HybridSportsParser as MultiSportParser
from data_collectors.api_football_parser import APIFootballParser
logger.info("🧪 ЗАПУСК В РЕЖИМЕ ГИБРИДНЫХ ДАННЫХ (Реальные + Mock)")

from ml_models.prediction_model import PredictionModel
from telegram_bot.event_publisher import TelegramPublisher
from database.db import Database
from analyzers.result_checker import ResultChecker
from telegram_bot.admin_handlers import admin_router
from telegram_bot.vip_manager import VIPManager, CryptoBotService, SubscriptionManager, SinglePurchaseService

logger.info("⏳ Инициализация ML-модели...")
ml_model = PredictionModel()



async def run_pipeline():
    """Основной пайплайн: парсинг → ML-предсказание → публикация"""
    from data_collectors.api_football_parser import APIFootballParser
    from telegram_bot.event_publisher import TelegramPublisher
    from database.db import Database
    from telegram_bot.vip_manager import SubscriptionManager
    from analyzers.feature_extractor import extract_features
    from datetime import datetime, timedelta
    
    api_parser = APIFootballParser()
    publisher = TelegramPublisher()
    db = Database()
    await db.init()
    manager = SubscriptionManager()
    await manager.init()

    try:
        api_matches = await api_parser.fetch_upcoming_matches(days=2)
    except Exception as e:
        logger.error(f"Ошибка API-Football: {e}")
        api_matches = []

    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    
    matches = []
    for m in api_matches:
        if not m.get("is_real", False):
            continue
        match_date_str = m.get("date", "")
        try:
            match_date = datetime.strptime(match_date_str[:10], "%Y-%m-%d").date()
            if match_date in [today, tomorrow]:
                matches.append(m)
        except Exception:
            continue
            
    if not matches:
        logger.info("📭 Реальных матчей на сегодня-завтра не найдено.")
        await publisher.close()
        return 0

    logger.info(f"📊 Найдено РЕАЛЬНЫХ матчей: {len(matches)}")
    
    published_count = 0
    for m in matches:
        home_team = m.get("home_team", "Unknown")
        away_team = m.get("away_team", "Unknown")
        match_date_str = m.get("date", "")
        match_time = m.get("time", "")
        league = m.get("league", "Unknown")
        fixture_id = m.get("fixture_id", f"api_{home_team}_{away_team}")
        
        home_odds = float(m.get("home_odds", 0) or 0)
        draw_odds = float(m.get("draw_odds", 0) or 0)
        away_odds = float(m.get("away_odds", 0) or 0)
        
        match_data = {
            "fixture_id": fixture_id, "league": league,
            "home_team": home_team, "away_team": away_team,
            "home_odds": home_odds, "draw_odds": draw_odds, "away_odds": away_odds,
            "date": match_date_str, "time": match_time
        }
        
        try:
            feature_cols = getattr(getattr(ml_model, 'model', ml_model), 'feature_cols', None)
            enriched_match_data = extract_features(match_data, feature_cols)
            ml_result = ml_model.predict(enriched_match_data)
        except Exception as e:
            logger.error(f"❌ Ошибка ML: {e}")
            ml_result = {"prediction": "H", "confidence": 0.5}
            
        # Bookmaker Odds Override (исправляем ничьи)
        if home_odds > 0 and draw_odds > 0 and away_odds > 0:
            min_odds = min(home_odds, draw_odds, away_odds)
            if ml_result.get("prediction") == "D" or ml_result.get("confidence", 0) < 0.45:
                if min_odds == home_odds:
                    ml_result["prediction"] = "H"
                    ml_result["confidence"] = max(ml_result.get("confidence", 0), 0.60)
                elif min_odds == away_odds:
                    ml_result["prediction"] = "A"
                    ml_result["confidence"] = max(ml_result.get("confidence", 0), 0.60)
                    
        prediction = ml_result.get("prediction", "H")
        confidence = ml_result.get("confidence", 0.5)
        pred_map = {"H": "П1 (Победа хозяев)", "D": "Ничья", "A": "П2 (Победа гостей)"}
        pred_text = pred_map.get(prediction, "П1")
        is_vip = confidence >= 0.65
        
        vip_tag = '💎 <i>VIP-сетап</i>' if is_vip else '📊 <i>Обычный прогноз</i>'
        post_text = f"⚽ <b>{league}</b>\n🏟 <b>{home_team} — {away_team}</b>\n📅 {match_date_str} в {match_time}\n\n🤖 <b>Прогноз AI:</b> {pred_text}\n🎯 <b>Уверенность:</b> {confidence:.0%}\n\n{vip_tag}"
        
        try:
            await publisher.publish_prediction(post_text, is_vip=is_vip)
            published_count += 1
            logger.info(f"✅ Опубликовано: {home_team} vs {away_team}")
        except Exception as e:
            logger.error(f"❌ Ошибка публикации: {e}")
            
    await publisher.close()
    logger.info(f"🏁 Пайплайн завершен. Опубликовано: {published_count}")
    return published_count


async def check_results_job():
    """Проверка результатов матчей"""
    checker = ResultChecker()
    await checker.run()


async def send_stats_report():
    """Еженедельный отчёт по понедельникам"""
    db = Database()
    await db.init()
    stats = await db.get_stats()
    publisher = TelegramPublisher()
    text = (
        f"📊 *ЕЖЕНЕДЕЛЬНЫЙ ОТЧЕТ* 📊\n\n"
        f"🏟 Всего: {stats['total']}\n"
        f"✅ Выигрышей: {stats['wins']}\n"
        f"❌ Проигрышей: {stats['losses']}\n"
        f"⏳ Ожидают: {stats['pending']}\n"
        f"🎯 Винрейт: {stats['winrate']:.1f}%\n"
    )
    try:
        await publisher.bot.send_message(
            chat_id=settings.CHANNEL_ID, text=text, parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Ошибка отчета: {e}")
    finally:
        await publisher.close()


async def check_crypto_payments():
    """Проверка оплат CryptoBot каждые 30 секунд"""
    publisher = TelegramPublisher()
    service = CryptoBotService()
    manager = SubscriptionManager()
    vip_manager = VIPManager(publisher.bot)
    purchase_service = SinglePurchaseService(service)

    await manager.init()
    pending = await manager.get_pending_invoices()
    if not pending:
        await publisher.close()
        await service.close()
        return

    for inv in pending:
        status = await service.check_invoice_status(inv["invoice_id"])
        if status == "paid":
            plan = inv["plan"]

            # ЭКСПРЕСС
            if plan.startswith("express_"):
                try:
                    parts = plan.split(":")
                    group_id = int(parts[1]) if len(parts) > 1 else int(plan.split("_")[2])

                    group_data = await manager.get_express_group(group_id)
                    if not group_data:
                        logger.error(f"❌ Группа {group_id} не найдена")
                        continue

                    full_text, keyboard = purchase_service.format_express_message(group_data)

                    await publisher.bot.send_message(
                        chat_id=inv["user_id"],
                        text=full_text,
                        reply_markup=keyboard,
                        parse_mode="HTML"
                    )

                    await manager.mark_invoice_paid(inv["invoice_id"])
                    logger.info(
                        f"✅ Экспресс x{group_data['events_count']} #{inv['invoice_id']} для @{inv['username']}"
                    )
                except Exception as e:
                    logger.error(f"❌ Ошибка выдачи экспресса: {e}")

            # ОДИНОЧНЫЙ ПЛАТНЫЙ ПРОГНОЗ
            elif plan.startswith("single_"):
                try:
                    parts = plan.split(":")
                    group_id = int(parts[1]) if len(parts) > 1 else int(plan.replace("single_", ""))

                    group_data = await manager.get_express_group(group_id)
                    if group_data and group_data["events"]:
                        ev = group_data["events"][0]
                        match_info = {
                            "home_team": ev["home_team"],
                            "away_team": ev["away_team"],
                            "date": ev["date"],
                            "sport": ev["sport"],
                            "league": ev["league"]
                        }
                        full_text, keyboard = purchase_service.format_prediction_message(
                            match_info=match_info,
                            prediction=ev["prediction"],
                            confidence=ev["confidence"],
                            odds=ev["odds"]
                        )

                        await publisher.bot.send_message(
                            chat_id=inv["user_id"],
                            text=full_text,
                            reply_markup=keyboard,
                            parse_mode="HTML"
                        )

                        await manager.mark_invoice_paid(inv["invoice_id"])
                        logger.info(f"✅ Одиночный #{inv['invoice_id']} для @{inv['username']}")
                except Exception as e:
                    logger.error(f"❌ Ошибка одиночного: {e}")

            # VIP-ПОДПИСКА
            elif plan in ["day", "week", "month", "quarter"]:
                try:
                    invite_link, expires_at = await vip_manager.create_personal_invite(
                        user_id=inv["user_id"], username=inv["username"], plan=plan
                    )
                    await manager.mark_invoice_paid(inv["invoice_id"])
                    expires_msk = expires_at.astimezone(timezone(timedelta(hours=3)))
                    await publisher.bot.send_message(
                        chat_id=inv["user_id"],
                        text=(
                            f"🎉 <b>Оплата получена!</b>\n\n"
                            f"👑 До: <b>{expires_msk.strftime('%d.%m.%Y %H:%M')} (МСК)</b>\n\n"
                            f"🔗 <a href='{invite_link}'>👉 ВОЙТИ В VIP</a>"
                        ),
                        parse_mode="HTML", disable_web_page_preview=True
                    )
                except Exception as e:
                    logger.error(f"❌ Ошибка VIP: {e}")

    await publisher.close()
    await service.close()


async def main():
    """Главная функция: запускает веб-сервер + бот + scheduler"""

    # 🆕 Запускаем веб-сервер параллельно с ботом
    try:
import uvicorn
from web.main import app as web_app

        config = uvicorn.Config(
            web_app,
            host="0.0.0.0",
            port=8000,
            log_level="warning",
            access_log=False
        )
        server = uvicorn.Server(config)
        asyncio.create_task(server.serve())
        logger.info("🌐 Веб-сайт запущен на http://0.0.0.0:8000")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось запустить веб-сервер: {e}")

    scheduler = AsyncIOScheduler(timezone=timezone(timedelta(hours=3)))

    # ГЛАВНАЯ ПУБЛИКАЦИЯ: каждый день в 8:00 МСК
    scheduler.add_job(
        run_pipeline,
        "cron",
        hour=8, minute=0,
        id="morning_publisher"
    )

    # ЕЖЕДНЕВНАЯ СТАТИСТИКА: каждый день в 8:05 МСК
    async def daily_stats_report():
        try:
            db = Database()
            await db.init()
            stats = await db.get_stats()
            publisher = TelegramPublisher()

            text = (
                f"📊 <b>СТАТИСТИКА ЗА ВЧЕРА</b> 📊\n\n"
                f"🏟 Сыграно прогнозов: {stats['total']}\n"
                f"✅ Выигрышей: {stats['wins']}\n"
                f"❌ Проигрышей: {stats['losses']}\n"
                f"⏳ Ожидают результата: {stats['pending']}\n"
                f"🎯 <b>Винрейт:</b> {stats['winrate']:.1f}%\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━\n"
                f"💡 <i>Подписывайтесь на VIP для эксклюзивных прогнозов!</i>\n\n"
                f"⚠️ <i>Дисклеймер: Прогнозы носят информационный характер. "
                f"Ответственная игра. 18+</i>"
            )

            await publisher.bot.send_message(
                chat_id=settings.CHANNEL_ID,
                text=text,
                parse_mode="HTML"
            )
            await publisher.close()
            logger.info("📊 Ежедневная статистика отправлена")
        except Exception as e:
            logger.error(f"Ошибка ежедневной статистики: {e}")

    scheduler.add_job(daily_stats_report, "cron", hour=8, minute=5, id="daily_stats")

    # Проверка результатов (каждые 30 минут)
    scheduler.add_job(
        check_results_job, "interval", minutes=30,
        next_run_time=datetime.now(), id="result_checker"
    )

    # Еженедельный отчёт (каждый понедельник в 12:00 МСК)
    scheduler.add_job(
        send_stats_report, "cron", day_of_week="mon",
        hour=12, minute=0, id="weekly_report"
    )

    scheduler.start()

    # Проверка просроченных VIP (каждый час)
    async def check_expired_vip():
        p = TelegramPublisher()
        v = VIPManager(p.bot)
        await v.remove_expired_users()
        await p.close()

    scheduler.add_job(
        check_expired_vip, "interval", hours=1,
        next_run_time=datetime.now(), id="vip_checker"
    )
    scheduler.add_job(
        check_crypto_payments, "interval", seconds=30,
        next_run_time=datetime.now(), id="crypto_checker"
    )

    # ЕЖЕНЕДЕЛЬНОЕ ПЕРЕОБУЧЕНИЕ: каждое воскресенье в 03:00 МСК
    async def weekly_retrain():
        try:
            logger.info("🔄 Запускаю еженедельное переобучение модели...")
from scripts.update_data import DataUpdater
            updater = DataUpdater()
            await updater.update()
from scripts.retrain_model import ModelRetrainer
            retrainer = ModelRetrainer()
            retrainer.retrain()
            global ml_model
            ml_model = PredictionModel()
            logger.info("✅ Еженедельное переобучение завершено!")
        except Exception as e:
            logger.error(f"❌ Ошибка еженедельного переобучения: {e}")

    scheduler.add_job(
        weekly_retrain, "cron", day_of_week="sun",
        hour=3, minute=0, id="weekly_retrain"
    )

    publisher = TelegramPublisher()
    dp = Dispatcher()





# ================================================


    # === ЗАПУСК TELEGRAM ПОЛЛИНГА ===
from aiogram import Bot
from config import settings
    
import os
    bot = Bot(token=(os.getenv('TELEGRAM_BOT_TOKEN') or os.getenv('BOT_TOKEN')))
    
    # Регистрируем роутеры (если они есть)
    try:
from telegram_bot.handlers import router as bot_router
        dp.include_router(bot_router)
        logger.info("✅ Роутеры бота зарегистрированы")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось зарегистрировать роутеры: {e}")
    # === ПОДКЛЮЧЕНИЕ ВСЕХ РОУТЕРОВ TELEGRAM-БОТА ===
import importlib
from aiogram import Router
    
    # Список всех модулей и их роутеров (в порядке приоритета)
    routers_config = [
        ("telegram_bot.handlers", "router"),                    # Основные команды
        ("telegram_bot.favorites", "router"),                   # Избранные команды
        ("telegram_bot.admin_handlers", "admin_router"),        # Админ-команды
        ("telegram_bot.referral_handlers", "router"),           # Реферальная система
    ]
    
    connected_routers = []
    for module_name, router_name in routers_config:
        try:
            module = importlib.import_module(module_name)
            router = getattr(module, router_name, None)
            if router and isinstance(router, Router):
                dp.include_router(router)
                connected_routers.append(f"{module_name}.{router_name}")
                logger.info(f"✅ Роутер {module_name}.{router_name} подключён")
            else:
                logger.warning(f"⚠️ Роутер {router_name} не найден в {module_name}")
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки {module_name}: {e}")
    
    if connected_routers:
        logger.info(f"✅ Всего подключено {len(connected_routers)} роутеров")
    else:
        logger.error("❌ Не подключено ни одного роутера!")
    # =================================================


    
    
    
    logger.info("🚀 Запускаю Telegram-поллинг...")
    await dp.start_polling(bot)
    # =================================


# --- БЛОК АВТОПОСТИНГА (ОБРАЗОВАТЕЛЬНЫЙ И ВОВЛЕКАЮЩИЙ КОНТЕНТ) ---
ENGAGEMENT_POSTS = [
    "🧠 <b>Что такое xG (ожидаемые голы)?</b>\n\nМногие смотрят на счет, но наш ИИ смотрит на xG. Если команда била 10 раз с убойных позиций, но забила 0 голов — xG покажет, что это случайность. Именно эти скрытые паттерны ловит наш XGBoost.\n\n<i>🤖 Машинный взгляд на спорт</i>",
    
    "🌳 <b>Как работает XGBoost?</b>\n\nПредставьте 1000 спортивных аналитиков. Первый смотрит на погоду, второй — на травмы. XGBoost строит тысячи таких «деревьев решений» и объединяет их в один мощный прогноз. Он не знает эмоций, он видит только математику.\n\n<i>📊 Ежедневная AI-выдача в 08:00 МСК</i>",
    
    "📊 <b>59% винрейта — это много?</b>\n\nВ мире профи винрейт 53-55% уже считается элитным. Наш ИИ показывает <b>59.01%</b> на исторических данных. Мы не обещаем 100% (это обман), мы предлагаем математический перевес над букмекером.\n\n<i>👑 Забирайте High-Confidence сетапы в VIP</i>",
    
    "🤖 <b>Проверь свою интуицию!</b>\n\nЗайдите в нашего умного бота @spanalyt_bot, выберите любимые команды через /favorites и проверьте личную статистику через /mystats.\n\n👇 <b>Скидывайте свой уровень из бота в комментарии!</b> Посмотрим, кто тут настоящий эксперт.",
    
    "⚙️ <b>Закулисье SportPredict AI</b>\n\nПока другие рисуют прогнозы в Excel, наш сервер на Railway ежесекундно парсит десятки лиг. Нейросеть анализирует 54 параметра на каждый матч. Это не просто канал, это полноценный IT-стартап, который работает на вас 24/7.\n\n<i>🔔 Включите уведомления, чтобы не пропустить AI-прогнозы завтра в 08:00!</i>"
]

async def send_engagement_post():
import random
    try:
        channel_id = "-1003730713406"  # ID вашего обычного канала
        post_text = random.choice(ENGAGEMENT_POSTS)
        await bot.send_message(chat_id=channel_id, text=post_text, parse_mode="HTML", disable_web_page_preview=True)
        logger.info("✅ Вовлекающий пост успешно опубликован в канале!")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось отправить вовлекающий пост: {e}")
# -----------------------------------------------------------------

if __name__ == "__main__":
    asyncio.run(main())
