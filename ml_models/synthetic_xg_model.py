"""
Модель с синтетическими xG признаками
Точность: 59.83% на тестовой выборке
42 признака: коэффициенты букмекеров + синтетический xG
"""
import pickle
import logging
from pathlib import Path
import numpy as np
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


class SyntheticXGModel:
    """Обёртка для обученной модели с синтетическими xG"""
    
    def __init__(self, model_path: str = "ml_models/model_synthetic_xg.pkl"):
        self.model_path = Path(model_path)
        self.model = None
        self.feature_cols = None
        self.accuracy = 0.0
        self.is_loaded = False
        
        self._load_model()
    
    def _load_model(self):
        """Загружает обученную модель из файла"""
        # Пробуем несколько возможных путей
        possible_paths = [
            Path(self.model_path),
            Path("ml_models/model_synthetic_xg.pkl"),
            Path("/app/ml_models/model_synthetic_xg.pkl"),
            Path("data/models/model_synthetic_xg.pkl"),
        ]
        
        loaded_path = None
        for path in possible_paths:
            if path.exists():
                loaded_path = path
                logger.info(f"✅ Модель найдена: {path}")
                break
        
        if not loaded_path:
            logger.error(f"❌ Модель не найдена ни в одном из путей:")
            for p in possible_paths:
                logger.error(f"   - {p}")
            return
        
        try:
            with open(loaded_path, "rb") as f:
                data = pickle.load(f)
        
        try:
            with open(self.model_path, "rb") as f:
                data = pickle.load(f)
            
            self.model = data["model"]
            self.feature_cols = data["feature_cols"]
            self.accuracy = data["accuracy"]
            self.is_loaded = True
            
            logger.info(f"✅ Модель загружена: {self.model_path}")
            logger.info(f"   Точность: {self.accuracy:.2%}")
            logger.info(f"   Признаков: {len(self.feature_cols)}")
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки модели: {e}")
    
    def predict(self, match_data: Dict) -> Tuple[str, float, Dict[str, float]]:
        """
        Делает прогноз для матча
        
        Args:
            match_data: Словарь с данными матча (коэффициенты, статистика)
        
        Returns:
            Tuple[str, float, Dict]: (прогноз, уверенность, вероятности)
        """
        if not self.is_loaded:
            logger.warning("⚠️ Модель не загружена, возвращаю случайный прогноз")
            return "H", 0.33, {"H": 0.33, "D": 0.33, "A": 0.33}
        
        # Извлекаем признаки
        features = []
        for col in self.feature_cols:
            value = match_data.get(col, 0)
            try:
                features.append(float(value))
            except (ValueError, TypeError):
                features.append(0.0)
        
        # Делаем прогноз
        features_array = np.array(features).reshape(1, -1)
        
        try:
            prediction_idx = self.model.predict(features_array)[0]
            probabilities = self.model.predict_proba(features_array)[0]
            
            # Маппинг индексов на результаты
            label_map = {0: "H", 1: "D", 2: "A"}
            prediction = label_map[prediction_idx]
            confidence = float(probabilities[prediction_idx])
            
            prob_dict = {
                "H": float(probabilities[0]),
                "D": float(probabilities[1]),
                "A": float(probabilities[2])
            }
            
            return prediction, confidence, prob_dict
        
        except Exception as e:
            logger.error(f"❌ Ошибка прогноза: {e}")
            return "H", 0.33, {"H": 0.33, "D": 0.33, "A": 0.33}
    
    def get_accuracy(self) -> float:
        """Возвращает точность модели"""
        return self.accuracy
