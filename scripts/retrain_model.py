import pandas as pd
import numpy as np
import pickle
import shutil
import logging
from pathlib import Path
from datetime import datetime
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class ModelRetrainer:
    def __init__(self, 
                 data_path: str = "data/historical/all_matches_clean.csv",
                 model_path: str = "data/models/model_real.pkl"):
        self.data_path = Path(data_path)
        self.model_path = Path(model_path)
        self.backup_path = self.model_path.with_suffix('.pkl.backup')
    
    def load_data(self) -> pd.DataFrame:
        if not self.data_path.exists():
            raise FileNotFoundError(f"Data file not found: {self.data_path}")
        df = pd.read_csv(self.data_path, encoding="utf-8")
        logger.info(f"Loaded {len(df)} matches")
        if "Date" in df.columns:
            for fmt in ["%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"]:
                try:
                    df["Date"] = pd.to_datetime(df["Date"], format=fmt, errors="coerce")
                    if df["Date"].notna().sum() > len(df) * 0.5:
                        break
                except:
                    continue
            df = df.dropna(subset=["Date"])
            df = df.sort_values("Date")
        return df
    
    def extract_features(self, df: pd.DataFrame) -> pd.DataFrame:
        logger.info("Extracting features...")
        features = []
        total = len(df)
        for idx, row in df.iterrows():
            if idx % 1000 == 0:
                logger.info(f"  {idx}/{total} ({idx/total*100:.1f}%)")
            home_team = row["HomeTeam"]
            away_team = row["AwayTeam"]
            match_date = row["Date"]
            
            home_matches = df[((df["HomeTeam"] == home_team) | (df["AwayTeam"] == home_team)) & (df["Date"] < match_date)].sort_values("Date", ascending=False).head(5)
            home_points = home_goals_s = home_goals_c = 0
            for _, m in home_matches.iterrows():
                if m["HomeTeam"] == home_team:
                    home_goals_s += m["FTHG"]; home_goals_c += m["FTAG"]
                    if m["FTR"] == "H": home_points += 3
                    elif m["FTR"] == "D": home_points += 1
                else:
                    home_goals_s += m["FTAG"]; home_goals_c += m["FTHG"]
                    if m["FTR"] == "A": home_points += 3
                    elif m["FTR"] == "D": home_points += 1
            
            away_matches = df[((df["HomeTeam"] == away_team) | (df["AwayTeam"] == away_team)) & (df["Date"] < match_date)].sort_values("Date", ascending=False).head(5)
            away_points = away_goals_s = away_goals_c = 0
            for _, m in away_matches.iterrows():
                if m["HomeTeam"] == away_team:
                    away_goals_s += m["FTHG"]; away_goals_c += m["FTAG"]
                    if m["FTR"] == "H": away_points += 3
                    elif m["FTR"] == "D": away_points += 1
                else:
                    away_goals_s += m["FTAG"]; away_goals_c += m["FTHG"]
                    if m["FTR"] == "A": away_points += 3
                    elif m["FTR"] == "D": away_points += 1
            
            h2h = df[(((df["HomeTeam"] == home_team) & (df["AwayTeam"] == away_team)) | ((df["HomeTeam"] == away_team) & (df["AwayTeam"] == home_team))) & (df["Date"] < match_date)].sort_values("Date", ascending=False).head(5)
            h2h_h = h2h_a = h2h_d = 0
            for _, m in h2h.iterrows():
                if m["FTR"] == "H":
                    if m["HomeTeam"] == home_team: h2h_h += 1
                    else: h2h_a += 1
                elif m["FTR"] == "A":
                    if m["AwayTeam"] == home_team: h2h_h += 1
                    else: h2h_a += 1
                else: h2h_d += 1
            
            features.append({
                "home_form_points": home_points,
                "home_form_goals_scored": home_goals_s,
                "home_form_goals_conceded": home_goals_c,
                "home_form_goal_diff": home_goals_s - home_goals_c,
                "away_form_points": away_points,
                "away_form_goals_scored": away_goals_s,
                "away_form_goals_conceded": away_goals_c,
                "away_form_goal_diff": away_goals_s - away_goals_c,
                "form_points_diff": home_points - away_points,
                "form_goal_diff_diff": (home_goals_s - home_goals_c) - (away_goals_s - away_goals_c),
                "h2h_home_wins": h2h_h,
                "h2h_away_wins": h2h_a,
                "h2h_draws": h2h_d,
                "h2h_matches": len(h2h),
                "result": row["FTR"]
            })
        features_df = pd.DataFrame(features)
        logger.info(f"Extracted {len(features_df)} samples")
        return features_df
    
    def backup_current_model(self):
        if self.model_path.exists():
            shutil.copy(self.model_path, self.backup_path)
            logger.info(f"Backup saved: {self.backup_path}")
    
    def load_old_accuracy(self) -> float:
        try:
            if self.model_path.exists():
                with open(self.model_path, "rb") as f:
                    data = pickle.load(f)
                return data.get("accuracy", 0.0)
        except:
            pass
        return 0.0
    
    def train_new_model(self, features_df: pd.DataFrame) -> tuple:
        logger.info("Training new RandomForest model...")
        feature_cols = [c for c in features_df.columns if c != "result"]
        X = features_df[feature_cols]
        y = features_df["result"]
        mask = X.notna().all(axis=1) & y.notna()
        X = X[mask]
        y = y[mask]
        logger.info(f"Training samples: {len(X)}")
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
        model = RandomForestClassifier(n_estimators=200, max_depth=15, min_samples_split=10, min_samples_leaf=5, random_state=42, n_jobs=-1)
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        logger.info(f"New model accuracy: {accuracy:.4f} ({accuracy*100:.2f}%)")
        return model, feature_cols, accuracy
    
    def save_model(self, model, feature_cols: list, accuracy: float):
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.model_path, "wb") as f:
            pickle.dump({"model": model, "feature_cols": feature_cols, "accuracy": accuracy, "trained_at": datetime.now().isoformat()}, f)
        logger.info(f"Model saved: {self.model_path}")
    
    def rollback(self):
        if self.backup_path.exists():
            shutil.copy(self.backup_path, self.model_path)
            logger.warning(f"Rolled back to backup")
    
    def retrain(self):
        logger.info("Starting model retraining")
        try:
            df = self.load_data()
            features_df = self.extract_features(df)
            old_accuracy = self.load_old_accuracy()
            logger.info(f"Old model accuracy: {old_accuracy:.4f} ({old_accuracy*100:.2f}%)")
            self.backup_current_model()
            model, feature_cols, new_accuracy = self.train_new_model(features_df)
            improvement = new_accuracy - old_accuracy
            logger.info(f"Improvement: {improvement:+.4f} ({improvement*100:+.2f}%)")
            if improvement >= -0.005:
                self.save_model(model, feature_cols, new_accuracy)
                logger.info("New model saved!")
                if improvement > 0 and self.backup_path.exists():
                    self.backup_path.unlink()
                    logger.info("Backup removed (new model is better)")
            else:
                logger.warning(f"New model worse by {abs(improvement)*100:.2f}% - rollback")
                self.rollback()
            logger.info("Retraining complete!")
        except Exception as e:
            logger.error(f"Retraining error: {e}")
            logger.warning("Rolling back to backup...")
            self.rollback()


def main():
    retrainer = ModelRetrainer()
    retrainer.retrain()


if __name__ == "__main__":
    main()
