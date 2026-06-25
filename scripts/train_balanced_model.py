"""
Переобучение модели с балансировкой классов
Решает проблему: слишком много прогнозов на ничью (D)
"""
import pandas as pd
import numpy as np
import pickle
import logging
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def load_data():
    """Загружает исторические данные"""
    data_path = Path("data/historical/all_matches_clean.csv")
    if not data_path.exists():
        raise FileNotFoundError(f"Файл не найден: {data_path}")
    
    df = pd.read_csv(data_path, encoding="utf-8", low_memory=False)
    logger.info(f"📚 Загружено {len(df)} матчей")
    
    # Парсинг дат
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"])
        df = df.sort_values("Date")
    
    return df


def extract_features(df):
    """Извлекает признаки для обучения"""
    logger.info("🔧 Извлекаю признаки...")
    
    features = []
    total = len(df)
    
    for idx, row in df.iterrows():
        if idx % 2000 == 0:
            logger.info(f"  ⏳ {idx}/{total} ({idx/total*100:.1f}%)")
        
        home_team = row["HomeTeam"]
        away_team = row["AwayTeam"]
        match_date = row["Date"]
        
        # Форма хозяев (последние 5 матчей)
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
        
        # Форма гостей
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
        
        # H2H
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
        
        features.append({
            "home_form_points": home_pts,
            "away_form_points": away_pts,
            "form_points_diff": home_pts - away_pts,
            "home_goals_scored": home_gs,
            "home_goals_conceded": home_gc,
            "home_goal_diff": home_gs - home_gc,
            "away_goals_scored": away_gs,
            "away_goals_conceded": away_gc,
            "away_goal_diff": away_gs - away_gc,
            "h2h_home_wins": h2h_h,
            "h2h_away_wins": h2h_a,
            "h2h_draws": h2h_d,
            "h2h_matches": len(h2h),
            "form_goal_diff_diff": (home_gs - home_gc) - (away_gs - away_gc),
            "home_form_goals_scored": home_gs,
            "home_form_goals_conceded": home_gc,
            "away_form_goals_scored": away_gs,
            "away_form_goals_conceded": away_gc,
            "result": row["FTR"]
        })
    
    features_df = pd.DataFrame(features)
    logger.info(f"✅ Извлечено {len(features_df)} примеров с {len(features_df.columns)-1} признаками")
    return features_df


def train_balanced_model(features_df):
    """Обучает модель с балансировкой классов"""
    logger.info("🎭 Обучаю модель с балансировкой классов...")
    
    feature_cols = [c for c in features_df.columns if c != "result"]
    X = features_df[feature_cols]
    y = features_df["result"]
    
    # Удаляем NaN
    mask = X.notna().all(axis=1) & y.notna()
    X = X[mask]
    y = y[mask]
    
    logger.info(f"📊 Обучающих примеров: {len(X)}")
    logger.info(f"📊 Распределение классов:")
    logger.info(f"  H (хозяева): {(y == 'H').sum()} ({(y == 'H').mean()*100:.1f}%)")
    logger.info(f"  D (ничьи):   {(y == 'D').sum()} ({(y == 'D').mean()*100:.1f}%)")
    logger.info(f"  A (гости):   {(y == 'A').sum()} ({(y == 'A').mean()*100:.1f}%)")
    
    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    # ✅ КЛЮЧЕВОЕ: class_weight='balanced' автоматически балансирует классы
    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=20,
        min_samples_split=5,
        min_samples_leaf=2,
        class_weight='balanced',  # ← ВАЖНО! Балансирует классы автоматически
        random_state=42,
        n_jobs=-1
    )
    
    logger.info("🌲 Обучаю RandomForest с class_weight='balanced'...")
    model.fit(X_train, y_train)
    
    # Оценка
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    logger.info(f"🎯 Accuracy: {accuracy:.4f} ({accuracy*100:.2f}%)")
    
    # Отчёт по классам
    logger.info("\n📊 Отчёт по классам:")
    print(classification_report(y_test, y_pred))
    
    # Проверка распределения предсказаний
    logger.info("\n📊 Распределение предсказаний на тестовой выборке:")
    pred_counts = pd.Series(y_pred).value_counts()
    for cls, count in pred_counts.items():
        logger.info(f"  {cls}: {count} ({count/len(y_pred)*100:.1f}%)")
    
    # Важность признаков
    logger.info("\n🔝 Топ-10 важных признаков:")
    feature_importance = pd.DataFrame({
        "feature": feature_cols,
        "importance": model.feature_importances_
    }).sort_values("importance", ascending=False)
    print(feature_importance.head(10))
    
    return model, feature_cols, accuracy


def save_model(model, feature_cols, accuracy):
    """Сохраняет модель"""
    model_path = Path("data/models/model_real.pkl")
    model_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(model_path, "wb") as f:
        pickle.dump({
            "model": model,
            "feature_cols": feature_cols,
            "accuracy": accuracy,
            "trained_at": pd.Timestamp.now().isoformat()
        }, f)
    
    logger.info(f"💾 Модель сохранена: {model_path}")
    logger.info(f"📦 Размер: {model_path.stat().st_size / 1024 / 1024:.1f} MB")


def main():
    logger.info("🚀 Начинаю переобучение модели с балансировкой\n")
    
    try:
        df = load_data()
        features_df = extract_features(df)
        model, feature_cols, accuracy = train_balanced_model(features_df)
        save_model(model, feature_cols, accuracy)
        
        logger.info("\n✅ Переобучение завершено!")
        logger.info("📤 Теперь сделайте: git add data/models/model_real.pkl")
        logger.info("📤 Затем: git commit -m 'Retrain model with balanced classes'")
        logger.info("📤 И: git push origin main")
        
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()