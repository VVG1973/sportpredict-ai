import pandas as pd
import numpy as np
import json
from pathlib import Path
from datetime import datetime
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

# Загрузка
df = pd.read_csv("data/historical/all_matches_clean.csv", low_memory=False)
df = df.dropna(subset=['FTHG', 'FTAG', 'FTR'])

# Таргеты
df['total_goals'] = df['FTHG'] + df['FTAG']
df['over_2_5'] = (df['total_goals'] > 2.5).astype(int)
df['both_scored'] = ((df['FTHG'] > 0) & (df['FTAG'] > 0)).astype(int)
df['goal_diff'] = df['FTHG'] - df['FTAG']
df['home_handicap_win'] = (df['goal_diff'] > 0).astype(int)

# Фичи
feature_cols = ['B365H', 'B365D', 'B365A', 'BWH', 'BWD', 'BWA', 
                'WHH', 'WHD', 'WHA', 'HS', 'AS', 'HST', 'AST', 'HC', 'AC']
feature_cols = [c for c in feature_cols if c in df.columns]
X = df[feature_cols].fillna(0)
y_outcome = df['FTR'].map({'H': 0, 'D': 1, 'A': 2})

# Разделение
X_train, X_test, y_train, y_test = train_test_split(X, y_outcome, test_size=0.2, random_state=42)

# Обучаем 4 модели XGBoost
models = {}

print("🏋️ Обучение исхода...")
model = XGBClassifier(n_estimators=200, max_depth=5, learning_rate=0.1, random_state=42)
model.fit(X_train, y_train)
models['outcome'] = model
print(f"✅ Исход: {accuracy_score(y_test, model.predict(X_test)):.2%}")

print("🏋️ Обучение тотала...")
model = XGBClassifier(n_estimators=150, max_depth=4, random_state=42)
model.fit(X_train, df['over_2_5'].loc[X_train.index])
models['total'] = model
print(f"✅ Тотал: {accuracy_score(df['over_2_5'].loc[X_test.index], model.predict(X_test)):.2%}")

print("🏋️ Обучение ОЗ...")
model = XGBClassifier(n_estimators=150, max_depth=4, random_state=42)
model.fit(X_train, df['both_scored'].loc[X_train.index])
models['both_scored'] = model
print(f"✅ ОЗ: {accuracy_score(df['both_scored'].loc[X_test.index], model.predict(X_test)):.2%}")

print("🏋️ Обучение форы...")
model = XGBClassifier(n_estimators=150, max_depth=4, random_state=42)
model.fit(X_train, df['home_handicap_win'].loc[X_train.index])
models['handicap'] = model
print(f"✅ Фора: {accuracy_score(df['home_handicap_win'].loc[X_test.index], model.predict(X_test)):.2%}")

# Сохраняем через XGBoost native format
Path("ml_models").mkdir(exist_ok=True)
for name, model in models.items():
    model.save_model(f"ml_models/xgboost_{name}.json")

# Метаданные
meta = {
    "feature_cols": feature_cols,
    "models": ["outcome", "total", "both_scored", "handicap"],
    "training_date": datetime.now().isoformat()
}
with open("ml_models/xgboost_models.meta.json", "w") as f:
    json.dump(meta, f)

print("💾 XGBoost модели сохранены в ml_models/xgboost_*.json")