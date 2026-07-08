"""
Публикатор прогнозов в Telegram каналы
- Обычный канал: 1-2 лучших прогноза (с исходом) + экспрессы
- VIP канал: 5-6 прогнозов БЕЗ исхода (замаскированы) + призыв купить
- Все посты с кнопками букмекеров
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
        months = ["января", "февраля", "марта", "апреля", "мая", "июня",
                   "июля", "августа", "сентября", "октября", "ноября", "декабря"]
        return f"{dt.day} {months[dt.month - 1]}, {dt.hour:02d}:{dt.minute:02d}"
    except Exception:
        return date_str[:16].replace("T", " ") if date_str else "Дата не указана"


class RateLimiter:
    def __init__(self, max_requests: int = 20, period: float = 1.0):
        self.max_requests = max_requests
        self.period = period
        self.requests = []
        self.lock = asyncio.Lock()

    async def acquire(self):
        async with self.lock:
            now = asyncio.get_event_loop().time()
            self.requests = [t for t in self.requests if now - t < self.period]
            if len(self.requests) >= self.max_requests:
                sleep_time = self.period - (now - self.requests[0])
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                    now = asyncio.get_event_loop().time()
                    self.requests = [t for t in self.requests if now - t < self.period]
            self.requests.append(now)


def create_bookmakers_keyboard() -> "InlineKeyboardMarkup":
    """Клавиатура с 6 российскими букмекерами"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    bookmakers = [
        ("Лига Ставок", "https://www.ligastavok.ru"),
        ("Фонбет", "https://www.fonbet.ru"),
        ("1хСтавка", "https://1xstavka.ru"),
        ("Бетсити", "https://www.betsiti.ru"),
        ("Винлайн", "https://www.winline.ru"),
        ("Марафон", "https://www.marathonbet.ru"),
    ]

    buttons = []
    for i in range(0, len(bookmakers), 2):
        row = []
        for j in range(2):
            if i + j < len(bookmakers):
                name, url = bookmakers[i + j]
                row.append(InlineKeyboardButton(text=name, url=url))
        buttons.append(row)

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _create_buy_vip_keyboard() -> "InlineKeyboardMarkup":
    """Клавиатура с призывом купить VIP"""
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👑 Купить VIP-прогноз — 50₽", callback_data="buy_single")],
        [InlineKeyboardButton(text="📅 VIP-подписка — от 99₽/день", callback_data="vip_menu")],
    ])


