"""Create a reproducible, fully synthetic 250-user/12-month wallet dataset."""
import csv
import json
import math
import random
import sys
from calendar import monthrange
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SEED = 202609
CATEGORIES = ["Food", "Transport", "Shopping", "Bills", "Mobile Recharge", "Education", "Entertainment", "Healthcare", "Cash Out", "Transfer", "Other"]
MERCHANTS = {
    "Food": ["Local Market", "Cafe", "Grocery Store", "Food Delivery"], "Transport": ["Ride Share", "Bus Ticket", "Fuel Station"],
    "Shopping": ["Online Store", "Clothing Shop", "Electronics"], "Bills": ["Electricity", "Internet", "Water Utility"],
    "Mobile Recharge": ["Mobile Operator"], "Education": ["Bookshop", "Course Platform", "Campus Cafe"],
    "Entertainment": ["Cinema", "Streaming", "Event Ticket"], "Healthcare": ["Pharmacy", "Clinic"],
    "Cash Out": ["Agent Point"], "Transfer": ["Family Transfer"], "Other": ["General Merchant", "Personal Services"]}
OCCUPATIONS = ["University student", "Private employee", "Freelancer", "Small business owner", "Teacher", "Healthcare worker", "Service worker"]
REGIONS = ["Dhaka", "Chattogram", "Sylhet", "Rajshahi", "Khulna", "Barishal", "Rangpur", "Mymensingh"]

def csv_write(path, fields, rows):
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)

