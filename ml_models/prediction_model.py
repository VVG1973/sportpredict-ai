"""
Prediction Model - обёртка для ML модели
Использует AdvancedPredictionModel (ансамбль + калибровка)
"""
import logging
from typing import Dict
from ml_models.advanced_model import AdvancedPredictionModel

logger = logging.getLogger(__name__)


class PredictionModel:
    """Основной класс для прогнозирования матчей"""

    def __init__(self):
        self.model = AdvancedPredictionModel()
        self.is_trained = self.model.is_loaded
        self.accuracy = self.model.accuracy

        if self.is_trained:
            logger.info(f"✅ PredictionModel инициализирован с точностью {self.accuracy:.2%}")
        else:
            logger.warning("⚠️ PredictionModel инициализирован без обученной модели")

    def predict(self, match_data: Dict = None, **kwargs) -> Dict:
        """
        Делает прогноз для матча.
        """
        if match_data is None:
            match_data = kwargs

        prediction, confidence, probabilities = self.model.predict(match_data)

        return {
            "prediction": prediction,
            "confidence": confidence,
            "probabilities": probabilities
        }

    def predict_with_value(self, match_data: Dict, min_odds: float = 1.5) -> Dict:
        """
        Прогноз с поиском value bet.
        """
        return self.model.predict_with_value(match_data, min_odds)

    def get_accuracy(self) -> float:
        return self.accuracy