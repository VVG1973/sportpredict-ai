"""
Парсер тенниса из Tennis Abstract (GitHub)
Бесплатные CSV файлы с историческими данными ATP

Источник: https://github.com/JeffSackmann/tennis_atp
"""
import httpx
import logging
import asyncio
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict
from pathlib import Path

logger = logging.getLogger(__name__)

# GitHub URLs для CSV файлов
TENNIS_BASE_URL = "https://raw.githubusercontent.com/JeffSackmann/tennis_atp/master"


class TennisAbstractParser:
    """Парсер теннисных данных из Tennis Abstract"""

    def __init__(self):
        self.base_url = TENNIS_BASE_URL
        self.cache_dir = Path("data/historical")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    async def download_year_data(self, year: int) -> pd.DataFrame:
        """Скачивает данные за год"""
        url = f"{self.base_url}/atp_matches_{year}.csv"
        cache_file = self.cache_dir / f"tennis_atp_{year}.csv"

        # Проверяем кэш
        if cache_file.exists():
            try:
                df = pd.read_csv(cache_file, encoding="utf-8-sig")
                if not df.empty:
                    logger.info(f"🎾 {year}: загружено из кэша ({len(df)} матчей)")
                    return df
            except:
                pass

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    cache_file.write_bytes(response.content)
                    df = pd.read_csv(cache_file, encoding="utf-8-sig")
                    logger.info(f"🎾 {year}: скачано {len(df)} матчей")
                    return df
                else:
                    logger.warning(f"⚠️ Нет данных за {year}: HTTP {response.status_code}")
                    return pd.DataFrame()
        except Exception as e:
            logger.error(f"❌ Ошибка скачивания {year}: {e}")
            return pd.DataFrame()

    def convert_to_format(self, df: pd.DataFrame, year: int) -> List[Dict]:
        """Конвертирует данные в формат приложения"""
        matches = []

        for idx, row in df.iterrows():
            try:
                # Извлекаем данные
                winner = row.get("winner_name", "")
                loser = row.get("loser_name", "")
                winner_rank = row.get("winner_rank", 0) or 0
                loser_rank = row.get("loser_rank", 0) or 0

                # Статистика
                w_aces = row.get("w_ace", 0) or 0
                l_aces = row.get("l_ace", 0) or 0
                w_svpt = row.get("w_svpt", 0) or 0
                l_svpt = row.get("l_svpt", 0) or 0
                w_1stIn = row.get("w_1stIn", 0) or 0
                l_1stIn = row.get("l_1stIn", 0) or 0

                # Турнир
                tourney_name = row.get("tourney_name", "")
                surface = row.get("surface", "")

                # Дата
                date_str = str(row.get("tourney_date", ""))
                if len(date_str) >= 8:
                    date_str = f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
                else:
                    date_str = ""

                matches.append({
                    "fixture_id": f"tennis_{year}_{idx}",
                    "date": date_str,
                    "league_name": f"{tourney_name} ({surface})",
                    "home_team": winner,
                    "away_team": loser,
                    "home_goals": w_aces,
                    "away_goals": l_aces,
                    "result": "H",  # Победитель = "home"
                    "B365H": 0,
                    "B365D": 0,  # В теннисе нет ничьих
                    "B365A": 0,
                    "HS": w_svpt,
                    "AS": l_svpt,
                    "HST": w_1stIn,
                    "AST": l_1stIn,
                    "HC": 0,
                    "AC": 0,
                    "sport": "🎾 Теннис",
                    "is_real": True,
                    "winner_rank": winner_rank,
                    "loser_rank": loser_rank,
                })
            except Exception as e:
                continue

        return matches

    async def get_recent_matches(self, days_back: int = 30) -> List[Dict]:
        """Получает недавние матчи тенниса"""
        all_matches = []
        current_year = datetime.now().year

        # Скачиваем данные за текущий и прошлый год
        for year in [current_year, current_year - 1]:
            df = await self.download_year_data(year)
            if not df.empty:
                matches = self.convert_to_format(df, year)
                all_matches.extend(matches)
            await asyncio.sleep(0.5)

        # Фильтруем по дате (последние N дней)
        if days_back > 0:
            cutoff_date = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
            filtered = []
            for m in all_matches:
                if m.get("date", "") >= cutoff_date:
                    filtered.append(m)
            all_matches = filtered

        logger.info(f"🎾 Теннис: получено {len(all_matches)} матчей")
        return all_matches
