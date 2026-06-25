import logging
from datetime import datetime, timezone, timedelta
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from config import settings

logger = logging.getLogger(__name__)

TEAMS_RU = {
    "Manchester City": "Манчестер Сити", "Arsenal": "Арсенал",
    "Liverpool": "Ливерпуль", "Manchester United": "Манчестер Юнайтед",
    "Tottenham": "Тоттенхэм", "Chelsea": "Челси", "Newcastle": "Ньюкасл",
    "Real Madrid": "Реал Мадрид", "Barcelona": "Барселона",
    "Atletico Madrid": "Атлетико Мадрид", "Bayern Munich": "Бавария",
    "Borussia Dortmund": "Боруссия Дортмунд", "PSG": "ПСЖ",
    "Inter Milan": "Интер", "AC Milan": "Милан", "Juventus": "Ювентус",
    "Зенит": "Зенит", "Спартак": "Спартак", "ЦСКА": "ЦСКА",
    "Djokovic": "Джокович", "Alcaraz": "Алькарас", "Sinner": "Синнер",
    "Medvedev": "Медведев", "Swiatek": "Швёнтек", "Sabalenka": "Соболенко",
    "Lakers": "Лейкерс", "Warriors": "Уорриорз", "Celtics": "Селтикс",
    "Oilers": "Эдмонтон", "Panthers": "Флорида", "ЦСКА М": "ЦСКА Москва",
    "Valencia": "Валенсия", "Napoli": "Наполи", "Milan": "Милан",
    "Bayer Leverkusen": "Байер Леверкузен", "RB Leipzig": "РБ Лейпциг",
    "NAVI": "NAVI", "FaZe": "FaZe Clan", "G2": "G2 Esports",
    "Vitality": "Team Vitality", "Spirit": "Team Spirit",
    "MOUZ": "MOUZ", "Heroic": "Heroic", "Astralis": "Astralis",
    "Liquid": "Team Liquid", "Complexity": "Complexity",
    "Virtus.pro": "Virtus.pro", "Cloud9": "Cloud9",
    "Team Spirit": "Team Spirit", "Gaimin Gladiators": "Gaimin Gladiators",
    "Tundra": "Tundra Esports", "Team Liquid": "Team Liquid",
    "BetBoom Team": "BetBoom Team", "Xtreme Gaming": "Xtreme Gaming",
    "Falcons": "Team Falcons", "OG": "OG", "PSG.LGD": "PSG.LGD",
    "Jon Jones": "Джон Джонс", "Islam Makhachev": "Ислам Махачев",
    "Alex Pereira": "Алекс Перейра", "Ilia Topuria": "Илия Топурия",
    "Khamzat Chimaev": "Хамзат Чимаев", "Sean O'Malley": "Шон О'Мэлли",
    "Dustin Poirier": "Дастин Порье"
}

MONTHS_RU = {
    1: "января", 2: "февраля", 3: "марта", 4: "апреля",
    5: "мая", 6: "июня", 7: "июля", 8: "августа",
    9: "сентября", 10: "октября", 11: "ноября", 12: "декабря"
}

BOOKMAKERS = [
    {"name": "🔥 Fonbet", "url": "https://fonbet.ru/"},
    {"name": "🎯 Winline", "url": "https://winline.ru/"},
    {"name": "⚡ Pari", "url": "https://pari.ru/"},
    {"name": "🏆 BetBoom", "url": "https://betboom.ru/"},
    {"name": "⭐ Liga Stavok", "url": "https://ligastavok.ru/"},
    {"name": "🎲 Leon", "url": "https://leon.ru/"},
]

def to_russian_name(name: str) -> str:
    return TEAMS_RU.get(name, name)

def format_datetime_ru(iso_date: str) -> str:
    try:
        clean = iso_date.split(".")[0]
        dt = datetime.fromisoformat(clean.replace("Z", "+00:00"))
        msk = timezone(timedelta(hours=3))
        dt_msk = dt.astimezone(msk)
        return f"{dt_msk.day} {MONTHS_RU.get(dt_msk.month, '')}, {dt_msk.strftime('%H:%M')} (МСК)"
    except Exception:
        return iso_date

