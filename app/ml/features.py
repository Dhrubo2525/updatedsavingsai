"""Time-ordered supervised examples for one-step expense forecasting."""
import pandas as pd

FEATURE_COLUMNS = ["income", "total_expense", "food_expense", "shopping_expense", "transport_expense",
    "bill_expense", "cashout_expense", "other_expense", "transaction_count", "average_transaction",
    "previous_month_expense", "rolling_3m_expense", "month_number", "season_sin", "season_cos"]

def load_examples(path):
    frame = pd.read_csv(path, parse_dates=["month"])
    frame = frame.sort_values(["month", "user_id"]).reset_index(drop=True)
    frame["month_index"] = frame["month"].map(lambda d: d.year * 12 + d.month)
    frame["next_expense"] = frame.groupby("user_id")["total_expense"].shift(-1)
    frame["target_index"] = frame.groupby("user_id")["month_index"].shift(-1)
    examples = frame.dropna(subset=["next_expense"]).copy()
    return examples, FEATURE_COLUMNS
