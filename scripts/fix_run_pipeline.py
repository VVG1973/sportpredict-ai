"""
Исправленный run_pipeline с интеграцией API-Football и правильным вызовом ML-модели
"""
import re
from pathlib import Path

main_path = Path("main.py")
if not main_path.exists():
    print(f"❌ Файл не найден: {main_path}")
    exit(1)

content = main_path.read_text(encoding="utf-8")

# Новая функция run_pipeline
new_run_pipeline = '''
async def run_pipeline():
    """Основной пайплайн: парсинг → ML-предсказание → публикация"""
    from data_collectors.multi_sport_parser import MultiSportParser
    from data_collectors.api_football_parser import APIFootballParser
    
    parser = MultiSportParser(min_confidence=0.70)
    api_parser = APIFootballParser()  # 🆕 API-Football для летних лиг
    publisher = TelegramPublisher()
    db = Database()
    await db.init()
    manager = SubscriptionManager()
    await manager.init()

    # Получаем матчи из MultiSportParser
    matches = await parser.fetch_upcoming_matches(count=20)
    
    # 🆕 Добавляем матчи из API-Football (летние лиги)
    try:
        api_matches = api_parser.get_matches_for_dates(days_ahead=3)
        if api_matches:
            matches.extend(api_matches)
            logger.info(f"🌍 Добавлено {len(api_matches)} матчей из API-Football")
    except Exception as e:
        logger.warning(f"⚠️ Ошибка API-Football: {e}")

    if not matches:
        logger.info("📭 Матчей не найдено.")
        await publisher.close()
        return

    logger.info(f"📊 Найдено матчей: {len(matches)}")

    # Загружаем исторические данные для анализа формы команд
    historical_df = None
    try:
        hist_path = Path("data/historical/all_matches_clean.csv")
        if hist_path.exists():
            import pandas as pd
            historical_df = pd.read_csv(hist_path, encoding="utf-8", low_memory=False)
            historical_df["Date"] = pd.to_datetime(historical_df["Date"], errors="coerce")
            logger.info(f"📚 Загружено {len(historical_df)} исторических матчей для анализа формы")
    except Exception as e:
        logger.warning(f"⚠️ Не удалось загрузить исторические данные: {e}")

    vip_predictions = []
    express_candidates = []
    regular_predictions = []

    for m in matches:
        # Извлекаем данные матча (поддержка обоих форматов)
        if isinstance(m, dict) and "teams" in m:
            # Формат MultiSportParser
            home_team = m["teams"]["home"]["name"]
            away_team = m["teams"]["away"]["name"]
            match_date_str = m["fixture"]["date"]
            fixture_id = m["fixture"]["id"]
        else:
            # Формат APIFootballParser
            home_team = m.get("home_team", "Unknown")
            away_team = m.get("away_team", "Unknown")
            match_date_str = m.get("date", "")
            fixture_id = m.get("fixture_id", f"api_{home_team}_{away_team}")
        
        import pandas as pd
        match_date = pd.to_datetime(match_date_str, errors="coerce")

        # 🆕 ФОРМИРУЕМ СЛОВАРЬ ДЛЯ ML-МОДЕЛИ (правильный формат!)
        match_data = {
            "home_team": home_team,
            "away_team": away_team,
            "match_date": match_date,
            "historical_df": historical_df,
            # Добавляем коэффициенты (если есть)
            "b365_home": m.get("home_odds", 2.0),
            "b365_draw": m.get("draw_odds", 3.5),
            "b365_away": m.get("away_odds", 3.0),
            "bw_home": m.get("home_odds", 2.0),
            "bw_draw": m.get("draw_odds", 3.5),
            "bw_away": m.get("away_odds", 3.0),
            "iw_home": m.get("home_odds", 2.0),
            "iw_draw": m.get("draw_odds", 3.5),
            "iw_away": m.get("away_odds", 3.0),
            "ps_home": m.get("home_odds", 2.0),
            "ps_draw": m.get("draw_odds", 3.5),
            "ps_away": m.get("away_odds", 3.0),
            "wh_home": m.get("home_odds", 2.0),
            "wh_draw": m.get("draw_odds", 3.5),
            "wh_away": m.get("away_odds", 3.0),
            # Синтетические признаки (fallback на 0)
            "home_xg": 0.0,
            "away_xg": 0.0,
            "xg_diff": 0.0,
            "home_sot_ratio": 0.0,
            "away_sot_ratio": 0.0,
            "home_dominance": 0.0,
            # Реальные xG из Understat (если есть)
            "home_season_xG": 0.0,
            "away_season_xG": 0.0,
            "home_season_xGA": 0.0,
            "away_season_xGA": 0.0,
            "xG_attack_diff": 0.0,
            "xG_defense_diff": 0.0,
            "home_attack_vs_away_defense": 0.0,
            "away_attack_vs_home_defense": 0.0,
            "home_season_NPxG": 0.0,
            "away_season_NPxG": 0.0,
            "home_ppda": 0.0,
            "away_ppda": 0.0,
        }

        # 🆕 ВЫЗЫВАЕМ ML-МОДЕЛЬ С СЛОВАРЕМ (правильно!)
        try:
            ml_result = ml_model.predict(match_data)
        except Exception as e:
            logger.error(f"❌ Ошибка ML-прогноза для {home_team} vs {away_team}: {e}")
            ml_result = {"prediction": "H", "confidence": 0.5}

        # Маппинг предсказания в русский формат
        outcome_mapping = {"H": "П1", "D": "X", "A": "П2"}
        predicted_outcome = ml_result["prediction"]
        if predicted_outcome in outcome_mapping:
            predicted_outcome = outcome_mapping[predicted_outcome]
        else:
            predicted_outcome = m.get("outcome", "П1")

        match_info = {
            "home_team": home_team,
            "away_team": away_team,
            "date": match_date_str,
            "fixture_id": fixture_id,
            "sport": m.get("sport", "⚽ Футбол"),
            "league": m.get("league", ""),
        }

        pred = {
            "prediction": predicted_outcome,
            "confidence": ml_result["confidence"],
            "odds_est": m.get("home_odds", m.get("odds", 2.0)),
            "match": match_info
        }

        # Категоризация на основе уверенности ML-модели
        from config import settings
        if pred["confidence"] >= settings.VIP_CONFIDENCE_THRESHOLD:
            vip_predictions.append(pred)
        elif pred["confidence"] >= 0.71:
            express_candidates.append(pred)
        else:
            regular_predictions.append(pred)

    published = 0

    # 1️⃣ VIP-прогнозы
    vip_predictions = sorted(vip_predictions, key=lambda x: x["confidence"], reverse=True)[:5]
    logger.info(f"🏆 Отобрано {len(vip_predictions)} VIP прогнозов (Топ-5 по уверенности)")

    for pred in vip_predictions:
        if await publisher.publish(pred, is_vip=True, is_single_purchase=False):
            published += 1

    # 2️⃣ Обычные прогнозы + персональные уведомления подписчикам команд
    regular_predictions = sorted(regular_predictions, key=lambda x: x["confidence"], reverse=True)[:5]
    logger.info(f"📊 Отобрано {len(regular_predictions)} обычных прогнозов (Топ-5 по уверенности)")

    for pred in regular_predictions:
        if await publisher.publish(pred, is_vip=False, is_single_purchase=False):
            published += 1
            await db.save_prediction(
                fixture_id=pred["match"]["fixture_id"],
                home=pred["match"]["home_team"],
                away=pred["match"]["away_team"],
                date=pred["match"]["date"],
                pred=pred["prediction"],
                conf=pred["confidence"],
                odds=pred["odds_est"]
            )

            # Персональные уведомления подписчикам команд
            try:
                home_team = pred["match"]["home_team"]
                away_team = pred["match"]["away_team"]

                home_followers = await db.get_team_followers(home_team)
                away_followers = await db.get_team_followers(away_team)
                all_followers = home_followers + away_followers

                if all_followers:
                    sport = pred["match"]["sport"]
                    league = pred["match"]["league"]
                    date_ru = pred["match"]["date"][:16].replace("T", " ")

                    personal_text = (
                        f"⚡ <b>Прогноз на вашу команду!</b>\n\n"
                        f"{sport} | <i>{league}</i>\n"
                        f"🏟 <b>{home_team}</b> — <b>{away_team}</b>\n"
                        f"📅 <i>{date_ru}</i>\n\n"
                        f"🎯 <b>Прогноз:</b> {pred['prediction']}\n"
                        f"📊 <b>Уверенность:</b> {pred['confidence']:.0%}\n"
                        f"💰 <b>Коэф:</b> {pred['odds_est']}\n\n"
                        f"━━━━━━━━━━━━━━━━━━━━━\n"
                        f"⚠️ <i>Ответственная игра. 18+</i>"
                    )

                    sent_count = 0
                    for user_id, username in all_followers:
                        try:
                            await publisher.bot.send_message(
                                chat_id=user_id,
                                text=personal_text,
                                parse_mode="HTML"
                            )
                            sent_count += 1
                            await asyncio.sleep(0.05)
                        except Exception as e:
                            logger.debug(f"Не удалось отправить {username}: {e}")

                    if sent_count > 0:
                        logger.info(f"📨 Персональные уведомления: {sent_count} ({home_team} vs {away_team})")
            except Exception as e:
                logger.warning(f"Ошибка персональных уведомлений: {e}")

    # 3️⃣ Экспрессы
    express_candidates.sort(key=lambda x: x["confidence"], reverse=True)
    express_published = 0
    admin_express_details = []

    if len(express_candidates) >= 5:
        express_2 = express_candidates[:2]
        events_2 = []
        total_odds_2 = 1.0
        for ev in express_2:
            events_2.append({
                "fixture_id": ev["match"]["fixture_id"],
                "home_team": ev["match"]["home_team"],
                "away_team": ev["match"]["away_team"],
                "date": ev["match"]["date"],
                "sport": ev["match"]["sport"],
                "league": ev["match"]["league"],
                "prediction": ev["prediction"],
                "confidence": ev["confidence"],
                "odds": ev["odds_est"]
            })
            total_odds_2 *= ev["odds_est"]

        group_id_2 = await manager.save_express_group(events_2, total_odds_2, 149)
        if await publisher.publish_express(express_2, group_id_2, 149):
            express_published += 1
            published += 1
            admin_express_details.append({
                "title": f"🔥 Экспресс x2 (149₽) — коэф {total_odds_2:.2f}",
                "events": express_2,
                "total_odds": total_odds_2,
                "price": 149
            })

        express_3 = express_candidates[2:5]
        events_3 = []
        total_odds_3 = 1.0
        for ev in express_3:
            events_3.append({
                "fixture_id": ev["match"]["fixture_id"],
                "home_team": ev["match"]["home_team"],
                "away_team": ev["match"]["away_team"],
                "date": ev["match"]["date"],
                "sport": ev["match"]["sport"],
                "league": ev["match"]["league"],
                "prediction": ev["prediction"],
                "confidence": ev["confidence"],
                "odds": ev["odds_est"]
            })
            total_odds_3 *= ev["odds_est"]

        group_id_3 = await manager.save_express_group(events_3, total_odds_3, 199)
        if await publisher.publish_express(express_3, group_id_3, 199):
            express_published += 1
            published += 1
            admin_express_details.append({
                "title": f"🔥 Экспресс x3 (199₽) — коэф {total_odds_3:.2f}",
                "events": express_3,
                "total_odds": total_odds_3,
                "price": 199
            })

    elif len(express_candidates) >= 2:
        express_2 = express_candidates[:2]
        events_2 = []
        total_odds_2 = 1.0
        for ev in express_2:
            events_2.append({
                "fixture_id": ev["match"]["fixture_id"],
                "home_team": ev["match"]["home_team"],
                "away_team": ev["match"]["away_team"],
                "date": ev["match"]["date"],
                "sport": ev["match"]["sport"],
                "league": ev["match"]["league"],
                "prediction": ev["prediction"],
                "confidence": ev["confidence"],
                "odds": ev["odds_est"]
            })
            total_odds_2 *= ev["odds_est"]

        group_id_2 = await manager.save_express_group(events_2, total_odds_2, 149)
        if await publisher.publish_express(express_2, group_id_2, 149):
            express_published += 1
            published += 1
            admin_express_details.append({
                "title": f"🔥 Экспресс x2 (149₽) — коэф {total_odds_2:.2f}",
                "events": express_2,
                "total_odds": total_odds_2,
                "price": 149
            })
        logger.info(f"⚠️ Создан только 1 экспресс (кандидатов: {len(express_candidates)})")

    if admin_express_details:
        try:
            from config import settings
            admin_text = "🔓 <b>ДЕТАЛИ ЭКСПРЕССОВ (только для вас)</b>\n\n"

            for express in admin_express_details:
                admin_text += f"<b>{express['title']}</b>\n"
                admin_text += f"━━━━━━━━━━━━━━━━━━━━━\n"

                for i, ev in enumerate(express["events"], 1):
                    match = ev.get("match", {})
                    home = match.get("home_team", "?")
                    away = match.get("away_team", "?")
                    sport = match.get("sport", "⚽")
                    league = match.get("league", "")
                    date_str = match.get("date", "")[:16].replace("T", " ")
                    prediction = ev.get("prediction", "?")
                    confidence = ev.get("confidence", 0)
                    odds = ev.get("odds_est", 2.0)

                    admin_text += (
                        f"<b>{i}.</b> {sport} | <i>{league}</i>\n"
                        f"🏟 <b>{home}</b> — <b>{away}</b>\n"
                        f"📅 <i>{date_str}</i>\n"
                        f"🎯 <b>Исход: {prediction}</b>\n"
                        f"📊 Уверенность: {confidence:.0%}\n"
                        f"💰 Коэф: {odds}\n\n"
                    )

                admin_text += (
                    f"💵 <b>Цена:</b> {express['price']}₽\n"
                    f"📈 <b>Общий коэф:</b> {express['total_odds']:.2f}\n\n"
                )

            admin_text += "━━━━━━━━━━━━━━━━━━━━━\n"
            admin_text += f"📤 Всего опубликовано экспрессов: {express_published}"

            await publisher.bot.send_message(
                chat_id=settings.ADMIN_ID,
                text=admin_text,
                parse_mode="HTML"
            )
            logger.info(f"📨 Детали экспрессов отправлены админу")
        except Exception as e:
            logger.error(f"Ошибка отправки деталей админу: {e}")

    logger.info(
        f"📤 Опубликовано {published}: VIP={len(vip_predictions)}, "
        f"обычные={len(regular_predictions)}, экспрессы={express_published}"
    )
    await publisher.close()
'''

# Находим старую функцию run_pipeline и заменяем
pattern = r'async def run_pipeline\(\):.*?(?=\n(?:async\s+)?def\s|\nif\s+__name__|$)'
match = re.search(pattern, content, re.DOTALL)

if match:
    content = content[:match.start()] + new_run_pipeline + content[match.end():]
    main_path.write_text(content, encoding="utf-8")
    print("✅ run_pipeline() успешно заменена!")
    print("🔧 Исправления:")
    print("   1. Добавлен APIFootballParser для летних лиг")
    print("   2. ML-модель теперь вызывается с словарем (правильно!)")
    print("   3. Добавлены коэффициенты из API-Football")
    print("   4. Добавлены fallback признаки для корректной работы")
else:
    print("⚠️ Не удалось найти функцию run_pipeline()")
    print("💡 Попробуйте ручной метод замены")
