"""
Публикатор прогнозов в Telegram каналы (с защитой от падения)
"""
import logging
from datetime import datetime
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from config import settings

logger = logging.getLogger(__name__)

def to_russian_name(name: str) -> str:
    translations = {
        "Manchester United": "Манчестер Юнайтед", "Manchester City": "Манчестер Сити",
        "Liverpool": "Ливерпуль", "Chelsea": "Челси", "Arsenal": "Арсенал",
        "Tottenham": "Тоттенхэм", "Real Madrid": "Реал Мадрид", "Barcelona": "Барселона",
        "Atletico Madrid": "Атлетико Мадрид", "Bayern Munich": "Бавария Мюнхен",
        "Borussia Dortmund": "Боруссия Дортмунд", "PSG": "ПСЖ", "Juventus": "Ювентус",
        "AC Milan": "Милан", "Inter Milan": "Интер", "Napoli": "Наполи",
        "Zenit": "Зенит", "Spartak Moscow": "Спартак Москва", "CSKA Moscow": "ЦСКА Москва",
    }
    return translations.get(name, name)

def format_datetime_ru(date_str: str) -> str:
    try:
        if not date_str: return "Дата не указана"
        if "T" in date_str: dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        else: dt = datetime.fromisoformat(date_str)
        months = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]
        return f"{dt.day} {months[dt.month - 1]}, {dt.hour:02d}:{dt.minute:02d}"
    except Exception:
        return date_str[:16].replace("T", " ") if date_str else "Дата не указана"

class TelegramPublisher:
    def __init__(self):
        self.channel_id = getattr(settings, 'CHANNEL_ID', None)
        self.vip_channel_id = getattr(settings, 'VIP_CHANNEL_ID', None)
        self.bot = None
        
        token = getattr(settings, 'TELEGRAM_BOT_TOKEN', "")
        
        # Защита: проверяем валидность токена ДО создания Bot
        if token and ":" in token and len(token) > 20:
            try:
                self.bot = Bot(token=token, default=DefaultBotProperties(parse_mode="HTML"))
                logger.info("✅ Telegram Bot для публикации инициализирован")
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации Telegram Bot: {e}")
                self.bot = None
        else:
            logger.warning("⚠️ TELEGRAM_BOT_TOKEN не задан или невалиден! Публикация в каналы отключена, но приложение продолжит работу.")
            
        logger.info(f"📢 Обычный канал: {self.channel_id or '❌ не настроен'}")
        logger.info(f"💎 VIP канал: {self.vip_channel_id or '❌ не настроен'}")
    
    async def publish(self, prediction: dict, is_vip: bool = False, is_single_purchase: bool = False):
        if not self.bot:
            logger.warning("⚠️ Пропуск публикации: Telegram Bot не инициализирован (нет токена)")
            return

        match = prediction.get("match", {})
        sport = match.get("sport", "⚽ Футбол")
        league = match.get("league", "")
        home = to_russian_name(match.get("home_team", "Команда 1"))
        away = to_russian_name(match.get("away_team", "Команда 2"))
        pred = prediction.get("prediction", "П1")
        date_ru = format_datetime_ru(match.get("date", ""))
        conf = prediction.get("confidence", 0.5)
        odds = prediction.get("odds_est", 2.0)
        
        vip_badge = "👑 <b>VIP-ПРОГНОЗ</b>\n\n" if is_vip else ""
        text = (
            f"{vip_badge}{sport} | {league}\n\n"
            f"🏟 <b>{home}</b> vs <b>{away}</b>\n"
            f"📅 {date_ru}\n\n"
            f"🎯 <b>Прогноз:</b> {pred}\n"
            f"📊 Уверенность: {conf:.0%}\n"
            f"💰 Коэффициент: {odds:.2f}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n🤖 <i>SportPredict AI</i>"
        )
        
        target_channel = self.vip_channel_id if (is_vip and self.vip_channel_id) else self.channel_id
        if not target_channel:
            logger.warning("⚠️ Канал для публикации не настроен")
            return

        try:
            await self.bot.send_message(chat_id=target_channel, text=text, parse_mode="HTML", disable_web_page_preview=True)
            logger.info(f"✅ Прогноз опубликован: {home} vs {away}")
        except Exception as e:
            logger.error(f"❌ Ошибка публикации в канал {target_channel}: {e}")
    
    async def close(self):
        if self.bot:
            await self.bot.session.close()
