"""
Prediction Model - обёртка для ML модели
"""
import logging
import os
import subprocess
from typing import Dict
from ml_models.advanced_model import AdvancedPredictionModel

logger = logging.getLogger(__name__)


class PredictionModel:
    """Основной класс для прогнозирования матчей"""

    def __init__(self):
        self.model = AdvancedPredictionModel()
        self.is_trained = self.model.is_loaded
        self.accuracy = self.model.accuracy

        # Если модель не загрузилась — обучаем
        if not self.is_trained:
            logger.warning("⚠️ Модель не загружена, пробуем обучить...")
            self._train_on_railway()
            
            # Перезагружаем
            self.model = AdvancedPredictionModel()
            self.is_trained = self.model.is_loaded
            self.accuracy = self.model.accuracy

        if self.is_trained:
            logger.info(f"✅ PredictionModel инициализирован с точностью {self.accuracy:.2%}")
        else:
            logger.warning("⚠️ PredictionModel инициализирован без обученной модели")

    def _train_on_railway(self):
        """Обучает модель на Railway если данных достаточно"""
        try:
            data_path = "data/historical/football_data_matches.csv"
            if not os.path.exists(data_path):
                logger.error(f"❌ Данные не найдены: {data_path}")
                return
            
            logger.info("🏋️ Запуск обучения модели на Railway...")
            result = subprocess.run(
                ["python", "scripts/prepare_and_train.py"],
                capture_output=True,
                text=True,
                timeout=900  # 15 минут
            )
            
            if result.returncode == 0:
                logger.info("✅ Модель успешно обучена на Railway")
            else:
                logger.error(f"❌ Ошибка обучения: {result.stderr[:500]}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка при обучении: {e}")

    def predict(self, match_data: Dict = None, **kwargs) -> Dict:
        if match_data is None:
            match_data = kwargs

        prediction, confidence, probabilities = self.model.predict(match_data)

        return {
            "prediction": prediction,
            "confidence": confidence,
            "probabilities": probabilities
        }

    def predict_with_value(self, match_data: Dict, min_odds: float = 1.5) -> Dict:
        return self.model.predict_with_value(match_data, min_odds)

    def get_accuracy(self) -> float:
        return self.accuracy