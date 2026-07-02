"""
Тесты для config.py
"""
import pytest
from config import Settings


def test_settings_loads():
    """Проверяем, что настройки создаются без ошибок"""
    settings = Settings()
    assert settings is not None


def test_telegram_token_is_secret():
    """Проверяем, что токен — SecretStr (не строка)"""
    settings = Settings()
    # TELEGRAM_BOT_TOKEN должен быть SecretStr, даже если пустой
    token = settings.TELEGRAM_BOT_TOKEN
    # Проверяем, что у объекта есть метод get_secret_value
    assert hasattr(token, "get_secret_value")


def test_vip_threshold_in_range():
    """Проверяем, что порог VIP в допустимых пределах"""
    settings = Settings()
    assert 0.0 <= settings.VIP_CONFIDENCE_THRESHOLD <= 1.0


def test_crypto_tokens_are_secret():
    """Проверяем, что крипто-токены тоже SecretStr"""
    settings = Settings()
    assert hasattr(settings.CRYPTO_BOT_TOKEN, "get_secret_value")
    assert hasattr(settings.CRYPTO_PAY_API_KEY, "get_secret_value")