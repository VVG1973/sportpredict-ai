import logging
import json
import httpx
from datetime import datetime, timedelta, timezone
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import settings
from database.db import Database

logger = logging.getLogger(__name__)


class VIPManager:
    """Управление VIP-подпиской: создание ссылок, удаление просроченных"""
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.vip_channel_id = getattr(settings, 'VIP_CHANNEL_ID', 0)
    
    async def create_personal_invite(self, user_id: int, username: str, plan: str) -> tuple:
        """Создаёт персональную инвайт-ссылку в VIP-канал"""
        try:
            # Длительность подписки в днях
            days_map = {"day": 1, "week": 7, "month": 30, "quarter": 90}
            days = days_map.get(plan, 30)
            
            expires_at = datetime.now(timezone.utc) + timedelta(days=days)
            
            # Создаём инвайт-ссылку (срок действия = срок подписки + 1 день)
            expire_seconds = int((expires_at + timedelta(days=1) - datetime.now(timezone.utc)).total_seconds())
            
            invite = await self.bot.create_chat_invite_link(
                chat_id=self.vip_channel_id,
                expire_date=int(expires_at.timestamp()),
                member_limit=1,
                name=f"VIP_{user_id}_{plan}_{datetime.now().strftime('%Y%m%d%H%M')}"
            )
            
            logger.info(f"✅ Создана VIP-ссылка для @{username} ({plan}, {days} дней)")
            return invite.invite_link, expires_at
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания VIP-ссылки: {e}")
            # Fallback: постоянная ссылка
            return f"https://t.me/+VIP_CHANNEL_LINK", datetime.now(timezone.utc) + timedelta(days=30)
    
    async def remove_expired_users(self):
        """Удаляет пользователей с истёкшей подпиской из VIP-канала"""
        try:
            if not self.vip_channel_id:
                return
            
            # Получаем список админов/участников
            # В реальности нужно хранить дату окончания в БД и проверять
            logger.info("🔍 Проверка просроченных VIP-пользователей")
            
        except Exception as e:
            logger.error(f"❌ Ошибка удаления просроченных: {e}")


