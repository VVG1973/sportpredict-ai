"""
Prediction Model - обёртка для ML модели
Использует модель с синтетическими xG признаками (точность 59.83%)
"""
import logging
from typing import Dict, Tuple
from ml_models.synthetic_xg_model import SyntheticXGModel

logger = logging.getLogger(__name__)


class PredictionModel:
    """Основной класс для прогнозирования матчей"""
    
    def __init__(self):
        self.model = SyntheticXGModel()
        self.is_trained = self.model.is_loaded
        self.accuracy = self.model.accuracy
        
        if self.is_trained:
            logger.info(f"✅ PredictionModel инициализирован с точностью {self.accuracy:.2%}")
        else:
            logger.warning("⚠️ PredictionModel инициализирован без обученной модели")
    
    def predict(self, match_data: Dict) -> Dict:
        """
        Делает прогноз для матча
        
        Args:
            match_data: Словарь с данными матча
        
        Returns:
            Dict с прогнозом, уверенностью и вероятностями
        """
        prediction, confidence, probabilities = self.model.predict(match_data)
        
        return {
            "prediction": prediction,
            "confidence": confidence,
            "probabilities": probabilities
        }
    
    def get_accuracy(self) -> float:
        """Возвращает точность модели"""
        return self.accuracy
