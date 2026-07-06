import asyncio
import logging
import sys
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Dispatcher
from config import settings

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

from data_collectors.real_sports_parser import HybridSportsParser as MultiSportParser
logger.info("🧪 ЗАПУСК В РЕЖИМЕ ГИБРИДНЫХ ДАННЫХ (Реальные + Mock)")

from ml_models.prediction_model import PredictionModel
# Инициализируем ML-модель один раз при старте
ml_model = PredictionModel()

from telegram_bot.event_publisher import TelegramPublisher
from database.db import Database
from analyzers.result_checker import ResultChecker
from telegram_bot.admin_handlers import admin_router
from telegram_bot.vip_manager import VIPManager, CryptoBotService, SubscriptionManager, SinglePurchaseService

# Глобальный замок от одновременных запусков пайплайна
is_pipeline_running = False

logger.info("⏳ Инициализация ML-модели завершена")


async def create_and_publish_express(candidates, count, price, manager, publisher, express_label):
    """
    💎 ПОМОЩНИК (DRY): Собирает, сохраняет в БД и публикует экспресс в канал.
    Помогает избежать дублирования кода для Экспрессов разного размера.
    """
    express_events = candidates[:count]
    events = []
    total_odds = 1.0
    
    for ev in express_events:
        events.append({
            "fixture_id": ev["match"]["fixture_id"],
            "home_team": ev["match"]["home_team"],
            "away_team": ev["match"]["away_team"],
            "date": ev["match"]["date"],
            "sport": ev["match"]["sport"],
            "league": ev["match"]["league"],
            "prediction": ev["prediction"],
            "confidence": ev["confidence"],
            "odds": ev["odds_est"]
        })
        total_odds *= ev["odds_est"]

    # Сохраняем группу экспресса в БД через менеджер подписок
    group_id = await manager.save_express_group(events, total_odds, price)
    
    # Публикуем экспресс в Telegram-канал
    success = await publisher.publish_express(express_events, group_id, price)
    return success, events, total_odds


