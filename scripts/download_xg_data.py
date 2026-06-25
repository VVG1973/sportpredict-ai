"""
Скачивает xG данные для всех топ-лиг
"""
import asyncio
import sys
from pathlib import Path

# Добавляем корень проекта в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from data_collectors.understat_parser import UnderstatParser


async def download_all():
    parser = UnderstatParser()
    
    # Скачиваем последние 3 сезона для всех лиг
    seasons = ["2023", "2022", "2021"]
    
    print("🚀 Начинаю скачивание xG данных...")
    print(f"📅 Сезоны: {', '.join(seasons)}")
    print(f"🏆 Лиги: EPL, La Liga, Serie A, Bundesliga, Ligue 1\n")
    
    data = await parser.fetch_all_leagues(seasons)
    
    # Статистика
    total_matches = 0
    for league, seasons_data in data.items():
        league_matches = sum(len(matches) for matches in seasons_data.values())
        total_matches += league_matches
        print(f"✅ {league}: {league_matches} матчей")
    
    print(f"\n🎉 Всего скачано: {total_matches} матчей с xG данными!")
    print(f"📁 Файлы сохранены в: data/historical/xg/")


if __name__ == "__main__":
    asyncio.run(download_all())
