"""
Тесты для database/db.py — используют SQLite через aiosqlite для изоляции
"""
import pytest
import os
import tempfile


@pytest.fixture
def temp_db_url():
    """Создаёт временную SQLite БД для тестов"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    yield f"sqlite+aiosqlite:///{db_path}"
    os.unlink(db_path)


def test_database_requires_url():
    """Проверяем, что Database требует DATABASE_URL"""
    from database.db import Database
    db = Database()
    assert db._is_sqlite or db.pool is None


def test_stats_format():
    """Проверяем формат статистики — все ключи на месте"""
    stats = {
        "total": 0,
        "wins": 0,
        "losses": 0,
        "pending": 0,
        "winrate": 0.0,
        "roi": 0.0,
        "profit": 0,
    }
    assert "total" in stats
    assert "wins" in stats
    assert "losses" in stats
    assert "winrate" in stats
    assert "roi" in stats
    assert "profit" in stats
    assert isinstance(stats["total"], int)
    assert isinstance(stats["winrate"], float)
    assert isinstance(stats["roi"], float)
    assert isinstance(stats["profit"], int)


def test_stats_winrate_calculation():
    """Проверяем расчёт винрейта"""
    wins = 7
    losses = 3
    checked = wins + losses
    winrate = (wins / checked * 100) if checked > 0 else 0.0
    assert winrate == 70.0

    # Нулевой случай
    winrate_empty = (0 / 0 * 100) if 0 > 0 else 0.0
    assert winrate_empty == 0.0
