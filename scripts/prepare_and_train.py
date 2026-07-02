"""
Подготовка данных и обучение продвинутой модели
"""
import pandas as pd
import numpy as np
import json
import pickle
import logging
from pathlib import Path
from typing import List, Tuple

from xgboost import XGBClassifier
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, log_loss

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def load_data(csv_path: str = "data/historical/football_data_matches.csv") -> pd.DataFrame:
    """Загружает исторические данные"""
    df = pd.read_csv(csv_path)
    logger.info(f"📊 Загружено {len(df)} матчей, {len(df.columns)} колонок")
    return df


def create_features(df: pd.DataFrame) -> pd.DataFrame:
    """Создаёт признаки для модели из сырых данных"""
    
    # Сортируем по дате
    df['date'] = pd.to_datetime(df['date'], dayfirst=True, errors='coerce')
    df = df.sort_values('date').reset_index(drop=True)
    
    # --- 1. Коэффициенты (берём среднее по букмекерам) ---
    home_odds_cols = ['b365_home', 'bw_home', 'iw_home', 'ps_home', 'wh_home']
    draw_odds_cols = ['b365_draw', 'bw_draw', 'iw_draw', 'ps_draw', 'wh_draw']
    away_odds_cols = ['b365_away', 'bw_away', 'iw_away', 'ps_away', 'wh_away']
    
    df['odds_home'] = df[home_odds_cols].mean(axis=1)
    df['odds_draw'] = df[draw_odds_cols].mean(axis=1)
    df['odds_away'] = df[away_odds_cols].mean(axis=1)
    
    # Implied probabilities
    df['impl_prob_home'] = 1 / df['odds_home']
    df['impl_prob_draw'] = 1 / df['odds_draw']
    df['impl_prob_away'] = 1 / df['odds_away']
    
    # Нормализация (overround)
    total_prob = df['impl_prob_home'] + df['impl_prob_draw'] + df['impl_prob_away']
    df['impl_prob_home'] /= total_prob
    df['impl_prob_draw'] /= total_prob
    df['impl_prob_away'] /= total_prob
    
    # --- 2. Статистика матча (для обучения используем прошлые матчи) ---
    # Создаём rolling статистику для каждой команды
    
    df = df.sort_values('date').reset_index(drop=True)
    
    # Функция для расчёта rolling формы
    def get_team_form(team, date, n=5):
        past_matches = df[((df['home_team'] == team) | (df['away_team'] == team)) & (df['date'] < date)].tail(n)
        if len(past_matches) == 0:
            return 0, 0, 0, 0
        
        points = 0
        goals_for = 0
        goals_against = 0
        shots = 0
        
        for _, match in past_matches.iterrows():
            if match['home_team'] == team:
                goals_for += match['home_goals']
                goals_against += match['away_goals']
                shots += match['home_shots'] if pd.notna(match['home_shots']) else 0
                if match['result'] == 'H':
                    points += 3
                elif match['result'] == 'D':
                    points += 1
            else:
                goals_for += match['away_goals']
                goals_against += match['home_goals']
                shots += match['away_shots'] if pd.notna(match['away_shots']) else 0
                if match['result'] == 'A':
                    points += 3
                elif match['result'] == 'D':
                    points += 1
        
        n_matches = len(past_matches)
        return points / n_matches, goals_for / n_matches, goals_against / n_matches, shots / n_matches
    
    # Применяем rolling форму
    logger.info("🏃 Расчёт формы команд...")
    
    home_forms = []
    away_forms = []
    
    for idx, row in df.iterrows():
        if idx % 1000 == 0:
            logger.info(f"   Обработано {idx}/{len(df)} матчей")
        
        home_team = row['home_team']
        away_team = row['away_team']
        date = row['date']
        
        h_points, h_gf, h_ga, h_shots = get_team_form(home_team, date, 5)
        a_points, a_gf, a_ga, a_shots = get_team_form(away_team, date, 5)
        
        home_forms.append({
            'home_points_last5': h_points,
            'home_goals_for_last5': h_gf,
            'home_goals_against_last5': h_ga,
            'home_shots_last5': h_shots,
            'away_points_last5': a_points,
            'away_goals_for_last5': a_gf,
            'away_goals_against_last5': a_ga,
            'away_shots_last5': a_shots,
        })
    
    form_df = pd.DataFrame(home_forms)
    df = pd.concat([df, form_df], axis=1)
    
    # --- 3. H2H статистика ---
    def get_h2h(home, away, date):
        past = df[((df['home_team'] == home) & (df['away_team'] == away)) & (df['date'] < date)].tail(5)
        if len(past) == 0:
            return 0, 0, 0
        
        home_wins = sum(past['result'] == 'H')
        draws = sum(past['result'] == 'D')
        away_wins = sum(past['result'] == 'A')
        
        return home_wins / len(past), draws / len(past), away_wins / len(past)
    
    logger.info("⚔️ Расчёт H2H статистики...")
    h2h_data = []
    for idx, row in df.iterrows():
        hw, d, aw = get_h2h(row['home_team'], row['away_team'], row['date'])
        h2h_data.append({'h2h_home_win_rate': hw, 'h2h_draw_rate': d, 'h2h_away_win_rate': aw})
    
    h2h_df = pd.DataFrame(h2h_data)
    df = pd.concat([df, h2h_df], axis=1)
    
    # --- 4. Дополнительные признаки ---
    df['goal_diff_last5'] = (df['home_goals_for_last5'] - df['home_goals_against_last5']) - \
                            (df['away_goals_for_last5'] - df['away_goals_against_last5'])
    
    df['points_diff'] = df['home_points_last5'] - df['away_points_last5']
    
    # --- 5. Целевая переменная ---
    result_map = {'H': 0, 'D': 1, 'A': 2}
    df['target'] = df['result'].map(result_map)
    
    # Убираем NaN
    df = df.dropna(subset=['target'])
    
    logger.info(f"✅ Признаки созданы. Размер датасета: {len(df)}")
    
    return df


