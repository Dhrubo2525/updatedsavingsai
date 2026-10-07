"""Small environment-driven application configuration."""
from pathlib import Path
import os

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
MODEL_DIR = ROOT / "models"
STATIC_DIR = Path(__file__).resolve().parent / "static"
DB_PATH = Path(os.getenv("UPAYSAVE_DB_PATH", str(ROOT / "upaysave.sqlite3")))
MODEL_PATH = MODEL_DIR / "expense_model.joblib"
METRICS_PATH = MODEL_DIR / "metrics.json"
FEATURES_PATH = MODEL_DIR / "feature_importance.json"
SAFETY_BUFFER_RATE = 0.05
MIN_SAFETY_BUFFER = 1000