def create_bookmakers_keyboard(is_vip: bool = False) -> InlineKeyboardMarkup:
    """Создаёт клавиатуру с 6 официальными российскими букмекерами.
    
    Обычный канал: 6 букмекеров + кнопка "Купить VIP"
    VIP-канал: те же 6 букмекеров + кнопка "Наш сайт"
    """
    buttons = []
    
    # === Первая строка (3 букмекера) ===
    buttons.append([
        InlineKeyboardButton(text=BOOKMAKERS[0]["name"], url=BOOKMAKERS[0]["url"]),
        InlineKeyboardButton(text=BOOKMAKERS[1]["name"], url=BOOKMAKERS[1]["url"]),
        InlineKeyboardButton(text=BOOKMAKERS[2]["name"], url=BOOKMAKERS[2]["url"]),
    ])
    
    # === Вторая строка (3 букмекера) ===
    buttons.append([
        InlineKeyboardButton(text=BOOKMAKERS[3]["name"], url=BOOKMAKERS[3]["url"]),
        InlineKeyboardButton(text=BOOKMAKERS[4]["name"], url=BOOKMAKERS[4]["url"]),
        InlineKeyboardButton(text=BOOKMAKERS[5]["name"], url=BOOKMAKERS[5]["url"]),
    ])
    
    # === Третья строка (зависит от канала) ===
    if is_vip:
        # VIP-канал: кнопка на сайт со статистикой
        buttons.append([
            InlineKeyboardButton(text="🌐 Наш сайт со статистикой", url="https://sportpredict-ai-production.up.railway.app")
        ])
    else:
        # Обычный канал: кнопка на покупку VIP
        buttons.append([
            InlineKeyboardButton(text="👑 VIP-прогнозы", url="https://t.me/spanalyt_bot?start=vip")
        ])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)