def get_feature_columns() -> List[str]:
    """Возвращает список признаков для модели"""
    return [
        # Коэффициенты
        'odds_home', 'odds_draw', 'odds_away',
        'impl_prob_home', 'impl_prob_draw', 'impl_prob_away',
        
        # Форма
        'home_points_last5', 'away_points_last5',
        'home_goals_for_last5', 'away_goals_for_last5',
        'home_goals_against_last5', 'away_goals_against_last5',
        'home_shots_last5', 'away_shots_last5',
        
        # H2H
        'h2h_home_win_rate', 'h2h_draw_rate', 'h2h_away_win_rate',
        
        # Разницы
        'goal_diff_last5', 'points_diff',
        
        # Статистика текущего матча (если есть)
        'home_shots', 'away_shots',
        'home_shots_on_target', 'away_shots_on_target',
        'home_corners', 'away_corners',
    ]


def train_model(df: pd.DataFrame):
    """Обучает ансамблевую модель"""
    
    feature_cols = [f for f in get_feature_columns() if f in df.columns]
    logger.info(f"📋 Используем {len(feature_cols)} признаков: {feature_cols}")
    
    X = df[feature_cols].fillna(0)
    y = df['target']
    
    # Разделяем: 70% train, 15% val, 15% test
    X_train, X_temp, y_train, y_temp = train_test_split(X, y, test_size=0.3, random_state=42, stratify=y)
    X_val, X_test, y_val, y_test = train_test_split(X_temp, y_temp, test_size=0.5, random_state=42, stratify=y_temp)
    
    logger.info(f"📊 Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}")
    
    # --- Модели ---
    xgb = XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        eval_metric='mlogloss'
    )
    
    rf = RandomForestClassifier(
        n_estimators=200,
        max_depth=12,
        min_samples_split=10,
        random_state=42,
        class_weight='balanced',
        n_jobs=-1
    )
    
    lr = LogisticRegression(
        max_iter=1000,
        random_state=42,
        class_weight='balanced',
        
    )
    
    # Ансамбль
    ensemble = VotingClassifier(
        estimators=[('xgb', xgb), ('rf', rf), ('lr', lr)],
        voting='soft'
    )
    
    logger.info("🏋️ Обучение ансамбля...")
    ensemble.fit(X_train, y_train)
    
    # --- Оценка ---
    val_pred = ensemble.predict(X_val)
    val_acc = accuracy_score(y_val, val_pred)
    logger.info(f"🎯 Accuracy на валидации: {val_acc:.2%}")
    
    # Калибровка
    logger.info("🔧 Калибровка...")
    calibrator = CalibratedClassifierCV(ensemble, method='isotonic', cv=5)
    calibrator.fit(X_val, y_val)
    
    # Финальный тест
    test_pred = calibrator.predict(X_test)
    test_probs = calibrator.predict_proba(X_test)
    test_acc = accuracy_score(y_test, test_pred)
    test_logloss = log_loss(y_test, test_probs)
    
    logger.info(f"\n{'='*50}")
    logger.info(f"📊 ФИНАЛЬНЫЕ РЕЗУЛЬТАТЫ")
    logger.info(f"{'='*50}")
    logger.info(f"🎯 Accuracy: {test_acc:.2%}")
    logger.info(f"📉 LogLoss: {test_logloss:.4f}")
    
    logger.info(f"\n📋 Classification Report:")
    print(classification_report(y_test, test_pred, target_names=['HOME', 'DRAW', 'AWAY']))
    
    # --- Сохранение ---
    Path("ml_models").mkdir(exist_ok=True)
    
    with open("ml_models/advanced_model.pkl", "wb") as f:
        pickle.dump(ensemble, f)
    
    with open("ml_models/advanced_model_calibrator.pkl", "wb") as f:
        pickle.dump(calibrator, f)
    
    meta = {
        "accuracy": float(test_acc),
        "logloss": float(test_logloss),
        "feature_cols": feature_cols,
        "n_features": len(feature_cols),
        "n_train": len(X_train),
        "n_test": len(X_test),
        "training_date": pd.Timestamp.now().isoformat()
    }
    
    with open("ml_models/advanced_model.meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    
    logger.info(f"\n💾 Модель сохранена в ml_models/")
    
    # Важность признаков
    if 'xgb' in ensemble.named_estimators_:
        xgb_model = ensemble.named_estimators_['xgb']
        importances = sorted(
            zip(feature_cols, xgb_model.feature_importances_),
            key=lambda x: x[1], reverse=True
        )
        logger.info(f"\n🔍 Топ-10 важных признаков:")
        for feature, imp in importances[:10]:
            logger.info(f"   {feature}: {imp:.3f}")
    
    return test_acc


def main():
    logger.info("🚀 Начинаем подготовку данных и обучение...")
    
    # 1. Загружаем
    df = load_data()
    
    # 2. Создаём признаки
    df = create_features(df)
    
    # 3. Обучаем
    accuracy = train_model(df)
    
    logger.info(f"\n✅ Готово! Точность модели: {accuracy:.2%}")
    
    return accuracy


if __name__ == "__main__":
    main()
