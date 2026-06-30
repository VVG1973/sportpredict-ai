"""
Диагностика отсутствия прогнозов в канале
"""
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def check_future_matches():
    """Проверяет, есть ли матчи на будущие даты"""
    print("=" * 60)
    print("🔍 ДИАГНОСТИКА: Почему прогнозы не публикуются")
    print("=" * 60)
    print()
    
    # 1. Проверяем данные матчей
    data_path = Path("data/historical/football_data_matches_with_xg.json")
    if not data_path.exists():
        print(f"❌ Файл не найден: {data_path}")
        return
    
    with open(data_path, encoding="utf-8") as f:
        matches = json.load(f)
    
    print(f"📚 Всего матчей в базе: {len(matches)}")
    
    # 2. Ищем матчи на будущие даты
    today = datetime.now()
    future_matches = []
    
    for match in matches:
        date_str = match.get("date", "")
        try:
            # Пробуем разные форматы дат
            for fmt in ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"]:
                try:
                    match_date = datetime.strptime(date_str, fmt)
                    if match_date > today:
                        future_matches.append({
                            "date": date_str,
                            "parsed_date": match_date,
                            "home": match.get("home_team", "N/A"),
                            "away": match.get("away_team", "N/A"),
                            "league": match.get("league", "N/A"),
                        })
                    break
                except ValueError:
                    continue
        except Exception as e:
            continue
    
    print(f"\n📅 Сегодня: {today.strftime('%d/%m/%Y')}")
    print(f"🔮 Матчей на будущие даты: {len(future_matches)}")
    
    if future_matches:
        # Сортируем по дате
        future_matches.sort(key=lambda m: m["parsed_date"])
        
        print("\n📋 Ближайшие матчи:")
        for i, match in enumerate(future_matches[:10]):
            days_ahead = (match["parsed_date"] - today).days
            print(f"   {i+1}. {match['date']} ({days_ahead} дн.) - {match['home']} vs {match['away']} [{match['league']}]")
    else:
        print("\n❌ НЕТ МАТЧЕЙ НА БУДУЩИЕ ДАТЫ!")
        print("💡 Это межсезонье - новые матчи появятся в августе")
        print()
        print("📊 Последние 5 матчей в базе:")
        recent = matches[-5:]
        for match in recent:
            print(f"   {match.get('date', 'N/A')} - {match.get('home_team', 'N/A')} vs {match.get('away_team', 'N/A')}")
    
    print()
    
    # 3. Проверяем модель
    print("🤖 Проверка модели:")
    try:
        from ml_models.real_xg_model import RealXGModel
        model = RealXGModel()
        
        if model.is_loaded:
            print(f"   ✅ Модель загружена: {model.accuracy:.2%}")
            print(f"   ✅ Признаков: {len(model.feature_cols)}")
            
            # Тестируем прогноз на последнем матче
            if matches:
                test_match = matches[-1]
                pred, conf, probs = model.predict(test_match)
                print(f"   📊 Тест прогноза: {pred} (уверенность: {conf:.1%})")
                
                if conf < 0.70:
                    print(f"   ⚠️ Уверенность {conf:.1%} < 70% - прогноз НЕ опубликуется!")
                else:
                    print(f"   ✅ Уверенность {conf:.1%} >= 70% - прогноз опубликуется")
        else:
            print("   ❌ Модель НЕ загружена!")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    print()
    print("=" * 60)
    print("💡 РЕКОМЕНДАЦИИ:")
    print("=" * 60)
    
    if not future_matches:
        print("1. Сейчас межсезонье - нет матчей для прогноза")
        print("2. Новые матчи появятся в августе 2025")
        print("3. Можно использовать mock-данные для тестирования")
    else:
        print("1. Матчи есть - проверьте логи Railway")
        print("2. Ищите строку 'run_pipeline' в логах")
        print("3. Проверьте, находит ли pipeline матчи")
    
    print()


if __name__ == "__main__":
    check_future_matches()
