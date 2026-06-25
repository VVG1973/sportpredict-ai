from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    BOT_TOKEN: str
    CHANNEL_ID: str
    ADMIN_ID: int = 0
    
    # VIP-канал и пороги
    VIP_CHANNEL_ID: int = 0
    CONFIDENCE_THRESHOLD: float = 0.75
    VIP_CONFIDENCE_THRESHOLD: float = 0.80
    
    # API и БД
    API_KEY_SPORTS: str = ""
    DATABASE_URL: str = "sqlite:///./sportpredict.db"
    
    # Расписание
    SCHEDULE_INTERVAL_MINUTES: int = 60
    LOG_LEVEL: str = "INFO"
    USE_MOCK_DATA: bool = True
    
    # CryptoBot
    CRYPTO_BOT_TOKEN: str = ""
    CRYPTO_BOT_NETWORK: str = "mainnet"

    class Config:
        env_file = Path(__file__).parent / ".env"
        env_file_encoding = "utf-8"

settings = Settings()
