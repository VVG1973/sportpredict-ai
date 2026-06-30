"""
Ручной запуск pipeline для тестирования публикации
"""
import asyncio
import logging
import json
import sys
import os
from pathlib import Path

# Добавляем корень проекта в путь импорта
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def test_publish():
    print("=" * 60)
    print("🚀 РУЧНОЙ ЗАПУСК PIPELINE")
    print("=" * 60)
    
    # 1. Загружаем данные
    data_path = Path("data/historical/football_data_matches_with_xg.json")
    if not data_path.exists():
        print("❌ Файл не найден: запустите сначала generate_synthetic_xg.py")
        return
    
    with open(data_path, encoding="utf-8") as f:
        matches = json.load(f)
    
    print(f"✅ Загружено {len(matches)} матчей")
    
    # 2. Берём последние 10 матчей (свежие)
    recent_matches = matches[-10:]
    print(f"📅 Последние матчи: {recent_matches[0].get('date')} - {recent_matches[-1].get('date')}")
    
    # 3. Загружаем модель
    from ml_models.synthetic_xg_model import SyntheticXGModel
    model = SyntheticXGModel()
    
    if not model.is_loaded:
        print("❌ Модель не загружена")
        return
    
    # 4. Делаем прогнозы
    print("\n📊 Прогнозы:")
    vip_count = 0
    for match in recent_matches:
        prediction, confidence, probs = model.predict(match)
        home = match.get('home_team', 'N/A')
        away = match.get('away_team', 'N/A')
        date = match.get('date', 'N/A')
        
        emoji = "💎" if confidence >= 0.70 else "📊"
        print(f"  {emoji} {date} | {home} vs {away}")
        print(f"     Прогноз: {prediction} | Уверенность: {confidence:.1%}")
        
        if confidence >= 0.70:
            vip_count += 1
    
    print(f"\n💎 VIP прогнозов (≥70%): {vip_count} из {len(recent_matches)}")
    print("\n✅ Тест завершён")


if __name__ == "__main__":
    asyncio.run(test_publish())
