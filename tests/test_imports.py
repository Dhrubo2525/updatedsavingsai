from pathlib import Path
from uuid import uuid4

from .conftest import client


def data(response):
    assert response.status_code < 400, response.text
    body = response.json()
    assert body["error"] is None
    return body["data"]


def csv_payload(tag=None):
    tag = tag or uuid4().hex[:10]
    content = (
        "date,amount,transaction_type,category,merchant\n"
        f"2026-01-02,1000,expense,Food,Market {tag}\n"
        f"2026-01-05,30000,income,,Salary {tag}\n"
        f"2026-02-01,250,payment,Transport,Bus {tag}\n"
    )
    return {
        "display_name": f"Imported {tag}",
        "monthly_income": 28000,
        "current_savings": 5000,
        "region": "Dhaka",
        "language": "en",
        "filename": "transactions.csv",
        "csv_text": content,
    }


def test_csv_preview_save_duplicate_export_and_delete():
    from app.db import initialize

    initialize(seed=True)
    payload = csv_payload()
    preview = data(client.post("/api/import/preview", json={
        "csv_text": payload["csv_text"], "region": payload["region"]
    }))
    assert preview["row_count"] == 3
    assert preview["expense_rows"] == 2
    assert preview["income_rows"] == 1
    assert preview["month_count"] == 2
    assert preview["duplicate_file"] is False
    assert preview["sample"][0]["category"] == "Food"

    response = client.post("/api/import", json=payload)
    assert response.status_code == 201, response.text
    created = response.json()["data"]
    user_id = created["user_id"]
    assert created["rows_imported"] == 3

    summary = data(client.get(f"/api/users/{user_id}/summary"))
    assert summary["transaction_count"] == 2
    assert [month["total"] for month in summary["spending"]["monthly"]] == [1000, 250]
    assert summary["monthly_income_estimate"] >= 28000
    incomes = data(client.get(f"/api/users/{user_id}/transactions?transaction_type=income"))
    assert incomes["total"] == 1

    duplicate_preview = data(client.post("/api/import/preview", json={
        "csv_text": payload["csv_text"], "region": payload["region"]
    }))
    assert duplicate_preview["duplicate_file"] is True
    duplicate = client.post("/api/import", json=payload)
    assert duplicate.status_code == 409

    goal = data(client.post("/api/goals", json={
        "user_id": user_id,
        "goal_name": "Imported goal",
        "target_amount": 20000,
        "current_saved_amount": 5000,
        "target_months": 6,
    }))
    plan = data(client.post(f"/api/goals/{goal['goal_id']}/plan", json={}))
    assert "imported months" in plan["assumption"]
    contribution = data(client.post(f"/api/goals/{goal['goal_id']}/contributions", json={"amount": 1000, "note": "Monthly deposit"}))
    assert contribution["current_saved_amount"] == 6000
    history = data(client.get(f"/api/goals/{goal['goal_id']}/history"))
    assert [event["cumulative_amount"] for event in history["events"]] == [5000, 6000]
    exceeds_goal = client.post(f"/api/goals/{goal['goal_id']}/contributions", json={"amount": 15000})
    assert exceeds_goal.status_code == 422

    exported = client.get(f"/api/users/{user_id}/transactions/export")
    assert exported.status_code == 200
    assert "text/csv" in exported.headers["content-type"]
    assert "timestamp,amount,transaction_type" in exported.text
    assert "Salary" in exported.text

    assert data(client.delete(f"/api/import/{user_id}"))["deleted"] is True
    assert client.get(f"/api/users/{user_id}").status_code == 404
    assert client.get(f"/api/goals/{goal['goal_id']}").status_code == 404
    after_delete = data(client.post("/api/import/preview", json={
        "csv_text": payload["csv_text"], "region": payload["region"]
    }))
    assert after_delete["duplicate_file"] is False


def test_csv_preview_rejects_missing_headers_and_bad_rows():
    from app.db import initialize

    initialize(seed=True)
    missing_header = client.post("/api/import/preview", json={"csv_text": "merchant,amount\nMarket,10\n"})
    assert missing_header.status_code == 422
    assert missing_header.json()["detail"]["code"] == "invalid_csv"

    bad_date = client.post("/api/import/preview", json={
        "csv_text": "date,amount\nnot-a-date,10\n"
    })
    assert bad_date.status_code == 422
    assert "Row 2" in bad_date.json()["detail"]["message"]

    bad_amount = client.post("/api/import/preview", json={
        "csv_text": "date,amount\n2026-01-01,not-money\n"
    })
    assert bad_amount.status_code == 422
    assert "amount must be a number" in bad_amount.json()["detail"]["message"]


def test_import_rejects_empty_and_excessive_header_columns():
    empty_header = client.post("/api/import/preview", json={
        "csv_text": ",date,amount\n,2026-01-01,10\n"
    })
    assert empty_header.status_code == 422
    assert "named columns" in empty_header.json()["detail"]["message"]

    headers = ["date", "amount", *[f"column_{index}" for index in range(79)]]
    values = ["2026-01-01", "10", *[""] * 79]
    too_many_columns = client.post("/api/import/preview", json={
        "csv_text": ",".join(headers) + "\n" + ",".join(values) + "\n"
    })
    assert too_many_columns.status_code == 422
    assert "80 columns" in too_many_columns.json()["detail"]["message"]


def test_initialize_migrates_existing_local_users_table(monkeypatch, tmp_path):
    import sqlite3
    from app import db

    old_database = tmp_path / "pre_import.sqlite3"
    connection = sqlite3.connect(old_database)
    connection.execute("CREATE TABLE users (user_id TEXT PRIMARY KEY, occupation TEXT NOT NULL, age_group TEXT NOT NULL, monthly_income REAL NOT NULL, current_savings REAL NOT NULL, language TEXT NOT NULL, region TEXT NOT NULL, city TEXT NOT NULL, account_age_days INTEGER NOT NULL, average_monthly_transactions REAL NOT NULL)")
    connection.commit()
    connection.close()
    monkeypatch.setattr(db, "DB_PATH", old_database)
    db.initialize(seed=False)
    with sqlite3.connect(old_database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(users)")}
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"display_name", "is_imported"} <= columns
    assert "import_batches" in tables

def test_custom_csv_headers_can_be_mapped_before_save():
    from app.db import initialize

    initialize(seed=True)
    content = (
        "When,Money,Kind,Group,Details\n"
        "2026-03-01,4200,expense,Shopping,Store MapTest\n"
        "2026-03-12,26000,income,Income,Salary MapTest\n"
    )
    columns = data(client.post("/api/import/columns", json={"csv_text": content}))
    assert columns["columns"] == ["When", "Money", "Kind", "Group", "Details"]
    assert columns["suggested_mapping"]["date"] == ""
    mapping = {"date": "When", "amount": "Money", "type": "Kind", "category": "Group", "merchant": "Details"}
    preview = data(client.post("/api/import/preview", json={"csv_text": content, "column_map": mapping}))
    assert preview["expense_total"] == 4200
    imported = data(client.post("/api/import", json={
        "display_name": "Mapped profile",
        "monthly_income": 26000,
        "current_savings": 0,
        "language": "en",
        "csv_text": content,
        "column_map": mapping,
    }))
    summary = data(client.get(f"/api/users/{imported['user_id']}/summary"))
    assert summary["monthly_spending"] == 4200
    assert data(client.delete(f"/api/import/{imported['user_id']}"))["deleted"] is True
