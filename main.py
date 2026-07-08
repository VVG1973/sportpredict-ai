import asyncio
import logging
import sys
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Dispatcher
from config import settings

# ╨Э╨░╤Б╤В╤А╨╛╨╣╨║╨░ ╨╗╨╛╨│╨╕╤А╨╛╨▓╨░╨╜╨╕╤П
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

from data_collectors.real_sports_parser import HybridSportsParser as MultiSportParser
logger.info("ЁЯзк ╨Ч╨Р╨Я╨г╨б╨Ъ ╨Т ╨а╨Х╨Ц╨Ш╨Ь╨Х ╨У╨Ш╨С╨а╨Ш╨Ф╨Э╨л╨е ╨Ф╨Р╨Э╨Э╨л╨е (╨а╨╡╨░╨╗╤М╨╜╤Л╨╡ + Mock)")

from ml_models.prediction_model import PredictionModel
# ╨Ш╨╜╨╕╤Ж╨╕╨░╨╗╨╕╨╖╨╕╤А╤Г╨╡╨╝ ML-╨╝╨╛╨┤╨╡╨╗╤М ╨╛╨┤╨╕╨╜ ╤А╨░╨╖ ╨┐╤А╨╕ ╤Б╤В╨░╤А╤В╨╡
ml_model = PredictionModel()

from telegram_bot.event_publisher import TelegramPublisher
from database.db import Database
from analyzers.result_checker import ResultChecker
from telegram_bot.admin_handlers import admin_router
from telegram_bot.favorites import router as favorites_router
from telegram_bot.handlers import router as handlers_router
from telegram_bot.vip_manager import VIPManager, CryptoBotService, SubscriptionManager, SinglePurchaseService

is_pipeline_running = False

# Shared instances для scheduler jobs (создаются один раз)
_shared_publisher = None
_shared_crypto_service = None
_shared_manager = None

logger.info("Инициализация ML-модели завершена")