def main():
    rng = random.Random(SEED)
    DATA.mkdir(exist_ok=True)
    user_rows, monthly_rows, transaction_rows = [], [], []
    starts = [(2025 + (9 + i) // 12, (9 + i) % 12 + 1) for i in range(12)]
    profiles = []
    for i in range(250):
        uid = f"SYN-{i+1:04d}"
        if i == 0: occupation, age, income, savings = "University student", "18-24", 18000, 13500
        elif i == 1: occupation, age, income, savings = "Private employee", "25-34", 36000, 27000
        elif i == 2: occupation, age, income, savings = "Freelancer", "25-34", 42000, 4000
        else:
            occupation = rng.choice(OCCUPATIONS); age = rng.choice(["18-24", "25-34", "35-44", "45-54"])
            income = round(rng.uniform(16000, 82000) / 500) * 500
            savings = round(rng.uniform(0.15, 2.4) * income / 500) * 500
        region = REGIONS[i % len(REGIONS)]; city = "Dhaka" if region == "Dhaka" else region
        lang = "bn" if i % 4 else "en"
        user_rows.append({"user_id": uid, "occupation": occupation, "age_group": age, "monthly_income": income,
            "current_savings": savings, "language": lang, "region": region, "city": city,
            "account_age_days": rng.randint(180, 2400), "average_monthly_transactions": round(rng.uniform(18, 55), 1)})
        profiles.append((uid, occupation, age, income, savings, region))

    tx_num = 0
    # Each persona has a distinct but still synthetic behavior pattern.
    for user_i, (uid, occupation, age, base_income, savings, region) in enumerate(profiles):
        is_student = occupation == "University student"
        is_freelancer = occupation == "Freelancer"
        base_expense = (14200 if user_i == 0 else 29400 if user_i == 1 else 31600 if user_i == 2 else base_income * rng.uniform(.64, .91))
        user_history = []
        income_history = []
        for month_idx, (year, month) in enumerate(starts):
            season = 1 + 0.035 * math.sin((month - 1) * 2 * math.pi / 12)
            trend = 1 + 0.0035 * month_idx + 0.015 * math.sin((month_idx + user_i % 6) / 2.1)
            monthly_noise = max(.83, min(1.20, rng.gauss(1.0, .075)))
            expense = base_expense * season * trend * monthly_noise
            if month in (12, 1): expense *= rng.uniform(1.03, 1.15)
            if is_student and month in (1, 6, 12): expense *= 1.08
            monthly_income = base_income * (rng.uniform(.58, 1.42) if is_freelancer else rng.uniform(.94, 1.06))
            if user_i == 2 and month_idx % 4 == 1: monthly_income *= .72
            if user_i == 2 and month_idx % 4 == 2: monthly_income *= 1.28
            shares = {"Food": .28, "Transport": .10, "Shopping": .14, "Bills": .15, "Mobile Recharge": .035,
                      "Education": .07 if is_student else .035, "Entertainment": .065, "Healthcare": .045,
                      "Cash Out": .07, "Transfer": .04, "Other": .07}
            if user_i == 0: shares.update({"Food": .31, "Shopping": .13, "Education": .11, "Cash Out": .09})
            if user_i == 1: shares.update({"Food": .30, "Shopping": .21, "Bills": .14})
            if user_i == 2: shares.update({"Cash Out": .11, "Transfer": .08, "Shopping": .12})
            if user_i == 1 and month_idx == 11: shares["Shopping"] *= 2.0
            norm = sum(shares.values()); shares = {k: v / norm for k, v in shares.items()}
            category_totals = {k: expense * v * max(.6, rng.gauss(1, .05)) for k, v in shares.items()}
            scale = expense / sum(category_totals.values()); category_totals = {k: v * scale for k, v in category_totals.items()}
            monthly_actual = 0; monthly_tx_count = 0
            for cat, budget in category_totals.items():
                # Higher-frequency categories are split into more plausible small transactions.
                count = max(1, int(round(budget / (1000 if cat in ("Bills", "Cash Out", "Transfer", "Healthcare") else 680))))
                count = min(count, 13)
                weights = [rng.lognormvariate(0, .45) for _ in range(count)]; sw = sum(weights)
                amounts = [round(budget * w / sw, 2) for w in weights]
                amounts[-1] = round(amounts[-1] + budget - sum(amounts), 2)
                for amount in amounts:
                    tx_num += 1; monthly_tx_count += 1; monthly_actual += amount
                    day = rng.randint(1, monthrange(year, month)[1])
                    tx_date = date(year, month, day)
                    tx_kind = "cash_out" if cat == "Cash Out" else "transfer" if cat == "Transfer" else "payment"
                    transaction_rows.append({"transaction_id": f"TX-{tx_num:07d}", "user_id": uid,
                        "timestamp": f"{tx_date.isoformat()}T{rng.randint(7,22):02d}:{rng.randint(0,59):02d}:00",
                        "amount": f"{amount:.2f}", "transaction_type": tx_kind, "category": cat,
                        "merchant": rng.choice(MERCHANTS[cat]), "device_type": rng.choice(["Android", "iOS", "Web"]),
                        "location": region, "channel": rng.choice(["wallet_app", "qr", "agent", "online"])})
            user_history.append(monthly_actual); income_history.append(monthly_income)
            month_key = f"{year:04d}-{month:02d}"
            cats = category_totals
            previous = user_history[-2] if len(user_history) > 1 else monthly_actual
            roll3 = sum(user_history[-3:]) / min(3, len(user_history))
            monthly_rows.append({"user_id": uid, "month": month_key, "income": round(monthly_income, 2),
                "total_expense": round(monthly_actual, 2), "food_expense": round(cats["Food"], 2),
                "shopping_expense": round(cats["Shopping"], 2), "transport_expense": round(cats["Transport"], 2),
                "entertainment_expense": round(cats["Entertainment"], 2),
                "bill_expense": round(cats["Bills"] + cats["Mobile Recharge"], 2),
                "cashout_expense": round(cats["Cash Out"], 2),
                "other_expense": round(sum(cats[k] for k in CATEGORIES if k not in ("Food", "Shopping", "Transport", "Bills", "Mobile Recharge", "Cash Out")), 2),
                "transaction_count": monthly_tx_count, "average_transaction": round(monthly_actual / monthly_tx_count, 2),
                "previous_month_expense": round(previous, 2), "rolling_3m_expense": round(roll3, 2),
                "month_number": month, "season_sin": round(math.sin(2*math.pi*month/12), 6),
                "season_cos": round(math.cos(2*math.pi*month/12), 6)})

    csv_write(DATA / "users.csv", list(user_rows[0]), user_rows)
    csv_write(DATA / "transactions.csv", list(transaction_rows[0]), transaction_rows)
    csv_write(DATA / "monthly_features.csv", list(monthly_rows[0]), monthly_rows)
    personas = [
      {"persona_id":"nadia","name":"Nadia","user_id":"SYN-0001","profile":"University student","story":"Irregular discretionary spending; building a small emergency fund.","demo_purpose":"Show a behavior-aware savings plan.","goal":{"name":"Emergency Fund","target_amount":30000,"current_saved_amount":13500,"target_months":6,"priority":"high","deadline":"2027-03-31"}},
      {"persona_id":"arif","name":"Arif","user_id":"SYN-0002","profile":"Private employee","story":"Regular income with higher food and shopping spending; shopping rose sharply in the latest synthetic month.","demo_purpose":"Show spending analysis, a grounded recommendation and What-If.","goal":{"name":"New Laptop","target_amount":60000,"current_saved_amount":27000,"target_months":6,"priority":"medium","deadline":"2027-03-31"}},
      {"persona_id":"rafi","name":"Rafi","user_id":"SYN-0003","profile":"Freelancer","story":"Income varies month to month, so the planner uses a conservative recent-income estimate.","demo_purpose":"Show variable-income planning and an honest difficult-goal result.","goal":{"name":"Emergency Reserve","target_amount":80000,"current_saved_amount":4000,"target_months":9,"priority":"high","deadline":"2027-06-30"}}
    ]
    (DATA / "personas.json").write_text(json.dumps(personas, ensure_ascii=False, indent=2), encoding="utf-8")
    assumptions = {"synthetic_only":True,"seed":SEED,"users":len(user_rows),"history_months":12,"transactions":len(transaction_rows),
      "period":f"{starts[0][0]:04d}-{starts[0][1]:02d} through {starts[-1][0]:04d}-{starts[-1][1]:02d}",
      "assumptions":["Transaction amounts are simulated category allocations, not wallet records.","Income is generated as a monthly signal; income rows are not transaction rows.","Freelancer income has a wider distribution than salaried income.","Rare category spikes are injected for model and anomaly demonstrations.","Synthetic users do not represent or validate real upay customers."]}
    (DATA / "synthetic_assumptions.json").write_text(json.dumps(assumptions, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Generated {len(user_rows)} synthetic users, {len(transaction_rows):,} transactions, and {len(monthly_rows):,} monthly rows.")

if __name__ == "__main__": main()
