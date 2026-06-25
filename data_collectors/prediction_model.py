import logging
import numpy as np
from config import settings

logger = logging.getLogger(__name__)

class PredictionModel:
    def __init__(self):
        self.weights = {
            "team_stats": 0.80, "player_perf": 0.60, "h2h": 0.50,
            "current_form": 0.75, "squad_changes": 0.40,
            "psychology": 0.30, "weather": 0.20, "referee": 0.15
        }

    def _normalize_weights(self):
        total = sum(self.weights.values())
        return {k: v / total for k, v in self.weights.items()}

    async def predict(self, match_data: dict) -> dict:
        """
        Базовая логика взвешенного прогноза.
        В продакшене замените на model.predict() из TensorFlow/Keras.
        """
        w = self._normalize_weights()
        
        # Пример извлечения признаков (замените на реальный парсинг)
        features = {
            "team_stats": match_data.get("home_form", 0.5) - match_data.get("away_form", 0.4),
            "player_perf": 0.05,
            "h2h": match_data.get("h2h_home_win", 0.5),
            "current_form": match_data.get("home_streak", 0) * 0.1,
            "squad_changes": -0.2 if match_data.get("key_injuries", False) else 0.0,
            "psychology": 0.0, "weather": 0.0, "referee": 0.0
        }

        raw_score = sum(features[k] * w[k] for k in w)
        confidence = min(abs(raw_score) * 2.5, 0.98)
        prediction = "HOME" if raw_score > 0.05 else ("AWAY" if raw_score < -0.05 else "DRAW")

        return {
            "match": match_data,
            "prediction": prediction,
            "confidence": confidence,
            "odds_est": self._est_odds(prediction)
        }

    def _est_odds(self, pred):
        return {"HOME": 1.75, "AWAY": 3.20, "DRAW": 3.40}.get(pred, 2.50)