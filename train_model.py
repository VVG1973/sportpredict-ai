import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import joblib
import os
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

def load_real_data():
    """Загружает реальные исторические данные"""
    csv_path = "data/historical_matches.csv"
    if not os.path.exists(csv_path):
        logger.error(f"❌ Файл {csv_path} не найден! Сначала запустите historical_data_loader.py")
        return None
    
    df = pd.read_csv(csv_path)
    logger.info(f"📊 Загружено {len(df)} реальных матчей")
    return df

def train_real_model():
    """Обучает модель на реальных данных"""
    df = load_real_data()
    if df is None:
        return
    
    # Признаки для модели
    features = ['home_form', 'away_form', 'h2h_home_win', 'home_streak', 'key_injuries']
    X = df[features]
    y = df['result']
    
    # Разделяем на train/test
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    logger.info("🏋️ Обучение RandomForest на реальных данных...")
    model = RandomForestClassifier(
        n_estimators=200,
        max_depth=12,
        random_state=42,
        class_weight='balanced',
        n_jobs=-1
    )
    model.fit(X_train, y_train)
    
    # Оценка качества
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    
    logger.info(f"✅ Модель обучена!")
    logger.info(f"🎯 Accuracy на тестовой выборке: {accuracy:.2%}")
    logger.info("\n📊 Classification Report:")
    print(classification_report(y_test, y_pred, target_names=['HOME', 'DRAW', 'AWAY']))
    
    # Сохраняем модель
    os.makedirs('data/models', exist_ok=True)
    model_path = 'data/models/model_real.pkl'
    joblib.dump(model, model_path)
    logger.info(f"💾 Модель сохранена в {model_path}")
    
    # Важность признаков
    logger.info("\n🔍 Важность признаков:")
    for feature, importance in zip(features, model.feature_importances_):
        logger.info(f"  {feature}: {importance:.3f}")

if __name__ == "__main__":
    train_real_model()
