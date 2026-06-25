"""
Ансамбль моделей: RandomForest + XGBoost + CatBoost + LogisticRegression
С коэффициентами букмекеров и ELO Rating
Целевая точность: 66-68%

Запуск: python scripts/train_ensemble_model.py
"""
import pandas as pd
import numpy as np
import pickle
import shutil
import logging
from pathlib import Path
from datetime import datetime, timedelta
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.calibration import CalibratedClassifierCV
from xgboost import XGBClassifier
from catboost import CatBoostClassifier

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class EnsembleModelTrainer:
    def __init__(self, 
                 data_path: str = "data/historical/all_matches_clean.csv",
                 model_path: str = "data/models/model_ensemble.pkl"):
        self.data_path = Path(data_path)
        self.model_path = Path(model_path)
        self.backup_path = self.model_path.with_suffix('.pkl.backup')
        self.elo_ratings = {}  # ELO рейтинги команд
    
    def load_data(self) -> pd.DataFrame:
        """Загружает и подготавливает данные"""
        if not self.data_path.exists():
            raise FileNotFoundError(f"Data file not found: {self.data_path}")
        
        df = pd.read_csv(self.data_path, encoding="utf-8", low_memory=False)
        logger.info(f"📚 Загружено {len(df)} матчей")
        
        # Парсинг дат
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
            df = df.dropna(subset=["Date"])
            df = df.sort_values("Date")
            logger.info(f"After date parsing: {len(df)} matches left")
        
        return df
    
    def calculate_elo_ratings(self, df: pd.DataFrame, k_factor: int = 32) -> dict:
        """Рассчитывает ELO рейтинги команд"""
        logger.info("🏆 Рассчитываю ELO рейтинги команд...")
        
        elo = {}
        initial_rating = 1500
        
        for _, row in df.iterrows():
            home_team = row["HomeTeam"]
            away_team = row["AwayTeam"]
            result = row["FTR"]
            
            # Инициализация рейтингов
            if home_team not in elo:
                elo[home_team] = initial_rating
            if away_team not in elo:
                elo[away_team] = initial_rating
            
            # Ожидаемый результат
            expected_home = 1 / (1 + 10 ** ((elo[away_team] - elo[home_team]) / 400))
            expected_away = 1 - expected_home
            
            # Фактический результат
            if result == "H":
                actual_home = 1.0
                actual_away = 0.0
            elif result == "A":
                actual_home = 0.0
                actual_away = 1.0
            else:  # Draw
                actual_home = 0.5
                actual_away = 0.5
            
            # Обновление рейтингов
            elo[home_team] += k_factor * (actual_home - expected_home)
            elo[away_team] += k_factor * (actual_away - expected_away)
        
        logger.info(f"✅ Рассчитаны ELO рейтинги для {len(elo)} команд")
        self.elo_ratings = elo
        return elo
    
    def extract_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Извлекает расширенные признаки с коэффициентами и ELO"""
        logger.info("🔧 Извлекаю расширенные признаки...")
        
        features = []
        total = len(df)
        
        for idx, row in df.iterrows():
            if idx % 1000 == 0:
                logger.info(f"  ⏳ {idx}/{total} ({idx/total*100:.1f}%)")
            
            home_team = row["HomeTeam"]
            away_team = row["AwayTeam"]
            match_date = row["Date"]
            
            # === ФОРМА КОМАНД (взвешенная) ===
            home_matches = df[
                ((df["HomeTeam"] == home_team) | (df["AwayTeam"] == home_team)) &
                (df["Date"] < match_date)
            ].sort_values("Date", ascending=False).head(5)
            
            home_pts = home_gs = home_gc = 0
            for i, (_, m) in enumerate(home_matches.iterrows()):
                w = 1.0 / (i + 1)
                if m["HomeTeam"] == home_team:
                    home_gs += m.get("FTHG", 0) * w
                    home_gc += m.get("FTAG", 0) * w
                    if m["FTR"] == "H": home_pts += 3 * w
                    elif m["FTR"] == "D": home_pts += 1 * w
                else:
                    home_gs += m.get("FTAG", 0) * w
                    home_gc += m.get("FTHG", 0) * w
                    if m["FTR"] == "A": home_pts += 3 * w
                    elif m["FTR"] == "D": home_pts += 1 * w
            
            away_matches = df[
                ((df["HomeTeam"] == away_team) | (df["AwayTeam"] == away_team)) &
                (df["Date"] < match_date)
            ].sort_values("Date", ascending=False).head(5)
            
            away_pts = away_gs = away_gc = 0
            for i, (_, m) in enumerate(away_matches.iterrows()):
                w = 1.0 / (i + 1)
                if m["HomeTeam"] == away_team:
                    away_gs += m.get("FTHG", 0) * w
                    away_gc += m.get("FTAG", 0) * w
                    if m["FTR"] == "H": away_pts += 3 * w
                    elif m["FTR"] == "D": away_pts += 1 * w
                else:
                    away_gs += m.get("FTAG", 0) * w
                    away_gc += m.get("FTHG", 0) * w
                    if m["FTR"] == "A": away_pts += 3 * w
                    elif m["FTR"] == "D": away_pts += 1 * w
            
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
            
            # === КОЭФФИЦИЕНТЫ БУКМЕКЕРОВ (ВАЖНО!) ===
            b365_h = row.get("B365H", 2.0)
            b365_d = row.get("B365D", 3.5)
            b365_a = row.get("B365A", 3.5)
            
            if pd.notna(b365_h) and pd.notna(b365_d) and pd.notna(b365_a):
                try:
                    total_odds = 1/b365_h + 1/b365_d + 1/b365_a
                    prob_h = (1/b365_h) / total_odds
                    prob_d = (1/b365_d) / total_odds
                    prob_a = (1/b365_a) / total_odds
                except:
                    prob_h, prob_d, prob_a = 0.45, 0.27, 0.28
            else:
                prob_h, prob_d, prob_a = 0.45, 0.27, 0.28
            
            # === ELO РЕЙТИНГИ ===
            home_elo = self.elo_ratings.get(home_team, 1500)
            away_elo = self.elo_ratings.get(away_team, 1500)
            elo_diff = home_elo - away_elo
            
            features.append({
                # Форма
                "home_form_weighted": home_pts,
                "away_form_weighted": away_pts,
                "form_weighted_diff": home_pts - away_pts,
                "home_goals_scored_weighted": home_gs,
                "home_goals_conceded_weighted": home_gc,
                "home_goal_diff_weighted": home_gs - home_gc,
                "away_goals_scored_weighted": away_gs,
                "away_goals_conceded_weighted": away_gc,
                "away_goal_diff_weighted": away_gs - away_gc,
                
                # H2H
                "h2h_home_wins": h2h_h,
                "h2h_away_wins": h2h_a,
                "h2h_draws": h2h_d,
                "h2h_matches": len(h2h),
                
                # Коэффициенты букмекеров (САМЫЕ ВАЖНЫЕ!)
                "bookmaker_prob_home": prob_h,
                "bookmaker_prob_draw": prob_d,
                "bookmaker_prob_away": prob_a,
                "odds_home": b365_h if pd.notna(b365_h) else 2.0,
                "odds_draw": b365_d if pd.notna(b365_d) else 3.5,
                "odds_away": b365_a if pd.notna(b365_a) else 3.5,
                
                # ELO рейтинги
                "home_elo": home_elo,
                "away_elo": away_elo,
                "elo_diff": elo_diff,
                
                # Целевая переменная
                "result": row["FTR"]
            })
        
        features_df = pd.DataFrame(features)
        logger.info(f"✅ Извлечено {len(features_df)} примеров с {len(features_df.columns)-1} признаками")
        return features_df
    
    def train_ensemble(self, features_df: pd.DataFrame) -> tuple:
        """Обучает ансамбль из 4 моделей"""
        logger.info("🎭 Обучаю ансамбль из 4 моделей...")
        
        feature_cols = [c for c in features_df.columns if c != "result"]
        X = features_df[feature_cols]
        y = features_df["result"]
        
        # Удаляем NaN
        mask = X.notna().all(axis=1) & y.notna()
        X = X[mask]
        y = y[mask]
        
        logger.info(f"📊 Обучающих примеров: {len(X)}")
        
        # Label encoding
        label_encoder = LabelEncoder()
        y_encoded = label_encoder.fit_transform(y)
        
        # Train/test split
        X_train, X_test, y_train, y_test = train_test_split(
            X, y_encoded, test_size=0.2, random_state=42, stratify=y_encoded
        )
        
        # === Модель 1: RandomForest ===
        logger.info("🌲 Обучаю RandomForest...")
        rf = RandomForestClassifier(
            n_estimators=500,
            max_depth=20,
            min_samples_split=5,
            min_samples_leaf=2,
            class_weight='balanced',
            random_state=42,
            n_jobs=-1
        )
        rf.fit(X_train, y_train)
        rf_acc = accuracy_score(y_test, rf.predict(X_test))
        logger.info(f"  RandomForest accuracy: {rf_acc:.4f} ({rf_acc*100:.2f}%)")
        
        # === Модель 2: XGBoost ===
        logger.info("🚀 Обучаю XGBoost...")
        xgb = XGBClassifier(
            n_estimators=300,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            n_jobs=-1,
            eval_metric='mlogloss'
        )
        xgb.fit(X_train, y_train)
        xgb_acc = accuracy_score(y_test, xgb.predict(X_test))
        logger.info(f"  XGBoost accuracy: {xgb_acc:.4f} ({xgb_acc*100:.2f}%)")
        
        # === Модель 3: CatBoost ===
        logger.info("🐱 Обучаю CatBoost...")
        catboost = CatBoostClassifier(
            iterations=300,
            depth=6,
            learning_rate=0.05,
            loss_function='MultiClass',
            random_seed=42,
            verbose=False
        )
        catboost.fit(X_train, y_train)
        catboost_acc = accuracy_score(y_test, catboost.predict(X_test))
        logger.info(f"  CatBoost accuracy: {catboost_acc:.4f} ({catboost_acc*100:.2f}%)")
        
        # === Модель 4: Logistic Regression ===
        logger.info("📊 Обучаю Logistic Regression...")
        scaler = StandardScaler()
        X_train_scaled = scaler.fit_transform(X_train)
        X_test_scaled = scaler.transform(X_test)
        
        lr = LogisticRegression(
            class_weight='balanced',
            max_iter=1000,
            random_state=42,
            )
        lr.fit(X_train_scaled, y_train)
        lr_acc = accuracy_score(y_test, lr.predict(X_test_scaled))
        logger.info(f"  Logistic Regression accuracy: {lr_acc:.4f} ({lr_acc*100:.2f}%)")
        
        # === Ансамбль (Voting Classifier) ===
        logger.info("🎭 Создаю ансамбль...")
        ensemble = VotingClassifier(
            estimators=[
                ('rf', rf),
                ('xgb', xgb),
                ('catboost', catboost),
                ('lr', LogisticRegression(class_weight='balanced', max_iter=1000, random_state=42, ))
            ],
            voting='soft'  # Усреднение вероятностей
        )
        
        # Для LR нужен scaler, поэтому обучаем ансамбль с предобработкой
        ensemble.fit(X_train_scaled, y_train)
        ensemble_acc = accuracy_score(y_test, ensemble.predict(X_test_scaled))
        logger.info(f"  Ensemble accuracy: {ensemble_acc:.4f} ({ensemble_acc*100:.2f}%)")
        
        # Калибровка вероятностей
        logger.info("🎯 Калибрую вероятности...")
        calibrated_ensemble = CalibratedClassifierCV(ensemble, method='isotonic', cv=3)
        calibrated_ensemble.fit(X_train_scaled, y_train)
        
        final_acc = accuracy_score(y_test, calibrated_ensemble.predict(X_test_scaled))
        logger.info(f"🎯 Финальная точность (после калибровки): {final_acc:.4f} ({final_acc*100:.2f}%)")
        
        # Отчёт по классам
        y_pred = calibrated_ensemble.predict(X_test_scaled)
        y_test_labels = label_encoder.inverse_transform(y_test)
        y_pred_labels = label_encoder.inverse_transform(y_pred)
        
        logger.info("\n📊 Отчёт по классам:")
        print(classification_report(y_test_labels, y_pred_labels))
        
        # Важность признаков (из RandomForest)
        logger.info("\n🔝 Топ-10 важных признаков:")
        feature_importance = pd.DataFrame({
            "feature": feature_cols,
            "importance": rf.feature_importances_
        }).sort_values("importance", ascending=False)
        print(feature_importance.head(10))
        
        return calibrated_ensemble, scaler, feature_cols, final_acc, label_encoder
    
    def backup_current_model(self):
        """Создаёт backup текущей модели"""
        if self.model_path.exists():
            shutil.copy(self.model_path, self.backup_path)
            logger.info(f"💾 Backup сохранён: {self.backup_path}")
    
    def load_old_accuracy(self) -> float:
        """Загружает точность старой модели"""
        try:
            old_model_path = Path("data/models/model_real.pkl")
            if old_model_path.exists():
                with open(old_model_path, "rb") as f:
                    data = pickle.load(f)
                return data.get("accuracy", 0.0)
        except:
            pass
        return 0.0
    
    def save_model(self, model, scaler, feature_cols: list, accuracy: float, label_encoder):
        """Сохраняет ансамбль на диск"""
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.model_path, "wb") as f:
            pickle.dump({
                "model": model,
                "scaler": scaler,
                "feature_cols": feature_cols,
                "accuracy": accuracy,
                "label_encoder": label_encoder,
                "elo_ratings": self.elo_ratings,
                "trained_at": datetime.now().isoformat()
            }, f)
        
        logger.info(f"💾 Модель сохранена: {self.model_path}")
        logger.info(f"📦 Размер: {self.model_path.stat().st_size / 1024 / 1024:.1f} MB")
    
    def train(self):
        """Основной метод обучения"""
        logger.info("🚀 Начинаю обучение ансамбля моделей\n")
        
        try:
            # Загружаем данные
            df = self.load_data()
            
            # Рассчитываем ELO рейтинги
            self.calculate_elo_ratings(df)
            
            # Извлекаем признаки
            features_df = self.extract_features(df)
            
            # Получаем старую точность
            old_accuracy = self.load_old_accuracy()
            logger.info(f"📊 Точность старой модели: {old_accuracy:.4f} ({old_accuracy*100:.2f}%)")
            
            # Backup
            self.backup_current_model()
            
            # Обучение ансамбля
            model, scaler, feature_cols, new_accuracy, label_encoder = self.train_ensemble(features_df)
            
            # Сравнение
            improvement = new_accuracy - old_accuracy
            logger.info(f"\n📈 Разница: {improvement:+.4f} ({improvement*100:+.2f}%)")
            
            if improvement >= -0.005:
                self.save_model(model, scaler, feature_cols, new_accuracy, label_encoder)
                logger.info(f"✅ Новая модель сохранена!")
                
                if improvement > 0 and self.backup_path.exists():
                    self.backup_path.unlink()
                    logger.info("🗑️ Backup удалён (новая модель лучше)")
            else:
                logger.warning(f"⚠️ Новая модель хуже на {abs(improvement)*100:.2f}% — откат к backup")
                if self.backup_path.exists():
                    shutil.copy(self.backup_path, self.model_path)
            
            logger.info("\n🎉 Обучение завершено!")
            
        except Exception as e:
            logger.error(f"❌ Ошибка обучения: {e}")
            import traceback
            traceback.print_exc()
            logger.warning("⚠️ Откат к backup...")
            if self.backup_path.exists():
                shutil.copy(self.backup_path, self.model_path)


def main():
    trainer = EnsembleModelTrainer()
    trainer.train()


if __name__ == "__main__":
    main()
