"""Parse user-supplied CSV exports and derive the monthly planning features."""
from collections import defaultdict
import csv
import io
import math
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

MAX_CSV_BYTES = 8_000_000
MAX_CSV_ROWS = 50_000
MAX_AMOUNT = 100_000_000

CATEGORIES = (
    "Food", "Transport", "Shopping", "Bills", "Mobile Recharge", "Education",
    "Entertainment", "Healthcare", "Cash Out", "Transfer", "Other",
)
FEATURE_COLUMNS = (
    "user_id", "month", "income", "total_expense", "food_expense", "shopping_expense",
    "transport_expense", "entertainment_expense", "bill_expense", "cashout_expense",
    "other_expense", "transaction_count", "average_transaction", "previous_month_expense",
    "rolling_3m_expense", "month_number", "season_sin", "season_cos",
)
FEATURE_CATEGORY_COLUMNS = {
    "Food": "food_expense", "Shopping": "shopping_expense", "Transport": "transport_expense",
    "Entertainment": "entertainment_expense", "Bills": "bill_expense",
    "Cash Out": "cashout_expense", "Other": "other_expense",
}


class CSVImportError(ValueError):
    """An actionable CSV formatting or row validation error."""


def normalize_header(value):
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def _column(headers, *candidates):
    return next((headers[candidate] for candidate in candidates if candidate in headers), None)


def _parse_amount(value, row_number):
    text = str(value or "").strip().replace("৳", "").replace("BDT", "").replace("bdt", "")
    text = text.replace("\u00a0", "").replace(" ", "")
    if "," in text and "." in text:
        text = text.replace(".", "").replace(",", ".") if text.rfind(",") > text.rfind(".") else text.replace(",", "")
    elif "," in text:
        whole, fractional = text.rsplit(",", 1)
        text = whole + "." + fractional if len(fractional) in (1, 2) else text.replace(",", "")
    if text.startswith("(") and text.endswith(")"):
        text = "-" + text[1:-1]
    try:
        amount = abs(Decimal(text))
    except (InvalidOperation, ValueError):
        raise CSVImportError(f"Row {row_number}: amount must be a number.") from None
    if not amount.is_finite() or amount == 0 or amount > MAX_AMOUNT:
        raise CSVImportError(f"Row {row_number}: amount must be greater than 0 and no more than ৳100,000,000.")
    result = float(amount)
    if not math.isfinite(result):
        raise CSVImportError(f"Row {row_number}: amount is outside the supported range.")
    return result


def _parse_timestamp(value, row_number):
    text = str(value or "").strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.isoformat(timespec="seconds")
    except ValueError:
        pass
    for fmt in ("%Y/%m/%d %H:%M:%S", "%Y/%m/%d", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, fmt).isoformat(timespec="seconds")
        except ValueError:
            continue
    raise CSVImportError(f"Row {row_number}: use YYYY-MM-DD or a common slash-separated date format.")


def _category(value, merchant=""):
    text = re.sub(r"[^a-z0-9]+", " ", f"{value or ''} {merchant or ''}".lower()).strip()
    aliases = (
        (("mobile recharge", "mobile top up", "top up", "topup", "recharge"), "Mobile Recharge"),
        (("cash out", "cashout", "withdraw", "atm"), "Cash Out"),
        (("transfer", "send money", "sent money", "p2p"), "Transfer"),
        (("food", "grocery", "groceries", "restaurant", "dining", "meal"), "Food"),
        (("transport", "travel", "ride", "commute", "fuel", "bus"), "Transport"),
        (("shopping", "retail", "purchase"), "Shopping"),
        (("bill", "utility", "electricity", "water bill"), "Bills"),
        (("education", "school", "tuition", "course"), "Education"),
        (("entertainment", "movie", "cinema", "leisure", "subscription"), "Entertainment"),
        (("healthcare", "health", "medical", "pharmacy", "hospital"), "Healthcare"),
    )
    for keys, category in aliases:
        if any(key in text for key in keys):
            return category
    exact = {item.lower(): item for item in CATEGORIES}
    return exact.get(text, "Other")


