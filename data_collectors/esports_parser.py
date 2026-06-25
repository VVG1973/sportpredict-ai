"""
Парсер киберспортивных матчей. Генерирует реалистичные матчи на сегодня-завтра.
"""
import logging
import random
from datetime import datetime, timedelta, timezone
from typing import List, Dict

logger = logging.getLogger(__name__)

MSK = timezone(timedelta(hours=3))


class EsportsParser:
    """Парсер киберспортивных матчей"""
    
    # 🎯 CS2 команды (на русском для единообразия)
    CS2_TEAMS_RU = {
        "NAVI": "NAVI", "FaZe": "FaZe Clan", "G2": "G2 Esports",
        "Vitality": "Team Vitality", "Spirit": "Team Spirit",
        "MOUZ": "MOUZ", "Heroic": "Heroic", "Astralis": "Astralis",
        "Liquid": "Team Liquid", "Complexity": "Complexity",
        "Virtus.pro": "Virtus.pro", "Cloud9": "Cloud9",
        "ENCE": "ENCE", "BIG": "BIG", "Fnatic": "Fnatic",
        "Monte": "Monte", "Eternal Fire": "Eternal Fire",
    }
    
    # 🗡️ Dota 2 команды
    DOTA2_TEAMS_RU = {
        "Team Spirit": "Team Spirit", "Gaimin Gladiators": "Gaimin Gladiators",
        "Tundra": "Tundra Esports", "Team Liquid": "Team Liquid",
        "BetBoom Team": "BetBoom Team", "Xtreme Gaming": "Xtreme Gaming",
        "Falcons": "Team Falcons", "OG": "OG", "PSG.LGD": "PSG.LGD",
        "Nigma Galaxy": "Nigma Galaxy", "Team Secret": "Team Secret",
    }
    
    # 🥊 MMA бойцы
    MMA_FIGHTERS_RU = {
        "Jon Jones": "Джон Джонс", "Islam Makhachev": "Ислам Махачев",
        "Alex Pereira": "Алекс Перейра", "Ilia Topuria": "Илия Топурия",
        "Khamzat Chimaev": "Хамзат Чимаев", "Sean O'Malley": "Шон О'Мэлли",
        "Dustin Poirier": "Дастин Порье", "Conor McGregor": "Конор Макгрегор",
        "Islam Makhachev": "Ислам Махачев", "Charles Oliveira": "Чарльз Оливейра",
    }
    
    CS2_TOURNAMENTS = [
        "IEM Katowice", "BLAST Premier", "ESL Pro League", 
        "PGL Major", "DreamHack", "BLAST Spring"
    ]
    
    DOTA2_TOURNAMENTS = [
        "The International", "DPC Major", "ESL One",
        "DreamLeague", "Riyadh Masters", "BetBoom Dacha"
    ]
    
    MMA_TOURNAMENTS = ["UFC Fight Night", "UFC PPV", "Bellator", "ACA"]
    
    def __init__(self, min_confidence: float = 0.70):
        self.min_confidence = min_confidence
    
    def _generate_realistic_time(self) -> datetime:
        """Генерирует время матча: сегодня или завтра, с 14:00 до 23:00 МСК"""
        # Выбираем день: сегодня (60%) или завтра (40%)
        if random.random() < 0.6:
            base_date = datetime.now(MSK).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            base_date = (datetime.now(MSK) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Время с 14:00 до 23:00 МСК (пиковое время для киберспорта)
        hour = random.randint(14, 22)
        minute = random.choice([0, 15, 30, 45])
        
        return base_date.replace(hour=hour, minute=minute)
    
    def _generate_cs2_match(self) -> Dict:
        teams = list(self.CS2_TEAMS_RU.keys())
        team1, team2 = random.sample(teams, 2)
        match_time = self._generate_realistic_time()
        confidence = round(random.uniform(0.72, 0.88), 2)
        
        return {
            "sport": "🎯 CS2",
            "league": random.choice(self.CS2_TOURNAMENTS),
            "home_team": self.CS2_TEAMS_RU[team1],
            "away_team": self.CS2_TEAMS_RU[team2],
            "date": match_time.isoformat(),
            "outcome": random.choice(["П1", "П2", "ТБ 2.5 карты", "Фора -1.5"]),
            "confidence": confidence,
            "odds": self._generate_odds(confidence),
            "is_real": False
        }
    
    def _generate_dota2_match(self) -> Dict:
        teams = list(self.DOTA2_TEAMS_RU.keys())
        team1, team2 = random.sample(teams, 2)
        match_time = self._generate_realistic_time()
        confidence = round(random.uniform(0.72, 0.88), 2)
        
        return {
            "sport": "🗡️ Dota 2",
            "league": random.choice(self.DOTA2_TOURNAMENTS),
            "home_team": self.DOTA2_TEAMS_RU[team1],
            "away_team": self.DOTA2_TEAMS_RU[team2],
            "date": match_time.isoformat(),
            "outcome": random.choice(["П1", "П2", "ТБ 2.5 карты", "Тотал убийств ТБ 45.5"]),
            "confidence": confidence,
            "odds": self._generate_odds(confidence),
            "is_real": False
        }
    
    def _generate_mma_match(self) -> Dict:
        fighters = list(self.MMA_FIGHTERS_RU.keys())
        f1, f2 = random.sample(fighters, 2)
        match_time = self._generate_realistic_time()
        confidence = round(random.uniform(0.72, 0.88), 2)
        
        return {
            "sport": "🥊 MMA",
            "league": random.choice(self.MMA_TOURNAMENTS),
            "home_team": self.MMA_FIGHTERS_RU[f1],
            "away_team": self.MMA_FIGHTERS_RU[f2],
            "date": match_time.isoformat(),
            "outcome": random.choice(["П1", "П2", "Досрочная победа", "Решение судей"]),
            "confidence": confidence,
            "odds": self._generate_odds(confidence),
            "is_real": False
        }
    
    def _generate_odds(self, confidence: float) -> float:
        if confidence >= 0.85:
            return round(random.uniform(1.40, 1.80), 2)
        elif confidence >= 0.78:
            return round(random.uniform(1.75, 2.30), 2)
        else:
            return round(random.uniform(2.20, 3.20), 2)
    
    async def fetch_esports_matches(self, count: int = 5) -> List[Dict]:
        """Генерирует киберспортивные матчи на сегодня-завтра"""
        logger.info(f"🎮 Генерация {count} киберспортивных матчей...")
        
        matches = []
        generators = [
            (self._generate_cs2_match, 0.50),   # 50% CS2
            (self._generate_dota2_match, 0.35), # 35% Dota 2
            (self._generate_mma_match, 0.15),   # 15% MMA
        ]
        
        for _ in range(count):
            gen_func, _ = random.choices(generators, weights=[g[1] for g in generators])[0]
            match = gen_func()
            
            formatted = {
                "fixture": {
                    "id": random.randint(10000, 99999),
                    "date": match["date"]
                },
                "teams": {
                    "home": {"name": match["home_team"]},
                    "away": {"name": match["away_team"]}
                },
                "sport": match["sport"],
                "league": match["league"],
                "outcome": match["outcome"],
                "confidence": match["confidence"],
                "odds": match["odds"],
                "is_real": match.get("is_real", False)
            }
            matches.append(formatted)
        
        logger.info(f"✅ Сгенерировано {len(matches)} киберспортивных матчей")
        return matches
