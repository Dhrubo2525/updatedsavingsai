"""Load the trained model and return a transparent next-month expense estimate."""
import json
import joblib
import pandas as pd
from ..config import MODEL_PATH, METRICS_PATH, FEATURES_PATH

_bundle = None
def load_model():
    global _bundle
    if _bundle is None and MODEL_PATH.exists(): _bundle = joblib.load(MODEL_PATH)
    return _bundle

def forecast_for_user(monthly_rows, *, is_imported=False):
    rows = [dict(r) for r in monthly_rows]
    origin = "user_import" if is_imported else "synthetic_demo"
    if not rows:
        return {"available":False,"prediction":0,"model":"unavailable","history_months":0,
          "data_origin":origin,"estimate_range":None}
    latest = rows[-1]
    recent = [float(row["total_expense"]) for row in rows[-3:]]
    if is_imported:
        # The bundled estimator is trained only on synthetic data. Keep imported-user
        # estimates personal and auditable until a governed real-data model exists.
        value = sum(recent) / len(recent)
        selected = "Personal rolling 3-month mean"
        estimate_range = ({"kind":"historical","lower":round(min(recent),2),"upper":round(max(recent),2),
          "method":"Range of the latest observed monthly expenses; descriptive history, not a prediction interval."}
          if len(recent) >= 2 else None)
    else:
        bundle = load_model()
        if bundle:
            x = pd.DataFrame([{k: latest[k] for k in bundle["feature_columns"]}])
            value = float(max(0, bundle["model"].predict(x)[0])); selected = bundle["selected_model"]
            error_band = bundle.get("validation_absolute_error_p90")
            estimate_range = ({"kind":"model_validation","lower":round(max(0,value-float(error_band)),2),"upper":round(value+float(error_band),2),
              "method":"Empirical ± 90th-percentile absolute error from synthetic walk-forward validation; not a calibrated probability interval."}
              if error_band is not None else None)
        else:
            value = sum(recent) / len(recent); selected = "Rolling 3-month baseline (model artifact missing)"
            estimate_range = ({"kind":"historical","lower":round(min(recent),2),"upper":round(max(recent),2),
              "method":"Range of recent synthetic monthly expenses; descriptive history, not a prediction interval."}
              if len(recent) >= 2 else None)
    return {"available":True,"prediction":round(value,2),"model":selected,"history_months":len(rows),
      "last_month_expense":round(float(latest["total_expense"]),2),"rolling_3m_expense":round(sum(recent)/len(recent),2),
      "data_origin":origin,"estimate_range":estimate_range,
      "assumption":("This personal baseline uses the latest imported months; the synthetic-trained model is not applied to imported profiles." if is_imported else "The selected model is evaluated on synthetic historical behavior; its estimate and empirical error band are not guarantees."),
      "assumption_bn":("এই ব্যক্তিগত ভিত্তি সর্বশেষ আমদানি করা মাসগুলোর ওপর নির্ভর করে; কৃত্রিম তথ্য দিয়ে প্রশিক্ষিত মডেল আমদানি করা প্রোফাইলে ব্যবহার করা হয় না।" if is_imported else "নির্বাচিত মডেলটি কৃত্রিম আগের তথ্য দিয়ে যাচাই করা হয়েছে; অনুমান ও অভিজ্ঞতালব্ধ ত্রুটির পরিসর নিশ্চিত ফল নয়।")}

def read_json(path, default):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): return default
