"""
Публикатор прогнозов в Telegram каналы
"""
import logging
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from config import settings
from utils.formatters import to_russian_name, format_datetime_ru

logger = logging.getLogger(__name__)


class TelegramPublisher:
    def __init__(self):
        """Инициализация бота и каналов"""
        self.bot = Bot(
            token=settings.TELEGRAM_BOT_TOKEN,
            default=DefaultBotProperties(parse_mode="HTML")
        )
        self.channel_id = settings.CHANNEL_ID
        self.vip_channel_id = getattr(settings, 'VIP_CHANNEL_ID', None)
        
        logger.info(f"📢 Обычный канал: {self.channel_id}")
        logger.info(f"💎 VIP канал: {self.vip_channel_id}")
        
        if not self.vip_channel_id:
            logger.warning("⚠️ VIP_CHANNEL_ID не настроен! VIP прогнозы будут идти в обычный канал.")
    
    async def publish(self, prediction: dict, is_vip: bool = False, is_single_purchase: bool = False):
        """Публикует прогноз в канал"""
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
        
        # Формируем текст прогноза
        vip_badge = "👑 <b>VIP-ПРОГНОЗ</b>\n\n" if is_vip else ""
        
        text = (
            f"{vip_badge}"
            f"{sport} | {league}\n\n"
            f"🏟 <b>{home}</b> vs <b>{away}</b>\n"
            f"📅 {date_ru}\n\n"
            f"🎯 <b>Прогноз:</b> {pred}\n"
            f"📊 Уверенность: {conf:.0%}\n"
            f"💰 Коэффициент: {odds:.2f}\n\n"
            f"━━━━━━━━━━━━━━━━━━━━━\n"
            f"🤖 <i>SportPredict AI</i>"
        )
        
        # Определяем целевой канал
        if is_vip and self.vip_channel_id:
            target_channel = self.vip_channel_id
            logger.info(f"💎 Публикую VIP прогноз в канал {target_channel}: {home} vs {away}")
        else:
            target_channel = self.channel_id
            if is_vip:
                logger.warning(f"⚠️ VIP прогноз {home} vs {away} идёт в обычный канал (VIP канал не настроен)")
            else:
                logger.info(f"📢 Публикую обычный прогноз в канал {target_channel}: {home} vs {away}")
        
        try:
            await self.bot.send_message(
                chat_id=target_channel,
                text=text,
                parse_mode="HTML",
                disable_web_page_preview=True
            )
            logger.info(f"✅ Прогноз опубликован: {home} vs {away}")
        except Exception as e:
            logger.error(f"❌ Ошибка публикации в канал {target_channel}: {e}")
            # Fallback: если не удалось в VIP, пробуем в обычный
            if is_vip and target_channel != self.channel_id:
                try:
                    await self.bot.send_message(
                        chat_id=self.channel_id,
                        text=text,
                        parse_mode="HTML",
                        disable_web_page_preview=True
                    )
                    logger.info(f"✅ VIP прогноз опубликован в обычный канал (fallback): {home} vs {away}")
                except Exception as e2:
                    logger.error(f"❌ Ошибка fallback публикации: {e2}")
    
    async def close(self):
        """Закрывает сессию бота"""
        await self.bot.session.close()