def csv_columns(text):
    if not isinstance(text, str) or not text.strip():
        raise CSVImportError("Choose a CSV file with a header row.")
    if len(text.encode("utf-8")) > MAX_CSV_BYTES:
        raise CSVImportError("CSV files must be 8 MB or smaller.")
    if "\ufffd" in text:
        raise CSVImportError("The CSV has invalid text encoding. Save it as UTF-8 and try again.")
    content = text.lstrip("\ufeff")
    try:
        dialect = csv.Sniffer().sniff(content[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(content), dialect=dialect)
    if reader.fieldnames:
        reader.fieldnames = [name.strip() if name else name for name in reader.fieldnames]
    columns = [str(value or "").strip() for value in (reader.fieldnames or [])]
    if not columns or any(not value for value in columns):
        raise CSVImportError("The CSV needs a header row with named columns.")
    if len(columns) > 80:
        raise CSVImportError("The CSV can contain at most 80 columns.")
    normalized = [normalize_header(value) for value in columns]
    if len(set(normalized)) != len(normalized):
        raise CSVImportError("The CSV has duplicate column names. Rename the columns and try again.")
    normalized_headers = {normalize_header(value): value for value in columns}
    aliases = {
        "date": ("timestamp", "date", "datetime", "transaction_date", "transaction_datetime", "time"),
        "amount": ("amount", "transaction_amount", "value"),
        "debit": ("debit", "withdrawal", "outflow"),
        "credit": ("credit", "deposit", "inflow"),
        "category": ("category", "transaction_category", "spending_category"),
        "type": ("transaction_type", "txn_type", "direction", "entry_type", "type"),
        "merchant": ("merchant", "description", "details", "narration", "recipient", "note", "name"),
        "location": ("location", "city"),
        "channel": ("channel", "payment_channel", "source"),
    }
    suggested = {key: next((normalized_headers[name] for name in names if name in normalized_headers), "") for key, names in aliases.items()}
    return columns, suggested


def parse_csv(text, fallback_region="", column_map=None):
    if not isinstance(text, str) or not text.strip():
        raise CSVImportError("Choose a CSV file with a header row.")
    if len(text.encode("utf-8")) > MAX_CSV_BYTES:
        raise CSVImportError("CSV files must be 8 MB or smaller.")
    if "\ufffd" in text:
        raise CSVImportError("The CSV has invalid text encoding. Save it as UTF-8 and try again.")
    content = text.lstrip("\ufeff")
    try:
        dialect = csv.Sniffer().sniff(content[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(content), dialect=dialect, restkey="__extra__")
    if reader.fieldnames:
        reader.fieldnames = [name.strip() if name else name for name in reader.fieldnames]
    if not reader.fieldnames:
        raise CSVImportError("The CSV needs a header row with date and amount columns.")
    if any(not name for name in reader.fieldnames):
        raise CSVImportError("The CSV needs a header row with named columns.")
    if len(reader.fieldnames) > 80:
        raise CSVImportError("The CSV can contain at most 80 columns.")
    normalized_names = [normalize_header(name) for name in reader.fieldnames if name]
    if len(set(normalized_names)) != len(normalized_names):
        raise CSVImportError("The CSV has duplicate column names. Rename the columns and try again.")
    headers = {normalize_header(name): name for name in reader.fieldnames if name}
    column_map = column_map or {}
    valid_columns = set(reader.fieldnames)
    allowed_map_keys = {"date", "amount", "debit", "credit", "category", "type", "merchant", "location", "channel"}
    if set(column_map) - allowed_map_keys:
        raise CSVImportError("The column mapping contains an unsupported field.")
    if any(value and value not in valid_columns for value in column_map.values()):
        raise CSVImportError("The selected column mapping does not match this CSV header.")
    def choose(key, *aliases):
        return column_map.get(key) or _column(headers, *aliases)
    date_col = choose("date", "timestamp", "date", "datetime", "transaction_date", "transaction_datetime", "time")
    amount_col = choose("amount", "amount", "transaction_amount", "value")
    debit_col = choose("debit", "debit", "withdrawal", "outflow")
    credit_col = choose("credit", "credit", "deposit", "inflow")
    if date_col is None or (amount_col is None and debit_col is None and credit_col is None):
        raise CSVImportError("Required columns: date/timestamp and amount. Debit and credit columns are also supported.")
    category_col = choose("category", "category", "transaction_category", "spending_category")
    type_col = choose("type", "transaction_type", "txn_type", "direction", "entry_type", "type")
    merchant_col = choose("merchant", "merchant", "description", "details", "narration", "recipient", "note", "name")
    location_col = choose("location", "location", "city")
    channel_col = choose("channel", "channel", "payment_channel", "source")
    income_words = {"income", "inflow", "credit", "deposit", "salary", "received", "cash in"}
    cash_words = {"cash out", "cashout", "withdrawal", "withdraw", "atm"}
    transfer_words = {"transfer", "send money", "sent", "p2p"}
    rows = []
    for row_number, raw in enumerate(reader, start=2):
        if raw.get("__extra__") and any(str(value).strip() for value in raw["__extra__"]):
            raise CSVImportError(f"Row {row_number}: there are values beyond the header columns.")
        if not any(str(value or "").strip() for key, value in raw.items() if key != "__extra__"):
            continue
        if len(rows) >= MAX_CSV_ROWS:
            raise CSVImportError("A single CSV import can contain up to 50,000 rows.")
        timestamp = _parse_timestamp(raw.get(date_col), row_number)
        raw_type = str(raw.get(type_col) or "").strip().lower().replace("_", " ") if type_col else ""
        from_credit = False
        debit_value = str(raw.get(debit_col) or "").strip() if debit_col else ""
        credit_value = str(raw.get(credit_col) or "").strip() if credit_col else ""
        if debit_value and credit_value and not (amount_col and str(raw.get(amount_col) or "").strip()):
            raise CSVImportError(f"Row {row_number}: a row cannot have both debit and credit amounts.")
        if amount_col and str(raw.get(amount_col) or "").strip():
            raw_amount = str(raw.get(amount_col)).strip()
        elif debit_col and str(raw.get(debit_col) or "").strip():
            raw_amount = str(raw.get(debit_col)).strip()
        elif credit_col and str(raw.get(credit_col) or "").strip():
            raw_amount = str(raw.get(credit_col)).strip()
            from_credit = True
        else:
            raise CSVImportError(f"Row {row_number}: amount is missing.")
        amount = _parse_amount(raw_amount, row_number)
        if raw_type in income_words or (not raw_type and from_credit):
            transaction_type = "income"
        elif raw_type in cash_words:
            transaction_type = "cash_out"
        elif raw_type in transfer_words:
            transaction_type = "transfer"
        else:
            transaction_type = "payment"
        merchant = str(raw.get(merchant_col) or "").strip()[:120] if merchant_col else ""
        raw_category = raw.get(category_col) if category_col else ""
        category = _category(raw_category, merchant)
        rows.append({
            "timestamp": timestamp,
            "amount": amount,
            "transaction_type": transaction_type,
            "category": category,
            "merchant": merchant or "Imported transaction",
            "device_type": "Imported CSV",
            "location": str(raw.get(location_col) or fallback_region or "Not provided")[:80] if location_col else (fallback_region or "Not provided")[:80],
            "channel": str(raw.get(channel_col) or "CSV import")[:40] if channel_col else "CSV import",
        })
    if not rows:
        raise CSVImportError("No transaction rows were found in this CSV.")
    return rows, list(reader.fieldnames)


def monthly_features(user_id, rows, monthly_income):
    months = sorted({row["timestamp"][:7] for row in rows})
    expenses = defaultdict(float)
    incomes = defaultdict(float)
    categories = defaultdict(lambda: defaultdict(float))
    counts = defaultdict(int)
    for row in rows:
        month = row["timestamp"][:7]
        if row["transaction_type"] == "income":
            incomes[month] += row["amount"]
            continue
        expenses[month] += row["amount"]
        categories[month][row["category"]] += row["amount"]
        counts[month] += 1
    feature_rows = []
    prior_expenses = []
    for month in months:
        total = expenses[month]
        prior_expenses.append(total)
        cats = categories[month]
        month_number = int(month[5:7])
        food = cats["Food"]
        shopping = cats["Shopping"]
        transport = cats["Transport"]
        entertainment = cats["Entertainment"]
        bills = cats["Bills"] + cats["Mobile Recharge"]
        cashout = cats["Cash Out"]
        other = sum(value for name, value in cats.items() if name not in {"Food", "Shopping", "Transport", "Entertainment", "Bills", "Mobile Recharge", "Cash Out"})
        feature_rows.append((
            user_id, month, round(incomes[month] or monthly_income, 2), round(total, 2),
            round(food, 2), round(shopping, 2), round(transport, 2), round(entertainment, 2),
            round(bills, 2), round(cashout, 2), round(other, 2), counts[month],
            round(total / counts[month], 2) if counts[month] else 0,
            round(prior_expenses[-2], 2) if len(prior_expenses) > 1 else round(total, 2),
            round(sum(prior_expenses[-3:]) / len(prior_expenses[-3:]), 2), month_number,
            round(math.sin(2 * math.pi * month_number / 12), 6),
            round(math.cos(2 * math.pi * month_number / 12), 6),
        ))
    return feature_rows


def preview_stats(rows, columns):
    months = sorted({row["timestamp"][:7] for row in rows})
    expense_rows = [row for row in rows if row["transaction_type"] != "income"]
    income_rows = [row for row in rows if row["transaction_type"] == "income"]
    return {
        "row_count": len(rows),
        "expense_rows": len(expense_rows),
        "income_rows": len(income_rows),
        "expense_total": round(sum(row["amount"] for row in expense_rows), 2),
        "month_count": len(months),
        "months": months,
        "columns": columns,
        "sample": rows[:5],
    }
