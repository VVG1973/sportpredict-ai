"""
Advanced Prediction Model
Ансамблевая модель с калибровкой вероятностей
"""
import logging
import json
import pickle
from pathlib import Path
from typing import Dict, Tuple, List, Optional
import numpy as np

from xgboost import XGBClassifier
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss

logger = logging.getLogger(__name__)


class AdvancedPredictionModel:
    """
    Ансамблевая модель для прогнозирования футбольных матчей.
    
    Использует:
    - XGBoost (основная модель)
    - RandomForest (для устойчивости)
    - LogisticRegression (для калибровки вероятностей)
    - Калибровку через isotonic regression
    """
    
    # Ключевые признаки (расширенный набор)
    FEATURE_COLS = [
        # === xG признаки ===
        'home_xg_last5', 'away_xg_last5',
        'home_xg_against_last5', 'away_xg_against_last5',
        'home_xg_diff_last5', 'away_xg_diff_last5',
        
        # === Форма ===
        'home_points_last5', 'away_points_last5',
        'home_points_last3', 'away_points_last3',
        'home_goals_scored_last5', 'away_goals_scored_last5',
        'home_goals_against_last5', 'away_goals_against_last5',
        
        # === Коэффициенты букмекеров ===
        'odds_home', 'odds_draw', 'odds_away',
        'odds_home_implied_prob', 'odds_draw_implied_prob', 'odds_away_implied_prob',
        'odds_value_home', 'odds_value_draw', 'odds_value_away',
        
        # === H2H ===
        'h2h_home_wins', 'h2h_draws', 'h2h_away_wins',
        'h2h_home_goals', 'h2h_away_goals',
        
        # === Турнирное положение ===
        'home_league_position', 'away_league_position',
        'home_points_total', 'away_points_total',
        'position_diff',
        
        # === Домашнее преимущество ===
        'home_win_rate_season', 'away_win_rate_season',
        'home_xg_season_avg', 'away_xg_season_avg',
        
        # === Статистика матчей ===
        'home_possession_avg', 'away_possession_avg',
        'home_shots_avg', 'away_shots_avg',
        'home_shots_on_target_avg', 'away_shots_on_target_avg',
        'home_corners_avg', 'away_corners_avg',
        
        # === Контекст ===
        'days_since_last_match_home', 'days_since_last_match_away',
        'is_derby', 'is_top_vs_bottom',
        'home_rest_days', 'away_rest_days',
        
        # === Рыночные сигналы ===
        'odds_movement_home', 'odds_movement_away',
        'betting_volume_home', 'betting_volume_away',
    ]
    
    def __init__(self, model_dir: str = "ml_models"):
        self.model_dir = Path(model_dir)
        self.model = None
        self.calibrator = None
        self.feature_cols = self.FEATURE_COLS
        self.accuracy = 0.0
        self.is_loaded = False
        self.calibration_quality = 0.0
        
        self._load_model()
    
    def _load_model(self):
        """Загружает обученную модель и калибратор"""
        model_path = self.model_dir / "advanced_model.pkl"
        calibrator_path = self.model_dir / "advanced_model_calibrator.pkl"
        meta_path = self.model_dir / "advanced_model.meta.json"
        
        if not model_path.exists():
            logger.error(f"❌ Модель не найдена: {model_path}")
            return
        
        try:
            # Загружаем модель
            with open(model_path, "rb") as f:
                self.model = pickle.load(f)
            
            # Загружаем калибратор (если есть)
            if calibrator_path.exists():
                with open(calibrator_path, "rb") as f:
                    self.calibrator = pickle.load(f)
            
            # Загружаем метаданные
            if meta_path.exists():
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                self.accuracy = meta.get("accuracy", 0.0)
                self.calibration_quality = meta.get("calibration_quality", 0.0)
                self.feature_cols = meta.get("feature_cols", self.FEATURE_COLS)
            
            self.is_loaded = True
            logger.info(f"✅ AdvancedModel загружена: точность {self.accuracy:.2%}, калибровка {self.calibration_quality:.3f}")
            
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки модели: {e}")
            self.is_loaded = False
    
    def _extract_features(self, match_data: Dict) -> np.ndarray:
        """Извлекает признаки из данных матча"""
        features = []
        
        for col in self.feature_cols:
            value = match_data.get(col, 0)
            try:
                features.append(float(value))
            except (ValueError, TypeError):
                features.append(0.0)
        
        return np.array(features).reshape(1, -1)
    
    def predict(self, match_data: Dict) -> Tuple[str, float, Dict[str, float]]:
        """
        Делает прогноз с калибровкой вероятностей.
        
        Returns:
            prediction: "H", "D" или "A"
            confidence: откалиброванная уверенность (0-1)
            probabilities: {"H": p, "D": p, "A": p}
        """
        if not self.is_loaded or self.model is None:
            logger.warning("⚠️ Модель не загружена")
            return "H", 0.33, {"H": 0.33, "D": 0.33, "A": 0.33}
        
        try:
            features = self._extract_features(match_data)
            
            # Базовые вероятности от ансамбля
            if hasattr(self.model, 'predict_proba'):
                base_probs = self.model.predict_proba(features)[0]
            else:
                # Fallback для моделей без predict_proba
                pred_idx = self.model.predict(features)[0]
                base_probs = np.zeros(3)
                base_probs[pred_idx] = 1.0
            
            # Калибровка вероятностей (если калибратор загружен)
            if self.calibrator is not None:
                calibrated_probs = self.calibrator.predict_proba(features)[0]
                # Взвешенное среднее: 70% калиброванные + 30% базовые
                # Это предотвращает переусреднение
                probs = 0.7 * calibrated_probs + 0.3 * base_probs
            else:
                probs = base_probs
            
            # Нормализация (чтобы сумма = 1)
            probs = probs / probs.sum()
            
            label_map = {0: "H", 1: "D", 2: "A"}
            prediction_idx = np.argmax(probs)
            prediction = label_map[prediction_idx]
            confidence = float(probs[prediction_idx])
            
            # Фильтр: если confidence < 0.55, считаем прогноз ненадёжным
            if confidence < 0.55:
                logger.info(f"⚠️ Низкая уверенность ({confidence:.2%}), прогноз может быть неточным")
            
            prob_dict = {
                "H": float(probs[0]),
                "D": float(probs[1]),
                "A": float(probs[2])
            }
            
            return prediction, confidence, prob_dict
            
        except Exception as e:
            logger.error(f"❌ Ошибка прогноза: {e}")
            return "H", 0.33, {"H": 0.33, "D": 0.33, "A": 0.33}
    
    def predict_with_value(self, match_data: Dict, min_odds: float = 1.5) -> Optional[Dict]:
        """
        Прогноз с поиском value bet (ставок с перевесом).
        
        Value bet = когда наша вероятность > implied probability букмекера
        """
        prediction, confidence, probs = self.predict(match_data)
        
        # Получаем коэффициенты
        odds_home = match_data.get('odds_home', 0)
        odds_draw = match_data.get('odds_draw', 0)
        odds_away = match_data.get('odds_away', 0)
        
        odds_map = {"H": odds_home, "D": odds_draw, "A": odds_away}
        current_odds = odds_map.get(prediction, 0)
        
        if current_odds <= 0:
            return None
        
        # Рассчитываем value
        implied_prob = 1.0 / current_odds
        our_prob = probs[prediction]
        
        value = our_prob - implied_prob
        edge = value / implied_prob if implied_prob > 0 else 0
        
        return {
            "prediction": prediction,
            "confidence": confidence,
            "odds": current_odds,
            "our_probability": our_prob,
            "implied_probability": implied_prob,
            "value": value,
            "edge_percent": edge * 100,
            "is_value_bet": value > 0.05 and confidence > 0.55,  # 5% перевеса и 55% уверенность
            "recommended_stake": "small" if edge < 0.1 else "medium" if edge < 0.2 else "large"
        }
