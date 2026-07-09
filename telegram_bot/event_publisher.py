"""
Публикатор прогнозов в Telegram каналы
- Обычный канал: 1 бесплатный прогноз + AI-комментарий + кнопка купить за 50₽
- VIP канал: 5 бесплатных прогнозов + AI-комментарий + кнопка купить за 50₽
- Экспрессы: на других матчах + AI-комментарий (199₽/299₽)
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

SUPPORTED_SPORTS = [
    "футбол", "football", "soccer",
    "хоккей", "hockey", "nhl", "кхл",
    "теннис", "tennis", "atp", "wta",
    "cs", "dota", "lol", "valorant", "кибер", "esport",
]

SPORT_EMOJI = {
    "футбол": "⚽", "football": "⚽", "soccer": "⚽",
    "хоккей": "🏒", "hockey": "🏒", "nhl": "🏒", "кхл": "🏒",
    "теннис": "🎾", "tennis": "🎾", "atp": "🎾", "wta": "🎾",
    "cs": "🎮", "dota": "🎮", "кибер": "🎮", "esport": "🎮",
}


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
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    bookmakers = [
        ("Fonbet", "https://www.fonbet.ru"),
        ("Winline", "https://www.winline.ru"),
        ("PARI", "https://pari.ru"),
        ("Лига Ставок", "https://www.ligastavok.ru"),
        ("OLIMPBET", "https://www.olimpbet.ru"),
        ("BetBoom", "https://betboom.ru"),
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
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💰 Купить прогноз — 50₽", callback_data="buy_single")],
        [InlineKeyboardButton(text="👑 VIP-подписка — от 99₽/день", callback_data="vip_menu")],
    ])


def _format_markets(prediction: dict) -> str:
    lines = []
    total = prediction.get("total", {})
    both = prediction.get("both_scored", {})
    handicap = prediction.get("handicap", {})

    if isinstance(total, dict) and total.get("prediction"):
        lines.append(f"⚽ Тотал: <b>{total['prediction']}</b>")
    elif isinstance(total, str) and total:
        lines.append(f"⚽ Тотал: <b>{total}</b>")

    if isinstance(both, dict) and both.get("prediction"):
        lines.append(f"🥅 Обе забьют: <b>{both['prediction']}</b>")
    elif isinstance(both, str) and both:
        lines.append(f"🥅 Обе забьют: <b>{both}</b>")

    if isinstance(handicap, dict) and handicap.get("prediction"):
        lines.append(f"📊 Фора: <b>{handicap['prediction']}</b>")
    elif isinstance(handicap, str) and handicap:
        lines.append(f"📊 Фора: <b>{handicap}</b>")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════
# AI-КОММЕНТАРИЙ К ПРОГНОЗУ
# ═══════════════════════════════════════════════════════
def generate_ai_commentary(prediction: dict) -> str:
    """Генерирует AI-комментарий к прогнозу на основе данных матча и модели"""
    match = prediction.get("match", {})
    pred = prediction.get("prediction", "П1")
    conf = prediction.get("confidence", 0.5)
    odds = prediction.get("odds_est", 2.0)
    home = to_russian_name(match.get("home_team", ""))
    away = to_russian_name(match.get("away_team", ""))
    sport = match.get("sport", "⚽ Футбол")

    # Анализ коэффициентов
    total_inv = 0
    home_prob = 0
    away_prob = 0
    if odds > 0:
        # Если есть полные коэффициенты
        home_odds = prediction.get("B365H", odds)
        away_odds = prediction.get("B365A", 2.0)
        if home_odds > 0 and away_odds > 0:
            total_inv = (1/home_odds) + (1/away_odds) + (1/3.0)  # Примерная ничья
            home_prob = (1/home_odds) / total_inv if total_inv > 0 else 0.4
            away_prob = (1/away_odds) / total_inv if total_inv > 0 else 0.4

    # Генерируем комментарий
    comments = []

    # Анализ фаворита
    if pred in ["П1", "H"]:
        if home_prob > 0.55:
            comments.append(f"📊 {home} — явный фаворит (вероятность победы {home_prob:.0%})")
        elif home_prob > 0.45:
            comments.append(f"📊 {home} имеет небольшое преимущество дома")
        else:
            comments.append(f"📊 Модель видит стоимость в ставке на {home}")

        # Фактор домашнего поля
        sport_lower = sport.lower()
        if any(s in sport_lower for s in ["футбол", "football", "хоккей", "hockey"]):
            comments.append("🏠 Фактор домашнего поля усиливает позицию")

    elif pred in ["П2", "A"]:
        if away_prob > 0.55:
            comments.append(f"📊 {away} — сильный гость (вероятность {away_prob:.0%})")
        else:
            comments.append(f"📊 Модель видит потенциал в {away}")

    # Анализ коэффициентов
    if odds > 2.5:
        comments.append(f"💰 Высокий коэффициент ({odds:.2f}) — хорошее соотношение риск/прибыль")
    elif odds < 1.5:
        comments.append(f"💰 Низкий коэффициент ({odds:.2f}) — высокая уверенность")

    # Уверенность
    if conf > 0.75:
        comments.append(f"🎯 Высокая уверенность модели ({conf:.0%})")
    elif conf > 0.60:
        comments.append(f"🎯 Умеренная уверенность ({conf:.0%})")

    # Value bet
    outcome_data = prediction.get("outcome", {})
    if outcome_data.get("is_value_bet"):
        value_pct = outcome_data.get('value', 0)
        comments.append(f"🔥 Value Bet: модель оценивает шанс на {abs(value_pct):.0%} выше рынка")

    # Дополнительные рынки
    total_pred = prediction.get("total", {})
    if isinstance(total_pred, dict) and total_pred.get("prediction"):
        comments.append(f"⚽ Тотал: {total_pred['prediction']}")

    both_pred = prediction.get("both_scored", {})
    if isinstance(both_pred, dict) and both_pred.get("prediction"):
        comments.append(f"🥅 Обе забьют: {both_pred['prediction']}")

    if not comments:
        comments.append("🤖 Прогноз основан на статистическом анализе коэффициентов и исторических данных")

    return "\n".join(comments[:4])  # Максимум 4 строки


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

    def _is_supported(self, sport: str) -> bool:
        return any(s in sport.lower() for s in SUPPORTED_SPORTS)

    def _get_match_fields(self, prediction: dict):
        match = prediction.get("match", {})
        sport = match.get("sport", "⚽ Футбол")
        home = to_russian_name(match.get("home_team", "Команда 1"))
        away = to_russian_name(match.get("away_team", "Команда 2"))
        pred = prediction.get("prediction", "П1")
        date_ru = format_datetime_ru(match.get("date", ""))
        conf = prediction.get("confidence", 0.5)
        odds = prediction.get("odds_est", 2.0)
        league = match.get("league", "")
        fixture_id = match.get("fixture_id", "")
        return match, sport, home, away, pred, date_ru, conf, odds, league, fixture_id

    async def _send(self, chat_id: str, text: str, keyboard=None):
        await self._rate_limiter.acquire()
        await self.bot.send_message(
            chat_id=chat_id, text=text, parse_mode="HTML",
            reply_markup=keyboard, disable_web_page_preview=True
        )

    # ═══════════════════════════════════════════════════════
    # ОБЫЧНЫЙ КАНАЛ: 1 бесплатный прогноз + AI-комментарий
    # + кнопка "Купить дополнительный за 50₽"
    # ═══════════════════════════════════════════════════════
    async def publish_to_channel(self, prediction: dict) -> bool:
        if not self.bot or not self.channel_id:
            return False

        match, sport, home, away, pred, date_ru, conf, odds, league, fixture_id = self._get_match_fields(prediction)

        if not self._is_supported(sport):
            return False
        if self._is_duplicate(home, away, date_ru):
            return False

        # AI-комментарий
        ai_commentary = generate_ai_commentary(prediction)
        if ai_commentary:
            ai_commentary = "\n" + ai_commentary + "\n"

        markets_text = _format_markets(prediction)
        if markets_text:
            markets_text = "\n" + markets_text + "\n"

        emoji = SPORT_EMOJI.get(sport.lower().split()[0], "⚽")

        text = (
            f"{emoji} <b>ПРОГНОЗ ДНЯ</b>\n\n"
            f"{sport} | <i>{league}</i>\n\n"
            f"🏟 <b>{home}</b> vs <b>{away}</b>\n"
            f"📅 {date_ru}\n\n"
            f"🔮 <b>Исход:</b> <b>{pred}</b>\n"
            f"📊 Уверенность: <b>{conf:.0%}</b>\n"
            f"💰 Коэффициент: <b>{odds:.2f}</b>"
            f"{markets_text}"
            f"{ai_commentary}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 <b>Купить ещё прогнозы — 50₽/шт</b>"
        )

        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 Купить прогноз — 50₽", callback_data="buy_single")],
        ])
        for row in create_bookmakers_keyboard().inline_keyboard:
            keyboard.inline_keyboard.append(row)

        try:
            await self._send(self.channel_id, text, keyboard)
            logger.info(f"📢 Канал: {home} vs {away} — {pred}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка публикации в канал: {e}")
            return False

    # ═══════════════════════════════════════════════════════
    # VIP КАНАЛ: 5 бесплатных прогнозов + AI-комментарий
    # + кнопка "Купить дополнительный за 50₽"
    # ═══════════════════════════════════════════════════════
    async def publish_to_vip(self, prediction: dict) -> bool:
        if not self.bot or not self.vip_channel_id:
            return False

        match, sport, home, away, pred, date_ru, conf, odds, league, fixture_id = self._get_match_fields(prediction)

        if not self._is_supported(sport):
            return False
        if self._is_duplicate(home, away, date_ru):
            return False

        # AI-комментарий
        ai_commentary = generate_ai_commentary(prediction)
        if ai_commentary:
            ai_commentary = "\n" + ai_commentary + "\n"

        # Показываем рынки как "скрытые"
        extra_hidden = []
        total = prediction.get("total", {})
        both = prediction.get("both_scored", {})
        handicap = prediction.get("handicap", {})

        if isinstance(total, dict) and total.get("prediction"):
            extra_hidden.append("⚽ Тотал: ❓")
        if isinstance(both, dict) and both.get("prediction"):
            extra_hidden.append("🥅 Обе забьют: ❓")
        if isinstance(handicap, dict) and handicap.get("prediction"):
            extra_hidden.append("📊 Фора: ❓")

        extra_text = ""
        if extra_hidden:
            extra_text = "\n" + "\n".join(extra_hidden) + "\n"

        emoji = SPORT_EMOJI.get(sport.lower().split()[0], "⚽")

        text = (
            f"🔒 <b>VIP-ПРОГНОЗ</b>\n\n"
            f"{emoji} {sport} | <i>{league}</i>\n\n"
            f"🏟 <b>{home}</b> vs <b>{away}</b>\n"
            f"📅 {date_ru}\n\n"
            f"🔮 <b>Исход:</b> ❓❓❓\n"
            f"📊 Уверенность: <b>{conf:.0%}</b>\n"
            f"💰 Коэффициент: <b>{odds:.2f}</b>"
            f"{extra_text}"
            f"{ai_commentary}\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 <b>Купить прогноз — 50₽</b>"
        )

        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 Купить прогноз — 50₽", callback_data=f"buy_single:{fixture_id}")],
        ])
        for row in create_bookmakers_keyboard().inline_keyboard:
            keyboard.inline_keyboard.append(row)

        try:
            await self._send(self.vip_channel_id, text, keyboard)
            logger.info(f"💎 VIP: {home} vs {away} — замаскирован")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка публикации в VIP: {e}")
            return False

    # ═══════════════════════════════════════════════════════
    # ЭКСПРЕСС: в ОБА канала + AI-комментарий
    # На ДРУГИХ матчах, чем в каналах
    # ═══════════════════════════════════════════════════════
    async def publish_express_to_both(self, express_events: list, total_odds: float, label: str) -> bool:
        if not self.bot:
            return False

        events_count = len(express_events)
        price = 199 if events_count <= 2 else 299

        events_text = ""
        ai_lines = []
        for i, ev in enumerate(express_events, 1):
            home = to_russian_name(ev.get("home_team", "?"))
            away = to_russian_name(ev.get("away_team", "?"))
            odds_val = ev.get("odds", 2.0)
            date_ru = format_datetime_ru(ev.get("date", ""))
            sport = ev.get("sport", "⚽")
            league = ev.get("league", "")
            emoji = SPORT_EMOJI.get(sport.lower().split()[0], "⚽")
            events_text += (
                f"<b>{i}.</b> {emoji} {sport} | <i>{league}</i>\n"
                f"🏟 <b>{home}</b> — <b>{away}</b>\n"
                f"📅 {date_ru}\n"
                f"💰 Коэф: <b>{odds_val:.2f}</b>\n\n"
            )
            # AI-комментарий для каждого события
            ai_lines.append(f"• {home} — {away}: коэф {odds_val:.2f}")

        ai_text = ""
        if ai_lines:
            ai_text = f"\n🤖 <i>Анализ:</i>\n" + "\n".join(ai_lines) + "\n"

        text = (
            f"🔥 <b>{label}</b>\n\n"
            f"{events_text}"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"📈 <b>Общий коэффициент:</b> {total_odds:.2f}\n"
            f"💰 <b>Цена:</b> {price}₽"
            f"{ai_text}\n"
            f"🔐 <i>Исходы скрыты. Купите экспресс!</i>"
        )

        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        buy_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"💰 Купить экспресс — {price}₽", callback_data=f"buy_express:{events_count}")],
        ])
        for row in create_bookmakers_keyboard().inline_keyboard:
            buy_kb.inline_keyboard.append(row)

        sent = False

        if self.channel_id:
            try:
                await self._send(self.channel_id, text, buy_kb)
                sent = True
            except Exception as e:
                logger.error(f"❌ Ошибка экспресса в канал: {e}")

        if self.vip_channel_id:
            try:
                await self._send(self.vip_channel_id, text, buy_kb)
                sent = True
            except Exception as e:
                logger.error(f"❌ Ошибка экспресса в VIP: {e}")

        if sent:
            logger.info(f"🔥 Экспресс: {label}")
        return sent

    # ═══════════════════════════════════════════════════════
    # РАСКРЫТИЕ ПРОГНОЗА (после оплаты)
    # ═══════════════════════════════════════════════════════
    async def publish_revealed(self, chat_id: str, prediction: dict) -> bool:
        if not self.bot:
            return False

        match, sport, home, away, pred, date_ru, conf, odds, league, _ = self._get_match_fields(prediction)
        markets_text = _format_markets(prediction)
        if markets_text:
            markets_text = "\n" + markets_text + "\n"

        ai_commentary = generate_ai_commentary(prediction)
        if ai_commentary:
            ai_commentary = "\n" + ai_commentary + "\n"

        emoji = SPORT_EMOJI.get(sport.lower().split()[0], "⚽")

        text = (
            f"✅ <b>ПРОГНОЗ РАСКРЫТ!</b>\n\n"
            f"{emoji} {sport} | <i>{league}</i>\n\n"
            f"🏟 <b>{home}</b> vs <b>{away}</b>\n"
            f"📅 {date_ru}\n\n"
            f"🔮 <b>Исход:</b> <b>{pred}</b>\n"
            f"📊 Уверенность: <b>{conf:.0%}</b>\n"
            f"💰 Коэффициент: <b>{odds:.2f}</b>"
            f"{markets_text}"
            f"{ai_commentary}\n"
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
