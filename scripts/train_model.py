"""
Скрипт для обучения ML-модели на исторических данных.
Извлекает признаки: форма команд, H2H, статистика.
Обучает RandomForest и сохраняет в model_real.pkl.

Запуск: python scripts/train_model.py
"""
import pandas as pd
import numpy as np
import joblib
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report


def load_data(csv_path: str = "data/historical/all_matches_clean.csv") -> pd.DataFrame:
    """Загружает очищенные данные"""
    print(f"📂 Загружаю данные из {csv_path}...")
    df = pd.read_csv(csv_path, encoding="utf-8")
    print(f"✅ Загружено {len(df)} матчей")
    return df


def calculate_team_form(df: pd.DataFrame, team: str, date, n_matches: int = 5) -> dict:
    """Рассчитывает форму команды за последние N матчей"""
    # Находим все матчи команды до текущей даты
    team_matches = df[
        ((df["HomeTeam"] == team) | (df["AwayTeam"] == team)) &
        (df["Date"] < date)
    ].sort_values("Date", ascending=False).head(n_matches)
    
    if len(team_matches) == 0:
        return {"form_points": 0, "form_goals_scored": 0, "form_goals_conceded": 0, "form_matches": 0}
    
    points = 0
    goals_scored = 0
    goals_conceded = 0
    
    for _, match in team_matches.iterrows():
        if match["HomeTeam"] == team:
            goals_scored += match["FTHG"]
            goals_conceded += match["FTAG"]
            if match["FTR"] == "H":
                points += 3
            elif match["FTR"] == "D":
                points += 1
        else:
            goals_scored += match["FTAG"]
            goals_conceded += match["FTHG"]
            if match["FTR"] == "A":
                points += 3
            elif match["FTR"] == "D":
                points += 1
    
    return {
        "form_points": points,
        "form_goals_scored": goals_scored,
        "form_goals_conceded": goals_conceded,
        "form_matches": len(team_matches)
    }


def calculate_h2h(df: pd.DataFrame, home_team: str, away_team: str, date, n_matches: int = 5) -> dict:
    """Рассчитывает историю личных встреч"""
    h2h_matches = df[
        (((df["HomeTeam"] == home_team) & (df["AwayTeam"] == away_team)) |
         ((df["HomeTeam"] == away_team) & (df["AwayTeam"] == home_team))) &
        (df["Date"] < date)
    ].sort_values("Date", ascending=False).head(n_matches)
    
    if len(h2h_matches) == 0:
        return {"h2h_home_wins": 0, "h2h_away_wins": 0, "h2h_draws": 0, "h2h_matches": 0}
    
    home_wins = 0
    away_wins = 0
    draws = 0
    
    for _, match in h2h_matches.iterrows():
        if match["FTR"] == "H":
            if match["HomeTeam"] == home_team:
                home_wins += 1
            else:
                away_wins += 1
        elif match["FTR"] == "A":
            if match["AwayTeam"] == home_team:
                home_wins += 1
            else:
                away_wins += 1
        else:
            draws += 1
    
    return {
        "h2h_home_wins": home_wins,
        "h2h_away_wins": away_wins,
        "h2h_draws": draws,
        "h2h_matches": len(h2h_matches)
    }


