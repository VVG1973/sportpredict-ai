"""
Advanced Prediction Model - Multi-Output
Прогнозирует: исход, тотал, обе забьют, фора
"""
import logging
import json
import pickle
from pathlib import Path
from typing import Dict, Tuple, List, Optional
import numpy as np

logger = logging.getLogger(__name__)


class AdvancedPredictionModel:
    """
    Multi-output модель для прогнозирования футбольных матчей.
    Загружает ансамбль из 4 моделей: исход, тотал, ОЗ, фора.
    """
    
    def __init__(self, model_dir: str = "ml_models"):
        self.model_dir = Path(model_dir)
        self.models = None
        self.feature_cols = []
        self.accuracy = {}
        self.is_loaded = False
        
        self._load_model()
    
    def _load_model(self):
        """Загружает multi-output модель"""
        model_path = self.model_dir / "multi_output_model.pkl"
        meta_path = self.model_dir / "multi_output_model.meta.json"
        
        if not model_path.exists():
            logger.error(f"❌ Модель не найдена: {model_path}")
            return
        
        try:
            with open(model_path, "rb") as f:
                self.models = pickle.load(f)
            
            self.feature_cols = self.models.get('feature_cols', [])
            self.accuracy = self.models.get('accuracy', {})
            
            if meta_path.exists():
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                self.accuracy = meta.get("accuracy", self.accuracy)
            
            self.is_loaded = True
            logger.info(f"✅ Multi-Output модель загружена: {self.accuracy}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки модели: {e}")
            self.is_loaded = False
    
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
            try:
                features.append(float(value))
            except (ValueError, TypeError):
                features.append(0.0)
        
        return np.array(features).reshape(1, -1)
    
    def predict(self, match_data: Dict) -> Dict:
        """
        Делает прогнозы по всем рынкам.
        
        Returns:
            {
                "outcome": {"prediction": "H", "confidence": 0.72},
                "total": {"prediction": "ТБ 2.5", "confidence": 0.68},
                "both_scored": {"prediction": "Да", "confidence": 0.55},
                "handicap": {"prediction": "Ф1(-0.5)", "confidence": 0.74},
            }
        """
        if not self.is_loaded or self.models is None:
            logger.warning("⚠️ Модель не загружена")
            return self._fallback_prediction()
        
        try:
            features = self._extract_features(match_data)
            
            # === ИСХОД (H/D/A) ===
            outcome_model = self.models['outcome']
            outcome_probs = outcome_model.predict_proba(features)[0]
            outcome_idx = np.argmax(outcome_probs)
            outcome_map = {0: "H", 1: "D", 2: "A"}
            outcome_conf = float(outcome_probs[outcome_idx])
            
            # === ТОТАЛ (ТБ/ТМ 2.5) ===
            total_model = self.models['total']
            total_probs = total_model.predict_proba(features)[0]
            # total_probs[0] = ТМ, total_probs[1] = ТБ
            total_pred = "ТБ 2.5" if total_probs[1] > total_probs[0] else "ТМ 2.5"
            total_conf = float(max(total_probs))
            
            # === ОБЕ ЗАБЬЮТ ===
            both_model = self.models['both_scored']
            both_probs = both_model.predict_proba(features)[0]
            # both_probs[0] = Нет, both_probs[1] = Да
            both_pred = "Да" if both_probs[1] > both_probs[0] else "Нет"
            both_conf = float(max(both_probs))
            
            # === ФОРА (Ф1/Ф2) ===
            handicap_model = self.models['handicap']
            hand_probs = handicap_model.predict_proba(features)[0]
            # hand_probs[0] = Ф2, hand_probs[1] = Ф1
            hand_pred = "Ф1(-0.5)" if hand_probs[1] > hand_probs[0] else "Ф2(+0.5)"
            hand_conf = float(max(hand_probs))
            
            return {
                "outcome": {
                    "prediction": outcome_map[outcome_idx],
                    "confidence": outcome_conf,
                    "probabilities": {
                        "H": float(outcome_probs[0]),
                        "D": float(outcome_probs[1]),
                        "A": float(outcome_probs[2])
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
            return self._fallback_prediction()
    
    def _fallback_prediction(self) -> Dict:
        """Fallback при ошибке"""
        return {
            "outcome": {"prediction": "H", "confidence": 0.33, "probabilities": {"H": 0.33, "D": 0.33, "A": 0.33}},
            "total": {"prediction": "ТБ 2.5", "confidence": 0.5},
            "both_scored": {"prediction": "Да", "confidence": 0.5},
            "handicap": {"prediction": "Ф1(-0.5)", "confidence": 0.5},
        }
    
    def predict_with_value(self, match_data: Dict, min_odds: float = 1.5) -> Optional[Dict]:
        """Прогноз с value bet анализом"""
        predictions = self.predict(match_data)
        
        # Анализируем value для исхода
        outcome = predictions['outcome']
        odds_home = match_data.get('odds_home', 0) or match_data.get('B365H', 0)
        odds_draw = match_data.get('odds_draw', 0) or match_data.get('B365D', 0)
        odds_away = match_data.get('odds_away', 0) or match_data.get('B365A', 0)
        
        odds_map = {"H": odds_home, "D": odds_draw, "A": odds_away}
        current_odds = odds_map.get(outcome['prediction'], 0)
        
        if current_odds > 0:
            implied_prob = 1.0 / current_odds
            our_prob = outcome['confidence']
            value = our_prob - implied_prob
            
            outcome['value'] = value
            outcome['is_value_bet'] = value > 0.05
        
        return predictions