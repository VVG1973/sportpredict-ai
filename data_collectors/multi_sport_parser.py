import random
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict

logger = logging.getLogger(__name__)

MSK = timezone(timedelta(hours=3))


class MultiSportParser:
    """Многовидовой парсер для генерации реалистичных прогнозов"""

    SPORTS_DATA = {
        "football": {
            "icon": "⚽",
            "leagues": {
                "АПЛ (Англия)": ["Manchester City", "Arsenal", "Liverpool", "Manchester United", "Chelsea", "Tottenham", "Newcastle", "Aston Villa"],
                "Ла Лига (Испания)": ["Real Madrid", "Barcelona", "Atletico Madrid", "Real Sociedad", "Athletic Bilbao", "Real Betis", "Villarreal"],
                "Серия А (Италия)": ["Inter Milan", "AC Milan", "Juventus", "Napoli", "Roma", "Lazio", "Atalanta", "Fiorentina"],
                "Бундеслига (Германия)": ["Bayern Munich", "Borussia Dortmund", "RB Leipzig", "Bayer Leverkusen", "Eintracht Frankfurt", "Stuttgart"],
                "Лига 1 (Франция)": ["PSG", "Marseille", "Monaco", "Lyon", "Lille", "Nice", "Lens"],
                "РПЛ (Россия)": ["Зенит", "Спартак", "ЦСКА", "Локомотив", "Динамо", "Краснодар", "Ростов"],
                "Лига Чемпионов": ["Real Madrid", "Manchester City", "Bayern Munich", "PSG", "Inter Milan", "Barcelona", "Arsenal"],
                "Лига Европы": ["Roma", "Atalanta", "Marseille", "Bayer Leverkusen", "West Ham", "Sporting CP", "Ajax"],
            },
            "outcomes": ["П1", "X", "П2", "ТБ 2.5", "ТМ 2.5", "Обе забьют"]
        },
        "tennis": {
            "icon": "🎾",
            "tournaments": ["ATP Wimbledon", "WTA Roland Garros", "ATP US Open", "ATP Australian Open", "ATP Masters 1000"],
            "players": ["Djokovic", "Alcaraz", "Sinner", "Medvedev", "Swiatek", "Sabalenka", "Zverev", "Rune", "Rublev"],
            "outcomes": ["П1", "П2", "ТБ 22.5", "ТМ 22.5", "Фора -3.5"]
        },
        "basketball": {
            "icon": "🏀",
            "leagues": ["NBA", "Евролига", "NCAA"],
            "teams": ["Lakers", "Warriors", "Celtics", "Bucks", "Nuggets", "Real Madrid", "Barcelona", "CSKA", "Fenerbahce", "Olympiacos"],
            "outcomes": ["П1", "П2", "ТБ 210.5", "ТМ 210.5", "Фора -5.5"]
        },
        "hockey": {
            "icon": "🏒",
            "leagues": ["NHL", "KHL"],
            "teams": ["Oilers", "Panthers", "Rangers", "Stars", "ЦСКА", "СКА", "Ак Барс", "Металлург", "Авангард", "Динамо М"],
            "outcomes": ["П1", "X", "П2", "ТБ 5.5", "ТМ 5.5"]
        },
    }

    def __init__(self, min_confidence: float = 0.70):
        self.min_confidence = min_confidence

    def _generate_realistic_time(self, allow_tomorrow: bool = True) -> datetime:
        """Генерирует время матча: сегодня или завтра, с 12:00 до 23:00 МСК"""
        # Футбол/хоккей/баскетбол обычно вечером
        if random.random() < 0.7:
            base_date = datetime.now(MSK).replace(hour=0, minute=0, second=0, microsecond=0)
        elif allow_tomorrow:
            base_date = (datetime.now(MSK) + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            base_date = datetime.now(MSK).replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Время с 12:00 до 23:00 МСК
        hour = random.randint(12, 22)
        minute = random.choice([0, 15, 30, 45])
        
        return base_date.replace(hour=hour, minute=minute)

    def _generate_confidence(self) -> float:
        weights = [0.15, 0.45, 0.30, 0.10]
        ranges = [(0.65, 0.72), (0.72, 0.79), (0.79, 0.85), (0.85, 0.92)]
        chosen_range = random.choices(ranges, weights=weights)[0]
        return round(random.uniform(chosen_range[0], chosen_range[1]), 2)

    def _generate_odds(self, confidence: float) -> float:
        if confidence >= 0.85:
            return round(random.uniform(1.40, 1.80), 2)
        elif confidence >= 0.78:
            return round(random.uniform(1.75, 2.30), 2)
        else:
            return round(random.uniform(2.20, 3.20), 2)

    def _generate_football_match(self) -> Dict:
        league = random.choice(list(self.SPORTS_DATA["football"]["leagues"].keys()))
        teams = self.SPORTS_DATA["football"]["leagues"][league]
        home, away = random.sample(teams, 2)
        confidence = self._generate_confidence()
        return {
            "sport": "⚽ Футбол", "league": league,
            "home_team": home, "away_team": away,
            "date": self._generate_realistic_time().isoformat(),
            "outcome": random.choice(self.SPORTS_DATA["football"]["outcomes"]),
            "confidence": confidence, "odds": self._generate_odds(confidence)
        }

    def _generate_tennis_match(self) -> Dict:
        tournament = random.choice(self.SPORTS_DATA["tennis"]["tournaments"])
        players = self.SPORTS_DATA["tennis"]["players"]
        p1, p2 = random.sample(players, 2)
        confidence = self._generate_confidence()
        return {
            "sport": "🎾 Теннис", "league": tournament,
            "home_team": p1, "away_team": p2,
            "date": self._generate_realistic_time().isoformat(),
            "outcome": random.choice(self.SPORTS_DATA["tennis"]["outcomes"]),
            "confidence": confidence, "odds": self._generate_odds(confidence)
        }

    def _generate_basketball_match(self) -> Dict:
        league = random.choice(self.SPORTS_DATA["basketball"]["leagues"])
        teams = self.SPORTS_DATA["basketball"]["teams"]
        home, away = random.sample(teams, 2)
        confidence = self._generate_confidence()
        return {
            "sport": "🏀 Баскетбол", "league": league,
            "home_team": home, "away_team": away,
            "date": self._generate_realistic_time().isoformat(),
            "outcome": random.choice(self.SPORTS_DATA["basketball"]["outcomes"]),
            "confidence": confidence, "odds": self._generate_odds(confidence)
        }

    def _generate_hockey_match(self) -> Dict:
        league = random.choice(self.SPORTS_DATA["hockey"]["leagues"])
        teams = self.SPORTS_DATA["hockey"]["teams"]
        home, away = random.sample(teams, 2)
        confidence = self._generate_confidence()
        return {
            "sport": "🏒 Хоккей", "league": league,
            "home_team": home, "away_team": away,
            "date": self._generate_realistic_time().isoformat(),
            "outcome": random.choice(self.SPORTS_DATA["hockey"]["outcomes"]),
            "confidence": confidence, "odds": self._generate_odds(confidence)
        }

    async def fetch_upcoming_matches(self, count: int = 20) -> List[Dict]:
        logger.info(f"🎭 Генерация {count} матчей...")
        matches = []
        
        generators = [
            self._generate_football_match,
            self._generate_tennis_match,
            self._generate_basketball_match,
            self._generate_hockey_match,
        ]
        distribution = [0.60, 0.15, 0.15, 0.10]
        
        for _ in range(count):
            gen = random.choices(generators, weights=distribution)[0]
            match = gen()
            formatted = {
                "fixture": {"id": random.randint(10000, 99999), "date": match["date"]},
                "teams": {"home": {"name": match["home_team"]}, "away": {"name": match["away_team"]}},
                "sport": match["sport"], "league": match["league"],
                "outcome": match["outcome"], "confidence": match["confidence"], "odds": match["odds"]
            }
            if match["confidence"] >= self.min_confidence:
                matches.append(formatted)
        
        logger.info(f"✅ Сгенерировано {len(matches)} прогнозов")
        return matches
