"""
Диагностика публикации прогнозов
"""
import asyncio
import json
import logging
from pathlib import Path
import sys

sys.path.insert(0, ".")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def diagnose():
    print("=" * 60)
    print("🔍 ДИАГНОСТИКА ПУБЛИКАЦИИ ПРОГНОЗОВ")
    print("=" * 60)
    print()
    
    # 1. Проверяем модель
    print("📊 1. Проверка модели...")
    try:
        from ml_models.synthetic_xg_model import SyntheticXGModel
        model = SyntheticXGModel()
        print(f"   ✅ Модель загружена: {model.is_loaded}")
        print(f"   ✅ Точность: {model.accuracy:.2%}")
        print(f"   ✅ Признаков: {len(model.feature_cols)}")
        print(f"   📋 Признаки: {model.feature_cols[:5]}...")
    except Exception as e:
        print(f"   ❌ Ошибка загрузки модели: {e}")
        return
    
    print()
    
    # 2. Проверяем данные матчей
    print("📊 2. Проверка данных матчей...")
    matches_path = Path("data/historical/football_data_matches.json")
    if not matches_path.exists():
        print(f"   ❌ Файл не найден: {matches_path}")
        return
    
    with open(matches_path, "r", encoding="utf-8") as f:
        matches = json.load(f)
    
    print(f"   ✅ Всего матчей: {len(matches)}")
    
    # Проверяем последний матч
    if matches:
        last_match = matches[-1]
        print(f"   📅 Последний матч: {last_match.get('date', 'N/A')}")
        print(f"   ⚽ {last_match.get('home_team', 'N/A')} vs {last_match.get('away_team', 'N/A')}")
        
        # Проверяем наличие признаков
        required_features = model.feature_cols
        missing = [f for f in required_features if f not in last_match]
        
        if missing:
            print(f"   ⚠️ Отсутствуют признаки ({len(missing)}):")
            for f in missing[:10]:
                print(f"      - {f}")
            if len(missing) > 10:
                print(f"      ... и ещё {len(missing) - 10}")
        else:
            print(f"   ✅ Все {len(required_features)} признаков на месте")
    
    print()
    
    # 3. Тестируем прогноз
    print("📊 3. Тест прогноза...")
    if matches:
        test_match = matches[-1]
        prediction, confidence, probs = model.predict(test_match)
        print(f"   🎯 Прогноз: {prediction}")
        print(f"   📊 Уверенность: {confidence:.2%}")
        print(f"   📈 Вероятности: H={probs['H']:.2%}, D={probs['D']:.2%}, A={probs['A']:.2%}")
    
    print()
    
    # 4. Проверяем publisher
    print("📊 4. Проверка TelegramPublisher...")
    try:
        from telegram_bot.event_publisher import TelegramPublisher
        from config import settings
        
        publisher = TelegramPublisher()
        print(f"   ✅ Bot: {publisher.bot is not None}")
        print(f"   ✅ Обычный канал: {publisher.channel_id}")
        print(f"   ✅ VIP канал: {publisher.vip_channel_id}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    print()
    print("=" * 60)
    print("✅ Диагностика завершена")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(diagnose())
