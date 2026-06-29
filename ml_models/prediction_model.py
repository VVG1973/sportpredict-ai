"""
Prediction Model - обёртка для ML модели
Использует модель с реальными xG признаками (точность 59.01%)
"""
import logging
from typing import Dict
from ml_models.real_xg_model import RealXGModel

logger = logging.getLogger(__name__)


class PredictionModel:
    """Основной класс для прогнозирования матчей"""
    
    def __init__(self):
        self.model = RealXGModel()
        self.is_trained = self.model.is_loaded
        self.accuracy = self.model.accuracy
        
        if self.is_trained:
            logger.info(f"✅ PredictionModel инициализирован с точностью {self.accuracy:.2%}")
        else:
            logger.warning("⚠️ PredictionModel инициализирован без обученной модели")
    
    def predict(self, match_data: Dict = None, **kwargs) -> Dict:
        """
        Делает прогноз для матча.
        Поддерживает передачу как словаря (match_data), так и именованных аргументов (home_team=... и т.д.).
        """
        # Если данные переданы как именованные аргументы, собираем их в словарь
        if match_data is None:
            match_data = kwargs
        
        prediction, confidence, probabilities = self.model.predict(match_data)
        
        return {
            "prediction": prediction,
            "confidence": confidence,
            "probabilities": probabilities
        }
    
    def get_accuracy(self) -> float:
        return self.accuracy