class TelegramPublisher:
    def __init__(self):
        self.bot = Bot(
            token=settings.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode="HTML")
        )
        self.channel_id = settings.CHANNEL_ID
        self.vip_channel_id = getattr(settings, 'VIP_CHANNEL_ID', 0)
        logger.info("🌐 Бот инициализирован (прямое подключение)")

    async def publish(self, prediction: dict, is_vip: bool = False, is_single_purchase: bool = False):
        match = prediction.get("match", {})
        sport = match.get("sport", "⚽ Футбол")
        league = match.get("league", "")
        home = to_russian_name(match.get("home_team", "Команда 1"))
        away = to_russian_name(match.get("away_team", "Команда 2"))
        pred = prediction.get("prediction", "П1")
        date_ru = format_datetime_ru(match.get("date", ""))
        conf = prediction.get("confidence", 0.5)
        odds = prediction.get("odds_est", 2.0)
        fixture_id = match.get("fixture_id", 0)
        
        vip_badge = "👑 <b>VIP-ПРОГНОЗ</b>\n\n" if is_vip else ""
        
        if is_vip and self.vip_channel_id:
            target_channel = self.vip_channel_id
        else:
            target_channel = self.channel_id

        if is_single_purchase:
            from telegram_bot.vip_manager import SubscriptionManager
            manager = SubscriptionManager()
            await manager.init()
            
            events = [{
                "fixture_id": fixture_id,
                "home_team": match.get("home_team", ""),
                "away_team": match.get("away_team", ""),
                "date": match.get("date", ""),
                "sport": sport,
                "league": league,
                "prediction": pred,
                "confidence": conf,
                "odds": odds
            }]
            group_id = await manager.save_express_group(events, odds, 99)
            
            text = (
                f"🔥 <b>ПРОГНОЗ AI (платный)</b> 🔥\n\n"
                f"{sport} | <i>{league}</i>\n\n"
                f"🏟 <b>{home}</b> — <b>{away}</b>\n"
                f"📅 <i>{date_ru}</i>\n\n"
                f"🎯 <b>Исход:</b> <i>🔒 Скрыто</i>\n"
                f"📊 <b>Уверенность AI:</b> {conf:.0%}\n"
                f"💰 <b>Коэффициент:</b> {odds}\n\n"
                f"💳 <b>Цена:</b> 99 ₽\n"
                f"<i>Нажмите кнопку ниже, чтобы открыть прогноз.</i>"
            )
            
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(
                    text=f"🔥 Купить за 99₽", 
                    callback_data=f"buy:single:{group_id}"
                )]
            ])
        else:
            text = (
                f"{vip_badge}"
                f"{sport} <b>ПРОГНОЗ AI</b>\n"
                f"🏆 <i>{league}</i>\n\n"
                f"🏟 <b>{home}</b> — <b>{away}</b>\n"
                f"📅 <i>{date_ru}</i>\n\n"
                f"🎯 <b>Исход:</b> {pred}\n"
                f"📊 <b>Уверенность:</b> {conf:.0%}\n"
                f"💰 <b>Коэф:</b> {odds}\n\n"
                f"🎰 <b>Где поставить:</b>"
            )
            keyboard = create_bookmakers_keyboard(is_vip=is_vip)

        disclaimer = (
            "\n\n━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ <i>Дисклеймер: Прогнозы носят информационный характер. "
            "Ответственная игра. 18+</i>"
        )
        text += disclaimer
        
        try:
            await self.bot.send_message(chat_id=target_channel, text=text, reply_markup=keyboard)
            logger.info(f"✅ {'[PAID] ' if is_single_purchase else ''}{sport} прогноз: {home} vs {away}")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка публикации: {e}")
            return False
    
    async def publish_express(self, events: list, group_id: int, price_rub: int):
        target_channel = self.channel_id
        events_count = len(events)
        
        total_odds = 1.0
        for ev in events:
            total_odds *= ev.get("odds_est", 1.5)
        
        events_text = ""
        for i, ev in enumerate(events, 1):
            match = ev.get("match", {})
            home = to_russian_name(match.get("home_team", "Команда 1"))
            away = to_russian_name(match.get("away_team", "Команда 2"))
            date_ru = format_datetime_ru(match.get("date", ""))
            sport = match.get("sport", "⚽")
            league = match.get("league", "")
            
            events_text += (
                f"<b>{i}.</b> {sport} | <i>{league}</i>\n"
                f"🏟 <b>{home}</b> — <b>{away}</b>\n"
                f"📅 <i>{date_ru}</i>\n"
                f"🎯 <b>Исход:</b> <i>🔒 Скрыто</i>\n"
                f"📊 <b>Уверенность AI:</b> {ev.get('confidence', 0):.0%}\n\n"
            )
        
        text = (
            f"🔥 <b>ЭКСПРЕСС ДНЯ ({events_count} события)</b> 🔥\n\n"
            f"{events_text}"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 <b>Общий коэф:</b> ~{total_odds:.2f}\n"
            f"💳 <b>Цена экспресса:</b> {price_rub} ₽\n\n"
            f"<i>Все исходы откроются после оплаты.</i>"
        )
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(
                text=f"🔥 Купить экспресс за {price_rub}₽", 
                callback_data=f"buy:expr:{group_id}:{events_count}"
            )]
        ])
        
        disclaimer = (
            "\n\n━━━━━━━━━━━━━━━━━━━━━\n"
            "⚠️ <i>Дисклеймер: Прогнозы носят информационный характер. "
            "Ответственная игра. 18+</i>"
        )
        text += disclaimer
        
        try:
            await self.bot.send_message(chat_id=target_channel, text=text, reply_markup=keyboard)
            logger.info(f"✅ [EXPRESS x{events_count}] опубликован, коэф {total_odds:.2f}, цена {price_rub}₽")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка публикации экспресса: {e}")
            return False

    async def close(self):
        await self.bot.session.close()
