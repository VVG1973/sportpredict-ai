"""
Публикатор прогнозов в Telegram каналы (с защитой от дублей, фильтром видов спорта и rate limiting)
"""
import logging
import asyncio
from datetime import datetime
from collections import deque
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
        if not date_str:
            return "Дата не указана"
        if "T" in date_str:
            dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        else:
            dt = datetime.fromisoformat(date_str)
        months = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]
        return f"{dt.day} {months[dt.month - 1]}, {dt.hour:02d}:{dt.minute:02d}"
    except Exception:
        return date_str[:16].replace("T", " ") if date_str else "Дата не указана"


class RateLimiter:
    """
    Rate limiter для Telegram API.
    Telegram ограничивает: ~30 сообщений/сек в одном чате, ~20/сек глобально.
    """
    def __init__(self, max_requests: int = 20, period: float = 1.0):
        self.max_requests = max_requests      # Макс запросов за период
        self.period = period                  # Период в секундах
        self.requests = []                    # Времена запросов
        self.lock = asyncio.Lock()

    async def acquire(self):
        """Ждёт, пока можно сделать запрос"""
        async with self.lock:
            now = asyncio.get_event_loop().time()
            
            # Удаляем старые запросы (вне периода)
            self.requests = [t for t in self.requests if now - t < self.period]
            
            # Если лимит превышен — ждём
            if len(self.requests) >= self.max_requests:
                sleep_time = self.period - (now - self.requests[0])
                if sleep_time > 0:
                    logger.debug(f"⏳ Rate limit: ждём {sleep_time:.2f} сек")
                    await asyncio.sleep(sleep_time)
                    # Пересчитываем после ожидания
                    now = asyncio.get_event_loop().time()
                    self.requests = [t for t in self.requests if now - t < self.period]
            
            # Добавляем текущий запрос
            self.requests.append(now)