class TelegramPublisher:
    _recently_published: deque = deque(maxlen=500)
    _recently_published_set: set = set()
    _rate_limiter = RateLimiter(max_requests=20, period=1.0)

    def __init__(self):
        self.channel_id = getattr(settings, 'CHANNEL_ID', None)
        self.vip_channel_id = getattr(settings, 'VIP_CHANNEL_ID', None)
        self.bot = None

        token_obj = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        token = token_obj.get_secret_value() if token_obj else ""

        if token and ":" in token and len(token) > 20:
            try:
                self.bot = Bot(token=token, default=DefaultBotProperties(parse_mode="HTML"))
                logger.info("✅ Telegram Bot инициализирован")
            except Exception as e:
                logger.error(f"❌ Ошибка инициализации: {e}")

        logger.info(f"📢 Канал: {self.channel_id or '❌'}")
        logger.info(f"💎 VIP: {self.vip_channel_id or '❌'}")

    def _is_duplicate(self, home: str, away: str, date_ru: str) -> bool:
        match_key = f"{home}_{away}_{date_ru}"
        if match_key in self._recently_published_set:
            return True
        if len(self._recently_published) == self._recently_published.maxlen:
            old = self._recently_published[0]
            self._recently_published_set.discard(old)
        self._recently_published.append(match_key)
        self._recently_published_set.add(match_key)
        return False

    def _get_match_fields(self, prediction: dict):
        """Извлекает общие поля матча"""
        match = prediction.get("match", {})
        sport = match.get("sport", "⚽ Футбол")
        home = to_russian_name(match.get("home_team", "Команда 1"))
        away = to_russian_name(match.get("away_team", "Команда 2"))
        pred = prediction.get("prediction", "П1")
        date_ru = format_datetime_ru(match.get("date", ""))
        conf = prediction.get("confidence", 0.5)
        odds = prediction.get("odds_est", 2.0)
        league = match.get("league", "")
        return match, sport, home, away, pred, date_ru, conf, odds, league

    async def _send(self, chat_id: str, text: str, keyboard=None):
        """Отправка с rate limiting"""
        await self._rate_limiter.acquire()
        await self.bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

    # ═══════════════════════════════════════════════════════
    # ОБЫЧНЫЙ КАНАЛ: 1-2 лучших прогноза С исходом
    # ═══════════════════════════════════════════════════════
    async def publish_to_channel(self, prediction: dict) -> bool:
        """Публикует прогноз в обычный канал (с исходом и кнопками букмекеров)"""
        if not self.bot or not self.channel_id:
            return False

        match, sport, home, away, pred, date_ru, conf, odds, league = self._get_match_fields(prediction)

        supported = ["футбол", "football", "soccer", "cs", "dota", "lol", "valorant", "кибер", "esport"]
        if not any(s in sport.lower() for s in supported):
            return False

        if self._is_duplicate(home, away, date_ru):
            return False

        # Value bet метка
        value_badge = ""
        outcome_data = prediction.get("outcome", {})
        if outcome_data.get("is_value_bet"):
            value_badge = f"\n🔥 Value Bet: {outcome_data.get('value', 0):+.1%}\n"

        text = (
            f"🎯 <b>ТОП ПРОГНОЗ</b>\n\n"
            f"{sport} | <i>{league}</i>\n\n"
            f"🏟 <b>{home}</b> vs <b>{away}</b>\n"
            f"📅 {date_ru}\n\n"
            f"🔮 <b>Исход:</b> <b>{pred}</b>\n"
            f"📊 Уверенность: <b>{conf:.0%}</b>\n"
            f"💰 Коэффициент: <b>{odds:.2f}</b>"
            f"{value_badge}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎰 <b>Ставь у букмекера:</b>"
        )

        try:
            await self._send(self.channel_id, text, create_bookmakers_keyboard())
            logger.info(f"📢 Канал: {home} vs {away} — {pred}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка публикации в канал: {e}")
            return False

    # ═══════════════════════════════════════════════════════
    # VIP КАНАЛ: 5-6 прогнозов БЕЗ исхода (замаскированы)
    # ═══════════════════════════════════════════════════════
    async def publish_to_vip(self, prediction: dict) -> bool:
        """Публикует замаскированный прогноз в VIP-канал (без исхода, с призывом купить)"""
        if not self.bot or not self.vip_channel_id:
            return False

        match, sport, home, away, pred, date_ru, conf, odds, league = self._get_match_fields(prediction)

        supported = ["футбол", "football", "soccer", "cs", "dota", "lol", "valorant", "кибер", "esport"]
        if not any(s in sport.lower() for s in supported):
            return False

        if self._is_duplicate(home, away, date_ru):
            return False

        text = (
            f"🔒 <b>VIP-ПРОГНОЗ</b>\n\n"
            f"{sport} | <i>{league}</i>\n\n"
            f"🏟 <b>{home}</b> vs <b>{away}</b>\n"
            f"📅 {date_ru}\n\n"
            f"🎯 <b>Исход:</b> ❓❓❓\n"
            f"📊 Уверенность: <b>{conf:.0%}</b>\n"
            f"💰 Коэффициент: <b>{odds:.2f}</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔐 <i>Прогноз скрыт. Купите доступ!</i>"
        )

        try:
            await self._send(self.vip_channel_id, text, _create_buy_vip_keyboard())
            logger.info(f"💎 VIP: {home} vs {away} — замаскирован")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка публикации в VIP: {e}")
            return False

    # ═══════════════════════════════════════════════════════
    # ЭКСПРЕСС: в ОБА канала одновременно
    # ═══════════════════════════════════════════════════════
    async def publish_express_to_both(self, express_events: list, total_odds: float, label: str) -> bool:
        """Публикует экспресс в оба канала"""
        if not self.bot:
            return False

        events_text = ""
        for i, ev in enumerate(express_events, 1):
            home = to_russian_name(ev.get("home_team", "?"))
            away = to_russian_name(ev.get("away_team", "?"))
            pred = ev.get("prediction", "?")
            odds = ev.get("odds", 2.0)
            date_ru = format_datetime_ru(ev.get("date", ""))
            sport = ev.get("sport", "⚽")
            league = ev.get("league", "")
            events_text += (
                f"<b>{i}.</b> {sport} | <i>{league}</i>\n"
                f"🏟 <b>{home}</b> — <b>{away}</b>\n"
                f"📅 {date_ru}\n"
                f"🎯 Исход: <b>{pred}</b> | Коэф: <b>{odds:.2f}</b>\n\n"
            )

        text = (
            f"🔥 <b>{label}</b>\n\n"
            f"{events_text}"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📈 <b>Общий коэффициент:</b> {total_odds:.2f}\n\n"
            f"🎰 <b>Ставь у букмекера:</b>"
        )

        keyboard = create_bookmakers_keyboard()
        sent = False

        # В обычный канал
        if self.channel_id:
            try:
                await self._send(self.channel_id, text, keyboard)
                sent = True
            except Exception as e:
                logger.error(f"❌ Ошибка экспресса в канал: {e}")

        # В VIP канал
        if self.vip_channel_id:
            try:
                await self._send(self.vip_channel_id, text, keyboard)
                sent = True
            except Exception as e:
                logger.error(f"❌ Ошибка экспресса в VIP: {e}")

        if sent:
            logger.info(f"🔥 Экспресс опубликован в оба канала: {label}")
        return sent

    # ═══════════════════════════════════════════════════════
    # РАСКРЫТИЕ ПРОГНОЗА (после оплаты)
    # ═══════════════════════════════════════════════════════
    async def publish_revealed(self, chat_id: str, prediction: dict) -> bool:
        """Отправляет раскрытый прогноз конкретному пользователю"""
        if not self.bot:
            return False

        match, sport, home, away, pred, date_ru, conf, odds, league = self._get_match_fields(prediction)

        text = (
            f"✅ <b>ПРОГНОЗ РАСКРЫТ!</b>\n\n"
            f"{sport} | <i>{league}</i>\n\n"
            f"🏟 <b>{home}</b> vs <b>{away}</b>\n"
            f"📅 {date_ru}\n\n"
            f"🔮 <b>Исход:</b> <b>{pred}</b>\n"
            f"📊 Уверенность: <b>{conf:.0%}</b>\n"
            f"💰 Коэффициент: <b>{odds:.2f}</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎰 <b>Ставь у букмекера:</b>"
        )

        try:
            await self._send(chat_id, text, create_bookmakers_keyboard())
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка отправки раскрытого прогноза: {e}")
            return False

    async def close(self):
        if self.bot:
            await self.bot.session.close()
