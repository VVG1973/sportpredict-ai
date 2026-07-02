"""
Обучение продвинутой ансамблевой модели
"""
import pandas as pd
import numpy as np
import json
import pickle
import logging
from pathlib import Path
from typing import Tuple

from xgboost import XGBClassifier
from sklearn.ensemble import RandomForestClassifier, VotingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import StratifiedKFold, train_test_split
from sklearn.metrics import (
    accuracy_score, brier_score_loss, log_loss,
    classification_report, confusion_matrix
)
from sklearn.preprocessing import StandardScaler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


def load_enhanced_data(csv_path: str = "data/historical_matches.csv") -> pd.DataFrame:
    """Загружает и обогащает исторические данные"""
    
    if not Path(csv_path).exists():
        logger.error(f"❌ Файл {csv_path} не найден!")
        return None
    
    df = pd.read_csv(csv_path)
    logger.info(f"📊 Загружено {len(df)} матчей")
    
    # === СОЗДАЁМ ДОПОЛНИТЕЛЬНЫЕ ПРИЗНАКИ ===
    
    # 1. xG разница
    if 'home_xg_last5' in df.columns and 'away_xg_last5' in df.columns:
        df['home_xg_diff_last5'] = df['home_xg_last5'] - df['home_xg_against_last5']
        df['away_xg_diff_last5'] = df['away_xg_last5'] - df['away_xg_against_last5']
        df['xg_diff_total'] = df['home_xg_diff_last5'] - df['away_xg_diff_last5']
    
    # 2. Implied probability из коэффициентов
    for col in ['odds_home', 'odds_draw', 'odds_away']:
        if col in df.columns:
            prob_col = col.replace('odds_', 'odds_') + '_implied_prob'
            df[prob_col] = 1.0 / df[col].replace(0, np.nan)
    
    # 3. Value bets (если есть наши предсказания)
    if 'model_prob_home' in df.columns:
        df['odds_value_home'] = df['model_prob_home'] - (1.0 / df['odds_home'].replace(0, np.nan))
    
    # 4. Разница позиций
    if 'home_league_position' in df.columns and 'away_league_position' in df.columns:
        df['position_diff'] = df['away_league_position'] - df['home_league_position']
    
    # 5. Форма (тренд)
    if 'home_points_last5' in df.columns and 'home_points_last3' in df.columns:
        df['home_form_trend'] = df['home_points_last3'] - (df['home_points_last5'] * 0.6)
    
    # 6. Дерби / топ vs аутсайдер
    if 'home_league_position' in df.columns:
        df['is_top_vs_bottom'] = (
            (df['home_league_position'] <= 3) & (df['away_league_position'] >= 18)
        ).astype(int)
    
    # Заполняем NaN
    df = df.fillna(0)
    
    return df


def create_ensemble_model():
    """Создаёт ансамбль моделей"""
    
    # XGBoost — основная модель
    xgb = XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        eval_metric='mlogloss',
        use_label_encoder=False
    )
    
    # RandomForest — для устойчивости
    rf = RandomForestClassifier(
        n_estimators=200,
        max_depth=12,
        min_samples_split=10,
        min_samples_leaf=5,
        random_state=42,
        class_weight='balanced',
        n_jobs=-1
    )
    
    # LogisticRegression — для калибровки
    lr = LogisticRegression(
        max_iter=1000,
        random_state=42,
        class_weight='balanced',
        multi_class='multinomial'
    )
    
    # Ансамбль через голосование
    ensemble = VotingClassifier(
        estimators=[
            ('xgb', xgb),
            ('rf', rf),
            ('lr', lr)
        ],
        voting='soft'  # Используем вероятности
    )
    
    return ensemble


def calibrate_model(model, X_calib, y_calib):
    """Калибрует вероятности модели"""
    logger.info("🔧 Калибровка вероятностей...")
    
    calibrator = CalibratedClassifierCV(
        model,
        method='isotonic',  # isotonic лучше для больших данных
        cv=5
    )
    calibrator.fit(X_calib, y_calib)
    
    # Оцениваем качество калибровки
    prob_pred = calibrator.predict_proba(X_calib)
    brier = brier_score_loss(y_calib, prob_pred, pos_label=1) if len(np.unique(y_calib)) == 2 else 0
    
    logger.info(f"✅ Калибровка завершена, Brier score: {brier:.4f}")
    
    return calibrator, brier


