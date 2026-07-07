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
from telegram_bot.vip_manager import VIPManager, CryptoBotService, SubscriptionManager, SinglePurchaseService

# ╨У╨╗╨╛╨▒╨░╨╗╤М╨╜╤Л╨╣ ╨╖╨░╨╝╨╛╨║ ╨╛╤В ╨╛╨┤╨╜╨╛╨▓╤А╨╡╨╝╨╡╨╜╨╜╤Л╤Е ╨╖╨░╨┐╤Г╤Б╨║╨╛╨▓ ╨┐╨░╨╣╨┐╨╗╨░╨╣╨╜╨░
is_pipeline_running = False

logger.info("тП│ ╨Ш╨╜╨╕╤Ж╨╕╨░╨╗╨╕╨╖╨░╤Ж╨╕╤П ML-╨╝╨╛╨┤╨╡╨╗╨╕ ╨╖╨░╨▓╨╡╤А╤И╨╡╨╜╨░")


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
                
            # ЁЯз╡ ╨Ю╨Я╨в╨Ш╨Ь╨Ш╨Ч╨Р╨ж╨Ш╨п: ╨Ю╨▒╤Г╤З╨╡╨╜╨╕╨╡/╤А╨░╤Б╤З╨╡╤В ML-╨╝╨╛╨┤╨╡╨╗╨╕ ╨▓╤Л╨╜╨╛╤Б╨╕╨╝ ╨▓ ╨╛╤В╨┤╨╡╨╗╤М╨╜╤Л╨╣ ╨┐╨╛╤В╨╛╨║
            ml_result = await asyncio.to_thread(
                ml_model.predict,
                home_team=home_team,
                away_team=away_team,
                match_date=match_date,
                historical_df=historical_df
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
            outcome_mapping = {"H": "╨Я1", "D": "X", "A": "╨Я2"}
            if predicted_outcome in outcome_mapping:
                predicted_outcome = outcome_mapping[predicted_outcome]
            else:
                predicted_outcome = m.get("outcome", "╨Я1")

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
                "match": match_data
            }

            # ╨Ъ╨░╤В╨╡╨│╨╛╤А╨╕╨╖╨░╤Ж╨╕╤П ╨┐╨╛ ╤Г╤А╨╛╨▓╨╜╤О ╤Г╨▓╨╡╤А╨╡╨╜╨╜╨╛╤Б╤В╨╕
            if pred["confidence"] >= settings.VIP_CONFIDENCE_THRESHOLD:
                vip_predictions.append(pred)
            elif pred["confidence"] >= 0.71:
                express_candidates.append(pred)
            else:
                regular_predictions.append(pred)

        published = 0

        # 1я╕ПтГг ╨Я╤Г╨▒╨╗╨╕╨║╨░╤Ж╨╕╤П VIP-╨┐╤А╨╛╨│╨╜╨╛╨╖╨╛╨▓
        for pred in vip_predictions:
            if await publisher.publish(pred, is_vip=True, is_single_purchase=False):
                published += 1

        # 2я╕ПтГг ╨Я╤Г╨▒╨╗╨╕╨║╨░╤Ж╨╕╤П ╨╛╨▒╤Л╤З╨╜╤Л╤Е ╨┐╤А╨╛╨│╨╜╨╛╨╖╨╛╨▓
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

                # ╨г╨▓╨╡╨┤╨╛╨╝╨╗╨╡╨╜╨╕╤П ╨┐╨╛╨┤╨┐╨╕╤Б╤З╨╕╨║╨░╨╝ ╨╗╤О╨▒╨╕╨╝╤Л╤Е ╨║╨╛╨╝╨░╨╜╨┤
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
                            f"тЪб <b>╨Я╤А╨╛╨│╨╜╨╛╨╖ ╨╜╨░ ╨▓╨░╤И╤Г ╨║╨╛╨╝╨░╨╜╨┤╤Г!</b>\n\n"
                            f"{sport} | <i>{league}</i>\n"
                            f"ЁЯПЯ <b>{home_team}</b> тАФ <b>{away_team}</b>\n"
                            f"ЁЯУЕ <i>{date_ru}</i>\n\n"
                            f"ЁЯОп <b>╨Я╤А╨╛╨│╨╜╨╛╨╖:</b> {pred['prediction']}\n"
                            f"ЁЯУК <b>╨г╨▓╨╡╤А╨╡╨╜╨╜╨╛╤Б╤В╤М:</b> {pred['confidence']:.0%}\n"
                            f"ЁЯТ░ <b>╨Ъ╨╛╤Н╤Д:</b> {pred['odds_est']}\n\n"
                            f"тФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБ\n"
                            f"тЪая╕П <i>╨Ю╤В╨▓╨╡╤В╤Б╤В╨▓╨╡╨╜╨╜╨░╤П ╨╕╨│╤А╨░. 18+</i>"
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
                                logger.debug(f"╨Э╨╡ ╤Г╨┤╨░╨╗╨╛╤Б╤М ╨╛╤В╨┐╤А╨░╨▓╨╕╤В╤М {username}: {e}")

                        if sent_count > 0:
                            logger.info(f"ЁЯУи ╨Ю╤В╨┐╤А╨░╨▓╨╗╨╡╨╜╨╛ ╨╗╨╕╤З╨╜╤Л╤Е ╤Г╨▓╨╡╨┤╨╛╨╝╨╗╨╡╨╜╨╕╨╣: {sent_count} ╨╜╨░ ╨╝╨░╤В╤З {home_team} - {away_team}")
                except Exception as e:
                    logger.warning(f"╨Ю╤И╨╕╨▒╨║╨░ ╨╛╤В╨┐╤А╨░╨▓╨║╨╕ ╤Г╨▓╨╡╨┤╨╛╨╝╨╗╨╡╨╜╨╕╨╣ ╨┐╨╛╨┤╨┐╨╕╤Б╤З╨╕╨║╨░╨╝: {e}")

        # 3я╕ПтГг ╨Я╤Г╨▒╨╗╨╕╨║╨░╤Ж╨╕╤П ╨н╨║╤Б╨┐╤А╨╡╤Б╤Б╨╛╨▓
        express_candidates.sort(key=lambda x: x["confidence"], reverse=True)
        express_published = 0
        admin_express_details = []

        # ╨б╤Ж╨╡╨╜╨░╤А╨╕╨╣ ╨Р: ╨Ъ╨░╨╜╨┤╨╕╨┤╨░╤В╨╛╨▓ ╨╝╨╜╨╛╨│╨╛ (>= 5) -> ╨┤╨╡╨╗╨░╨╡╨╝ ╨╛╨┤╨╕╨╜ ╤Н╨║╤Б╨┐╤А╨╡╤Б╤Б ╤Е2 ╨╕ ╨╛╨┤╨╕╨╜ ╤Е3
        if len(express_candidates) >= 5:
            # ╨н╨║╤Б╨┐╤А╨╡╤Б╤Б ╤Е2 (╨▒╨╡╤А╨╡╨╝ ╨┐╨╡╤А╨▓╤Л╨╡ 2 ╨╗╤Г╤З╤И╨╕╤Е ╨║╨░╨╜╨┤╨╕╨┤╨░╤В╨░)
            success, events, odds = await create_and_publish_express(
                candidates=express_candidates[:2],
                count=2,
                price=149,
                manager=manager,
                publisher=publisher,
                express_label="╨н╨║╤Б╨┐╤А╨╡╤Б╤Б x2"
            )
            if success:
                express_published += 1
                published += 1
                admin_express_details.append({
                    "title": f"ЁЯФе ╨н╨║╤Б╨┐╤А╨╡╤Б╤Б x2 (149тВ╜) тАФ ╨║╨╛╤Н╤Д {odds:.2f}",
                    "events": events,
                    "total_odds": odds,
                    "price": 149
                })

            # ╨н╨║╤Б╨┐╤А╨╡╤Б╤Б ╤Е3 (╨▒╨╡╤А╨╡╨╝ ╤Б╨╗╨╡╨┤╤Г╤О╤Й╨╕╤Е 3 ╨║╨░╨╜╨┤╨╕╨┤╨░╤В╨╛╨▓)
            success, events, odds = await create_and_publish_express(
                candidates=express_candidates[2:5],
                count=3,
                price=199,
                manager=manager,
                publisher=publisher,
                express_label="╨н╨║╤Б╨┐╤А╨╡╤Б╤Б x3"
            )
            if success:
                express_published += 1
                published += 1
                admin_express_details.append({
                    "title": f"ЁЯФе ╨н╨║╤Б╨┐╤А╨╡╤Б╤Б x3 (199тВ╜) тАФ ╨║╨╛╤Н╤Д {odds:.2f}",
                    "events": events,
                    "total_odds": odds,
                    "price": 199
                })

        # ╨б╤Ж╨╡╨╜╨░╤А╨╕╨╣ ╨С: ╨Ъ╨░╨╜╨┤╨╕╨┤╨░╤В╨╛╨▓ ╨╝╨░╨╗╨╛ (╨╛╤В 2 ╨┤╨╛ 4) -> ╨┤╨╡╨╗╨░╨╡╨╝ ╤В╨╛╨╗╤М╨║╨╛ ╨╛╨┤╨╕╨╜ ╤Н╨║╤Б╨┐╤А╨╡╤Б╤Б ╤Е2
        elif len(express_candidates) >= 2:
            success, events, odds = await create_and_publish_express(
                candidates=express_candidates[:2],
                count=2,
                price=149,
                manager=manager,
                publisher=publisher,
                express_label="╨н╨║╤Б╨┐╤А╨╡╤Б╤Б x2"
            )
            if success:
                express_published += 1
                published += 1
                admin_express_details.append({
                    "title": f"ЁЯФе ╨н╨║╤Б╨┐╤А╨╡╤Б╤Б x2 (149тВ╜) тАФ ╨║╨╛╤Н╤Д {odds:.2f}",
                    "events": events,
                    "total_odds": odds,
                    "price": 149
                })
            logger.info(f"тЪая╕П ╨б╨╛╨╖╨┤╨░╨╜ ╤В╨╛╨╗╤М╨║╨╛ 1 ╤Н╨║╤Б╨┐╤А╨╡╤Б╤Б. ╨Э╨╡╨┤╨╛╤Б╤В╨░╤В╨╛╤З╨╜╨╛ ╨║╨░╨╜╨┤╨╕╨┤╨░╤В╨╛╨▓ ╨┤╨╗╤П ╨▓╤В╨╛╤А╨╛╨│╨╛: {len(express_candidates)}")

        # ╨Ю╤В╨┐╤А╨░╨▓╨╗╤П╨╡╨╝ ╨╛╤В╤З╨╡╤В ╨░╨┤╨╝╨╕╨╜╤Г ╨▓ ╨Ы╨б
        if admin_express_details:
            try:
                admin_text = "ЁЯФУ <b>╨Ф╨Х╨в╨Р╨Ы╨Ш ╨б╨д╨Ю╨а╨Ь╨Ш╨а╨Ю╨Т╨Р╨Э╨Э╨л╨е ╨н╨Ъ╨б╨Я╨а╨Х╨б╨б╨Ю╨Т</b>\n\n"
                for express in admin_express_details:
                    admin_text += f"<b>{express['title']}</b>\n"
                    admin_text += f"тФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБ\n"
                    for i, ev in enumerate(express["events"], 1):
                        admin_text += (
                            f"<b>{i}.</b> {ev['sport']} | <i>{ev['league']}</i>\n"
                            f"ЁЯПЯ <b>{ev['home_team']}</b> тАФ <b>{ev['away_team']}</b>\n"
                            f"ЁЯУЕ <i>{ev['date'][:16].replace('T', ' ')}</i>\n"
                            f"ЁЯОп <b>╨Ш╤Б╤Е╨╛╨┤: {ev['prediction']}</b>\n"
                            f"ЁЯУК ╨г╨▓╨╡╤А╨╡╨╜╨╜╨╛╤Б╤В╤М: {ev['confidence']:.0%}\n"
                            f"ЁЯТ░ ╨Ъ╨╛╤Н╤Д: {ev['odds']}\n\n"
                        )
                    admin_text += (
                        f"ЁЯТ╡ <b>╨ж╨╡╨╜╨░:</b> {express['price']}тВ╜\n"
                        f"ЁЯУИ <b>╨Ю╨▒╤Й╨╕╨╣ ╨║╨╛╤Н╤Д:</b> {express['total_odds']:.2f}\n\n"
                    )
                admin_text += "тФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБтФБ\n"
                admin_text += f"ЁЯУд ╨Т╤Б╨╡╨│╨╛ ╨╛╨┐╤Г╨▒╨╗╨╕╨║╨╛╨▓╨░╨╜╨╛ ╤Н╨║╤Б╨┐╤А╨╡╤Б╤Б╨╛╨▓: {express_published}"
                await publisher.bot.send_message(chat_id=settings.ADMIN_ID, text=admin_text, parse_mode="HTML")
                logger.info("ЁЯУи ╨Ф╨╡╤В╨░╨╗╨╕ ╤Н╨║╤Б╨┐╤А╨╡╤Б╤Б╨╛╨▓ ╨╛╤В╨┐╤А╨░╨▓╨╗╨╡╨╜╤Л ╨░╨┤╨╝╨╕╨╜╨╕╤Б╤В╤А╨░╤В╨╛╤А╤Г")
            except Exception as e:
                logger.error(f"╨Ю╤И╨╕╨▒╨║╨░ ╨╛╤В╨┐╤А╨░╨▓╨║╨╕ ╨╛╤В╤З╨╡╤В╨░ ╨░╨┤╨╝╨╕╨╜╤Г: {e}")

        logger.info(f"ЁЯУд ╨Я╨░╨╣╨┐╨╗╨░╨╣╨╜ ╨╖╨░╨▓╨╡╤А╤И╨╡╨╜. ╨Ю╨┐╤Г╨▒╨╗╨╕╨║╨╛╨▓╨░╨╜╨╛ ╨┐╤А╨╛╨│╨╜╨╛╨╖╨╛╨▓: {published} (VIP: {len(vip_predictions)}, ╨Ю╨▒╤Л╤З╨╜╤Л╨╡: {len(regular_predictions)}, ╨н╨║╤Б╨┐╤А╨╡╤Б╤Б╤Л: {express_published})")
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
    """╨Я╤А╨╛╨▓╨╡╤А╨║╨░ ╨╛╨┐╨╗╨░╤В CryptoBot ╨║╨░╨╢╨┤╤Л╨╡ 30 ╤Б╨╡╨║╤Г╨╜╨┤"""
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
        logger.error(f"тЭМ ╨б╨╕╤Б╤В╨╡╨╝╨╜╨░╤П ╨╛╤И╨╕╨▒╨║╨░ ╨▓ check_crypto_payments: {e}")
    finally:
        # ╨У╨░╤А╨░╨╜╤В╨╕╤А╨╛╨▓╨░╨╜╨╜╨╛╨╡ ╨╖╨░╨║╤А╤Л╤В╨╕╨╡ ╤Б╨╡╤Б╤Б╨╕╨╣
        if publisher:
            await publisher.close()
        if service:
            await service.close()


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


