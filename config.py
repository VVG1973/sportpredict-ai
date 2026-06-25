"""
Конфигурация приложения
"""
from pydantic_settings import BaseSettings
from pydantic import Field
import logging

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """Настройки приложения (автоматически читаются из переменных окружения)"""
    
    # === TELEGRAM ===
    TELEGRAM_BOT_TOKEN: str = Field(default="", description="Токен Telegram бота")
    CHANNEL_ID: str = Field(default="", description="ID обычного канала для прогнозов")
    VIP_CHANNEL_ID: str = Field(default="", description="ID VIP канала для точных прогнозов")
    ADMIN_ID: int = Field(default=0, description="ID администратора")
    
    # === МОДЕЛЬ ===
    VIP_CONFIDENCE_THRESHOLD: float = Field(default=0.70, description="Порог уверенности для VIP прогнозов (70%)")
    MODEL_PATH: str = Field(default="data/models/model_real.pkl", description="Путь к модели")
    
    # === КРИПТО ОПЛАТА ===
    CRYPTO_BOT_TOKEN: str = Field(default="", description="Токен CryptoBot API")
    CRYPTO_PAY_API_KEY: str = Field(default="", description="API ключ CryptoPay")
    
    # === БАЗА ДАННЫХ ===
    DATABASE_URL: str = Field(default="data/predictions.db", description="Путь к БД")
    
    # === ЛОГИРОВАНИЕ ===
    LOG_LEVEL: str = Field(default="INFO", description="Уровень логирования")
    
    # === РАЗНОЕ ===
    DEBUG: bool = Field(default=False, description="Режим отладки")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Создаём глобальный объект настроек
try:
    settings = Settings()
    logger.info(f"✅ Конфигурация загружена:")
    logger.info(f"   - TELEGRAM_BOT_TOKEN: {'✅ установлен' if settings.TELEGRAM_BOT_TOKEN else '❌ ПУСТОЙ'}")
    logger.info(f"   - CHANNEL_ID: {settings.CHANNEL_ID}")
    logger.info(f"   - VIP_CHANNEL_ID: {settings.VIP_CHANNEL_ID or '❌ не настроен'}")
    logger.info(f"   - VIP_CONFIDENCE_THRESHOLD: {settings.VIP_CONFIDENCE_THRESHOLD:.0%}")
except Exception as e:
    logger.error(f"❌ Ошибка загрузки конфигурации: {e}")
    settings = Settings()
