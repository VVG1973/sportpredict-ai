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

        if not self.is_trained:
            logger.warning("⚠️ Модель не загружена, пробуем обучить...")
            self._train_on_railway()
            
            self.model = AdvancedPredictionModel()
            self.is_trained = self.model.is_loaded
            self.accuracy = self.model.accuracy

        if self.is_trained:
            logger.info(f"✅ PredictionModel инициализирован с точностью {self.accuracy:.2%}")
        else:
            logger.warning("⚠️ PredictionModel инициализирован без обученной модели")

        def _train_on_railway(self):
        """Обучает модель на Railway если данных достаточно"""
        # Пробуем разные пути
        possible_paths = [
            "data/historical/football_data_matches.csv",
            "data/football_data_matches.csv",
            "/app/data/historical/football_data_matches.csv",
            "/app/data/football_data_matches.csv"
        ]
        
        logger.info(f"🔍 Текущая директория: {os.getcwd()}")
        logger.info(f"🔍 Содержимое текущей директории: {os.listdir('.')}")
        
        data_path = None
        for path in possible_paths:
            exists = os.path.exists(path)
            logger.info(f"   Проверяем {path}: {'✅' if exists else '❌'}")
            if exists:
                data_path = path
                break
        
        if not data_path:
            logger.error("❌ Данные не найдены")
            # Покажем всё в data/
            if os.path.exists("data"):
                for root, dirs, files in os.walk("data"):
                    for f in files:
                        logger.info(f"   Файл: {os.path.join(root, f)}")
            return
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
