"""
Тесты для result_checker.py
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from analyzers.result_checker import ResultChecker


def _make_mock_client(response_data):
    """Создаёт мок httpx.AsyncClient с нужным ответом"""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = response_data

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


@pytest.mark.asyncio
async def test_no_random_results():
    """Проверяем, что при отсутствии данных результат = None"""
    checker = ResultChecker()
    mock_client = _make_mock_client({"response": []})

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await checker._get_match_result("12345")
        assert result is None


@pytest.mark.asyncio
async def test_real_result_parsed():
    """Проверяем победу хозяев"""
    checker = ResultChecker()
    mock_client = _make_mock_client({
        "response": [{
            "fixture": {"id": 12345, "status": {"short": "FT"}},
            "goals": {"home": 2, "away": 1}
        }]
    })

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await checker._get_match_result("12345")
        assert result == "H"


@pytest.mark.asyncio
async def test_draw_result():
    """Проверяем ничью"""
    checker = ResultChecker()
    mock_client = _make_mock_client({
        "response": [{
            "fixture": {"id": 12345, "status": {"short": "FT"}},
            "goals": {"home": 1, "away": 1}
        }]
    })

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await checker._get_match_result("12345")
        assert result == "D"


@pytest.mark.asyncio
async def test_away_win_result():
    """Проверяем победу гостей"""
    checker = ResultChecker()
    mock_client = _make_mock_client({
        "response": [{
            "fixture": {"id": 12345, "status": {"short": "FT"}},
            "goals": {"home": 0, "away": 3}
        }]
    })

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await checker._get_match_result("12345")
        assert result == "A"


@pytest.mark.asyncio
async def test_match_not_finished():
    """Проверяем незавершённый матч"""
    checker = ResultChecker()
    mock_client = _make_mock_client({
        "response": [{
            "fixture": {"id": 12345, "status": {"short": "1H"}},
            "goals": {"home": 1, "away": 0}
        }]
    })

    with patch("httpx.AsyncClient", return_value=mock_client):
        result = await checker._get_match_result("12345")
        assert result is None


def test_check_prediction_win():
    """Проверяем маппинг прогнозов"""
    checker = ResultChecker()
    assert checker._check_prediction_win("П1", "H") is True
    assert checker._check_prediction_win("П1", "A") is False
    assert checker._check_prediction_win("X", "D") is True
    assert checker._check_prediction_win("X", "H") is False
    assert checker._check_prediction_win("П2", "A") is True
    assert checker._check_prediction_win("П2", "D") is False
    assert checker._check_prediction_win("H", "H") is True
    assert checker._check_prediction_win("D", "D") is True
    assert checker._check_prediction_win("A", "A") is True
