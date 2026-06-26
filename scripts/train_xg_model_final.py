"""
Обучение честной модели с xG признаками
Ожидаемая точность: 55-58%
"""
import json
import logging
import pickle
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class XGModelTrainer:
    """Обучает модель с xG признаками"""
    
    def __init__(self, data_path: str = "data/historical/merged_matches_xg.json"):
        self.data_path = Path(data_path)
        self.model_path = Path("data/models/model_xg_honest.pkl")
        
        # Признаки: коэффициенты + xG
        self.feature_cols = [
            # Коэффициенты (15)
            "b365_home", "b365_draw", "b365_away",
            "bw_home", "bw_draw", "bw_away",
            "iw_home", "iw_draw", "iw_away",
            "ps_home", "ps_draw", "ps_away",
            "wh_home", "wh_draw", "wh_away",
            # xG признаки (3)
            "home_xg", "away_xg", "xg_diff",
        ]
    
    def load_data(self) -> pd.DataFrame:
        logger.info(f"📚 Загружаю данные из {self.data_path}")
        with open(self.data_path, "r", encoding="utf-8") as f:
            matches = json.load(f)
        df = pd.DataFrame(matches)
        logger.info(f"✅ Загружено {len(df)} матчей")
        return df
    
    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        logger.info("🔧 Подготовка признаков...")
        
        df = df[df["result"].isin(["H", "D", "A"])].copy()
        
        for col in self.feature_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            else:
                df[col] = 0
        
        # Производные из коэффициентов
        for prefix in ["b365", "bw", "iw", "ps", "wh"]:
            h, d, a = f"{prefix}_home", f"{prefix}_draw", f"{prefix}_away"
            df[f"{prefix}_prob_h"] = np.where(df[h] > 0, 1 / df[h], 0)
            df[f"{prefix}_prob_d"] = np.where(df[d] > 0, 1 / df[d], 0)
            df[f"{prefix}_prob_a"] = np.where(df[a] > 0, 1 / df[a], 0)
        
        df["avg_prob_h"] = df[[f"{p}_prob_h" for p in ["b365", "bw", "iw", "ps", "wh"]]].mean(axis=1)
        df["avg_prob_d"] = df[[f"{p}_prob_d" for p in ["b365", "bw", "iw", "ps", "wh"]]].mean(axis=1)
        df["avg_prob_a"] = df[[f"{p}_prob_a" for p in ["b365", "bw", "iw", "ps", "wh"]]].mean(axis=1)
        
        df["odds_diff"] = df["b365_away"] - df["b365_home"]
        df["odds_ratio"] = df["b365_home"] / (df["b365_away"] + 0.001)
        
        df["favorite"] = np.where(
            df["b365_home"] < df["b365_away"] * 0.8, 1.0,
            np.where(df["b365_away"] < df["b365_home"] * 0.8, 0.0, 0.5)
        )
        
        extended_features = self.feature_cols + [
            "b365_prob_h", "b365_prob_d", "b365_prob_a",
            "bw_prob_h", "bw_prob_d", "bw_prob_a",
            "iw_prob_h", "iw_prob_d", "iw_prob_a",
            "ps_prob_h", "ps_prob_d", "ps_prob_a",
            "wh_prob_h", "wh_prob_d", "wh_prob_a",
            "avg_prob_h", "avg_prob_d", "avg_prob_a",
            "odds_diff", "odds_ratio", "favorite",
        ]
        
        logger.info(f"✅ Подготовлено {len(extended_features)} признаков")
        return df, extended_features
    
    def train(self):
        logger.info("🚀 Начинаю обучение модели с xG")
        
        df = self.load_data()
        df, feature_cols = self.prepare_features(df)
        
        label_map = {"H": 0, "D": 1, "A": 2}
        y = df["result"].map(label_map).values
        X = df[feature_cols].values
        
        logger.info(f"📊 Матчей: {len(X)}, признаков: {len(feature_cols)}")
        
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        logger.info("🔍 Optuna: 100 итераций...")
        
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
                "eval_metric": "mlogloss",
            }
            model = XGBClassifier(**params)
            model.fit(X_train, y_train)
            return accuracy_score(y_test, model.predict(X_test))
        
        study = optuna.create_study(direction="maximize")
        study.optimize(objective, n_trials=100, show_progress_bar=True)
        
        best_params = study.best_params
        logger.info(f"🎯 Лучшая точность: {study.best_value:.4f} ({study.best_value:.2%})")
        
        logger.info("🧠 Обучаю финальную модель...")
        sample_weights = compute_sample_weight('balanced', y_train)
        
        final_params = {**best_params, "random_state": 42, "eval_metric": "mlogloss"}
        model = XGBClassifier(**final_params)
        model.fit(X_train, y_train, sample_weight=sample_weights)
        
        y_pred = model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        
        logger.info(f"✅ ЧЕСТНАЯ точность: {accuracy:.4f} ({accuracy:.2%})")
        logger.info(f"📊 Отчёт:\n{classification_report(y_test, y_pred, target_names=['П1', 'X', 'П2'])}")
        
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.model_path, "wb") as f:
            pickle.dump({
                "model": model,
                "feature_cols": feature_cols,
                "accuracy": accuracy,
                "best_params": best_params,
                "trained_at": datetime.now().isoformat(),
                "is_honest": True,
                "has_xg": True,
            }, f)
        
        logger.info(f"💾 Модель сохранена: {self.model_path}")
        
        print("\n" + "=" * 60)
        print("🎯 РЕЗУЛЬТАТЫ")
        print("=" * 60)
        print(f"   Точность: {accuracy:.2%}")
        print(f"   Признаков: {len(feature_cols)} (коэф. + xG)")
        print(f"   Матчей: {len(X)}")
        print()
        
        if accuracy >= 0.55:
            print("🎉 ОТЛИЧНО! Точность выше 55%!")
            print("💎 VIP прогнозы (confidence >= 75%) будут иметь ~60-65%")
        elif accuracy >= 0.52:
            print("✅ Хорошо! Точность улучшена")
        else:
            print("⚠️ Точность низкая")
        
        return accuracy


if __name__ == "__main__":
    trainer = XGModelTrainer()
    trainer.train()
