"""Train, compare, evaluate and persist the synthetic-data forecast model."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.inspection import permutation_importance
from .features import load_examples
from .evaluate import evaluate_candidates
from ..config import DATA_DIR, MODEL_DIR, MODEL_PATH, METRICS_PATH, FEATURES_PATH

def train():
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    frame, features = load_examples(DATA_DIR / "monthly_features.csv")
    groups=pd.read_csv(DATA_DIR/"users.csv",usecols=["user_id","occupation"])
    frame=frame.merge(groups,on="user_id",how="left")
    metrics, candidates, _ = evaluate_candidates(frame, features)
    selected = metrics["selected_model"]
    model = candidates[selected]
    model.fit(frame[features], frame.next_expense)
    # Permutation importance uses a final chronological holdout (the two latest target months).
    target_dates = sorted(frame.target_index.unique()); holdout_dates = target_dates[-2:]
    train_frame = frame[frame.target_index < holdout_dates[0]]
    holdout = frame[frame.target_index.isin(holdout_dates)]
    imp_model = candidates[selected]
    imp_model.fit(train_frame[features], train_frame.next_expense)
    imp = permutation_importance(imp_model, holdout[features], holdout.next_expense, n_repeats=5,
                                 random_state=19, scoring="neg_mean_absolute_error", n_jobs=-1)
    importance = [{"feature": f, "importance": float(max(0, v)), "plain_language": {
       "previous_month_expense":"Your latest spending level", "rolling_3m_expense":"Your recent three-month spending average",
       "income":"Your monthly income signal", "shopping_expense":"Your shopping spending", "food_expense":"Your food spending",
       "transaction_count":"How often you transact", "bill_expense":"Your bills and mobile spending",
       "month_number":"Seasonal timing"}.get(f, f.replace("_", " ").capitalize())}
       for f, v in zip(features, imp.importances_mean)]
    importance.sort(key=lambda x: x["importance"], reverse=True)
    importance_doc = {"method":"Permutation importance on the last two chronological target months; negative values are floored for display.",
      "features":importance, "synthetic_evaluation":True}
    model.fit(frame[features], frame.next_expense)
    import joblib
    joblib.dump({"model":model,"feature_columns":features,"selected_model":selected,
      "validation_absolute_error_p90":metrics.get("validation_absolute_error_p90"),
      "data_origin":"synthetic_demo"}, MODEL_PATH)
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    FEATURES_PATH.write_text(json.dumps(importance_doc, indent=2), encoding="utf-8")
    (DATA_DIR / "model_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps({"selected_model":selected,"beats_at_least_one_baseline":metrics["beats_at_least_one_baseline"],
      "metrics":metrics["models"][selected],"best_baseline":metrics["baselines"][metrics["best_baseline"]]}, indent=2))
    if not metrics["beats_at_least_one_baseline"]:
        print("WARNING: selected model did not beat either baseline on this synthetic run.")
    return metrics

if __name__ == "__main__": train()