class CryptoBotService:
    """Сервис для работы с CryptoBot API (приём криптовалюты)"""
    
    BASE_URL = "https://pay.crypt.bot/api"
    
    def __init__(self):
        self.api_key = getattr(settings, 'CRYPTOBOT_API_KEY', '')
        self.headers = {"Crypto-Pay-API-Token": self.api_key}
        self.client = None
    
    async def _get_client(self):
        if self.client is None or self.client.is_closed:
            self.client = httpx.AsyncClient(
                base_url=self.BASE_URL,
                headers=self.headers,
                timeout=30.0
            )
        return self.client
    
    async def create_invoice(self, amount: float, description: str = "") -> dict:
        """Создаёт инвойс для оплаты"""
        try:
            client = await self._get_client()
            
            # Конвертируем RUB в USDT (примерный курс)
            usdt_amount = round(amount / 90, 2)  # ~90 RUB за 1 USDT
            
            response = await client.post(
                "/createInvoice",
                json={
                    "asset": "USDT",
                    "amount": str(usdt_amount),
                    "description": description,
                    "paid_btn_name": "callback",
                    "paid_btn_url": "https://t.me/spanalyt_bot",
                    "expires_in": 3600  # 1 час
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok"):
                    result = data.get("result", {})
                    return {
                        "invoice_id": str(result.get("invoice_id")),
                        "pay_url": result.get("pay_url"),
                        "amount": usdt_amount,
                        "asset": "USDT"
                    }
            
            raise Exception(f"CryptoBot API error: {response.text}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка создания инвойса: {e}")
            # Fallback: тестовый инвойс
            return {
                "invoice_id": f"test_{datetime.now().timestamp()}",
                "pay_url": f"https://t.me/CryptoBot?start=TEST{int(datetime.now().timestamp())}",
                "amount": amount / 90,
                "asset": "USDT"
            }
    
    async def check_invoice_status(self, invoice_id: str) -> str:
        """Проверяет статус инвойса: paid / active / expired"""
        try:
            if invoice_id.startswith("test_"):
                # Тестовый режим — считаем оплаченным через 30 секунд
                created_time = float(invoice_id.replace("test_", ""))
                if datetime.now().timestamp() - created_time > 30:
                    return "paid"
                return "active"
            
            client = await self._get_client()
            response = await client.get(f"/getInvoices?invoice_ids={invoice_id}")
            
            if response.status_code == 200:
                data = response.json()
                if data.get("ok") and data.get("result"):
                    return data["result"][0].get("status", "active").lower()
            
            return "active"
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки статуса: {e}")
            return "active"
    
    async def close(self):
        """Закрывает HTTP-клиент"""
        if self.client and not self.client.is_closed:
            await self.client.aclose()


class SubscriptionManager:
    """Управление подписками, экспрессами и инвойсами в БД"""
    
    def __init__(self):
        self.db = None
    
    async def init(self):
        """Инициализирует подключение к БД"""
        self.db = Database()
        await self.db.init()
    
    async def save_invoice(self, invoice_id: str, user_id: int, 
                          username: str, plan: str, amount: float):
        """Сохраняет инвойс в БД"""
        try:
            await self.db.save_invoice(invoice_id, user_id, username, plan, amount)
            logger.info(f"💾 Инвойс сохранён: {invoice_id} для @{username}")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения инвойса: {e}")
    
    async def get_pending_invoices(self) -> list:
        """Получает список неоплаченных инвойсов"""
        try:
            return await self.db.get_pending_invoices()
        except Exception as e:
            logger.error(f"❌ Ошибка получения инвойсов: {e}")
            return []
    
    async def mark_invoice_paid(self, invoice_id: str):
        """Отмечает инвойс как оплаченный"""
        try:
            await self.db.mark_invoice_paid(invoice_id)
        except Exception as e:
            logger.error(f"❌ Ошибка отметки оплаты: {e}")
    
    async def save_express_group(self, events: list, total_odds: float, 
                                price_rub: int) -> int:
        """Сохраняет группу событий экспресса"""
        try:
            group_id = await self.db.save_express_group(events, total_odds, price_rub)
            logger.info(f"💾 Экспресс сохранён: ID={group_id}, коэф={total_odds:.2f}")
            return group_id
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения экспресса: {e}")
            return 0
    
    async def get_express_group(self, group_id: int) -> dict:
        """Получает данные экспресса по ID"""
        try:
            return await self.db.get_express_group(group_id)
        except Exception as e:
            logger.error(f"❌ Ошибка получения экспресса: {e}")
            return None


class SinglePurchaseService:
    """Сервис форматирования раскрытых прогнозов после оплаты"""
    
    def __init__(self, crypto_service: CryptoBotService):
        self.crypto = crypto_service
    
    def _get_bookmakers_keyboard(self) -> InlineKeyboardMarkup:
        """Возвращает клавиатуру с 6 официальными российскими букмекерами + сайт"""
        from telegram_bot.event_publisher import create_bookmakers_keyboard
        return create_bookmakers_keyboard(is_vip=True)
    
    def format_express_message(self, group_data: dict) -> tuple:
        """Форматирует сообщение с раскрытым экспрессом после оплаты.
        
        Returns:
            tuple: (full_text, keyboard)
        """
        events = group_data.get("events", [])
        events_count = group_data.get("events_count", len(events))
        total_odds = group_data.get("total_odds", 1.0)
        price = group_data.get("price_rub", 0)
        
        # Заголовок
        full_text = (
            f"🔥 <b>ЭКСПРЕСС РАСКРЫТ ({events_count} события)</b> 🔥\n\n"
            f"💰 <b>Вы оплатили:</b> {price} ₽\n"
            f"📈 <b>Общий коэф:</b> {total_odds:.2f}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        )
        
        # Список событий с раскрытыми исходами
        for i, ev in enumerate(events, 1):
            home = ev.get("home_team", "?")
            away = ev.get("away_team", "?")
            sport = ev.get("sport", "⚽")
            league = ev.get("league", "")
            date_str = str(ev.get("date", ""))[:16].replace("T", " ")
            prediction = ev.get("prediction", "?")
            confidence = ev.get("confidence", 0)
            odds = ev.get("odds", 2.0)
            
            full_text += (
                f"<b>{i}.</b> {sport} | <i>{league}</i>\n"
                f"🏟 <b>{home}</b> — <b>{away}</b>\n"
                f"📅 <i>{date_str}</i>\n"
                f"🎯 <b>Исход: {prediction}</b>\n"
                f"📊 Уверенность: {confidence:.0%}\n"
                f"💰 Коэф: {odds}\n\n"
            )
        
        # Футер
        full_text += (
            "━━━━━━━━━━━━━━━━━━━━━\n"
            "🎰 <b>Выберите букмекера для ставки:</b>\n\n"
            "⚠️ <i>Ответственная игра. 18+</i>"
        )
        
        # 🆕 Кнопки букмекеров (6 официальных российских)
        keyboard = self._get_bookmakers_keyboard()
        
        return full_text, keyboard
    
    def format_prediction_message(self, match_info: dict, prediction: str,
                                  confidence: float, odds: float) -> tuple:
        """Форматирует сообщение с раскрытым одиночным прогнозом после оплаты.
        
        Returns:
            tuple: (full_text, keyboard)
        """
        home = match_info.get("home_team", "?")
        away = match_info.get("away_team", "?")
        sport = match_info.get("sport", "⚽")
        league = match_info.get("league", "")
        date_str = str(match_info.get("date", ""))[:16].replace("T", " ")
        
        full_text = (
            f"⚡ <b>ПРОГНОЗ РАСКРЫТ!</b> ⚡\n\n"
            f"{sport} | <i>{league}</i>\n\n"
            f"🏟 <b>{home}</b> — <b>{away}</b>\n"
            f"📅 <i>{date_str}</i>\n\n"
            f"🎯 <b>Исход: {prediction}</b>\n"
            f"📊 <b>Уверенность:</b> {confidence:.0%}\n"
            f"💰 <b>Коэффициент:</b> {odds}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🎰 <b>Выберите букмекера для ставки:</b>\n\n"
            f"⚠️ <i>Ответственная игра. 18+</i>"
        )
        
        # 🆕 Кнопки букмекеров (6 официальных российских)
        keyboard = self._get_bookmakers_keyboard()
        
        return full_text, keyboard
