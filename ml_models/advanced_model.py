import json
import logging
from pathlib import Path
from typing import Dict, Optional
import numpy as np
import xgboost as xgb

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
        self._load_model()

    def _load_model(self):
        """Загружает XGBoost модели из JSON-файлов"""
        # Пробуем несколько путей (Railway Volume → локально)
        possible_paths = [
            Path("/app/data/ml_models/xgboost_models.meta.json"),  # Railway Volume
            Path("ml_models/xgboost_models.meta.json"),              # Локально
            Path("/app/ml_models/xgboost_models.meta.json"),       # Railway локально
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
            self.accuracy = meta.get("accuracy", {})  
            self.feature_cols = meta.get("feature_cols", [])
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
                value = match_data.get("odds_home", 0)
            if value == 0 and col == "B365D":
                value = match_data.get("odds_draw", 0)
            if value == 0 and col == "B365A":
                value = match_data.get("odds_away", 0)
            try:
                features.append(float(value))
            except (ValueError, TypeError):
                features.append(0.0)
        return np.array(features).reshape(1, -1)

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

    def predict_with_value(self, match_data: Dict, min_odds: float = 1.5) -> Optional[Dict]:
        """Прогноз с value bet анализом"""
        predictions = self.predict(match_data)

        # Анализируем value для исхода
        outcome = predictions.get('outcome', {})
        odds_home = match_data.get('odds_home', 0) or match_data.get('B365H', 0)
        odds_draw = match_data.get('odds_draw', 0) or match_data.get('B365D', 0)
        odds_away = match_data.get('odds_away', 0) or match_data.get('B365A', 0)

        odds_map = {"H": odds_home, "D": odds_draw, "A": odds_away}
        current_odds = odds_map.get(outcome.get('prediction', 'H'), 0)

        if current_odds > 0:
            implied_prob = 1.0 / current_odds
            our_prob = outcome.get('confidence', 0)
            value = our_prob - implied_prob
            outcome['value'] = value
            outcome['is_value_bet'] = value > 0.05

        return predictions