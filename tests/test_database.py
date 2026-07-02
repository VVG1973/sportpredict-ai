"""
Тесты для database/db.py
"""
import pytest
import asyncio
from database.db import Database


@pytest.fixture
async def db():
    """Фикстура — создаёт БД для тестов"""
    database = Database()
    await database.init()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_database_init():
    """Проверяем, что БД инициализируется"""
    database = Database()
    # Без DATABASE_URL должна быть ошибка
    with pytest.raises(ValueError):
        await database.init()


@pytest.mark.asyncio
async def test_save_and_get_prediction(db):
    """Проверяем сохранение и получение прогноза"""
    await db.save_prediction(
        fixture_id="test_123",
        home="Team A",
        away="Team B",
        date="2026-07-02T15:00:00",
        pred="П1",
        conf=0.75,
        odds=1.85
    )

    pending = await db.get_pending_predictions()
    # Проверяем, что прогноз появился в списке
    fixture_ids = [p[0] for p in pending]
    assert "test_123" in fixture_ids


@pytest.mark.asyncio
async def test_update_result(db):
    """Проверяем обновление результата"""
    await db.save_prediction(
        fixture_id="test_456",
        home="Team C",
        away="Team D",
        date="2026-07-02T15:00:00",
        pred="X",
        conf=0.60,
        odds=3.20
    )

    await db.update_result("test_456", "win")

    # Проверяем, что прогноз больше не в pending
    pending = await db.get_pending_predictions()
    fixture_ids = [p[0] for p in pending]
    assert "test_456" not in fixture_ids


@pytest.mark.asyncio
async def test_stats_format(db):
    """Проверяем формат статистики"""
    stats = await db.get_stats()
    assert "total" in stats
    assert "wins" in stats
    assert "losses" in stats
    assert "winrate" in stats
    assert "roi" in stats
    assert isinstance(stats["total"], int)
    assert isinstance(stats["winrate"], float)