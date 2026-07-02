"""
Тесты для result_checker.py — проверяем отсутствие случайных результатов
"""
import pytest
from unittest.mock import AsyncMock, patch
from analyzers.result_checker import ResultChecker


@pytest.mark.asyncio
async def test_no_random_results():
    """Проверяем, что при отсутствии данных результат = None, а не случайный"""
    checker = ResultChecker()

    # Мокаем API-ответ (пустой — нет данных)
    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"events": []}
        mock_response.text = '{"events": []}'
        mock_get.return_value = mock_response

        result = await checker._get_match_result("Team A", "Team B", "2026-07-02T15:00:00")

        # ❗ Важно: результат должен быть None, а не "H"/"D"/"A"
        assert result is None


@pytest.mark.asyncio
async def test_real_result_parsed():
    """Проверяем, что реальный результат парсится правильно"""
    checker = ResultChecker()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "events": [{
                "strHomeTeam": "Team A",
                "strAwayTeam": "Team B",
                "intHomeScore": "2",
                "intAwayScore": "1"
            }]
        }
        mock_response.text = '{"events": [...]}'
        mock_get.return_value = mock_response

        result = await checker._get_match_result("Team A", "Team B", "2026-07-02T15:00:00")

        assert result == "H"  # Победа хозяев


@pytest.mark.asyncio
async def test_draw_result():
    """Проверяем ничью"""
    checker = ResultChecker()

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "events": [{
                "strHomeTeam": "Team A",
                "strAwayTeam": "Team B",
                "intHomeScore": "1",
                "intAwayScore": "1"
            }]
        }
        mock_response.text = '{"events": [...]}'
        mock_get.return_value = mock_response

        result = await checker._get_match_result("Team A", "Team B", "2026-07-02T15:00:00")

        assert result == "D"