def extract_features(df: pd.DataFrame) -> pd.DataFrame:
    """Извлекает признаки для каждого матча"""
    print("🔧 Извлекаю признаки (это может занять 2-5 минут)...")
    
    features = []
    total = len(df)
    
    for idx, row in df.iterrows():
        if idx % 500 == 0:
            print(f"  ⏳ Обработано {idx}/{total} матчей ({idx/total*100:.1f}%)")
        
        home_team = row["HomeTeam"]
        away_team = row["AwayTeam"]
        match_date = row["Date"]
        
        # Форма хозяев
        home_form = calculate_team_form(df, home_team, match_date, n_matches=5)
        
        # Форма гостей
        away_form = calculate_team_form(df, away_team, match_date, n_matches=5)
        
        # История личных встреч
        h2h = calculate_h2h(df, home_team, away_team, match_date, n_matches=5)
        
        # Дополнительные признаки из данных
        feature_row = {
            # Форма хозяев
            "home_form_points": home_form["form_points"],
            "home_form_goals_scored": home_form["form_goals_scored"],
            "home_form_goals_conceded": home_form["form_goals_conceded"],
            "home_form_goal_diff": home_form["form_goals_scored"] - home_form["form_goals_conceded"],
            
            # Форма гостей
            "away_form_points": away_form["form_points"],
            "away_form_goals_scored": away_form["form_goals_scored"],
            "away_form_goals_conceded": away_form["form_goals_conceded"],
            "away_form_goal_diff": away_form["form_goals_scored"] - away_form["form_goals_conceded"],
            
            # Разница в форме
            "form_points_diff": home_form["form_points"] - away_form["form_points"],
            "form_goal_diff_diff": (home_form["form_goals_scored"] - home_form["form_goals_conceded"]) - 
                                   (away_form["form_goals_scored"] - away_form["form_goals_conceded"]),
            
            # H2H
            "h2h_home_wins": h2h["h2h_home_wins"],
            "h2h_away_wins": h2h["h2h_away_wins"],
            "h2h_draws": h2h["h2h_draws"],
            "h2h_matches": h2h["h2h_matches"],
            
            # Целевая переменная (результат)
            "result": row["FTR"]  # H, D, A
        }
        
        # Добавляем коэффициенты, если есть
        if "B365H" in row and pd.notna(row["B365H"]):
            feature_row["odds_home"] = row["B365H"]
            feature_row["odds_draw"] = row["B365D"]
            feature_row["odds_away"] = row["B365A"]
        
        # Добавляем статистику ударов, если есть
        if "HS" in row and pd.notna(row["HS"]):
            feature_row["home_shots"] = row["HS"]
            feature_row["away_shots"] = row["AS"]
        if "HST" in row and pd.notna(row["HST"]):
            feature_row["home_shots_on_target"] = row["HST"]
            feature_row["away_shots_on_target"] = row["AST"]
        
        features.append(feature_row)
    
    features_df = pd.DataFrame(features)
    print(f"✅ Извлечено {len(features_df)} примеров с {len(features_df.columns)} признаками")
    return features_df


def train_model(features_df: pd.DataFrame) -> None:
    """Обучает RandomForest модель"""
    print("\n🧠 Обучаю модель RandomForest...")
    
    # Разделяем на признаки и целевую переменную
    feature_cols = [c for c in features_df.columns if c not in ["result", "odds_home", "odds_draw", "odds_away"]]
    X = features_df[feature_cols]
    y = features_df["result"]
    
    # Удаляем строки с NaN
    mask = X.notna().all(axis=1) & y.notna()
    X = X[mask]
    y = y[mask]
    
    print(f"📊 Обучающих примеров: {len(X)}")
    print(f"📊 Распределение классов:")
    print(y.value_counts(normalize=True))
    
    # Разделяем на train/test
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    # Обучаем модель
    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=15,
        min_samples_split=10,
        min_samples_leaf=5,
        random_state=42,
        n_jobs=-1
    )
    
    model.fit(X_train, y_train)
    
    # Оцениваем
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    
    print(f"\n🎯 Точность на тесте: {accuracy:.4f} ({accuracy*100:.1f}%)")
    print("\n📊 Отчёт по классам:")
    print(classification_report(y_test, y_pred))
    
    # Важность признаков
    print("\n🔝 Топ-10 важных признаков:")
    feature_importance = pd.DataFrame({
        "feature": feature_cols,
        "importance": model.feature_importances_
    }).sort_values("importance", ascending=False)
    print(feature_importance.head(10))
    
    # Сохраняем модель
    model_dir = Path("data/models")
    model_dir.mkdir(parents=True, exist_ok=True)
        # Лучше переименовать расширение файла с .pkl на .joblib, чтобы не было путаницы
    model_path = model_dir / "model_real.joblib"
    
    joblib.dump({
        "model": model,
        "feature_cols": feature_cols,
        "accuracy": accuracy,
    }, model_path)
    
    print(f"\n💾 Модель сохранена: {model_path}")
    print(f"📦 Размер: {model_path.stat().st_size / 1024:.1f} KB")


def main():
    print("🚀 Начинаю обучение ML-модели на исторических данных\n")
    
    # Загружаем данные
    df = load_data()
    
    # Преобразуем дату
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date"])
    df = df.sort_values("Date")
    
    # Извлекаем признаки
    features_df = extract_features(df)
    
    # Обучаем модель
    train_model(features_df)
    
    print("\n🎉 Обучение завершено!")


if __name__ == "__main__":
    main()
