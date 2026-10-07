"""Synthetic transaction aggregation and explainable unusual-pattern detection."""
from collections import defaultdict
import statistics
from sklearn.ensemble import IsolationForest

CATEGORY_BN={"Food":"খাবার","Transport":"যাতায়াত","Shopping":"শপিং","Bills":"বিল",
 "Mobile Recharge":"মোবাইল রিচার্জ","Education":"পড়াশোনা","Entertainment":"বিনোদন",
 "Healthcare":"স্বাস্থ্যসেবা","Cash Out":"ক্যাশ আউট","Transfer":"টাকা পাঠানো","Other":"অন্যান্য"}

def summarize(transactions, monthly_rows):
    by_month = defaultdict(lambda: defaultdict(float)); by_category = defaultdict(float); month_counts = defaultdict(int)
    spending_transactions = [row for row in transactions if row.get("transaction_type") != "income"]
    for row in spending_transactions:
        month = row["timestamp"][:7]; cat = row["category"]
        by_month[month][cat] += float(row["amount"]); by_category[cat] += float(row["amount"]); month_counts[month] += 1
    months = sorted(by_month)
    monthly = [{"month":m,"total":round(sum(by_month[m].values()),2),"transactions":month_counts[m],
       "categories":{k:round(v,2) for k,v in by_month[m].items()}} for m in months]
    latest = months[-1] if months else None
    anomalies = []
    if len(months) > 4:
        categories=sorted(by_category)
        histories={cat:[by_month[m].get(cat,0.0) for m in months[:-1]] for cat in categories}
        medians={cat:statistics.median(histories[cat]) for cat in categories}
        # Normalize each category to its own typical level, then fit one multivariate Isolation Forest.
        matrix=[]
        for i in range(len(months)-1):
            matrix.append([(histories[cat][i]-medians[cat])/max(medians[cat],1) for cat in categories])
        current_vector=[(by_month[latest].get(cat,0.0)-medians[cat])/max(medians[cat],1) for cat in categories]
        forest=IsolationForest(n_estimators=64,contamination="auto",random_state=42).fit(matrix)
        month_is_unusual=forest.predict([current_vector])[0] == -1
        for cat in categories:
            history=histories[cat]; current=by_month[latest].get(cat,0.0); median=medians[cat]
            if median <= 0: continue
            deviations=[abs(x-median) for x in history]
            mad=statistics.median(deviations) if deviations else 0
            threshold=max(median*1.55,median+2.5*mad)
            if current>threshold and month_is_unusual:
                pct=round((current/max(median,1)-1)*100)
                anomalies.append({"category":cat,"month":latest,"current_amount":round(current,2),
                  "normal_median":round(median,2),"change_pct":pct,"method":"Isolation Forest + robust median threshold",
                  "explanation_en":f"{cat} spending was ৳{current:,.0f} in {latest}, about {pct}% above your previous-month median of ৳{median:,.0f}.",
                  "explanation_bn":f"{latest} মাসে {CATEGORY_BN.get(cat,cat)} খরচ ৳{current:,.0f}, যা আগের মাসগুলোর মধ্যমা ৳{median:,.0f} থেকে প্রায় {pct}% বেশি।"})
    category_rows = [{"category":k,"amount":round(v,2),"share_pct":round(v/max(sum(by_category.values()),1)*100,1)} for k,v in sorted(by_category.items(), key=lambda kv:kv[1], reverse=True)]
    changes = []
    if len(months)>1:
        current, previous = by_month[months[-1]], by_month[months[-2]]
        for cat in sorted(set(current)|set(previous)):
            old, new = previous.get(cat,0), current.get(cat,0)
            changes.append({"category":cat,"previous_amount":round(old,2),"current_amount":round(new,2),
              "change_pct":round((new-old)/old*100,1) if old else (100 if new else 0)})
    return {"monthly":monthly[-12:],"categories":category_rows,"month_over_month":changes,
      "anomalies":anomalies,"latest_month":latest,"transaction_count":len(spending_transactions),
      "monthly_total":monthly[-1]["total"] if monthly else 0}
