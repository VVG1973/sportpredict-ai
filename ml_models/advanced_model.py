import xgboost as xgb

class AdvancedPredictionModel:
    def __init__(self, model_dir: str = "ml_models"):
        self.models = {}
        self.feature_cols = []
        self.accuracy = {}
        self.is_loaded = False
        self._load_model()
    
    def _load_model(self):
        meta_path = Path("ml_models/xgboost_models.meta.json")
        if not meta_path.exists():
            logger.error("❌ XGBoost модели не найдены")
            return
        
        with open(meta_path) as f:
            meta = json.load(f)
        
        self.feature_cols = meta.get("feature_cols", [])
        
        for name in meta.get("models", []):
            path = Path(f"ml_models/xgboost_{name}.json")
            if path.exists():
                model = xgb.XGBClassifier()
                model.load_model(str(path))
                self.models[name] = model
        
        self.is_loaded = len(self.models) > 0
        logger.info(f"✅ Загружено {len(self.models)} XGBoost моделей")