def create_bookmakers_keyboard(is_vip: bool = False) -> "InlineKeyboardMarkup":
    """Создаёт клавиатуру с букмекерами"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    bookmakers = [
        ("Лига Ставок", "https://www.ligastavok.ru"),
        "Фонбет", "https://www.fonbet.ru",
        "1хСтавка", "https://1xstavka.ru",
        "Бетсити", "https://www.betsiti.ru",
        "Винлайн", "https://www.winline.ru",
        "Марафон", "https://www.marathonbet.ru",
    ]

    buttons = []
    for i in range(0, len(bookmakers), 2):
        row = []
        for j in range(2):
            if i + j < len(bookmakers):
                item = bookmakers[i + j]
                if isinstance(item, tuple):
                    name, url = item
                else:
                    name, url = item, item
                row.append(InlineKeyboardButton(text=name, url=url))
        buttons.append(row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)


class TelegramPublisher:
    # 🛡️ Кэш для защиты от дублей (FIFO eviction при переполнении)
    _recently_published: deque = deque(maxlen=500)
    _recently_published_set: set = set()

    # 🛡️ Rate limiter (20 запросов в секунду — запас до лимита Telegram)
    _rate_limiter = RateLimiter(max_requests=20, period=1.0)

    def __init__(self):
        self.channel_id = getattr(settings, 'CHANNEL_ID', None)
        self.vip_channel_id = getattr(settings, 'VIP_CHANNEL_ID', None)
        self.bot = None

        # Получаем токен из SecretStr
        token_obj = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        token = token_obj.get_secret_value() if token_obj else ""

        if token and ":" in token and len(token) > 20:
            try:
                self.bot = Bot(token=token, default=DefaultBotProperties(parse_mode="HTML"))
                logger.info("✅ Telegram Bot для публикации инициализирован")
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации Telegram Bot: {e}")
        else:
            logger.warning("⚠️ TELEGRAM_BOT_TOKEN не задан или невалиден!")

        logger.info(f"📢 Обычный канал: {self.channel_id or '❌ не настроен'}")
        logger.info(f"💎 VIP канал: {self.vip_channel_id or '❌ не настроен'}")

    async def publish(self, prediction: dict, is_vip: bool = False, is_single_purchase: bool = False):
        if not self.bot:
            return

        match = prediction.get("match", {})
        sport = match.get("sport", "⚽ Футбол")

        # 🛑 ФИЛЬТР 1: Игнорируем неподдерживаемые виды спорта
        supported_sports = ["футбол", "football", "soccer", "cs", "dota", "lol", "valorant", "кибер", "esport"]
        if not any(s in sport.lower() for s in supported_sports):
            logger.info(f"⏭️ Пропуск неподдерживаемого вида спорта: {sport}")
            return

        league = match.get("league", "")
        home = to_russian_name(match.get("home_team", "Команда 1"))
        away = to_russian_name(match.get("away_team", "Команда 2"))
        pred = prediction.get("prediction", "П1")
        date_ru = format_datetime_ru(match.get("date", ""))
        conf = prediction.get("confidence", 0.5)
        odds = prediction.get("odds_est", 2.0)

        # 🛑 ФИЛЬТР 2: Защита от дублей (FIFO eviction)
        match_key = f"{home}_{away}_{date_ru}"
        if match_key in self._recently_published_set:
            logger.warning(f"⚠️ Пропуск дубликата: {home} vs {away}")
            return

        # Добавляем в deque (автоматически удаляет самый старый при переполнении)
        if len(self._recently_published) == self._recently_published.maxlen:
            old_key = self._recently_published[0]
            self._recently_published_set.discard(old_key)
        self._recently_published.append(match_key)
        self._recently_published_set.add(match_key)

        # 🛑 ФИЛЬТР 3: Ничья только для футбола
        if pred in ["X", "D", "Ничья"] and not any(s in sport.lower() for s in ["футбол", "football", "soccer"]):
            logger.warning(f"⚠️ Пропуск ничьей для {sport}: {home} vs {away}")
            return

        vip_badge = "👑 <b>VIP-ПРОГНОЗ</b>\n\n" if is_vip else ""
        # Дополнительные рынки из multi-output
        extra_lines = []
        total = prediction.get("total", {})
        both_scored = prediction.get("both_scored", {})
        handicap = prediction.get("handicap", {})

        if isinstance(total, dict) and total.get("prediction"):
            extra_lines.append(f"⚽ Тотал: {total.get('prediction')}")
        elif isinstance(total, str) and total:
            extra_lines.append(f"⚽ Тотал: {total}")
        if isinstance(both_scored, dict) and both_scored.get("prediction"):
            extra_lines.append(f"🥅 Обе забьют: {both_scored.get('prediction')}")
        elif isinstance(both_scored, str) and both_scored:
            extra_lines.append(f"🥅 Обе забьют: {both_scored}")
        if isinstance(handicap, dict) and handicap.get("prediction"):
            extra_lines.append(f"📊 Фора: {handicap.get('prediction')}")
        elif isinstance(handicap, str) and handicap:
            extra_lines.append(f"📊 Фора: {handicap}")

        extra_text = "\n".join(extra_lines)
        if extra_text:
            extra_text = "\n" + extra_text + "\n"

        # Value bet метки
        value_badge = ""
        if isinstance(prediction, dict):
            outcome_data = prediction.get("outcome", {})
            total_data = prediction.get("total", {})
            both_data = prediction.get("both_scored", {})
            handicap_data = prediction.get("handicap", {})
            
            value_parts = []
            if outcome_data.get("is_value_bet"):
                value_parts.append(f"💎 Исход {outcome_data.get('value', 0):+.1%}")
            if total_data.get("is_value_bet"):
                value_parts.append(f"⚽ Тотал {total_data.get('value', 0):+.1%}")
            if both_data.get("is_value_bet"):
                value_parts.append(f"🥅 ОЗ {both_data.get('value', 0):+.1%}")
            if handicap_data.get("is_value_bet"):
                value_parts.append(f"📊 Фора {handicap_data.get('value', 0):+.1%}")
            
            if value_parts:
                value_badge = "\n🔥 " + " | ".join(value_parts) + "\n"

        text = (
            f"{vip_badge}{sport} | {league}\n\n"
            f"🏟 <b>{home}</b> vs <b>{away}</b>\n"
            f"📅 {date_ru}\n\n"
            f"🎯 <b>Прогноз:</b> {pred}\n"
            f"📊 Уверенность: {conf:.0%}\n"
            f"💰 Коэффициент: {odds:.2f}"
            f"{extra_text}"
            f"{value_badge}"
            f"━━━━━━━━━━━━━━━━━━━━━\n🤖 <i>SportPredict AI</i>"
        )

        target_channel = self.vip_channel_id if (is_vip and self.vip_channel_id) else self.channel_id
        if not target_channel:
            return

        try:
            # 🛡️ Ждём rate limit ПЕРЕД отправкой
            await self._rate_limiter.acquire()
            
            await self.bot.send_message(
                chat_id=target_channel,
                text=text,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            logger.info(f"✅ Опубликовано ({'VIP' if is_vip else 'Обычный'}): {home} vs {away}")
        except Exception as e:
            logger.error(f"❌ Ошибка публикации: {e}")

    async def close(self):
        if self.bot:
            await self.bot.session.close()

