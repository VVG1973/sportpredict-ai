import json
import logging
from pathlib import Path
from typing import Dict, List, Optional
import httpx
import asyncio
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class EsportsDataCollector:
    """Сбор данных киберспорта с Pandascore API"""
    
    BASE_URL = "https://api.pandascore.co"
    TOKEN = "F-fZFrnMfNMw3w2CjmGIPorazuipMezHM0ziYK_HWFUpHlB2COg"
    CACHE_DIR = Path("/tmp/esports_cache")
    
    def __init__(self):
        try:
            self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError):
            pass
        self.headers = {"Authorization": f"Bearer {self.TOKEN}"}
        self.team_cache = {}
    
    async def _request(self, endpoint: str, params: dict = None) -> list:
        """Делает запрос с кэшированием"""
        cache_key = endpoint.replace("/", "_") + "_" + "_".join([f"{k}_{v}" for k, v in (params or {}).items()])
        cache_file = self.CACHE_DIR / f"{cache_key[:100]}.json"
        
        # Проверяем кэш (валиден 30 минут)
        if cache_file.exists():
            age = datetime.now() - datetime.fromtimestamp(cache_file.stat().st_mtime)
            if age < timedelta(minutes=30):
                with open(cache_file, "r", encoding="utf-8") as f:
                    return json.load(f)
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                url = f"{self.BASE_URL}/{endpoint}"
                response = await client.get(url, headers=self.headers, params=params or {})
                data = response.json()
                
                # Сохраняем в кэш
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(data, f)
                
                return data
        except Exception as e:
            logger.error(f"❌ Ошибка запроса {endpoint}: {e}")
            return []
    
    async def get_upcoming_matches(self, game: str = "csgo", count: int = 10) -> List[Dict]:
        """Получает предстоящие матчи"""
        data = await self._request(f"{game}/matches/upcoming", {"page[size]": count})
        matches = []
        for match in data:
            matches.append({
                "id": match.get("id"),
                "name": match.get("name"),
                "game": game,
                "status": match.get("status"),
                "scheduled_at": match.get("scheduled_at"),
                "league": match.get("league", {}).get("name", ""),
                "serie": match.get("serie", {}).get("name", ""),
                "team1": {
                    "name": match.get("opponents", [{}])[0].get("opponent", {}).get("name", "TBD"),
                    "id": match.get("opponents", [{}])[0].get("opponent", {}).get("id")
                },
                "team2": {
                    "name": match.get("opponents", [{}])[1].get("opponent", {}).get("name", "TBD"),
                    "id": match.get("opponents", [{}])[1].get("opponent", {}).get("id")
                },
                "odds": self._extract_odds(match)
            })
        return matches
    
    def _extract_odds(self, match: Dict) -> Dict:
        """Извлекает коэффициенты из матча"""
        # Pandascore не всегда даёт odds, пробуем найти
        return {
            "home": 0,
            "away": 0
        }
    
    async def get_team_matches(self, team_id: int, game: str = "csgo", count: int = 50) -> List[Dict]:
        """Получает историю матчей команды"""
        data = await self._request(f"{game}/matches", {"filter[opponent_id]": team_id, "page[size]": count})
        return [m for m in data if m.get("status") == "finished"]
    
    async def get_team_stats(self, team_id: int, game: str = "csgo") -> Dict:
        """Получает статистику команды"""
        # Используем историю матчей для расчёта статистики
        matches = await self.get_team_matches(team_id, game, count=50)
        
        wins = 0
        losses = 0
        total_maps = 0
        rounds_won = []
        rounds_lost = []
        
        for match in matches:
            # Определяем, выиграла ли команда
            winner_id = match.get("winner", {}).get("id")
            if winner_id == team_id:
                wins += 1
            else:
                losses += 1
            
            # Статистика по картам
            for game_map in match.get("games", []):
                total_maps += 1
                # Здесь можно добавить подсчёт раундов если API даёт
        
        total = wins + losses
        return {
            "wins": wins,
            "losses": losses,
            "winrate": wins / total if total > 0 else 0.5,
            "total_maps": total_maps,
            "recent_form": self._calculate_form(matches[:10], team_id)
        }
    
    def _calculate_form(self, matches: List[Dict], team_id: int) -> List[str]:
        """Рассчитывает форму (W/L)"""
        form = []
        for match in matches:
            winner_id = match.get("winner", {}).get("id")
            if winner_id == team_id:
                form.append("W")
            else:
                form.append("L")
        return form
    
    async def get_match_features(self, team1_id: int, team2_id: int, game: str = "csgo") -> Optional[Dict]:
        """Создаёт фичи для матча"""
        stats1 = await self.get_team_stats(team1_id, game)
        stats2 = await self.get_team_stats(team2_id, game)
        
        # H2H
        h2h_matches = await self._get_h2h_matches(team1_id, team2_id, game)
        h2h_wins = sum(1 for m in h2h_matches if m.get("winner", {}).get("id") == team1_id)
        h2h_total = len(h2h_matches)
        
        return {
            "winrate1": stats1["winrate"],
            "winrate2": stats2["winrate"],
            "wins1": stats1["wins"],
            "wins2": stats2["wins"],
            "form1_wins": stats1["recent_form"].count("W"),
            "form2_wins": stats2["recent_form"].count("W"),
            "h2h_winrate": h2h_wins / h2h_total if h2h_total > 0 else 0.5,
            "h2h_count": h2h_total,
        }
    
    async def _get_h2h_matches(self, team1_id: int, team2_id: int, game: str) -> List[Dict]:
        """Получает H2H матчи"""
        matches1 = await self.get_team_matches(team1_id, game, count=100)
        return [m for m in matches1 if any(
            o.get("opponent", {}).get("id") == team2_id 
            for o in m.get("opponents", [])
        )]
