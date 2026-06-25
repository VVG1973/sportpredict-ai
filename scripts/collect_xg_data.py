"""
Скрипт для сбора xG данных с Understat.com
Запускается вручную или по расписанию (раз в неделю)
"""
import asyncio
import sys
import os

# Добавляем корень проекта в PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data_collectors.understat_xg_parser import collect_xg_data
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


async def main():
    print("=" * 60)
    print("📊 СБОР XG ДАННЫХ С UNDERSTAT.COM")
    print("=" * 60)
    print()
    print("⏳ Процесс займёт 5-10 минут")
    print("🌐 Будут обработаны 6 лиг за 3 сезона")
    print("💾 Данные сохранятся в data/historical/xg/")
    print()
    
    data = await collect_xg_data()
    
    print()
    print("=" * 60)
    print("📈 ИТОГОВАЯ СТАТИСТИКА:")
    print("=" * 60)
    for league, matches in data.items():
        print(f"  {league}: {len(matches)} матчей")
    
    total = sum(len(matches) for matches in data.values())
    print()
    print(f"✅ ВСЕГО: {total} матчей с xG статистикой")
    print()
    print("🎯 Следующий шаг: переобучение ML модели с новыми признаками")


if __name__ == "__main__":
    asyncio.run(main())
