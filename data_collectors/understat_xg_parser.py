"""
Парсер xG-статистики с Understat.com
Собирает данные по матчам с xG, xGA, xPts
"""
import asyncio
import json
import logging
from pathlib import Path
from datetime import datetime
import httpx
from bs4 import BeautifulSoup
import re

logger = logging.getLogger(__name__)

# URL лиг на Understat
LEAGUES = {
    "EPL": "https://understat.com/league/EPL",
    "La_liga": "https://understat.com/league/La_liga",
    "Bundesliga": "https://understat.com/league/Bundesliga",
    "Serie_A": "https://understat.com/league/Serie_A",
    "Ligue_1": "https://understat.com/league/Ligue_1",
    "RFPL": "https://understat.com/league/RFPL",  # РПЛ
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
}


class UnderstatParser:
    """Парсер xG данных с Understat.com"""
    
    def __init__(self, data_dir: str = "data/historical/xg"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    async def parse_league_season(self, league: str, season: int) -> list:
        """
        Парсит одну лигу за один сезон
        season: 2023 = сезон 2023/2024
        Возвращает список матчей с xG статистикой
        """
        url = f"{LEAGUES[league]}/{season}"
        logger.info(f"📊 Парсинг {league} {season}/{season+1}: {url}")
        
        try:
            async with httpx.AsyncClient(headers=HEADERS, timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                
                html = response.text
                
                # Understat хранит данные в JSON внутри <script> тегов
                # Ищем переменную datesData (список всех матчей)
                matches_data = self._extract_json_data(html, "datesData")
                
                if not matches_data:
                    logger.warning(f"⚠️ Не удалось извлечь данные для {league} {season}")
                    return []
                
                # Преобразуем в удобный формат
                parsed_matches = []
                for match in matches_data:
                    try:
                        parsed = {
                            "fixture_id": f"understat_{match.get('id', '')}",
                            "date": match.get("datetime", ""),
                            "home_team": match.get("h", {}).get("title", ""),
                            "away_team": match.get("a", {}).get("title", ""),
                            "home_goals": int(match.get("goals", {}).get("h", 0)),
                            "away_goals": int(match.get("goals", {}).get("a", 0)),
                            "home_xg": float(match.get("xG", {}).get("h", 0)),
                            "away_xg": float(match.get("xG", {}).get("a", 0)),
                            "result": match.get("result", ""),
                            "league": league,
                            "season": season,
                        }
                        parsed_matches.append(parsed)
                    except (ValueError, KeyError, TypeError) as e:
                        logger.debug(f"Пропуск матча: {e}")
                        continue
                
                logger.info(f"✅ {league} {season}: получено {len(parsed_matches)} матчей")
                return parsed_matches
        
        except httpx.HTTPError as e:
            logger.error(f"❌ HTTP ошибка при парсинге {league} {season}: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Ошибка парсинга {league} {season}: {e}")
            return []
    
    def _extract_json_data(self, html: str, var_name: str) -> list:
        """Извлекает JSON данные из HTML скрипта Understat"""
        try:
            # Understat хранит данные как: var datesData = JSON.parse('...')
            pattern = rf"var\s+{var_name}\s*=\s*JSON\.parse\('(.+?)'\)"
            match = re.search(pattern, html)
            
            if not match:
                return []
            
            # Декодируем JSON (там escape-последовательности)
            json_str = match.group(1)
            # Unescape: \' -> ' и т.д.
            json_str = json_str.encode().decode('unicode_escape')
            
            return json.loads(json_str)
        except Exception as e:
            logger.error(f"Ошибка извлечения {var_name}: {e}")
            return []
    
    async def parse_all_leagues(self, seasons: list = None) -> dict:
        """
        Парсит все лиги за указанные сезоны
        seasons: [2023, 2022, 2021] (по умолчанию последние 3 сезона)
        """
        if seasons is None:
            current_year = datetime.now().year
            seasons = [current_year - 1, current_year - 2, current_year - 3]
        
        all_data = {}
        
        for league in LEAGUES.keys():
            league_data = []
            
            for season in seasons:
                # Вежливая задержка, чтобы не получить бан
                await asyncio.sleep(2)
                
                matches = await self.parse_league_season(league, season)
                league_data.extend(matches)
            
            all_data[league] = league_data
            
            # Сохраняем данные по лиге
            output_file = self.data_dir / f"{league}_xg.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(league_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"💾 Сохранено {len(league_data)} матчей {league} в {output_file}")
        
        return all_data
    
    async def get_team_xg_stats(self, team_name: str, last_n: int = 5) -> dict:
        """
        Возвращает xG-статистику команды за последние N матчей
        Используется для обогащения признаков в ML модели
        """
        # Ищем команду во всех файлах лиг
        home_xg_for = []  # xG забитые дома
        home_xg_against = []  # xG пропущенные дома
        away_xg_for = []  # xG забитые в гостях
        away_xg_against = []  # xG пропущенные в гостях
        
        for file_path in self.data_dir.glob("*_xg.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    matches = json.load(f)
                
                for match in matches:
                    if match["home_team"] == team_name:
                        home_xg_for.append(match["home_xg"])
                        home_xg_against.append(match["away_xg"])
                    elif match["away_team"] == team_name:
                        away_xg_for.append(match["away_xg"])
                        away_xg_against.append(match["home_xg"])
            except Exception as e:
                logger.debug(f"Ошибка чтения {file_path}: {e}")
                continue
        
        # Берём последние N матчей
        home_xg_for = home_xg_for[-last_n:]
        home_xg_against = home_xg_against[-last_n:]
        away_xg_for = away_xg_for[-last_n:]
        away_xg_against = away_xg_against[-last_n:]
        
        def safe_avg(lst):
            return sum(lst) / len(lst) if lst else 0.0
        
        return {
            "home_xg_for_avg": safe_avg(home_xg_for),
            "home_xg_against_avg": safe_avg(home_xg_against),
            "away_xg_for_avg": safe_avg(away_xg_for),
            "away_xg_against_avg": safe_avg(away_xg_against),
            "total_xg_for_avg": safe_avg(home_xg_for + away_xg_for),
            "total_xg_against_avg": safe_avg(home_xg_against + away_xg_against),
            "xg_difference": safe_avg(home_xg_for + away_xg_for) - safe_avg(home_xg_against + away_xg_against),
            "matches_count": len(home_xg_for) + len(away_xg_for),
        }


async def collect_xg_data():
    """Главная функция для сбора xG данных"""
    parser = UnderstatParser()
    
    logger.info("🚀 Начинаем сбор xG данных с Understat.com")
    logger.info("⏳ Это может занять 5-10 минут (с задержками для вежливости)")
    
    # Собираем последние 3 сезона для всех лиг
    data = await parser.parse_all_leagues(seasons=[2024, 2023, 2022])
    
    total = sum(len(matches) for matches in data.values())
    logger.info(f"✅ Сбор завершён! Всего матчей: {total}")
    
    # Пример использования
    logger.info("\n📊 Пример xG статистики для Manchester City:")
    stats = await parser.get_team_xg_stats("Manchester City", last_n=5)
    for key, value in stats.items():
        logger.info(f"  {key}: {value:.3f}" if isinstance(value, float) else f"  {key}: {value}")
    
    return data


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    asyncio.run(collect_xg_data())
