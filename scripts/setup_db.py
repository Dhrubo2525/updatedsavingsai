"""Create the SQLite demo database and import the generated synthetic dataset."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.db import initialize
from app.config import DB_PATH
initialize(seed=True)
print(f"SQLite database ready: {DB_PATH}")
