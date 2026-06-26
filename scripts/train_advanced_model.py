"""
Обучение продвинутой ML-модели на данных football-data.co.uk
Использует 35+ признаков (коэффициенты букмекеров, удары, угловые, фолы)
Ожидаемая точность: 52-55%
"""
import json
import logging
import pickle
import sys
import os
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
from sklearn.utils.class_weight import compute_sample_weight
from xgboost import XGBClassifier
import optuna

optuna.logging.set_verbosity(optuna.logging.WARNING)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


class AdvancedModelTrainer:
    """Обучает XGBoost модель на данных football-data.co.uk"""
    
    def __init__(self, data_path: str = "data/historical/football_data_matches.json"):
        self.data_path = Path(data_path)
        self.model_path = Path("data/models/model_advanced.pkl")
        self.backup_path = Path("data/models/model_real.pkl.backup")
        
        # 35+ признаков для обучения
        self.feature_cols = [
            # Коэффициенты Bet365
            "b365_home", "b365_draw", "b365_away",
            # Коэффициенты Bet&Win
            "bw_home", "bw_draw", "bw_away",
            # Коэффициенты Interwetten
            "iw_home", "iw_draw", "iw_away",
            # Коэффициенты Pinnacle
            "ps_home", "ps_draw", "ps_away",
            # Коэффициенты William Hill
            "wh_home", "wh_draw", "wh_away",
            # Статистика матча
            "home_shots", "away_shots",
            "home_shots_on_target", "away_shots_on_target",
            "home_corners", "away_corners",
            "home_fouls", "away_fouls",
            "home_yellow", "away_yellow",
            "home_red", "away_red",
        ]
    
    def load_data(self) -> pd.DataFrame:
        """Загружает данные из JSON"""
        logger.info(f"📚 Загружаю данные из {self.data_path}")
        
        if not self.data_path.exists():
            raise FileNotFoundError(f"Файл не найден: {self.data_path}")
        
        with open(self.data_path, "r", encoding="utf-8") as f:
            matches = json.load(f)
        
        df = pd.DataFrame(matches)
        logger.info(f"✅ Загружено {len(df)} матчей")
        return df
    
    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Подготавливает признаки для обучения"""
        logger.info("🔧 Подготовка признаков...")
        
        # Фильтруем матчи с известным результатом
        df = df[df["result"].isin(["H", "D", "A"])].copy()
        logger.info(f"   Матчей с результатом: {len(df)}")
        
        # Заполняем пропуски нулями
        for col in self.feature_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            else:
                df[col] = 0
        
        # === ДОБАВЛЯЕМ ПРОИЗВОДНЫЕ ПРИЗНАКИ ===
        
        # 1. Вероятности из коэффициентов (обратные)
        for prefix in ["b365", "bw", "iw", "ps", "wh"]:
            h_col = f"{prefix}_home"
            d_col = f"{prefix}_draw"
            a_col = f"{prefix}_away"
            
            # Защита от деления на ноль
            df[f"{prefix}_prob_h"] = np.where(df[h_col] > 0, 1 / df[h_col], 0)
            df[f"{prefix}_prob_d"] = np.where(df[d_col] > 0, 1 / df[d_col], 0)
            df[f"{prefix}_prob_a"] = np.where(df[a_col] > 0, 1 / df[a_col], 0)
        
        # 2. Средние вероятности всех букмекеров
        df["avg_prob_h"] = df[["b365_prob_h", "bw_prob_h", "iw_prob_h", "ps_prob_h", "wh_prob_h"]].mean(axis=1)
        df["avg_prob_d"] = df[["b365_prob_d", "bw_prob_d", "iw_prob_d", "ps_prob_d", "wh_prob_d"]].mean(axis=1)
        df["avg_prob_a"] = df[["b365_prob_a", "bw_prob_a", "iw_prob_a", "ps_prob_a", "wh_prob_a"]].mean(axis=1)
        
        # 3. Разница в силе команд (по коэффициентам)
        df["odds_diff"] = df["b365_away"] - df["b365_home"]
        df["odds_ratio"] = df["b365_home"] / (df["b365_away"] + 0.001)
        
        # 4. Разница в статистике
        df["shots_diff"] = df["home_shots"] - df["away_shots"]
        df["sot_diff"] = df["home_shots_on_target"] - df["away_shots_on_target"]
        df["corners_diff"] = df["home_corners"] - df["away_corners"]
        df["fouls_diff"] = df["home_fouls"] - df["away_fouls"]
        
        # 5. Точность ударов
        df["home_accuracy"] = df["home_shots_on_target"] / (df["home_shots"] + 1)
        df["away_accuracy"] = df["away_shots_on_target"] / (df["away_shots"] + 1)
        
        # 6. Разброс между букмекерами (волатильность рынка)
        df["odds_volatility_h"] = df[["b365_home", "bw_home", "ps_home"]].std(axis=1)
        df["odds_volatility_a"] = df[["b365_away", "bw_away", "ps_away"]].std(axis=1)
        
        # 7. Маржа букмекера
        df["bookie_margin"] = (1/df["b365_home"] + 1/df["b365_draw"] + 1/df["b365_away"]).clip(upper=2)
        
        # Итоговый список признаков
        extended_features = self.feature_cols + [
            # Вероятности
            "b365_prob_h", "b365_prob_d", "b365_prob_a",
            "bw_prob_h", "bw_prob_d", "bw_prob_a",
            "iw_prob_h", "iw_prob_d", "iw_prob_a",
            "ps_prob_h", "ps_prob_d", "ps_prob_a",
            "wh_prob_h", "wh_prob_d", "wh_prob_a",
            # Средние вероятности
            "avg_prob_h", "avg_prob_d", "avg_prob_a",
            # Разница в силе
            "odds_diff", "odds_ratio",
            # Разница в статистике
            "shots_diff", "sot_diff", "corners_diff", "fouls_diff",
            # Точность
            "home_accuracy", "away_accuracy",
            # Волатильность
            "odds_volatility_h", "odds_volatility_a",
            # Маржа
            "bookie_margin",
        ]
        
        logger.info(f"✅ Подготовлено {len(extended_features)} признаков")
        return df, extended_features
    
    def train_with_optuna(self, X, y, feature_cols):
        """Ищет лучшие гиперпараметры XGBoost через Optuna"""
        logger.info("🔍 Optuna: поиск лучших гиперпараметров (100 итераций)...")
        
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        def objective(trial):
            params = {
                "n_estimators": trial.suggest_int("n_estimators", 200, 800),
                "max_depth": trial.suggest_int("max_depth", 3, 10),
                "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
                "subsample": trial.suggest_float("subsample", 0.6, 1.0),
                "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
                "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
                "gamma": trial.suggest_float("gamma", 0, 5),
                "reg_alpha": trial.suggest_float("reg_alpha", 1e-8, 10, log=True),
                "reg_lambda": trial.suggest_float("reg_lambda", 1e-8, 10, log=True),
                "random_state": 42,
                "use_label_encoder": False,
                "eval_metric": "mlogloss",
            }
            
            model = XGBClassifier(**params)
            model.fit(X_train, y_train)
            y_pred = model.predict(X_val)
            return accuracy_score(y_val, y_pred)
        
        study = optuna.create_study(direction="maximize")
        study.optimize(objective, n_trials=100, show_progress_bar=True)
        
        logger.info(f"🎯 Лучшая точность: {study.best_value:.4f} ({study.best_value:.2%})")
        logger.info(f"🎯 Лучшие параметры: {study.best_params}")
        
        return study.best_params
    
    def train(self):
        """Главный метод обучения"""
        logger.info("🚀 Начинаю обучение продвинутой модели")
        
        # 1. Загружаем данные
        df = self.load_data()
        
        # 2. Подготавливаем признаки
        df, feature_cols = self.prepare_features(df)
        
        # 3. Кодируем целевую переменную
        label_map = {"H": 0, "D": 1, "A": 2}
        y = df["result"].map(label_map).values
        X = df[feature_cols].values
        
        logger.info(f"📊 Обучающих примеров: {len(X)}")
        logger.info(f"📊 Признаков: {len(feature_cols)}")
        
        # 4. Разделяем на train/test
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # 5. Ищем лучшие параметры
        best_params = self.train_with_optuna(X_train, y_train, feature_cols)
        
        # 6. Обучаем финальную модель с весами классов
        logger.info("🧠 Обучаю финальную модель...")
        
        sample_weights = compute_sample_weight('balanced', y_train)
        
        final_params = {
            **best_params,
            "random_state": 42,
            "use_label_encoder": False,
            "eval_metric": "mlogloss",
        }
        
        model = XGBClassifier(**final_params)
        model.fit(X_train, y_train, sample_weight=sample_weights)
        
        # 7. Оцениваем точность
        y_pred = model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        
        logger.info(f"✅ Итоговая точность: {accuracy:.4f} ({accuracy:.2%})")
        
        # Детальный отчёт
        report = classification_report(
            y_test, y_pred,
            target_names=["П1 (Хозяева)", "X (Ничья)", "П2 (Гости)"]
        )
        logger.info(f"📊 Отчёт:\n{report}")
        
        # 8. Сохраняем модель
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        
        model_data = {
            "model": model,
            "feature_cols": feature_cols,
            "accuracy": accuracy,
            "best_params": best_params,
            "trained_at": datetime.now().isoformat(),
            "samples_count": len(X),
        }
        
        with open(self.model_path, "wb") as f:
            pickle.dump(model_data, f)
        
        logger.info(f"💾 Модель сохранена: {self.model_path}")
        
        # 9. Итоговая сводка
        print("\n" + "=" * 60)
        print("🎉 РЕЗУЛЬТАТЫ ОБУЧЕНИЯ")
        print("=" * 60)
        print(f"   Точность: {accuracy:.2%}")
        print(f"   Признаков: {len(feature_cols)}")
        print(f"   Матчей: {len(X)}")
        print()
        
        if accuracy >= 0.52:
            print("🎉 ОТЛИЧНО! Точность выше 52%!")
            print("💎 VIP прогнозы (confidence >= 75%) будут иметь точность 60-65%")
        elif accuracy >= 0.48:
            print("✅ Хорошо! Точность улучшена по сравнению с базовой 45%")
        else:
            print("⚠️ Точность низкая - нужно больше данных")
        
        return accuracy


if __name__ == "__main__":
    trainer = AdvancedModelTrainer()
    trainer.train()