async def run_pipeline():
    """Основной пайплайн: парсинг → ML-предсказание → публикация"""
    global is_pipeline_running
    
    # Защита от спама/одновременных запусков
    if is_pipeline_running:
        logger.warning("⏳ Пайплайн уже запущен, игнорируем повторный запрос")
        return 0
        
    is_pipeline_running = True
    
    # Объявляем переменные заранее, чтобы гарантированно закрыть их в блоке finally
    publisher = None
    db = None
    manager = None
    
    try:
        parser = MultiSportParser(min_confidence=0.70)
        publisher = TelegramPublisher()
        db = Database()
        await db.init()
        manager = SubscriptionManager()
        await manager.init()

        matches = await parser.fetch_upcoming_matches(count=20)

        # 🛡️ Фильтр фейковых матчей
        real_matches = []
        for m in matches:
            fid = m.get("fixture", {}).get("id")
            if fid and isinstance(fid, int) and fid > 10000:
                real_matches.append(m)
                
        matches = real_matches

        if not matches:
            logger.info("📭 Реальных матчей не найдено. Фейковые матчи отключены.")
            try:
                await publisher.bot.send_message(
                    chat_id=settings.ADMIN_ID,
                    text="⚠️ <b>Публикация отменена:</b> Нет реальных матчей на сегодня.",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Не удалось отправить сообщение админу: {e}")
            return 0

        logger.info(f"📊 Найдено РЕАЛЬНЫХ матчей: {len(matches)}")

        # 🧵 ОПТИМИЗАЦИЯ: Читаем тяжелый CSV файл в отдельном потоке, чтобы не блокировать бота
        historical_df = None
        try:
            hist_path = Path("data/historical/all_matches_clean.csv")
            if hist_path.exists():
                # Читаем файл асинхронно
                historical_df = await asyncio.to_thread(
                    pd.read_csv, hist_path, encoding="utf-8", low_memory=False
                )
                
                # Функция для конвертации дат, которую мы тоже запустим асинхронно
                def parse_dates(df):
                    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
                    return df
                
                historical_df = await asyncio.to_thread(parse_dates, historical_df)
                logger.info(f"📚 Загружено {len(historical_df)} исторических матчей в фоновом потоке")
        except Exception as e:
            logger.warning(f"⚠️ Не удалось загрузить исторические данные: {e}")

        vip_predictions = []
        express_candidates = []
        regular_predictions = []

        for m in matches:
            home_team = m["teams"]["home"]["name"]
            away_team = m["teams"]["away"]["name"]
            match_date = pd.to_datetime(m["fixture"]["date"], errors="coerce")
            
            # Жесткий фильтр прошедших матчей
            now = pd.Timestamp.now(tz="UTC")
            if pd.isna(match_date) or match_date < now - pd.Timedelta(days=2):
                continue
                
            # 🧵 ОПТИМИЗАЦИЯ: Обучение/расчет ML-модели выносим в отдельный поток
             # Получаем все прогнозы
            # Получаем все прогнозы
ml_result = await asyncio.to_thread(
    get_ml_model().predict,
    home_team=home_team,
    away_team=away_team,
    match_date=match_date,
    historical_df=historical_df
)

# Основной прогноз (исход)
outcome = ml_result.get('outcome', {})
prediction = outcome.get('prediction', 'H')
confidence = outcome.get('confidence', 0.5)

# Дополнительные рынки
markets = ml_result.get('markets', ml_result)
total_pred = markets.get('total', {}).get('prediction', '')
both_scored_pred = markets.get('both_scored', {}).get('prediction', '')
handicap_pred = markets.get('handicap', {}).get('prediction', '')

# Формируем текст прогноза с дополнительными рынками
extra_markets = []
if total_pred:
    extra_markets.append(f"⚽ Тотал: {total_pred}")
if both_scored_pred:
    extra_markets.append(f"🥅 Обе забьют: {both_scored_pred}")
if handicap_pred:
    extra_markets.append(f"📊 Фора: {handicap_pred}")

extra_text = "\n".join(extra_markets) if extra_markets else ""
# Дополнительные рынки
markets = ml_result.get('markets', ml_result)
total_pred = markets.get('total', {}).get('prediction', '')
both_scored_pred = markets.get('both_scored', {}).get('prediction', '')
handicap_pred = markets.get('handicap', {}).get('prediction', '')

# Формируем текст прогноза с дополнительными рынками
extra_markets = []
if total_pred:
    extra_markets.append(f"⚽ Тотал: {total_pred}")
if both_scored_pred:
    extra_markets.append(f"🥅 Обе забьют: {both_scored_pred}")
if handicap_pred:
    extra_markets.append(f"📊 Фора: {handicap_pred}")

extra_text = "\n".join(extra_markets) if extra_markets else ""

            # Маппинг предсказания в русский формат
            outcome_mapping = {"H": "П1", "D": "X", "A": "П2"}
            predicted_outcome = ml_result["prediction"]
            if predicted_outcome in outcome_mapping:
                predicted_outcome = outcome_mapping[predicted_outcome]
            else:
                predicted_outcome = m.get("outcome", "П1")

            # 🛡️ ИСПРАВЛЕН БАГ: Словарь match_data теперь вынесен ИЗ блока else и доступен ВСЕГДА
            match_data = {
                "home_team": home_team,
                "away_team": away_team,
                "date": m["fixture"]["date"],
                "fixture_id": m["fixture"]["id"],
                "sport": m.get("sport", "⚽ Футбол"),
                "league": m.get("league", ""),
                "odds_url": m.get("odds_url") or f"https://www.google.com/search?q={home_team}+{away_team}+betting+odds"
            }

            pred = {
                "prediction": predicted_outcome,
                "confidence": ml_result["confidence"],
                "odds_est": m.get("odds", 2.0),
                "match": match_data
            }

            # Категоризация по уровню уверенности
            if pred["confidence"] >= settings.VIP_CONFIDENCE_THRESHOLD:
                vip_predictions.append(pred)
            elif pred["confidence"] >= 0.71:
                express_candidates.append(pred)
            else:
                regular_predictions.append(pred)

        published = 0

        # 1️⃣ Публикация VIP-прогнозов
        for pred in vip_predictions:
            if await publisher.publish(pred, is_vip=True, is_single_purchase=False):
                published += 1

        # 2️⃣ Публикация обычных прогнозов
        for pred in regular_predictions:
            if await publisher.publish(pred, is_vip=False, is_single_purchase=False):
                published += 1
                await db.save_prediction(
                    fixture_id=pred["match"]["fixture_id"],
                    home=pred["match"]["home_team"],
                    away=pred["match"]["away_team"],
                    date=pred["match"]["date"],
                    pred=pred["prediction"],
                    conf=pred["confidence"],
                    odds=pred["odds_est"]
                )

                # Уведомления подписчикам любимых команд
                try:
                    home_team = pred["match"]["home_team"]
                    away_team = pred["match"]["away_team"]

                    home_followers = await db.get_team_followers(home_team)
                    away_followers = await db.get_team_followers(away_team)
                    all_followers = home_followers + away_followers

                    if all_followers:
                        sport = pred["match"]["sport"]
                        league = pred["match"]["league"]
                        date_ru = pred["match"]["date"][:16].replace("T", " ")

                        personal_text = (
                            f"⚡ <b>Прогноз на вашу команду!</b>\n\n"
                            f"{sport} | <i>{league}</i>\n"
                            f"🏟 <b>{home_team}</b> — <b>{away_team}</b>\n"
                            f"📅 <i>{date_ru}</i>\n\n"
                            f"🎯 <b>Прогноз:</b> {pred['prediction']}\n"
                            f"📊 <b>Уверенность:</b> {pred['confidence']:.0%}\n"
                            f"💰 <b>Коэф:</b> {pred['odds_est']}\n\n"
                            f"━━━━━━━━━━━━━━━━━━━━━\n"
                            f"⚠️ <i>Ответственная игра. 18+</i>"
                        )

                        sent_count = 0
                        for user_id, username in all_followers:
                            try:
                                await publisher.bot.send_message(
                                    chat_id=user_id,
                                    text=personal_text,
                                    parse_mode="HTML"
                                )
                                sent_count += 1
                                await asyncio.sleep(0.05)
                            except Exception as e:
                                logger.debug(f"Не удалось отправить {username}: {e}")

                        if sent_count > 0:
                            logger.info(f"📨 Отправлено личных уведомлений: {sent_count} на матч {home_team} - {away_team}")
                except Exception as e:
                    logger.warning(f"Ошибка отправки уведомлений подписчикам: {e}")

        # 3️⃣ Публикация Экспрессов
        express_candidates.sort(key=lambda x: x["confidence"], reverse=True)
        express_published = 0
        admin_express_details = []

        # Сценарий А: Кандидатов много (>= 5) -> делаем один экспресс х2 и один х3
        if len(express_candidates) >= 5:
            # Экспресс х2 (берем первые 2 лучших кандидата)
            success, events, odds = await create_and_publish_express(
                candidates=express_candidates[:2],
                count=2,
                price=149,
                manager=manager,
                publisher=publisher,
                express_label="Экспресс x2"
            )
            if success:
                express_published += 1
                published += 1
                admin_express_details.append({
                    "title": f"🔥 Экспресс x2 (149₽) — коэф {odds:.2f}",
                    "events": events,
                    "total_odds": odds,
                    "price": 149
                })

            # Экспресс х3 (берем следующих 3 кандидатов)
            success, events, odds = await create_and_publish_express(
                candidates=express_candidates[2:5],
                count=3,
                price=199,
                manager=manager,
                publisher=publisher,
                express_label="Экспресс x3"
            )
            if success:
                express_published += 1
                published += 1
                admin_express_details.append({
                    "title": f"🔥 Экспресс x3 (199₽) — коэф {odds:.2f}",
                    "events": events,
                    "total_odds": odds,
                    "price": 199
                })

        # Сценарий Б: Кандидатов мало (от 2 до 4) -> делаем только один экспресс х2
        elif len(express_candidates) >= 2:
            success, events, odds = await create_and_publish_express(
                candidates=express_candidates[:2],
                count=2,
                price=149,
                manager=manager,
                publisher=publisher,
                express_label="Экспресс x2"
            )
            if success:
                express_published += 1
                published += 1
                admin_express_details.append({
                    "title": f"🔥 Экспресс x2 (149₽) — коэф {odds:.2f}",
                    "events": events,
                    "total_odds": odds,
                    "price": 149
                })
            logger.info(f"⚠️ Создан только 1 экспресс. Недостаточно кандидатов для второго: {len(express_candidates)}")

        # Отправляем отчет админу в ЛС
        if admin_express_details:
            try:
                admin_text = "🔓 <b>ДЕТАЛИ СФОРМИРОВАННЫХ ЭКСПРЕССОВ</b>\n\n"
                for express in admin_express_details:
                    admin_text += f"<b>{express['title']}</b>\n"
                    admin_text += f"━━━━━━━━━━━━━━━━━━━━━\n"
                    for i, ev in enumerate(express["events"], 1):
                        admin_text += (
                            f"<b>{i}.</b> {ev['sport']} | <i>{ev['league']}</i>\n"
                            f"🏟 <b>{ev['home_team']}</b> — <b>{ev['away_team']}</b>\n"
                            f"📅 <i>{ev['date'][:16].replace('T', ' ')}</i>\n"
                            f"🎯 <b>Исход: {ev['prediction']}</b>\n"
                            f"📊 Уверенность: {ev['confidence']:.0%}\n"
                            f"💰 Коэф: {ev['odds']}\n\n"
                        )
                    admin_text += (
                        f"💵 <b>Цена:</b> {express['price']}₽\n"
                        f"📈 <b>Общий коэф:</b> {express['total_odds']:.2f}\n\n"
                    )
                admin_text += "━━━━━━━━━━━━━━━━━━━━━\n"
                admin_text += f"📤 Всего опубликовано экспрессов: {express_published}"
                await publisher.bot.send_message(chat_id=settings.ADMIN_ID, text=admin_text, parse_mode="HTML")
                logger.info("📨 Детали экспрессов отправлены администратору")
            except Exception as e:
                logger.error(f"Ошибка отправки отчета админу: {e}")

        logger.info(f"📤 Пайплайн завершен. Опубликовано прогнозов: {published} (VIP: {len(vip_predictions)}, Обычные: {len(regular_predictions)}, Экспрессы: {express_published})")
        return published
        
    except Exception as e:
        logger.error(f"❌ Критическая ошибка в пайплайне: {e}")
        return 0
    finally:
        # 🛡️ ГАРАНТИРОВАННОЕ ЗАКРЫТИЕ: Сессии закроются при любом исходе
        if publisher:
            await publisher.close()
        if db and hasattr(db, 'close'):
            try:
                await db.close()
            except Exception:
                pass
        is_pipeline_running = False


async def check_results_job():
    """Проверка результатов матчей"""
    checker = ResultChecker()
    await checker.run()


async def send_stats_report():
    """Еженедельный отчёт по понедельникам"""
    db = None
    publisher = None
    try:
        db = Database()
        await db.init()
        stats = await db.get_stats(since=datetime.now(timezone.utc) - timedelta(days=7))
        publisher = TelegramPublisher()
        text = (
            f"📊 *ЕЖЕНЕДЕЛЬНЫЙ ОТЧЕТ* 📊\n\n"
            f"🏟 Всего прогнозов: {stats['total']}\n"
            f"✅ Выигрышей: {stats['wins']}\n"
            f"❌ Проигрышей: {stats['losses']}\n"
            f"⏳ Ожидают расчета: {stats['pending']}\n"
            f"🎯 Винрейт: {stats['winrate']:.1f}%\n"
        )
        await publisher.bot.send_message(chat_id=settings.CHANNEL_ID, text=text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка генерации еженедельного отчета: {e}")
    finally:
        # Гарантированное закрытие ресурсов
        if publisher:
            await publisher.close()
        if db and hasattr(db, 'close'):
            try:
                await db.close()
            except Exception:
                pass


async def check_crypto_payments():
    """Проверка оплат CryptoBot каждые 30 секунд"""
    publisher = None
    service = None
    manager = None
    
    try:
        publisher = TelegramPublisher()
        service = CryptoBotService()
        manager = SubscriptionManager()
        vip_manager = VIPManager(publisher.bot)
        purchase_service = SinglePurchaseService(service)

        await manager.init()
        pending = await manager.get_pending_invoices()
        if not pending:
            return

        for inv in pending:
            # 🛡️ Каждый инвойс обрабатываем в своем блоке try-except, 
            # чтобы ошибка одного платежа не ломала проверку всех остальных.
            try:
                status = await service.check_invoice_status(inv["invoice_id"])
                if status == "paid":
                    plan = inv["plan"]
                    
                    # Обработка экспрессов
                    if plan.startswith("express_"):
                        parts = plan.split(":")
                        group_id = int(parts[1]) if len(parts) > 1 else int(plan.split("_")[2])
                        group_data = await manager.get_express_group(group_id)
                        if not group_data:
                            logger.error(f"❌ Группа {group_id} не найдена в системе")
                            continue
                        full_text, keyboard = purchase_service.format_express_message(group_data)
                        await publisher.bot.send_message(chat_id=inv["user_id"], text=full_text, reply_markup=keyboard, parse_mode="HTML")
                        await manager.mark_invoice_paid(inv["invoice_id"])
                        logger.info(f"✅ Выдан экспресс x{group_data['events_count']} #{inv['invoice_id']} для @{inv['username']}")
                    
                    # Обработка одиночных VIP-покупок
                    elif plan.startswith("single_"):
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
                            await publisher.bot.send_message(chat_id=inv["user_id"], text=full_text, reply_markup=keyboard, parse_mode="HTML")
                            await manager.mark_invoice_paid(inv["invoice_id"])
                            logger.info(f"✅ Выдан одиночный VIP #{inv['invoice_id']} для @{inv['username']}")
                    
                    # Обработка VIP-подписок (день, неделя, месяц...)
                    elif plan in ["day", "week", "month", "quarter"]:
                        invite_link, expires_at = await vip_manager.create_personal_invite(
                            user_id=inv["user_id"], 
                            username=inv["username"], 
                            plan=plan
                        )
                        await manager.mark_invoice_paid(inv["invoice_id"])
                        expires_msk = expires_at.astimezone(timezone(timedelta(hours=3)))
                        await publisher.bot.send_message(
                            chat_id=inv["user_id"], 
                            text=(
                                f"🎉 <b>Оплата успешно получена!</b>\n\n"
                                f"👑 VIP доступен до: <b>{expires_msk.strftime('%d.%m.%Y %H:%M')} (МСК)</b>\n\n"
                                f"🔗 <a href='{invite_link}'>👉 НАЖМИТЕ СЮДА, ЧТОБЫ ВОЙТИ В VIP</a>"
                            ), 
                            parse_mode="HTML", 
                            disable_web_page_preview=True
                        )
                        logger.info(f"✅ Активирована VIP подписка ({plan}) #{inv['invoice_id']} для @{inv['username']}")
            except Exception as invoice_error:
                logger.error(f"❌ Ошибка обработки конкретного инвойса #{inv.get('invoice_id')}: {invoice_error}")
                
    except Exception as e:
        logger.error(f"❌ Системная ошибка в check_crypto_payments: {e}")
    finally:
        # Гарантированное закрытие сессий
        if publisher:
            await publisher.close()
        if service:
            await service.close()


async def main():
    """Главная функция: запускает веб-сервер + бот + scheduler"""
    try:
        import uvicorn
        from web.main import app as web_app
        config = uvicorn.Config(web_app, host="0.0.0.0", port=8000, log_level="warning", access_log=False)
        server = uvicorn.Server(config)
        asyncio.create_task(server.serve())
        logger.info("🌐 Веб-сайт успешно запущен на http://0.0.0.0:8000")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось запустить веб-сервер: {e}")

    # Настраиваем планировщик на Московское время (UTC+3)
    scheduler = AsyncIOScheduler(timezone=timezone(timedelta(hours=3)))
    
    # Регулярные задачи по расписанию
    scheduler.add_job(run_pipeline, "cron", hour=8, minute=0, id="morning_publisher")

    async def daily_stats_report():
        db = None
        publisher = None
        try:
            db = Database()
            await db.init()
            stats = await db.get_stats(since=datetime.now(timezone.utc) - timedelta(days=1))
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
                f"⚠️ <i>Дисклеймер: Прогнозы носят информационный характер. Ответственная игра. 18+</i>"
            )
            await publisher.bot.send_message(chat_id=settings.CHANNEL_ID, text=text, parse_mode="HTML")
            logger.info("📊 Ежедневная статистика отправлена в канал")
        except Exception as e:
            logger.error(f"Ошибка ежедневной статистики: {e}")
        finally:
            if publisher:
                await publisher.close()
            if db and hasattr(db, 'close'):
                try:
                    await db.close()
                except Exception:
                    pass

    scheduler.add_job(daily_stats_report, "cron", hour=8, minute=5, id="daily_stats")
    scheduler.add_job(check_results_job, "interval", minutes=30, next_run_time=datetime.now(), id="result_checker")
    scheduler.add_job(send_stats_report, "cron", day_of_week="mon", hour=12, minute=0, id="weekly_report")
    
    async def check_expired_vip():
        p = None
        try:
            p = TelegramPublisher()
            v = VIPManager(p.bot)
            await v.remove_expired_users()
        except Exception as e:
            logger.error(f"Ошибка удаления просроченных VIP пользователей: {e}")
        finally:
            if p:
                await p.close()

    scheduler.add_job(check_expired_vip, "interval", hours=1, next_run_time=datetime.now(), id="vip_checker")
    scheduler.add_job(check_crypto_payments, "interval", seconds=30, next_run_time=datetime.now(), id="crypto_checker")
    
    scheduler.start()

    # Инициализация Aiogram Bot & Dispatcher
    publisher = TelegramPublisher()
    dp = Dispatcher()
    dp.include_router(admin_router)

    try:
        await publisher.bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        logger.warning(f"⚠️ Ошибка удаления вебхука: {e}")

    logger.info("🤖 SportPredict AI запущен и готов к работе. Расписание: 8:00 МСК ежедневно.")
    
    try:
        await dp.start_polling(publisher.bot)
    finally:
        await publisher.close()


if __name__ == "__main__":
    asyncio.run(main())