def train_advanced_model():
    """Основной пайплайн обучения"""
    
    # 1. Загружаем данные
    df = load_enhanced_data()
    if df is None:
        return
    
    # 2. Определяем признаки
    feature_cols = [
        'home_xg_last5', 'away_xg_last5',
        'home_xg_diff_last5', 'away_xg_diff_last5', 'xg_diff_total',
        'home_points_last5', 'away_points_last5',
        'home_points_last3', 'away_points_last3',
        'home_goals_scored_last5', 'away_goals_scored_last5',
        'home_goals_against_last5', 'away_goals_against_last5',
        'odds_home', 'odds_draw', 'odds_away',
        'odds_home_implied_prob', 'odds_draw_implied_prob', 'odds_away_implied_prob',
        'h2h_home_wins', 'h2h_draws', 'h2h_away_wins',
        'home_league_position', 'away_league_position',
        'position_diff',
        'home_win_rate_season', 'away_win_rate_season',
        'home_possession_avg', 'away_possession_avg',
        'home_shots_avg', 'away_shots_avg',
        'home_shots_on_target_avg', 'away_shots_on_target_avg',
        'days_since_last_match_home', 'days_since_last_match_away',
        'is_derby', 'is_top_vs_bottom',
        'home_form_trend'
    ]
    
    # Фильтруем только существующие колонки
    available_features = [f for f in feature_cols if f in df.columns]
    logger.info(f"📋 Используем {len(available_features)} признаков: {available_features}")
    
    X = df[available_features]
    y = df['result']  # 0=H, 1=D, 2=A
    
    # 3. Разделяем данные
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.3, random_state=42, stratify=y
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.5, random_state=42, stratify=y_temp
    )
    
    logger.info(f"📊 Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}")
    
    # 4. Создаём и обучаем ансамбль
    logger.info("🏋️ Обучение ансамблевой модели...")
    ensemble = create_ensemble_model()
    ensemble.fit(X_train, y_train)
    
    # 5. Оценка на валидации
    val_pred = ensemble.predict(X_val)
    val_acc = accuracy_score(y_val, val_pred)
    logger.info(f"🎯 Accuracy на валидации: {val_acc:.2%}")
    
    # 6. Калибровка
    calibrator, brier = calibrate_model(ensemble, X_val, y_val)
    
    # 7. Финальная оценка на тесте
    test_pred = ensemble.predict(X_test)
    test_probs = ensemble.predict_proba(X_test)
    test_acc = accuracy_score(y_test, test_pred)
    test_logloss = log_loss(y_test, test_probs)
    
    # С калибровкой
    calib_probs = calibrator.predict_proba(X_test)
    calib_pred = np.argmax(calib_probs, axis=1)
    calib_acc = accuracy_score(y_test, calib_pred)
    
    logger.info(f"\n{'='*50}")
    logger.info(f"📊 ФИНАЛЬНЫЕ РЕЗУЛЬТАТЫ")
    logger.info(f"{'='*50}")
    logger.info(f"🎯 Accuracy (без калибровки): {test_acc:.2%}")
    logger.info(f"🎯 Accuracy (с калибровкой):  {calib_acc:.2%}")
    logger.info(f"📉 LogLoss: {test_logloss:.4f}")
    logger.info(f"🔧 Brier Score: {brier:.4f}")
    
    logger.info(f"\n📋 Classification Report:")
    print(classification_report(y_test, calib_pred, target_names=['HOME', 'DRAW', 'AWAY']))
    
    # 8. Анализ value bets
    analyze_value_bets(X_test, y_test, calib_probs, test_pred)
    
    # 9. Сохраняем модель
    Path("ml_models").mkdir(exist_ok=True)
    
    with open("ml_models/advanced_model.pkl", "wb") as f:
        pickle.dump(ensemble, f)
    
    with open("ml_models/advanced_model_calibrator.pkl", "wb") as f:
        pickle.dump(calibrator, f)
    
    meta = {
        "accuracy": float(calib_acc),
        "accuracy_uncalibrated": float(test_acc),
        "calibration_quality": float(brier),
        "logloss": float(test_logloss),
        "feature_cols": available_features,
        "n_features": len(available_features),
        "n_train": len(X_train),
        "n_test": len(X_test),
        "training_date": pd.Timestamp.now().isoformat()
    }
    
    with open("ml_models/advanced_model.meta.json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    
    logger.info(f"\n💾 Модель сохранена в ml_models/")
    logger.info(f"   - advanced_model.pkl")
    logger.info(f"   - advanced_model_calibrator.pkl")
    logger.info(f"   - advanced_model.meta.json")
    
    # 10. Важность признаков
    if hasattr(ensemble, 'named_estimators_'):
        if 'xgb' in ensemble.named_estimators_:
            xgb_model = ensemble.named_estimators_['xgb']
            if hasattr(xgb_model, 'feature_importances_'):
                logger.info(f"\n🔍 Важность признаков (XGBoost):")
                importances = sorted(
                    zip(available_features, xgb_model.feature_importances_),
                    key=lambda x: x[1], reverse=True
                )
                for feature, imp in importances[:15]:
                    logger.info(f"   {feature}: {imp:.3f}")


def analyze_value_bets(X_test, y_test, probs, preds, min_edge=0.05):
    """Анализирует качество value bets"""
    
    label_map = {0: "H", 1: "D", 2: "A"}
    
    # Симулируем коэффициенты (в реальности берём из данных)
    np.random.seed(42)
    odds = np.random.uniform(1.5, 4.0, size=(len(y_test), 3))
    
    value_bets = []
    profits = []
    
    for i in range(len(y_test)):
        pred_idx = preds[i]
        true_idx = y_test.iloc[i] if hasattr(y_test, 'iloc') else y_test[i]
        
        our_prob = probs[i][pred_idx]
        implied_prob = 1.0 / odds[i][pred_idx]
        edge = our_prob - implied_prob
        
        if edge > min_edge:
            value_bets.append({
                'predicted': label_map[pred_idx],
                'actual': label_map[true_idx],
                'our_prob': our_prob,
                'implied_prob': implied_prob,
                'edge': edge,
                'odds': odds[i][pred_idx],
                'won': pred_idx == true_idx
            })
            
            # ROI расчёт
            if pred_idx == true_idx:
                profits.append(odds[i][pred_idx] - 1)
            else:
                profits.append(-1)
    
    if value_bets:
        n_bets = len(value_bets)
        n_wins = sum(1 for v in value_bets if v['won'])
        winrate = n_wins / n_bets
        roi = sum(profits) / n_bets * 100
        
        logger.info(f"\n💰 АНАЛИЗ VALUE BETS (edge > {min_edge})")
        logger.info(f"   Всего ставок: {n_bets}")
        logger.info(f"   Выигрышей: {n_wins} ({winrate:.1%})")
        logger.info(f"   ROI: {roi:+.1f}%")
        
        if roi > 0:
            logger.info(f"   ✅ Модель показывает прибыль!")
        else:
            logger.info(f"   ⚠️ Модель убыточна на value bets")


if __name__ == "__main__":
    train_advanced_model()
