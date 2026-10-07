"""SQLite data access and deterministic demo seeding."""
import csv
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from .config import DB_PATH, DATA_DIR

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS users (
  user_id TEXT PRIMARY KEY, occupation TEXT NOT NULL, age_group TEXT NOT NULL,
  monthly_income REAL NOT NULL, current_savings REAL NOT NULL, language TEXT NOT NULL,
  region TEXT NOT NULL, city TEXT NOT NULL, account_age_days INTEGER NOT NULL,
  average_monthly_transactions REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS import_batches (
  import_id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(user_id),
  filename TEXT NOT NULL, fingerprint TEXT NOT NULL UNIQUE, row_count INTEGER NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS transactions (
  transaction_id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(user_id),
  timestamp TEXT NOT NULL, amount REAL NOT NULL, transaction_type TEXT NOT NULL,
  category TEXT NOT NULL, merchant TEXT NOT NULL, device_type TEXT NOT NULL,
  location TEXT NOT NULL, channel TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_transactions_user_date ON transactions(user_id, timestamp);
CREATE INDEX IF NOT EXISTS ix_transactions_user_category_date ON transactions(user_id, category, timestamp);
CREATE INDEX IF NOT EXISTS ix_transactions_user_type_date ON transactions(user_id, transaction_type, timestamp);
CREATE INDEX IF NOT EXISTS ix_import_batches_user ON import_batches(user_id);
CREATE TABLE IF NOT EXISTS monthly_features (
  user_id TEXT NOT NULL REFERENCES users(user_id), month TEXT NOT NULL, income REAL NOT NULL,
  total_expense REAL NOT NULL, food_expense REAL NOT NULL, shopping_expense REAL NOT NULL,
  transport_expense REAL NOT NULL, entertainment_expense REAL NOT NULL, bill_expense REAL NOT NULL, cashout_expense REAL NOT NULL,
  other_expense REAL NOT NULL, transaction_count INTEGER NOT NULL, average_transaction REAL NOT NULL,
  previous_month_expense REAL NOT NULL, rolling_3m_expense REAL NOT NULL,
  month_number INTEGER NOT NULL, season_sin REAL NOT NULL, season_cos REAL NOT NULL,
  PRIMARY KEY(user_id, month)
);
CREATE TABLE IF NOT EXISTS goals (
  goal_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL REFERENCES users(user_id),
  goal_name TEXT NOT NULL, target_amount REAL NOT NULL, current_saved_amount REAL NOT NULL,
  target_months INTEGER NOT NULL, deadline TEXT, priority TEXT NOT NULL,
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS goal_contributions (
  contribution_id INTEGER PRIMARY KEY AUTOINCREMENT, goal_id INTEGER NOT NULL REFERENCES goals(goal_id),
  amount REAL NOT NULL CHECK(amount>0), note TEXT NOT NULL DEFAULT '',
  created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS ix_goals_user_latest ON goals(user_id, goal_id DESC);
CREATE INDEX IF NOT EXISTS ix_contributions_goal_date ON goal_contributions(goal_id, created_at);
CREATE TABLE IF NOT EXISTS goal_plans (
  plan_id INTEGER PRIMARY KEY AUTOINCREMENT, goal_id INTEGER NOT NULL REFERENCES goals(goal_id),
  plan_json TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS recommendations (
  recommendation_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL REFERENCES users(user_id),
  kind TEXT NOT NULL, text_en TEXT NOT NULL, text_bn TEXT NOT NULL,
  reason_en TEXT NOT NULL, reason_bn TEXT NOT NULL, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS model_metrics (
  metric_key TEXT PRIMARY KEY, value_json TEXT NOT NULL
);
"""

@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def initialize(seed=True):
    with connect() as conn:
        conn.executescript(SCHEMA)
        user_columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
        if "display_name" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN display_name TEXT NOT NULL DEFAULT ''")
        if "is_imported" not in user_columns:
            conn.execute("ALTER TABLE users ADD COLUMN is_imported INTEGER NOT NULL DEFAULT 0")
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if not seed:
            return
        metrics = DATA_DIR / "model_metrics.json"
        if metrics.exists():
            conn.execute("INSERT OR REPLACE INTO model_metrics VALUES (?,?)", ("forecast", metrics.read_text(encoding="utf-8")))
        if count:
            return
        users_path = DATA_DIR / "users.csv"
        tx_path = DATA_DIR / "transactions.csv"
        monthly_path = DATA_DIR / "monthly_features.csv"
        if not users_path.exists():
            return
        with users_path.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                conn.execute("INSERT INTO users (user_id,occupation,age_group,monthly_income,current_savings,language,region,city,account_age_days,average_monthly_transactions) VALUES (?,?,?,?,?,?,?,?,?,?)", (
                    row["user_id"], row["occupation"], row["age_group"], float(row["monthly_income"]),
                    float(row["current_savings"]), row["language"], row["region"], row["city"],
                    int(row["account_age_days"]), float(row["average_monthly_transactions"])))
        with tx_path.open(encoding="utf-8-sig", newline="") as f:
            batch = []
            for row in csv.DictReader(f):
                batch.append(tuple(row[k] for k in ("transaction_id", "user_id", "timestamp", "amount", "transaction_type", "category", "merchant", "device_type", "location", "channel")))
                if len(batch) == 2000:
                    conn.executemany("INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?,?,?)", batch); batch.clear()
            if batch: conn.executemany("INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?,?,?)", batch)
        with monthly_path.open(encoding="utf-8-sig", newline="") as f:
            cols = ("user_id", "month", "income", "total_expense", "food_expense", "shopping_expense", "transport_expense", "entertainment_expense", "bill_expense", "cashout_expense", "other_expense", "transaction_count", "average_transaction", "previous_month_expense", "rolling_3m_expense", "month_number", "season_sin", "season_cos")
            sql = "INSERT INTO monthly_features VALUES (" + ",".join("?" for _ in cols) + ")"
            batch = []
            for row in csv.DictReader(f):
                vals = [row[k] if k in ("user_id", "month") else int(row[k]) if k in ("transaction_count", "month_number") else float(row[k]) for k in cols]
                batch.append(vals)
                if len(batch) == 2000:
                    conn.executemany(sql, batch); batch.clear()
            if batch: conn.executemany(sql, batch)
        personas_path = DATA_DIR / "personas.json"
        if personas_path.exists():
            personas = json.loads(personas_path.read_text(encoding="utf-8"))
            for p in personas:
                conn.execute("INSERT INTO goals (user_id,goal_name,target_amount,current_saved_amount,target_months,deadline,priority) VALUES (?,?,?,?,?,?,?)",
                    (p["user_id"], p["goal"]["name"], p["goal"]["target_amount"], p["goal"]["current_saved_amount"], p["goal"]["target_months"], p["goal"].get("deadline"), p["goal"].get("priority", "medium")))

def row_dict(row):
    return dict(row) if row is not None else None
