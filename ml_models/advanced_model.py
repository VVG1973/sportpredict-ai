import json
import logging
from pathlib import Path
from typing import Dict, Optional
import numpy as np
import xgboost as xgb
try:
    from data_collectors.esports_collector import EsportsDataCollector
    ESPORTS_AVAILABLE = True
except ImportError:
    ESPORTS_AVAILABLE = False

logger = logging.getLogger(__name__)


class AdvancedPredictionModel:
    """Multi-output модель для прогнозирования футбольных матчей.
    Загружает ансамбль из 4 XGBoost моделей: исход, тотал, ОЗ, фора.
    """

    def __init__(self, model_dir: str = "ml_models"):
        self.models = {}
        self.feature_cols = []
        self.accuracy = {}
        self.is_loaded = False
        self.esports_collector = EsportsDataCollector() if ESPORTS_AVAILABLE else None
        self.esports_models = {}
        self._load_model()
        self._load_esports_models()

    def _load_esports_models(self):
        """Загружает модели киберспорта"""
        for game in ["csgo", "dota2"]:
            try:
                model_path = Path(f"ml_models/xgboost_{game}.json")
                if model_path.exists():
                    model = xgb.XGBClassifier()
                    model.load_model(str(model_path))
                    self.esports_models[game] = model
                    logger.info(f"✅ Модель {game} загружена")
                else:
                    logger.info(f"ℹ️ Модель {game} не найдена")
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки {game}: {e}")

    def _load_model(self):
        """Загружает XGBoost модели из JSON-файлов"""
        possible_paths = [
            Path("/app/data/ml_models/xgboost_models.meta.json"),
            Path("ml_models/xgboost_models.meta.json"),
            Path("/app/ml_models/xgboost_models.meta.json"),
        ]

        meta_path = None
        for path in possible_paths:
            if path.exists():
                meta_path = path
                break

        if meta_path is None:
            logger.error(f"❌ XGBoost meta не найден. Проверил: {possible_paths}")
            return

        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)

            self.feature_cols = meta.get("feature_cols", [])
            self.accuracy = meta.get("accuracy", {})
            model_dir = meta_path.parent

            for name in meta.get("models", []):
                path = model_dir / f"xgboost_{name}.json"
                logger.info(f"🔍 Проверяю {path}")
                if path.exists():
                    model = xgb.XGBClassifier()
                    model.load_model(str(path))
                    self.models[name] = model
                    logger.info(f"✅ Загружена модель: {name}")
                else:
                    logger.error(f"❌ Не найдена модель: {path}")

            self.is_loaded = len(self.models) > 0
            logger.info(f"📊 Загружено {len(self.models)}/{len(meta.get('models', []))} XGBoost моделей")

        except Exception as e:
            logger.error(f"❌ Ошибка загрузки моделей: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def _extract_features(self, match_data: Dict) -> np.ndarray:
        """Извлекает признаки из данных матча"""
        features = []
        for col in self.feature_cols:
            value = match_data.get(col, 0)
            # Пробуем разные варианты названий
            if value == 0:
                value = match_data.get(col.lower(), 0)
            if value == 0:
                value = match_data.get(col.upper(), 0)
            # Пробуем альтернативные имена
            if value == 0 and col == "B365H":
                value = match_data.get("odds_home", 0) or match_data.get("BWH", 0)
            if value == 0 and col == "B365D":
                value = match_data.get("odds_draw", 0) or match_data.get("BWD", 0)
            if value == 0 and col == "B365A":
                value = match_data.get("odds_away", 0) or match_data.get("BWA", 0)
            try:
                features.append(float(value))
            except (ValueError, TypeError):
                features.append(0.0)
        return np.array(features).reshape(1, -1)

    async def predict_esports(self, match_data: Dict, game: str = "csgo") -> Dict:
        """Прогноз для киберспортивных матчей"""
        if not self.esports_collector or game not in self.esports_models:
            logger.warning(f"⚠️ Модель {game} не доступна, используем fallback")
            return self._fallback_prediction_esports(game)
        
        try:
            team1_name = match_data.get("home_team", "")
            team2_name = match_data.get("away_team", "")
            
            # Находим ID команд через API
            # (упрощённо — используем имена как есть)
            # В реальности нужно искать team_id через поиск
            
            # Получаем фичи через коллектор
            # Здесь нужно знать team_id, пока используем fallback
            logger.info(f"🎮 Прогноз {game}: {team1_name} vs {team2_name}")
            
            # Заглушка: используем базовую логику
            # В полной версии здесь будет вызов get_match_features
            
            return self._fallback_prediction_esports(game)
            
        except Exception as e:
            logger.error(f"❌ Ошибка прогноза {game}: {e}")
            return self._fallback_prediction_esports(game)

    def _fallback_prediction_esports(self, game: str = "csgo") -> Dict:
        """Fallback для киберспорта"""
        if game == "dota2":
            return {
                "outcome": {"prediction": "H", "confidence": 0.55, "probabilities": {"H": 0.55, "A": 0.45}},
                "total": {"prediction": "ТБ 50.5", "confidence": 0.5},
                "both_scored": {"prediction": "—", "confidence": 0.5},
                "handicap": {"prediction": "Ф1 +5.5", "confidence": 0.5}
            }
        else:  # csgo
            return {
                "outcome": {"prediction": "H", "confidence": 0.55, "probabilities": {"H": 0.55, "A": 0.45}},
                "total": {"prediction": "ТБ 22.5", "confidence": 0.5},
                "both_scored": {"prediction": "—", "confidence": 0.5},
                "handicap": {"prediction": "Ф1 +3.5", "confidence": 0.5}
            }

    def predict(self, match_data: Dict) -> Dict:
        """Делает прогнозы по всем рынкам"""
        if not self.is_loaded or not self.models:
            logger.warning("⚠️ Модель не загружена, используем fallback")
            return self._fallback_prediction()

        try:
            features = self._extract_features(match_data)

            # === ИСХОД (H/D/A) ===
            outcome_model = self.models.get('outcome')
            if outcome_model:
                outcome_probs = outcome_model.predict_proba(features)[0]
                outcome_idx = int(np.argmax(outcome_probs))
                outcome_map = {0: "H", 1: "D", 2: "A"}
                outcome_conf = float(outcome_probs[outcome_idx])
            else:
                outcome_idx = 0
                outcome_map = {0: "H", 1: "D", 2: "A"}
                outcome_conf = 0.33

            # === ТОТАЛ (ТБ/ТМ 2.5) ===
            total_model = self.models.get('total')
            if total_model:
                total_probs = total_model.predict_proba(features)[0]
                total_pred = "ТБ 2.5" if total_probs[1] > total_probs[0] else "ТМ 2.5"
                total_conf = float(max(total_probs))
            else:
                total_pred = "ТБ 2.5"
                total_conf = 0.5

            # === ОБЕ ЗАБЬЮТ ===
            both_model = self.models.get('both_scored')
            if both_model:
                both_probs = both_model.predict_proba(features)[0]
                both_pred = "Да" if both_probs[1] > both_probs[0] else "Нет"
                both_conf = float(max(both_probs))
            else:
                both_pred = "Да"
                both_conf = 0.5

            # === ФОРА ===
            handicap_model = self.models.get('handicap')
            if handicap_model:
                hand_probs = handicap_model.predict_proba(features)[0]
                hand_pred = "Ф1(-0.5)" if hand_probs[1] > hand_probs[0] else "Ф2(+0.5)"
                hand_conf = float(max(hand_probs))
            else:
                hand_pred = "Ф1(-0.5)"
                hand_conf = 0.5

            return {
                "outcome": {
                    "prediction": outcome_map[outcome_idx],
                    "confidence": outcome_conf,
                    "probabilities": {
                        "H": float(outcome_probs[0]) if outcome_model else 0.33,
                        "D": float(outcome_probs[1]) if outcome_model else 0.33,
                        "A": float(outcome_probs[2]) if outcome_model else 0.33,
                    }
                },
                "total": {
                    "prediction": total_pred,
                    "confidence": total_conf
                },
                "both_scored": {
                    "prediction": both_pred,
                    "confidence": both_conf
                },
                "handicap": {
                    "prediction": hand_pred,
                    "confidence": hand_conf
                }
            }

        except Exception as e:
            logger.error(f"❌ Ошибка прогноза: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return self._fallback_prediction()

    def _fallback_prediction(self) -> Dict:
        """Fallback при ошибке"""
        return {
            "outcome": {
                "prediction": "H",
                "confidence": 0.33,
                "probabilities": {"H": 0.33, "D": 0.33, "A": 0.33}
            },
            "total": {
                "prediction": "ТБ 2.5",
                "confidence": 0.5
            },
            "both_scored": {
                "prediction": "Да",
                "confidence": 0.5
            },
            "handicap": {
                "prediction": "Ф1(-0.5)",
                "confidence": 0.5
            }
        }

    def predict_with_value(self, match_data: Dict) -> Dict:
        """Прогноз с value bet анализом для всех рынков"""
        predictions = self.predict(match_data)
        
        # Получаем коэффициенты — пробуем разные форматы
        odds = match_data.get('odds', {})
        if not odds:
            odds = {
                'home': match_data.get('odds_home', 0) or match_data.get('B365H', 0),
                'draw': match_data.get('odds_draw', 0) or match_data.get('B365D', 0),
                'away': match_data.get('odds_away', 0) or match_data.get('B365A', 0),
                'over_2_5': match_data.get('odds_over_2_5', 0),
                'under_2_5': match_data.get('odds_under_2_5', 0),
                'both_yes': match_data.get('odds_both_yes', 0),
                'both_no': match_data.get('odds_both_no', 0),
                'handicap_home': match_data.get('odds_handicap_home', 0),
                'handicap_away': match_data.get('odds_handicap_away', 0),
            }

        # === Value для ИСХОДА ===
        outcome = predictions.get('outcome', {})
        odds_home = float(odds.get('home', 0)) or float(match_data.get('B365H', 0))
        odds_draw = float(odds.get('draw', 0)) or float(match_data.get('B365D', 0))
        odds_away = float(odds.get('away', 0)) or float(match_data.get('B365A', 0))
        
        odds_map = {"H": odds_home, "D": odds_draw, "A": odds_away}
        current_odds = odds_map.get(outcome.get('prediction', 'H'), 0)
        
        if current_odds and current_odds > 0:
            implied_prob = 1.0 / current_odds
            our_prob = outcome.get('confidence', 0)
            value = our_prob - implied_prob
            outcome['value'] = round(value, 4)
            outcome['is_value_bet'] = value > 0.05
            outcome['odds'] = round(current_odds, 2)
            logger.info(f"💎 Value исхода: {outcome['prediction']} | our={our_prob:.2%} | implied={implied_prob:.2%} | value={value:+.2%}")

        # === Value для ТОТАЛА ===
        total = predictions.get('total', {})
        over_odds = float(odds.get('over_2_5', 0))
        under_odds = float(odds.get('under_2_5', 0))
        
        if total.get('prediction') == "ТБ 2.5" and over_odds > 0:
            implied_prob = 1.0 / over_odds
            our_prob = total.get('confidence', 0)
            value = our_prob - implied_prob
            total['value'] = round(value, 4)
            total['is_value_bet'] = value > 0.05
            total['odds'] = round(over_odds, 2)
            logger.info(f"💎 Value тотала: ТБ 2.5 | our={our_prob:.2%} | implied={implied_prob:.2%} | value={value:+.2%}")
        elif total.get('prediction') == "ТМ 2.5" and under_odds > 0:
            implied_prob = 1.0 / under_odds
            our_prob = total.get('confidence', 0)
            value = our_prob - implied_prob
            total['value'] = round(value, 4)
            total['is_value_bet'] = value > 0.05
            total['odds'] = round(under_odds, 2)
            logger.info(f"💎 Value тотала: ТМ 2.5 | our={our_prob:.2%} | implied={implied_prob:.2%} | value={value:+.2%}")

        # === Value для ОБЕ ЗАБЬЮТ ===
        both = predictions.get('both_scored', {})
        yes_odds = float(odds.get('both_yes', 0))
        no_odds = float(odds.get('both_no', 0))
        
        if both.get('prediction') == "Да" and yes_odds > 0:
            implied_prob = 1.0 / yes_odds
            our_prob = both.get('confidence', 0)
            value = our_prob - implied_prob
            both['value'] = round(value, 4)
            both['is_value_bet'] = value > 0.05
            both['odds'] = round(yes_odds, 2)
            logger.info(f"💎 Value ОЗ: Да | our={our_prob:.2%} | implied={implied_prob:.2%} | value={value:+.2%}")
        elif both.get('prediction') == "Нет" and no_odds > 0:
            implied_prob = 1.0 / no_odds
            our_prob = both.get('confidence', 0)
            value = our_prob - implied_prob
            both['value'] = round(value, 4)
            both['is_value_bet'] = value > 0.05
            both['odds'] = round(no_odds, 2)
            logger.info(f"💎 Value ОЗ: Нет | our={our_prob:.2%} | implied={implied_prob:.2%} | value={value:+.2%}")

        # === Value для ФОРЫ ===
        handicap = predictions.get('handicap', {})
        home_handicap_odds = float(odds.get('handicap_home', 0))
        away_handicap_odds = float(odds.get('handicap_away', 0))
        
        if handicap.get('prediction', '').startswith('Ф1') and home_handicap_odds > 0:
            implied_prob = 1.0 / home_handicap_odds
            our_prob = handicap.get('confidence', 0)
            value = our_prob - implied_prob
            handicap['value'] = round(value, 4)
            handicap['is_value_bet'] = value > 0.05
            handicap['odds'] = round(home_handicap_odds, 2)
            logger.info(f"💎 Value фора: Ф1 | our={our_prob:.2%} | implied={implied_prob:.2%} | value={value:+.2%}")
        elif handicap.get('prediction', '').startswith('Ф2') and away_handicap_odds > 0:
            implied_prob = 1.0 / away_handicap_odds
            our_prob = handicap.get('confidence', 0)
            value = our_prob - implied_prob
            handicap['value'] = round(value, 4)
            handicap['is_value_bet'] = value > 0.05
            handicap['odds'] = round(away_handicap_odds, 2)
            logger.info(f"💎 Value фора: Ф2 | our={our_prob:.2%} | implied={implied_prob:.2%} | value={value:+.2%}")

        # Считаем общий value score
        all_values = [
            outcome.get('value', 0),
            total.get('value', 0),
            both.get('value', 0),
            handicap.get('value', 0)
        ]
        predictions['max_value'] = round(max(all_values), 4)
        predictions['avg_value'] = round(sum(all_values) / len(all_values), 4) if all_values else 0
        predictions['has_value_bet'] = any(v > 0.05 for v in all_values)
        
        # Собираем список value-рынков для публикации
        value_markets = []
        if outcome.get('is_value_bet'): value_markets.append('Исход')
        if total.get('is_value_bet'): value_markets.append('Тотал')
        if both.get('is_value_bet'): value_markets.append('ОЗ')
        if handicap.get('is_value_bet'): value_markets.append('Фора')
        predictions['value_markets'] = value_markets

        logger.info(f"📊 Value summary: max={predictions['max_value']:+.2%}, avg={predictions['avg_value']:+.2%}, value_bets={len(value_markets)}")

        return predictions