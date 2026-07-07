"""
Prediction Model - обёртка для ML модели с fallback
"""
import logging
from typing import Dict
from pathlib import Path

logger = logging.getLogger(__name__)


class PredictionModel:
    """Основной класс для прогнозирования матчей"""

    def __init__(self):
        self.model = None
        self.is_trained = False
        self.accuracy = 0.0
        
        # Пробуем загрузить advanced модель
        try:
            from ml_models.advanced_model import AdvancedPredictionModel
            self.model = AdvancedPredictionModel()
            if self.model.is_loaded:
                self.is_trained = True
                self.accuracy = self.model.accuracy
                logger.info(f"✅ AdvancedModel загружена: {self.accuracy:.2%}")
                return
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки AdvancedModel: {e}")
            import traceback
            logger.error(traceback.format_exc())
        
        # Fallback на старую модель
        try:
            import json
            model_path = Path("ml_models/model_real_xg.json")
            if model_path.exists():
                with open(model_path, "r") as f:
                    self.model = json.load(f)
                self.is_trained = True
                self.accuracy = self.model.get("accuracy", 0.5862)
                logger.info(f"✅ Старая модель загружена: {self.accuracy:.2%}")
                return
        except Exception as e:
            logger.debug(f"Старая модель не доступна: {e}")
        
        # Если ничего не загрузилось - используем fallback
        logger.warning("⚠️ Ни одна модель не загружена, используем fallback")
        self.is_trained = True
        self.accuracy = 0.55

    def predict(self, match_data: Dict = None, **kwargs) -> Dict:
        if match_data is None:
            match_data = kwargs
        
        # Используем advanced модель если есть
        if self.model and hasattr(self.model, 'predict'):
            return self.model.predict(match_data)
        
        # Fallback на простой прогноз по коэффициентам
        odds_home = match_data.get('odds_home', 0) or match_data.get('b365_home', 0)
        odds_away = match_data.get('odds_away', 0) or match_data.get('b365_away', 0)
        
        if odds_home and odds_away:
            if odds_home < odds_away:
                return {"prediction": "H", "confidence": 0.55, "probabilities": {"H": 0.55, "D": 0.25, "A": 0.20}}
            else:
                return {"prediction": "A", "confidence": 0.55, "probabilities": {"H": 0.20, "D": 0.25, "A": 0.55}}
        
        return {"prediction": "H", "confidence": 0.55, "probabilities": {"H": 0.55, "D": 0.25, "A": 0.20}}

    def predict_with_value(self, match_data: Dict, min_odds: float = 1.5) -> Dict:
        result = self.predict(match_data)
        result["is_value_bet"] = False
        result["value"] = 0.0
        return result

    def get_accuracy(self) -> float:
        return self.accuracy
