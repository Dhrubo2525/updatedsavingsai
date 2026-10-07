import os
from pathlib import Path
from tempfile import gettempdir

ROOT=Path(__file__).resolve().parents[1]
os.environ["UPAYSAVE_DB_PATH"]=str(Path(gettempdir())/f"upaysave_ai_test_{os.getpid()}.sqlite3")
if not (ROOT/"data"/"users.csv").exists():
    from scripts.generate_data import main
    main()

from fastapi.testclient import TestClient
from app.main import app

client=TestClient(app)
