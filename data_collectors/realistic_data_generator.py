import pandas as pd
import numpy as np
import os
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

class RealisticDataGenerator:
    """Генерирует реалистичные синтетические данные матчей АПЛ"""
    
    # Реальные команды АПЛ с их силой (от 0.4 до 0.95)
    TEAMS = {
        "Manchester City": 0.95, "Arsenal": 0.90, "Liverpool": 0.88,
        "Manchester United": 0.78, "Tottenham": 0.76, "Chelsea": 0.75,
        "Newcastle": 0.74, "Brighton": 0.70, "Aston Villa": 0.68,
        "West Ham": 0.65, "Crystal Palace": 0.62, "Fulham": 0.60,
        "Brentford": 0.58, "Wolves": 0.56, "Everton": 0.54,
        "Bournemouth": 0.52, "Nottingham Forest": 0.50, "Luton Town": 0.45,
        "Burnley": 0.43, "Sheffield United": 0.40
    }
    
    def __init__(self, n_matches=1000, seed=42):
        self.n_matches = n_matches
        np.random.seed(seed)
        
    def generate_form(self, team_strength: float) -> float:
        """Генерирует форму команды (зависит от силы + случайность)"""
        base = team_strength
        noise = np.random.uniform(-0.15, 0.15)
        return np.clip(base + noise, 0.2, 0.95)
    
    def simulate_match_result(self, home_strength: float, away_strength: float) -> tuple:
        """Симулирует результат матча на основе силы команд"""
        # Преимущество домашнего поля
        home_advantage = 0.08
        home_power = home_strength + home_advantage
        away_power = away_strength
        
        # Вероятности исходов
        diff = home_power - away_power
        
        if diff > 0.2:  # Явный фаворит - хозяева
            probs = [0.65, 0.20, 0.15]  # HOME, DRAW, AWAY
        elif diff > 0.1:
            probs = [0.55, 0.25, 0.20]
        elif diff > 0:
            probs = [0.45, 0.30, 0.25]
        elif diff > -0.1:
            probs = [0.35, 0.30, 0.35]
        elif diff > -0.2:
            probs = [0.25, 0.25, 0.50]
        else:  # Явный фаворит - гости
            probs = [0.15, 0.20, 0.65]
        
        # Результат: 0=HOME, 1=DRAW, 2=AWAY
        result = np.random.choice([0, 1, 2], p=probs)
        
        # Генерируем реалистичный счёт
        if result == 0:  # Победа хозяев
            home_goals = np.random.choice([1, 2, 3, 4], p=[0.35, 0.40, 0.20, 0.05])
            away_goals = np.random.randint(0, home_goals)
        elif result == 2:  # Победа гостей
            away_goals = np.random.choice([1, 2, 3, 4], p=[0.35, 0.40, 0.20, 0.05])
            home_goals = np.random.randint(0, away_goals)
        else:  # Ничья
            goals = np.random.choice([0, 1, 2, 3], p=[0.25, 0.40, 0.30, 0.05])
            home_goals = goals
            away_goals = goals
            
        return home_goals, away_goals, result
    
    def generate_h2h(self, home_strength: float, away_strength: float) -> float:
        """Генерирует историю личных встреч (процент побед хозяев)"""
        base = 0.3 + (home_strength - away_strength) * 0.4
        noise = np.random.uniform(-0.1, 0.1)
        return np.clip(base + noise, 0.15, 0.75)
    
    def generate(self) -> pd.DataFrame:
        """Генерирует датасет"""
        logger.info(f"🎲 Генерация {self.n_matches} реалистичных матчей АПЛ...")
        
        matches = []
        team_names = list(self.TEAMS.keys())
        base_date = datetime(2024, 8, 17)  # Начало сезона 2024/25
        
        for i in range(self.n_matches):
            # Выбираем две разные команды
            home_team, away_team = np.random.choice(team_names, 2, replace=False)
            home_strength = self.TEAMS[home_team]
            away_strength = self.TEAMS[away_team]
            
            # Генерируем признаки
            home_form = self.generate_form(home_strength)
            away_form = self.generate_form(away_strength)
            h2h_home_win = self.generate_h2h(home_strength, away_strength)
            home_streak = np.random.randint(-3, 5)
            key_injuries = np.random.choice([0, 1], p=[0.85, 0.15])
            
            # Симулируем результат
            home_goals, away_goals, result = self.simulate_match_result(home_strength, away_strength)
            
            # Дата матча
            match_date = base_date + timedelta(days=i % 280)
            
            matches.append({
                "fixture_id": 10000 + i,
                "home_team": home_team,
                "away_team": away_team,
                "date": match_date.strftime("%Y-%m-%d"),
                "home_form": home_form,
                "away_form": away_form,
                "h2h_home_win": h2h_home_win,
                "home_streak": home_streak,
                "key_injuries": key_injuries,
                "home_goals": home_goals,
                "away_goals": away_goals,
                "result": result
            })
        
        df = pd.DataFrame(matches)
        
        # Создаём папку data
        os.makedirs("data", exist_ok=True)
        df.to_csv("data/historical_matches.csv", index=False)
        
        logger.info(f"✅ Сгенерировано {len(df)} матчей")
        logger.info(f"📊 Распределение результатов:")
        logger.info(f"   HOME (победа хозяев): {(df['result'] == 0).sum()} ({(df['result'] == 0).mean():.1%})")
        logger.info(f"   DRAW (ничья): {(df['result'] == 1).sum()} ({(df['result'] == 1).mean():.1%})")
        logger.info(f"   AWAY (победа гостей): {(df['result'] == 2).sum()} ({(df['result'] == 2).mean():.1%})")
        logger.info(f"💾 Сохранено в data/historical_matches.csv")
        
        return df

if __name__ == "__main__":
    generator = RealisticDataGenerator(n_matches=1000)
    generator.generate()
