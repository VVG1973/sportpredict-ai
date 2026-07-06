import re
from pathlib import Path

main_file = Path("main.py")
content = main_file.read_text(encoding="utf-8")

# 1. Полностью заменяем блок инициализации парсеров и сбора матчей
old_block_pattern = r'parser = MultiSportParser.*?logger\.info\(f"📊 Найдено матчей: \{len\(matches\)\}"\)'

new_block = """api_parser = APIFootballParser()
    publisher = TelegramPublisher()
    db = Database()
    await db.init()
    manager = SubscriptionManager()
    await manager.init()

    # 🆕 ЖЕСТКИЙ СБОР ТОЛЬКО РЕАЛЬНЫХ МАТЧЕЙ ИЗ API-FOOTBALL
    from datetime import datetime, timedelta
    try:
        api_matches = await api_parser.fetch_upcoming_matches(days=2)
    except Exception as e:
        logger.error(f"Ошибка API-Football: {e}")
        api_matches = []

    today = datetime.now().date()
    tomorrow = today + timedelta(days=1)
    
    matches = []
    for m in api_matches:
        if not m.get("is_real", False):
            continue # Жестко пропускаем любые выдуманные матчи
            
        match_date_str = m.get("date", "")
        try:
            match_date = datetime.strptime(match_date_str[:10], "%Y-%m-%d").date()
            if match_date in [today, tomorrow]:
                matches.append(m)
        except:
            continue
            
    if not matches:
        logger.info("📭 Реальных матчей на сегодня-завтра не найдено.")
        await publisher.close()
        return

    logger.info(f"📊 Найдено РЕАЛЬНЫХ матчей на сегодня-завтра: {len(matches)}")"""

if re.search(old_block_pattern, content, flags=re.DOTALL):
    content = re.sub(old_block_pattern, new_block, content, flags=re.DOTALL)
    print("✅ Блок сбора матчей переписан: только реальные матчи на сегодня-завтра!")
else:
    print("⚠️ Старый блок сбора матчей не найден (возможно, уже изменен).")

# 2. Добавляем умную корректировку прогнозов (Bookmaker Odds Override)
override_logic = """
        # 🆕 УМНАЯ КОРРЕКТИРОВКА НА ОСНОВЕ КОЭФФИЦИЕНТОВ (Bookmaker Odds Override)
        home_odds = float(match_data.get("home_odds", 0) or 0)
        draw_odds = float(match_data.get("draw_odds", 0) or 0)
        away_odds = float(match_data.get("away_odds", 0) or 0)
        
        if home_odds > 0 and draw_odds > 0 and away_odds > 0:
            min_odds = min(home_odds, draw_odds, away_odds)
            # Если модель выдает ничью или неуверенный прогноз (< 45%), используем мудрость букмекеров
            if ml_result.get("prediction") == "D" or ml_result.get("confidence", 0) < 0.45:
                if min_odds == home_odds:
                    ml_result["prediction"] = "H"
                    ml_result["confidence"] = max(ml_result.get("confidence", 0), 0.60)
                elif min_odds == away_odds:
                    ml_result["prediction"] = "A"
                    ml_result["confidence"] = max(ml_result.get("confidence", 0), 0.60)
"""

predict_pattern = r'(ml_result = ml_model\.predict\(enriched_match_data\)\s*\n\s*except Exception as e:\s*\n\s*logger\.error\(f"❌ Ошибка ML-прогноза для \{home_team\} vs \{away_team\}: \{e\}"\)\s*\n\s*ml_result = \{"prediction": "H", "confidence": 0\.5\})'

if re.search(predict_pattern, content):
    content = re.sub(predict_pattern, r'\1\n' + override_logic, content)
    print("✅ Добавлена умная корректировка прогнозов по коэффициентам!")
else:
    print("⚠️ Паттерн predict не найден для вставки корректировки.")

main_file.write_text(content, encoding="utf-8")
print("💾 main.py успешно обновлен!")
