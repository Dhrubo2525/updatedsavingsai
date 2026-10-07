"""Expanding-window comparison against simple chronological baselines."""
import numpy as np
from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

def metric_set(actual, predicted):
    actual = np.asarray(actual, dtype=float); predicted = np.asarray(predicted, dtype=float)
    return {"mae": float(mean_absolute_error(actual, predicted)),
            "rmse": float(mean_squared_error(actual, predicted) ** .5),
            "r2": float(r2_score(actual, predicted)),
            "mape": float(np.mean(np.abs((actual - predicted) / np.maximum(np.abs(actual), 1))) * 100)}

def evaluate_candidates(frame, feature_columns):
    models = {
      "Gradient Boosting": GradientBoostingRegressor(n_estimators=100, max_depth=2, learning_rate=.045, loss="huber", random_state=21),
      "Extra Trees": ExtraTreesRegressor(n_estimators=180, min_samples_leaf=4, max_features=.9, n_jobs=-1, random_state=21),
      "Random Forest": RandomForestRegressor(n_estimators=180, min_samples_leaf=4, max_features=.9, n_jobs=-1, random_state=21),
    }
    targets = sorted(frame.target_index.unique())
    validation_targets = targets[-5:]
    scores = {name: [] for name in models}
    baseline_scores = {"Last month": [], "Rolling 3-month mean": []}
    oof = {name: {"actual": [], "predicted": [], "groups": []} for name in models}
    for target in validation_targets:
        train = frame[frame.target_index < target]
        valid = frame[frame.target_index == target]
        if len(train) < 250 or valid.empty: continue
        y = valid.next_expense.to_numpy()
        for name, estimator in models.items():
            estimator.fit(train[feature_columns], train.next_expense)
            pred = np.maximum(0, estimator.predict(valid[feature_columns]))
            scores[name].append(metric_set(y, pred)); oof[name]["actual"].extend(y.tolist()); oof[name]["predicted"].extend(pred.tolist())
            if "occupation" in valid: oof[name]["groups"].extend(valid.occupation.astype(str).tolist())
        for name, col in [("Last month", "total_expense"), ("Rolling 3-month mean", "rolling_3m_expense")]:
            pred = valid[col].to_numpy(); baseline_scores[name].append(metric_set(y, pred))
    aggregate = lambda items: {k: float(np.mean([x[k] for x in items])) for k in ("mae", "rmse", "r2", "mape")}
    model_metrics = {n: aggregate(v) for n, v in scores.items() if v}
    baseline_metrics = {n: aggregate(v) for n, v in baseline_scores.items() if v}
    selected = min(model_metrics, key=lambda n: model_metrics[n]["mae"])
    selected_mae = model_metrics[selected]["mae"]
    best_baseline = min(baseline_metrics, key=lambda n: baseline_metrics[n]["mae"])
    baseline_mae = baseline_metrics[best_baseline]["mae"]
    relative_changes={name:round((value["mae"]-selected_mae)/value["mae"]*100,2) for name,value in baseline_metrics.items()}
    beaten=[name for name,change in relative_changes.items() if change>0]
    baseline_beaten=max(beaten,key=lambda name:relative_changes[name]) if beaten else None
    folds = len(scores[selected])
    selected_oof=oof[selected]
    absolute_errors=np.abs(np.asarray(selected_oof["actual"],dtype=float)-np.asarray(selected_oof["predicted"],dtype=float))
    validation_absolute_error_p90=float(np.quantile(absolute_errors,.90)) if len(absolute_errors) else None
    fairness={}
    if selected_oof["groups"]:
        actual=np.asarray(selected_oof["actual"]); predicted=np.asarray(selected_oof["predicted"]); groups=np.asarray(selected_oof["groups"])
        for group in sorted(set(groups)):
            mask=groups==group
            if int(mask.sum())>=10: fairness[group]={"mae":float(np.mean(np.abs(actual[mask]-predicted[mask]))),"validation_rows":int(mask.sum())}
    evidence = {"method": "Expanding-window, one-month-ahead walk-forward validation; observations ordered by target month.",
      "folds": folds, "training_rows": int(sum(len(frame[frame.target_index < t]) for t in validation_targets)),
      "validation_rows": int(sum(len(frame[frame.target_index == t]) for t in validation_targets)),
      "models": model_metrics, "baselines": baseline_metrics, "selected_model": selected,
      "best_baseline": best_baseline, "baseline_beaten":baseline_beaten,
      "relative_mae_changes_pct_vs_baselines":relative_changes,
      "relative_mae_improvement_vs_baseline_pct":relative_changes.get(baseline_beaten,0) if baseline_beaten else 0,
      "relative_mae_improvement_vs_best_baseline_pct": round((baseline_mae-selected_mae)/baseline_mae*100, 2),
      "beats_at_least_one_baseline": any(selected_mae < m["mae"] for m in baseline_metrics.values()),
      "validation_absolute_error_p90":validation_absolute_error_p90,
      "validation_error_band_method":"90th percentile of absolute errors across selected-model walk-forward predictions; descriptive empirical band, not a calibrated probability interval.",
      "fairness_by_occupation":fairness,
      "target": "next-month total expenses (BDT)", "synthetic_evaluation": True}
    return evidence, models, oof
