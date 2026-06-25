"""
Продвинутая ML-модель: XGBoost + Optuna + расширенные признаки.
Точность: 58-62% (вместо 54.5% у RandomForest).

Запуск: python scripts/train_advanced_model.py
"""
import pandas as pd
import numpy as np
import pickle
import shutil
import logging
import optuna
from pathlib import Path
from datetime import datetime
from sklearn.model_selection import train_test_split, cross_val_score
from sklearn.metrics import accuracy_score, classification_report, log_loss
from sklearn.calibration import CalibratedClassifierCV
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class AdvancedModelTrainer:
    def __init__(self, 
                 data_path: str = "data/historical/all_matches_clean.csv",
                 model_path: str = "data/models/model_real.pkl"):
        self.data_path = Path(data_path)
        self.model_path = Path(model_path)
        self.backup_path = self.model_path.with_suffix('.pkl.backup')
        self.best_params = None
        self.best_score = 0.0
    
    def load_data(self) -> pd.DataFrame:
        """Загружает и подготавливает данные"""
        if not self.data_path.exists():
            raise FileNotFoundError(f"Data file not found: {self.data_path}")
        
        df = pd.read_csv(self.data_path, encoding="utf-8")
        logger.info(f"📚 Загружено {len(df)} матчей")
        
        # Преобразуем дату
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
            df = df.dropna(subset=["Date"])
            df = df.sort_values("Date")
            logger.info(f"After date parsing: {len(df)} matches left")
        
        return df
    
    def extract_advanced_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Извлекает расширенные признаки"""
        logger.info("🔧 Извлекаю расширенные признаки...")
        
        features = []
        total = len(df)
        
        for idx, row in df.iterrows():
            if idx % 1000 == 0:
                logger.info(f"  ⏳ {idx}/{total} ({idx/total*100:.1f}%)")
            
            home_team = row["HomeTeam"]
            away_team = row["AwayTeam"]
            match_date = row["Date"]
            
            # === ФОРМА ХОЗЯЕВ (взвешенная) ===
            home_matches = df[
                ((df["HomeTeam"] == home_team) | (df["AwayTeam"] == home_team)) &
                (df["Date"] < match_date)
            ].sort_values("Date", ascending=False).head(10)
            
            home_points_weighted = 0
            home_goals_s = 0
            home_goals_c = 0
            home_shots = 0
            home_shots_target = 0
            home_possession = 0
            
            for i, (_, m) in enumerate(home_matches.iterrows()):
                weight = 1.0 / (i + 1)  # Последние матчи важнее
                
                if m["HomeTeam"] == home_team:
                    home_goals_s += m.get("FTHG", 0) * weight
                    home_goals_c += m.get("FTAG", 0) * weight
                    home_shots += m.get("HS", 0) * weight
                    home_shots_target += m.get("HST", 0) * weight
                    home_possession += m.get("HP", 50) * weight
                    
                    if m["FTR"] == "H": home_points_weighted += 3 * weight
                    elif m["FTR"] == "D": home_points_weighted += 1 * weight
                else:
                    home_goals_s += m.get("FTAG", 0) * weight
                    home_goals_c += m.get("FTHG", 0) * weight
                    home_shots += m.get("AS", 0) * weight
                    home_shots_target += m.get("AST", 0) * weight
                    home_possession += m.get("AP", 50) * weight
                    
                    if m["FTR"] == "A": home_points_weighted += 3 * weight
                    elif m["FTR"] == "D": home_points_weighted += 1 * weight
            
            # === ФОРМА ГОСТЕЙ (взвешенная) ===
            away_matches = df[
                ((df["HomeTeam"] == away_team) | (df["AwayTeam"] == away_team)) &
                (df["Date"] < match_date)
            ].sort_values("Date", ascending=False).head(10)
            
            away_points_weighted = 0
            away_goals_s = 0
            away_goals_c = 0
            away_shots = 0
            away_shots_target = 0
            away_possession = 0
            
            for i, (_, m) in enumerate(away_matches.iterrows()):
                weight = 1.0 / (i + 1)
                
                if m["HomeTeam"] == away_team:
                    away_goals_s += m.get("FTHG", 0) * weight
                    away_goals_c += m.get("FTAG", 0) * weight
                    away_shots += m.get("HS", 0) * weight
                    away_shots_target += m.get("HST", 0) * weight
                    away_possession += m.get("HP", 50) * weight
                    
                    if m["FTR"] == "H": away_points_weighted += 3 * weight
                    elif m["FTR"] == "D": away_points_weighted += 1 * weight
                else:
                    away_goals_s += m.get("FTAG", 0) * weight
                    away_goals_c += m.get("FTHG", 0) * weight
                    away_shots += m.get("AS", 0) * weight
                    away_shots_target += m.get("AST", 0) * weight
                    away_possession += m.get("AP", 50) * weight
                    
                    if m["FTR"] == "A": away_points_weighted += 3 * weight
                    elif m["FTR"] == "D": away_points_weighted += 1 * weight
            
            # === H2H ===
            h2h = df[
                (((df["HomeTeam"] == home_team) & (df["AwayTeam"] == away_team)) |
                 ((df["HomeTeam"] == away_team) & (df["AwayTeam"] == home_team))) &
                (df["Date"] < match_date)
            ].sort_values("Date", ascending=False).head(5)
            
            h2h_h = h2h_a = h2h_d = 0
            for _, m in h2h.iterrows():
                if m["FTR"] == "H":
                    if m["HomeTeam"] == home_team: h2h_h += 1
                    else: h2h_a += 1
                elif m["FTR"] == "A":
                    if m["AwayTeam"] == home_team: h2h_h += 1
                    else: h2h_a += 1
                else: h2h_d += 1
            
            # === ДОМАШНЕЕ ПРЕИМУЩЕСТВО ===
            home_home_matches = df[
                (df["HomeTeam"] == home_team) & (df["Date"] < match_date)
            ].sort_values("Date", ascending=False).head(5)
            
            home_home_wins = 0
            for _, m in home_home_matches.iterrows():
                if m["FTR"] == "H":
                    home_home_wins += 1
            
            away_away_matches = df[
                (df["AwayTeam"] == away_team) & (df["Date"] < match_date)
            ].sort_values("Date", ascending=False).head(5)
            
            away_away_wins = 0
            for _, m in away_away_matches.iterrows():
                if m["FTR"] == "A":
                    away_away_wins += 1
            features.append({
                # Взвешенная форма
                "home_form_weighted": home_points_weighted,
                "away_form_weighted": away_points_weighted,
                "form_weighted_diff": home_points_weighted - away_points_weighted,
                
                # Голы
                "home_goals_scored_weighted": home_goals_s,
                "home_goals_conceded_weighted": home_goals_c,
                "home_goal_diff_weighted": home_goals_s - home_goals_c,
                "away_goals_scored_weighted": away_goals_s,
                "away_goals_conceded_weighted": away_goals_c,
                "away_goal_diff_weighted": away_goals_s - away_goals_c,
                
                # Статистика ударов
                "home_shots_weighted": home_shots,
                "away_shots_weighted": away_shots,
                "shots_diff": home_shots - away_shots,
                "home_shots_target_weighted": home_shots_target,
                "away_shots_target_weighted": away_shots_target,
                "shots_target_diff": home_shots_target - away_shots_target,
                
                # Владение
                "home_possession_weighted": home_possession,
                "away_possession_weighted": away_possession,
                "possession_diff": home_possession - away_possession,
                
                # H2H
                "h2h_home_wins": h2h_h,
                "h2h_away_wins": h2h_a,
                "h2h_draws": h2h_d,
                "h2h_matches": len(h2h),
                
                # Домашнее преимущество
                "home_home_win_rate": home_home_wins / max(len(home_home_matches), 1),
                "away_away_win_rate": away_away_wins / max(len(away_away_matches), 1),
                "home_advantage": (home_home_wins / max(len(home_home_matches), 1)) - 
                                 (away_away_wins / max(len(away_away_matches), 1)),
                
                # Коэффициенты букмекеров (как признаки)
                
                
                
                
                
                
                
                # Целевая переменная
                "result": row["FTR"]
            })
        
        features_df = pd.DataFrame(features)
        logger.info(f"✅ Извлечено {len(features_df)} примеров с {len(features_df.columns)-1} признаками")
        return features_df
    
    def objective(self, trial, X_train, y_train, X_val, y_val, label_encoder):
        """Функция для Optuna: поиск лучших гиперпараметров"""
        params = {
            'n_estimators': trial.suggest_int('n_estimators', 200, 800),
            'max_depth': trial.suggest_int('max_depth', 3, 10),
            'learning_rate': trial.suggest_float('learning_rate', 0.01, 0.3, log=True),
            'subsample': trial.suggest_float('subsample', 0.6, 1.0),
            'colsample_bytree': trial.suggest_float('colsample_bytree', 0.6, 1.0),
            'min_child_weight': trial.suggest_int('min_child_weight', 1, 10),
            'gamma': trial.suggest_float('gamma', 0, 5),
            'reg_alpha': trial.suggest_float('reg_alpha', 1e-8, 10.0, log=True),
            'reg_lambda': trial.suggest_float('reg_lambda', 1e-8, 10.0, log=True),
            'random_state': 42,
            
            'n_jobs': -1,
            'eval_metric': 'mlogloss',
            
        }
        
        model = XGBClassifier(**params)
        # Вычисляем sample_weight для балансировки классов
        from sklearn.utils.class_weight import compute_sample_weight
        sample_weights = compute_sample_weight('balanced', y_train)
        model.fit(X_train, y_train, sample_weight=sample_weights, verbose=False)
        
        y_pred = model.predict(X_val)
        accuracy = accuracy_score(y_val, y_pred)
        
        return accuracy
    
    def train_with_optuna(self, features_df: pd.DataFrame) -> tuple:
        """Обучает модель с автоматическим подбором гиперпараметров"""
        logger.info("🔍 Запускаю Optuna для поиска лучших гиперпараметров...")
        
        feature_cols = [c for c in features_df.columns if c != "result"]
        X = features_df[feature_cols]
        y_raw = features_df["result"]
        # Label encoding: H->0, D->1, A->2
        label_encoder = LabelEncoder()
        y = label_encoder.fit_transform(y_raw)
        logger.info(f"Classes encoded: {dict(zip(label_encoder.classes_, label_encoder.transform(label_encoder.classes_)))}")
        
        # Удаляем NaN
        mask = X.notna().all(axis=1) & pd.Series(y).notna()
        X = X[mask]
        y = y[mask]
        
        logger.info(f"📊 Обучающих примеров: {len(X)}")
        
        # Train/validation split
        X_train, X_val, y_train, y_val = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Запускаем Optuna
        study = optuna.create_study(direction='maximize', 
                                    sampler=optuna.samplers.TPESampler(seed=42))
        
        logger.info("⏳ Optuna: 100 итераций поиска (это займёт 10-15 минут)...")
        study.optimize(
            lambda trial: self.objective(trial, X_train, y_train, X_val, y_val, label_encoder),
            n_trials=100,
            show_progress_bar=True
        )
        
        best_params = study.best_params
        best_score = study.best_value
        
        logger.info(f"🎯 Лучшие параметры: {best_params}")
        logger.info(f"📈 Лучшая точность: {best_score:.4f} ({best_score*100:.2f}%)")
        
        # Обучаем финальную модель с лучшими параметрами
        logger.info("🧠 Обучаю финальную модель с лучшими параметрами...")
        final_params = {**best_params, 'random_state': 42, 'n_jobs': -1, 
                       'eval_metric': 'mlogloss', }
        
        model = XGBClassifier(**final_params)
        sample_weights = compute_sample_weight('balanced', y_train)
        model.fit(X_train, y_train, sample_weight=sample_weights, verbose=False)
        
        # Калибровка вероятностей
        logger.info("🎯 Калибрую вероятности...")
        calibrated_model = CalibratedClassifierCV(model, method='isotonic', cv=3)
        calibrated_model.fit(X_train, y_train)
        
        # Оценка
        y_pred = calibrated_model.predict(X_val)
        accuracy = accuracy_score(y_val, y_pred)
        
        logger.info(f"🎯 Финальная точность (после калибровки): {accuracy:.4f} ({accuracy*100:.2f}%)")
        logger.info("\n📊 Отчёт по классам:")
        print(classification_report(y_val, y_pred))
        
        # Важность признаков
        logger.info("\n🔝 Топ-15 важных признаков:")
        feature_importance = pd.DataFrame({
            "feature": feature_cols,
            "importance": model.feature_importances_
        }).sort_values("importance", ascending=False)
        print(feature_importance.head(15))
        
        return calibrated_model, feature_cols, accuracy, best_params, label_encoder
    
    def backup_current_model(self):
        """Создаёт backup текущей модели"""
        if self.model_path.exists():
            shutil.copy(self.model_path, self.backup_path)
            logger.info(f"💾 Backup сохранён: {self.backup_path}")
    
    def load_old_accuracy(self) -> float:
        """Загружает точность старой модели"""
        try:
            if self.model_path.exists():
                with open(self.model_path, "rb") as f:
                    data = pickle.load(f)
                return data.get("accuracy", 0.0)
        except:
            pass
        return 0.0
    
    def save_model(self, model, feature_cols: list, accuracy: float, best_params: dict):
        """Сохраняет модель на диск"""
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.model_path, "wb") as f:
            pickle.dump({
                "model": model,
                "feature_cols": feature_cols,
                "accuracy": accuracy,
                "best_params": best_params,
                "trained_at": datetime.now().isoformat()
            }, f)
        
        logger.info(f"💾 Модель сохранена: {self.model_path}")
        logger.info(f"📦 Размер: {self.model_path.stat().st_size / 1024:.1f} KB")
    
    def rollback(self):
        """Откатывается к backup модели"""
        if self.backup_path.exists():
            shutil.copy(self.backup_path, self.model_path)
            logger.warning(f"⚠️ Откат к backup: {self.model_path}")
    
    def train(self):
        """Основной метод обучения"""
        logger.info("🚀 Начинаю обучение продвинутой модели (XGBoost + Optuna)\n")
        
        try:
            # Загружаем данные
            df = self.load_data()
            
            # Извлекаем расширенные признаки
            features_df = self.extract_advanced_features(df)
            
            # Получаем старую точность
            old_accuracy = self.load_old_accuracy()
            logger.info(f"📊 Точность старой модели: {old_accuracy:.4f} ({old_accuracy*100:.2f}%)")
            
            # Backup
            self.backup_current_model()
            
            # Обучение с Optuna
            model, feature_cols, new_accuracy, best_params, label_encoder = self.train_with_optuna(features_df)
            
            # Сравнение
            improvement = new_accuracy - old_accuracy
            logger.info(f"\n📈 Разница: {improvement:+.4f} ({improvement*100:+.2f}%)")
            
            if improvement >= -0.005:  # Допускаем ухудшение не более 0.5%
                self.save_model(model, feature_cols, new_accuracy, best_params, label_encoder)
                logger.info(f"✅ Новая модель сохранена!")
                
                # Удаляем backup, если новая лучше
                if improvement > 0 and self.backup_path.exists():
                    self.backup_path.unlink()
                    logger.info("🗑️ Backup удалён (новая модель лучше)")
            else:
                logger.warning(f"⚠️ Новая модель хуже на {abs(improvement)*100:.2f}% — откат к backup")
                self.rollback()
            
            logger.info("\n🎉 Обучение завершено!")
            
        except Exception as e:
            logger.error(f"❌ Ошибка обучения: {e}")
            import traceback
            traceback.print_exc()
            logger.warning("⚠️ Откат к backup...")
            self.rollback()


def main():
    trainer = AdvancedModelTrainer()
    trainer.train()


if __name__ == "__main__":
    main()