async def create_and_publish_express(candidates, count, price, manager, publisher, express_label):
    """
    ЁЯТО ╨Я╨Ю╨Ь╨Ю╨й╨Э╨Ш╨Ъ (DRY): ╨б╨╛╨▒╨╕╤А╨░╨╡╤В, ╤Б╨╛╤Е╤А╨░╨╜╤П╨╡╤В ╨▓ ╨С╨Ф ╨╕ ╨┐╤Г╨▒╨╗╨╕╨║╤Г╨╡╤В ╤Н╨║╤Б╨┐╤А╨╡╤Б╤Б ╨▓ ╨║╨░╨╜╨░╨╗.
    ╨Я╨╛╨╝╨╛╨│╨░╨╡╤В ╨╕╨╖╨▒╨╡╨╢╨░╤В╤М ╨┤╤Г╨▒╨╗╨╕╤А╨╛╨▓╨░╨╜╨╕╤П ╨║╨╛╨┤╨░ ╨┤╨╗╤П ╨н╨║╤Б╨┐╤А╨╡╤Б╤Б╨╛╨▓ ╤А╨░╨╖╨╜╨╛╨│╨╛ ╤А╨░╨╖╨╝╨╡╤А╨░.
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

    # ╨б╨╛╤Е╤А╨░╨╜╤П╨╡╨╝ ╨│╤А╤Г╨┐╨┐╤Г ╤Н╨║╤Б╨┐╤А╨╡╤Б╤Б╨░ ╨▓ ╨С╨Ф ╤З╨╡╤А╨╡╨╖ ╨╝╨╡╨╜╨╡╨┤╨╢╨╡╤А ╨┐╨╛╨┤╨┐╨╕╤Б╨╛╨║
    group_id = await manager.save_express_group(events, total_odds, price)
    
    # ╨Я╤Г╨▒╨╗╨╕╨║╤Г╨╡╨╝ ╤Н╨║╤Б╨┐╤А╨╡╤Б╤Б ╨▓ Telegram-╨║╨░╨╜╨░╨╗
    success = await publisher.publish_express(express_events, group_id, price)
    return success, events, total_odds


async def run_pipeline():
    """╨Ю╤Б╨╜╨╛╨▓╨╜╨╛╨╣ ╨┐╨░╨╣╨┐╨╗╨░╨╣╨╜: ╨┐╨░╤А╤Б╨╕╨╜╨│ тЖТ ML-╨┐╤А╨╡╨┤╤Б╨║╨░╨╖╨░╨╜╨╕╨╡ тЖТ ╨┐╤Г╨▒╨╗╨╕╨║╨░╤Ж╨╕╤П"""
    global is_pipeline_running
    
    # ╨Ч╨░╤Й╨╕╤В╨░ ╨╛╤В ╤Б╨┐╨░╨╝╨░/╨╛╨┤╨╜╨╛╨▓╤А╨╡╨╝╨╡╨╜╨╜╤Л╤Е ╨╖╨░╨┐╤Г╤Б╨║╨╛╨▓
    if is_pipeline_running:
        logger.warning("тП│ ╨Я╨░╨╣╨┐╨╗╨░╨╣╨╜ ╤Г╨╢╨╡ ╨╖╨░╨┐╤Г╤Й╨╡╨╜, ╨╕╨│╨╜╨╛╤А╨╕╤А╤Г╨╡╨╝ ╨┐╨╛╨▓╤В╨╛╤А╨╜╤Л╨╣ ╨╖╨░╨┐╤А╨╛╤Б")
        return 0
        
    is_pipeline_running = True
    
    # ╨Ю╨▒╤К╤П╨▓╨╗╤П╨╡╨╝ ╨┐╨╡╤А╨╡╨╝╨╡╨╜╨╜╤Л╨╡ ╨╖╨░╤А╨░╨╜╨╡╨╡, ╤З╤В╨╛╨▒╤Л ╨│╨░╤А╨░╨╜╤В╨╕╤А╨╛╨▓╨░╨╜╨╜╨╛ ╨╖╨░╨║╤А╤Л╤В╤М ╨╕╤Е ╨▓ ╨▒╨╗╨╛╨║╨╡ finally
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

        # ЁЯЫбя╕П ╨д╨╕╨╗╤М╤В╤А ╤Д╨╡╨╣╨║╨╛╨▓╤Л╤Е ╨╝╨░╤В╤З╨╡╨╣
        real_matches = []
        for m in matches:
            fid = m.get("fixture", {}).get("id")
            if fid and isinstance(fid, int) and fid > 10000:
                real_matches.append(m)
                
        matches = real_matches

        if not matches:
            logger.info("ЁЯУн ╨а╨╡╨░╨╗╤М╨╜╤Л╤Е ╨╝╨░╤В╤З╨╡╨╣ ╨╜╨╡ ╨╜╨░╨╣╨┤╨╡╨╜╨╛. ╨д╨╡╨╣╨║╨╛╨▓╤Л╨╡ ╨╝╨░╤В╤З╨╕ ╨╛╤В╨║╨╗╤О╤З╨╡╨╜╤Л.")
            try:
                await publisher.bot.send_message(
                    chat_id=settings.ADMIN_ID,
                    text="тЪая╕П <b>╨Я╤Г╨▒╨╗╨╕╨║╨░╤Ж╨╕╤П ╨╛╤В╨╝╨╡╨╜╨╡╨╜╨░:</b> ╨Э╨╡╤В ╤А╨╡╨░╨╗╤М╨╜╤Л╤Е ╨╝╨░╤В╤З╨╡╨╣ ╨╜╨░ ╤Б╨╡╨│╨╛╨┤╨╜╤П.",
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨╛╤В╨┐╤А╨░╨▓╨╕╤В╤М ╤Б╨╛╨╛╨▒╤Й╨╡╨╜╨╕╨╡ ╨░╨┤╨╝╨╕╨╜╤Г: {e}")
            return 0

        logger.info(f"ЁЯУК ╨Э╨░╨╣╨┤╨╡╨╜╨╛ ╨а╨Х╨Р╨Ы╨м╨Э╨л╨е ╨╝╨░╤В╤З╨╡╨╣: {len(matches)}")

        # ЁЯз╡ ╨Ю╨Я╨в╨Ш╨Ь╨Ш╨Ч╨Р╨ж╨Ш╨п: ╨з╨╕╤В╨░╨╡╨╝ ╤В╤П╨╢╨╡╨╗╤Л╨╣ CSV ╤Д╨░╨╣╨╗ ╨▓ ╨╛╤В╨┤╨╡╨╗╤М╨╜╨╛╨╝ ╨┐╨╛╤В╨╛╨║╨╡, ╤З╤В╨╛╨▒╤Л ╨╜╨╡ ╨▒╨╗╨╛╨║╨╕╤А╨╛╨▓╨░╤В╤М ╨▒╨╛╤В╨░
        historical_df = None
        try:
            hist_path = Path("data/historical/all_matches_clean.csv")
            if hist_path.exists():
                # ╨з╨╕╤В╨░╨╡╨╝ ╤Д╨░╨╣╨╗ ╨░╤Б╨╕╨╜╤Е╤А╨╛╨╜╨╜╨╛
                historical_df = await asyncio.to_thread(
                    pd.read_csv, hist_path, encoding="utf-8", low_memory=False
                )
                
                # ╨д╤Г╨╜╨║╤Ж╨╕╤П ╨┤╨╗╤П ╨║╨╛╨╜╨▓╨╡╤А╤В╨░╤Ж╨╕╨╕ ╨┤╨░╤В, ╨║╨╛╤В╨╛╤А╤Г╤О ╨╝╤Л ╤В╨╛╨╢╨╡ ╨╖╨░╨┐╤Г╤Б╤В╨╕╨╝ ╨░╤Б╨╕╨╜╤Е╤А╨╛╨╜╨╜╨╛
                def parse_dates(df):
                    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
                    return df
                
                historical_df = await asyncio.to_thread(parse_dates, historical_df)
                logger.info(f"ЁЯУЪ ╨Ч╨░╨│╤А╤Г╨╢╨╡╨╜╨╛ {len(historical_df)} ╨╕╤Б╤В╨╛╤А╨╕╤З╨╡╤Б╨║╨╕╤Е ╨╝╨░╤В╤З╨╡╨╣ ╨▓ ╤Д╨╛╨╜╨╛╨▓╨╛╨╝ ╨┐╨╛╤В╨╛╨║╨╡")
        except Exception as e:
            logger.warning(f"тЪая╕П ╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨╖╨░╨│╤А╤Г╨╖╨╕╤В╤М ╨╕╤Б╤В╨╛╤А╨╕╤З╨╡╤Б╨║╨╕╨╡ ╨┤╨░╨╜╨╜╤Л╨╡: {e}")

        vip_predictions = []
        express_candidates = []
        regular_predictions = []

        for m in matches:
            home_team = m["teams"]["home"]["name"]
            away_team = m["teams"]["away"]["name"]
            match_date = pd.to_datetime(m["fixture"]["date"], errors="coerce")
            
            # ╨Ц╨╡╤Б╤В╨║╨╕╨╣ ╤Д╨╕╨╗╤М╤В╤А ╨┐╤А╨╛╤И╨╡╨┤╤И╨╕╤Е ╨╝╨░╤В╤З╨╡╨╣
            now = pd.Timestamp.now(tz="UTC")
            if pd.isna(match_date) or match_date < now - pd.Timedelta(days=2):
                continue

            # Извлекаем коэффициенты из данных матча
            match_odds = m.get("odds", {})
            if isinstance(match_odds, (int, float)):
                match_odds = {"home": match_odds, "draw": 0, "away": 0}

            # Определяем вид спорта
            sport_lower = m.get("sport", "").lower()
            is_esports = any(s in sport_lower for s in ["cs", "dota", "lol", "valorant", "overwatch", "esport", "кибер"])
            is_hockey = any(s in sport_lower for s in ["хоккей", "hockey", "nhl", "кхл"])
            is_tennis = any(s in sport_lower for s in ["теннис", "tennis", "atp", "wta"])

            if is_esports:
                # Киберспорт: используем специальную модель
                game = "csgo" if "cs" in sport_lower else "dota2" if "dota" in sport_lower else "csgo"
                ml_result = await ml_model.predict_esports({
                    "home_team": home_team,
                    "away_team": away_team,
                    "match_date": str(match_date),
                    "odds": match_odds
                }, game=game)
            elif is_hockey or is_tennis:
                # Хоккей/Теннис: предсказание на основе коэффициентов
                home_odd = match_odds.get('home', 2.0) or 2.0
                away_odd = match_odds.get('away', 2.0) or 2.0
                draw_odd = match_odds.get('draw', 0) or 0

                # Имplied probability
                home_prob = 1.0 / home_odd if home_odd > 0 else 0.33
                away_prob = 1.0 / away_odd if away_odd > 0 else 0.33

                if home_prob > away_prob:
                    predicted_outcome = "П1"
                    confidence = min(home_prob * 1.1, 0.85)
                else:
                    predicted_outcome = "П2"
                    confidence = min(away_prob * 1.1, 0.85)

                ml_result = {"prediction": predicted_outcome.replace("П1", "H").replace("П2", "A"), "confidence": confidence}
            else:
                # Футбол: используем основную модель с value bet
                predict_method = getattr(ml_model, 'predict_with_value', ml_model.predict)
                
                ml_input = {
                    "home_team": home_team,
                    "away_team": away_team,
                    "match_date": str(match_date),
                    "odds": match_odds,
                    "B365H": match_odds.get('home', 0) or m.get("odds", {}).get('home', 0),
                    "B365D": match_odds.get('draw', 0) or m.get("odds", {}).get('draw', 0),
                    "B365A": match_odds.get('away', 0) or m.get("odds", {}).get('away', 0),
                }
                
                if historical_df is not None:
                    ml_input["historical_df"] = historical_df
                
                ml_result = await asyncio.to_thread(
                    predict_method,
                    ml_input
                )

            # ЁЯФД Multi-output ╨╛╨▒╤А╨░╨▒╨╛╤В╨║╨░
            if isinstance(ml_result, dict) and 'outcome' in ml_result:
                # ╨Э╨╛╨▓╤Л╨╣ ╤Д╨╛╤А╨╝╨░╤В (multi-output)
                outcome = ml_result['outcome']
                predicted_outcome = outcome['prediction']
                confidence = outcome['confidence']
            else:
                # ╨б╤В╨░╤А╤Л╨╣ ╤Д╨╛╤А╨╝╨░╤В
                predicted_outcome = ml_result.get('prediction', 'H')
                confidence = ml_result.get('confidence', 0.5)

            # ╨Ь╨░╨┐╨┐╨╕╨╜╨│ ╨┐╤А╨╡╨┤╤Б╨║╨░╨╖╨░╨╜╨╕╤П ╨▓ ╤А╤Г╤Б╤Б╨║╨╕╨╣ ╤Д╨╛╤А╨╝╨░╤В
            outcome_mapping = {"H": "П1", "D": "X", "A": "П2"}
            if predicted_outcome in outcome_mapping:
                predicted_outcome = outcome_mapping[predicted_outcome]
            else:
                predicted_outcome = m.get("outcome", "П1")

            # ЁЯЫбя╕П ╨Ш╨б╨Я╨а╨Р╨Т╨Ы╨Х╨Э ╨С╨Р╨У: ╨б╨╗╨╛╨▓╨░╤А╤М match_data ╤В╨╡╨┐╨╡╤А╤М ╨▓╤Л╨╜╨╡╤Б╨╡╨╜ ╨Ш╨Ч ╨▒╨╗╨╛╨║╨░ else ╨╕ ╨┤╨╛╤Б╤В╤Г╨┐╨╡╨╜ ╨Т╨б╨Х╨У╨Ф╨Р
            match_data = {
                "home_team": home_team,
                "away_team": away_team,
                "date": m["fixture"]["date"],
                "fixture_id": m["fixture"]["id"],
                "sport": m.get("sport", "тЪ╜ ╨д╤Г╤В╨▒╨╛╨╗"),
                "league": m.get("league", ""),
                "odds_url": m.get("odds_url") or f"https://www.google.com/search?q={home_team}+{away_team}+betting+odds"
            }

            pred = {
                "prediction": predicted_outcome,
                "confidence": confidence,
                "odds_est": m.get("odds", 2.0),
                "match": match_data,
                "total": ml_result.get("total", {}),
                "both_scored": ml_result.get("both_scored", {}),
                "handicap": ml_result.get("handicap", {}),
            }

            # ╨Ъ╨░╤В╨╡╨│╨╛╤А╨╕╨╖╨░╤Ж╨╕╤П ╨┐╨╛ ╤Г╤А╨╛╨▓╨╜╤О ╤Г╨▓╨╡╤А╨╡╨╜╨╜╨╛╤Б╤В╨╕
            if pred["confidence"] >= settings.VIP_CONFIDENCE_THRESHOLD:
                vip_predictions.append(pred)
            elif pred["confidence"] >= 0.65:
                express_candidates.append(pred)
            else:
                regular_predictions.append(pred)

        published = 0

        # ═══════════════════════════════════════════════════
        # 1. ОБЫЧНЫЙ КАНАЛ: 1-2 лучших прогноза С исходом
        # ═══════════════════════════════════════════════════
        top_predictions = sorted(vip_predictions, key=lambda x: x["confidence"], reverse=True)[:2]
        for pred in top_predictions:
            if await publisher.publish_to_channel(pred):
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

        # ═══════════════════════════════════════════════════
        # 2. VIP КАНАЛ: 5-6 прогнозов БЕЗ исхода (замаскированы)
        # ═══════════════════════════════════════════════════
        vip_blurred = sorted(vip_predictions, key=lambda x: x["confidence"], reverse=True)[:6]
        for pred in vip_blurred:
            if await publisher.publish_to_vip(pred):
                published += 1

        # ═══════════════════════════════════════════════════
        # 3. ЭКСПРЕССЫ: в ОБА канала одновременно
        # ═══════════════════════════════════════════════════
        express_candidates.sort(key=lambda x: x["confidence"], reverse=True)
        express_published = 0

        if len(express_candidates) >= 2:
            events_x2 = express_candidates[:2]
            events_data = []
            total_odds_x2 = 1.0
            for e in events_x2:
                events_data.append({
                    "home_team": e["match"]["home_team"],
                    "away_team": e["match"]["away_team"],
                    "prediction": e["prediction"],
                    "confidence": e["confidence"],
                    "odds": e["odds_est"],
                    "date": e["match"]["date"],
                    "sport": e["match"]["sport"],
                    "league": e["match"]["league"],
                })
                total_odds_x2 *= e["odds_est"]

            await publisher.publish_express_to_both(events_data, total_odds_x2, "🔥 ЭКСПРЕСС x2")
            express_published += 1
            published += 1
            await manager.save_express_group(events_data, total_odds_x2, 199)

        if len(express_candidates) >= 5:
            events_x3 = express_candidates[2:5]
            events_data_3 = []
            total_odds_x3 = 1.0
            for e in events_x3:
                events_data_3.append({
                    "home_team": e["match"]["home_team"],
                    "away_team": e["match"]["away_team"],
                    "prediction": e["prediction"],
                    "confidence": e["confidence"],
                    "odds": e["odds_est"],
                    "date": e["match"]["date"],
                    "sport": e["match"]["sport"],
                    "league": e["match"]["league"],
                })
                total_odds_x3 *= e["odds_est"]

            await publisher.publish_express_to_both(events_data_3, total_odds_x3, "🔥 ЭКСПРЕСС x3")
            express_published += 1
            published += 1
            await manager.save_express_group(events_data_3, total_odds_x3, 299)

        logger.info(f"✅ Опубликовано: {published} (обычный: {len(top_predictions)}, VIP: {len(vip_blurred)}, экспрессы: {express_published})")

        return published
    except Exception as e:
        logger.error(f"тЭМ ╨Ъ╤А╨╕╤В╨╕╤З╨╡╤Б╨║╨░╤П ╨╛╤И╨╕╨▒╨║╨░ ╨▓ ╨┐╨░╨╣╨┐╨╗╨░╨╣╨╜╨╡: {e}")
        return 0
    finally:
        # ЁЯЫбя╕П ╨У╨Р╨а╨Р╨Э╨в╨Ш╨а╨Ю╨Т╨Р╨Э╨Э╨Ю╨Х ╨Ч╨Р╨Ъ╨а╨л╨в╨Ш╨Х: ╨б╨╡╤Б╤Б╨╕╨╕ ╨╖╨░╨║╤А╨╛╤О╤В╤Б╤П ╨┐╤А╨╕ ╨╗╤О╨▒╨╛╨╝ ╨╕╤Б╤Е╨╛╨┤╨╡
        if publisher:
            await publisher.close()
        if db and hasattr(db, 'close'):
            try:
                await db.close()
            except Exception:
                pass
        is_pipeline_running = False


async def check_results_job():
    """╨Я╤А╨╛╨▓╨╡╤А╨║╨░ ╤А╨╡╨╖╤Г╨╗╤М╤В╨░╤В╨╛╨▓ ╨╝╨░╤В╤З╨╡╨╣"""
    checker = ResultChecker()
    await checker.run()


async def send_stats_report():
    """╨Х╨╢╨╡╨╜╨╡╨┤╨╡╨╗╤М╨╜╤Л╨╣ ╨╛╤В╤З╤С╤В ╨┐╨╛ ╨┐╨╛╨╜╨╡╨┤╨╡╨╗╤М╨╜╨╕╨║╨░╨╝"""
    db = None
    publisher = None
    try:
        db = Database()
        await db.init()
        stats = await db.get_stats()
        publisher = TelegramPublisher()
        text = (
            f"ЁЯУК *╨Х╨Ц╨Х╨Э╨Х╨Ф╨Х╨Ы╨м╨Э╨л╨Щ ╨Ю╨в╨з╨Х╨в* ЁЯУК\n\n"
            f"ЁЯПЯ ╨Т╤Б╨╡╨│╨╛ ╨┐╤А╨╛╨│╨╜╨╛╨╖╨╛╨▓: {stats['total']}\n"
            f"тЬЕ ╨Т╤Л╨╕╨│╤А╤Л╤И╨╡╨╣: {stats['wins']}\n"
            f"тЭМ ╨Я╤А╨╛╨╕╨│╤А╤Л╤И╨╡╨╣: {stats['losses']}\n"
            f"тП│ ╨Ю╨╢╨╕╨┤╨░╤О╤В ╤А╨░╤Б╤З╨╡╤В╨░: {stats['pending']}\n"
            f"ЁЯОп ╨Т╨╕╨╜╤А╨╡╨╣╤В: {stats['winrate']:.1f}%\n"
        )
        await publisher.bot.send_message(chat_id=settings.CHANNEL_ID, text=text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"╨Ю╤И╨╕╨▒╨║╨░ ╨│╨╡╨╜╨╡╤А╨░╤Ж╨╕╨╕ ╨╡╨╢╨╡╨╜╨╡╨┤╨╡╨╗╤М╨╜╨╛╨│╨╛ ╨╛╤В╤З╨╡╤В╨░: {e}")
    finally:
        # ╨У╨░╤А╨░╨╜╤В╨╕╤А╨╛╨▓╨░╨╜╨╜╨╛╨╡ ╨╖╨░╨║╤А╤Л╤В╨╕╨╡ ╤А╨╡╤Б╤Г╤А╤Б╨╛╨▓
        if publisher:
            await publisher.close()
        if db and hasattr(db, 'close'):
            try:
                await db.close()
            except Exception:
                pass


async def check_crypto_payments():
    """Проверка оплат CryptoBot каждые 30 секунд"""
    global _shared_publisher, _shared_crypto_service, _shared_manager

    try:
        # Инициализируем shared-экземпляры один раз
        if _shared_publisher is None:
            _shared_publisher = TelegramPublisher()
        if _shared_crypto_service is None:
            _shared_crypto_service = CryptoBotService()
        if _shared_manager is None:
            _shared_manager = SubscriptionManager()
            await _shared_manager.init()

        publisher = _shared_publisher
        service = _shared_crypto_service
        manager = _shared_manager
        vip_manager = VIPManager(publisher.bot)
        purchase_service = SinglePurchaseService(service)

        pending = await manager.get_pending_invoices()
        if not pending:
            return

        for inv in pending:
            # ЁЯЫбя╕П ╨Ъ╨░╨╢╨┤╤Л╨╣ ╨╕╨╜╨▓╨╛╨╣╤Б ╨╛╨▒╤А╨░╨▒╨░╤В╤Л╨▓╨░╨╡╨╝ ╨▓ ╤Б╨▓╨╛╨╡╨╝ ╨▒╨╗╨╛╨║╨╡ try-except, 
            # ╤З╤В╨╛╨▒╤Л ╨╛╤И╨╕╨▒╨║╨░ ╨╛╨┤╨╜╨╛╨│╨╛ ╨┐╨╗╨░╤В╨╡╨╢╨░ ╨╜╨╡ ╨╗╨╛╨╝╨░╨╗╨░ ╨┐╤А╨╛╨▓╨╡╤А╨║╤Г ╨▓╤Б╨╡╤Е ╨╛╤Б╤В╨░╨╗╤М╨╜╤Л╤Е.
            try:
                status = await service.check_invoice_status(inv["invoice_id"])
                if status == "paid":
                    plan = inv["plan"]
                    
                    # ╨Ю╨▒╤А╨░╨▒╨╛╤В╨║╨░ ╤Н╨║╤Б╨┐╤А╨╡╤Б╤Б╨╛╨▓
                    if plan.startswith("express_"):
                        parts = plan.split(":")
                        group_id = int(parts[1]) if len(parts) > 1 else int(plan.split("_")[2])
                        group_data = await manager.get_express_group(group_id)
                        if not group_data:
                            logger.error(f"тЭМ ╨У╤А╤Г╨┐╨┐╨░ {group_id} ╨╜╨╡ ╨╜╨░╨╣╨┤╨╡╨╜╨░ ╨▓ ╤Б╨╕╤Б╤В╨╡╨╝╨╡")
                            continue
                        full_text, keyboard = purchase_service.format_express_message(group_data)
                        await publisher.bot.send_message(chat_id=inv["user_id"], text=full_text, reply_markup=keyboard, parse_mode="HTML")
                        await manager.mark_invoice_paid(inv["invoice_id"])
                        logger.info(f"тЬЕ ╨Т╤Л╨┤╨░╨╜ ╤Н╨║╤Б╨┐╤А╨╡╤Б╤Б x{group_data['events_count']} #{inv['invoice_id']} ╨┤╨╗╤П @{inv['username']}")
                    
                    # ╨Ю╨▒╤А╨░╨▒╨╛╤В╨║╨░ ╨╛╨┤╨╕╨╜╨╛╤З╨╜╤Л╤Е VIP-╨┐╨╛╨║╤Г╨┐╨╛╨║
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
                            logger.info(f"тЬЕ ╨Т╤Л╨┤╨░╨╜ ╨╛╨┤╨╕╨╜╨╛╤З╨╜╤Л╨╣ VIP #{inv['invoice_id']} ╨┤╨╗╤П @{inv['username']}")
                    
                    # ╨Ю╨▒╤А╨░╨▒╨╛╤В╨║╨░ VIP-╨┐╨╛╨┤╨┐╨╕╤Б╨╛╨║ (╨┤╨╡╨╜╤М, ╨╜╨╡╨┤╨╡╨╗╤П, ╨╝╨╡╤Б╤П╤Ж...)
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
                                f"ЁЯОЙ <b>╨Ю╨┐╨╗╨░╤В╨░ ╤Г╤Б╨┐╨╡╤И╨╜╨╛ ╨┐╨╛╨╗╤Г╤З╨╡╨╜╨░!</b>\n\n"
                                f"ЁЯСС VIP ╨┤╨╛╤Б╤В╤Г╨┐╨╡╨╜ ╨┤╨╛: <b>{expires_msk.strftime('%d.%m.%Y %H:%M')} (╨Ь╨б╨Ъ)</b>\n\n"
                                f"ЁЯФЧ <a href='{invite_link}'>ЁЯСЙ ╨Э╨Р╨Ц╨Ь╨Ш╨в╨Х ╨б╨о╨Ф╨Р, ╨з╨в╨Ю╨С╨л ╨Т╨Ю╨Щ╨в╨Ш ╨Т VIP</a>"
                            ), 
                            parse_mode="HTML", 
                            disable_web_page_preview=True
                        )
                        logger.info(f"тЬЕ ╨Р╨║╤В╨╕╨▓╨╕╤А╨╛╨▓╨░╨╜╨░ VIP ╨┐╨╛╨┤╨┐╨╕╤Б╨║╨░ ({plan}) #{inv['invoice_id']} ╨┤╨╗╤П @{inv['username']}")
            except Exception as invoice_error:
                logger.error(f"тЭМ ╨Ю╤И╨╕╨▒╨║╨░ ╨╛╨▒╤А╨░╨▒╨╛╤В╨║╨╕ ╨║╨╛╨╜╨║╤А╨╡╤В╨╜╨╛╨│╨╛ ╨╕╨╜╨▓╨╛╨╣╤Б╨░ #{inv.get('invoice_id')}: {invoice_error}")
                
    except Exception as e:
        logger.error(f"Системная ошибка в check_crypto_payments: {e}")
    # Не закрываем shared-экземпляры — они используются повторно


async def main():
    """╨У╨╗╨░╨▓╨╜╨░╤П ╤Д╤Г╨╜╨║╤Ж╨╕╤П: ╨╖╨░╨┐╤Г╤Б╨║╨░╨╡╤В ╨▓╨╡╨▒-╤Б╨╡╤А╨▓╨╡╤А + ╨▒╨╛╤В + scheduler"""
    try:
        import uvicorn
        from web.main import app as web_app
        config = uvicorn.Config(web_app, host="0.0.0.0", port=8000, log_level="warning", access_log=False)
        server = uvicorn.Server(config)
        asyncio.create_task(server.serve())
        logger.info("ЁЯМР ╨Т╨╡╨▒-╤Б╨░╨╣╤В ╤Г╤Б╨┐╨╡╤И╨╜╨╛ ╨╖╨░╨┐╤Г╤Й╨╡╨╜ ╨╜╨░ http://0.0.0.0:8000")
    except Exception as e:
        logger.warning(f"тЪая╕П ╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨╖╨░╨┐╤Г╤Б╤В╨╕╤В╤М ╨▓╨╡╨▒-╤Б╨╡╤А╨▓╨╡╤А: {e}")

    # ╨Э╨░╤Б╤В╤А╨░╨╕╨▓╨░╨╡╨╝ ╨┐╨╗╨░╨╜╨╕╤А╨╛╨▓╤Й╨╕╨║ ╨╜╨░ ╨Ь╨╛╤Б╨║╨╛╨▓╤Б╨║╨╛╨╡ ╨▓╤А╨╡╨╝╤П (UTC+3)
    scheduler = AsyncIOScheduler(timezone=timezone(timedelta(hours=3)))
    
    # ╨а╨╡╨│╤Г╨╗╤П╤А╨╜╤Л╨╡ ╨╖╨░╨┤╨░╤З╨╕ ╨┐╨╛ ╤А╨░╤Б╨┐╨╕╤Б╨░╨╜╨╕╤О
    scheduler.add_job(run_pipeline, "cron", hour=8, minute=0, id="morning_publisher")

    async def daily_stats_report():
        db = None
        publisher = None
        try:
            db = Database()
            await db.init()
            stats = await db.get_stats()
            publisher = TelegramPublisher()
            text = (
                f"ЁЯУК <b>╨б╨в╨Р╨в╨Ш╨б╨в╨Ш╨Ъ╨Р ╨Ч╨Р ╨Т╨з╨Х╨а╨Р</b> ЁЯУК\n\n"
                f"ЁЯПЯ ╨б╤Л╨│╤А╨░╨╜╨╛ ╨┐╤А╨╛╨│╨╜╨╛╨╖╨╛╨▓: {stats['total']}\n"
                f"тЬЕ ╨Т╤Л╨╕╨│╤А╤Л╤И╨╡╨╣: {stats['wins']}\n"
                f"тЭМ ╨Я╤А╨╛╨╕╨│╤А╤Л╤И╨╡╨╣: {stats['losses']}\n"
                f"тП│ ╨Ю╨╢╨╕╨┤╨░╤О╤В ╤А╨╡╨╖╤Г╨╗╤М╤В╨░╤В╨░: {stats['pending']}\n"
                f"ЁЯОп <b>╨Т╨╕╨╜╤А╨╡╨╣╤В:</b> {stats['winrate']:.1f}%\n\n"
                f"тФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБ\n"
                f"ЁЯТб <i>╨Я╨╛╨┤╨┐╨╕╤Б╤Л╨▓╨░╨╣╤В╨╡╤Б╤М ╨╜╨░ VIP ╨┤╨╗╤П ╤Н╨║╤Б╨║╨╗╤О╨╖╨╕╨▓╨╜╤Л╤Е ╨┐╤А╨╛╨│╨╜╨╛╨╖╨╛╨▓!</i>\n\n"
                f"тЪая╕П <i>╨Ф╨╕╤Б╨║╨╗╨╡╨╣╨╝╨╡╤А: ╨Я╤А╨╛╨│╨╜╨╛╨╖╤Л ╨╜╨╛╤Б╤П╤В ╨╕╨╜╤Д╨╛╤А╨╝╨░╤Ж╨╕╨╛╨╜╨╜╤Л╨╣ ╤Е╨░╤А╨░╨║╤В╨╡╤А. ╨Ю╤В╨▓╨╡╤В╤Б╤В╨▓╨╡╨╜╨╜╨░╤П ╨╕╨│╤А╨░. 18+</i>"
            )
            await publisher.bot.send_message(chat_id=settings.CHANNEL_ID, text=text, parse_mode="HTML")
            logger.info("ЁЯУК ╨Х╨╢╨╡╨┤╨╜╨╡╨▓╨╜╨░╤П ╤Б╤В╨░╤В╨╕╤Б╤В╨╕╨║╨░ ╨╛╤В╨┐╤А╨░╨▓╨╗╨╡╨╜╨░ ╨▓ ╨║╨░╨╜╨░╨╗")
        except Exception as e:
            logger.error(f"╨Ю╤И╨╕╨▒╨║╨░ ╨╡╨╢╨╡╨┤╨╜╨╡╨▓╨╜╨╛╨╣ ╤Б╤В╨░╤В╨╕╤Б╤В╨╕╨║╨╕: {e}")
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
            logger.error(f"╨Ю╤И╨╕╨▒╨║╨░ ╤Г╨┤╨░╨╗╨╡╨╜╨╕╤П ╨┐╤А╨╛╤Б╤А╨╛╤З╨╡╨╜╨╜╤Л╤Е VIP ╨┐╨╛╨╗╤М╨╖╨╛╨▓╨░╤В╨╡╨╗╨╡╨╣: {e}")
        finally:
            if p:
                await p.close()

    scheduler.add_job(check_expired_vip, "interval", hours=1, next_run_time=datetime.now(), id="vip_checker")
    scheduler.add_job(check_crypto_payments, "interval", seconds=30, next_run_time=datetime.now(), id="crypto_checker")
    
    scheduler.start()

    # ╨Ш╨╜╨╕╤Ж╨╕╨░╨╗╨╕╨╖╨░╤Ж╨╕╤П Aiogram Bot & Dispatcher
    publisher = TelegramPublisher()
    dp = Dispatcher()
    dp.include_router(handlers_router)
    dp.include_router(admin_router)
    dp.include_router(favorites_router)

    try:
        await publisher.bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        logger.warning(f"тЪая╕П ╨Ю╤И╨╕╨▒╨║╨░ ╤Г╨┤╨░╨╗╨╡╨╜╨╕╤П ╨▓╨╡╨▒╤Е╤Г╨║╨░: {e}")

    logger.info("ЁЯдЦ SportPredict AI ╨╖╨░╨┐╤Г╤Й╨╡╨╜ ╨╕ ╨│╨╛╤В╨╛╨▓ ╨║ ╤А╨░╨▒╨╛╤В╨╡. ╨а╨░╤Б╨┐╨╕╤Б╨░╨╜╨╕╨╡: 8:00 ╨Ь╨б╨Ъ ╨╡╨╢╨╡╨┤╨╜╨╡╨▓╨╜╨╛.")
    
    try:
        await dp.start_polling(publisher.bot)
    finally:
        await publisher.close()


if __name__ == "__main__":
    asyncio.run(main())


