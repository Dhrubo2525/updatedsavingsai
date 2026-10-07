"""Compare two synthetic savings-plan scenarios; not real-world evidence."""
import csv, json, statistics
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/"data"
def main():
    users={r["user_id"]:r for r in csv.DictReader((DATA/"users.csv").open(encoding="utf-8-sig",newline=""))}
    by_user={}
    for r in csv.DictReader((DATA/"monthly_features.csv").open(encoding="utf-8-sig",newline="")):
        by_user.setdefault(r["user_id"],[]).append(r)
    achieved={"control":0,"treatment":0}; projected={"control":0.0,"treatment":0.0}; reductions=[]; feasible={"control":0,"treatment":0}
    capacity={"control":0.0,"treatment":0.0}; by_occupation=defaultdict(lambda:{"profiles":0,"control_goals":0,"treatment_goals":0})
    count=0
    for uid,rows in by_user.items():
        rows=sorted(rows,key=lambda x:x["month"]); recent=rows[-3:]
        occupation=users[uid].get("occupation","Not provided")
        income_values=[float(x["income"]) for x in recent]
        income=statistics.median(income_values)
        income_mean=statistics.mean(income_values)
        income_cv=statistics.stdev(income_values)/max(income_mean,1) if len(income_values)>1 else 0
        buffer_rate=max(.05,min(.20,income_cv*.95))
        reserve=max(1000,round(income*buffer_rate))
        expense=statistics.mean(float(x["total_expense"]) for x in recent)
        shop=statistics.mean(float(x["shopping_expense"]) for x in recent)
        cap=max(0,income-expense-reserve)
        treat_cap=max(0,income-(expense-shop*.08)-reserve)
        # A common synthetic benchmark target: six-month gap equals roughly 18% of average income.
        gap=income*.18; horizon=6
        for key,value in [("control",cap),("treatment",treat_cap)]:
            if value>0: feasible[key]+=1
            capacity[key]+=value
            projected[key]+=min(gap,value*horizon)
            if value*horizon>=gap: achieved[key]+=1
        group=by_occupation[occupation]; group["profiles"]+=1
        group["control_goals"]+=int(cap*horizon>=gap)
        group["treatment_goals"]+=int(treat_cap*horizon>=gap)
        reductions.append((treat_cap-cap)); count+=1
    occupation_outcomes={name:{"profiles":values["profiles"],
      "control_goal_feasibility_pct":round(values["control_goals"]/max(1,values["profiles"])*100,1),
      "treatment_goal_feasibility_pct":round(values["treatment_goals"]/max(1,values["profiles"])*100,1)}
      for name,values in sorted(by_occupation.items())}
    result={"label":"Synthetic scenario model — not real customer evidence","method":"Per-profile six-month projection over the latest three synthetic months. The scenario applies an illustrative 8% reduction to Shopping expenses; it is not observed behavior, an experiment, or a causal estimate.",
      "primary_metric":"Six-month goal feasibility: share of profiles whose estimated reserve-aware monthly capacity covers a benchmark goal equal to 18% of median monthly income within six months.",
      "guardrail":"The same income-volatility-aware safety buffer is subtracted in both scenarios. Contributions are capped by the remaining estimated capacity.",
      "sample_users":count,"control":{"goal_feasibility_pct":round(achieved["control"]/max(1,count)*100,1),"goals_achieved":achieved["control"],"projected_savings_per_user":round(projected["control"]/max(1,count),2),"users_with_positive_capacity_pct":round(feasible["control"]/max(1,count)*100,1)},
      "treatment":{"goal_feasibility_pct":round(achieved["treatment"]/max(1,count)*100,1),"goals_achieved":achieved["treatment"],"projected_savings_per_user":round(projected["treatment"]/max(1,count),2),"users_with_positive_capacity_pct":round(feasible["treatment"]/max(1,count)*100,1)},
      "goal_feasibility_change_percentage_points":round(achieved["treatment"]/max(1,count)*100-achieved["control"]/max(1,count)*100,1),
      "mean_simulated_monthly_capacity_change":round(statistics.mean(reductions),2),
      "mean_reserve_aware_monthly_capacity":{"control":round(capacity["control"]/max(1,count),2),"treatment":round(capacity["treatment"]/max(1,count),2)},
      "synthetic_occupation_outcomes":occupation_outcomes,
      "caveat":"Outputs describe a fixed generated-data scenario with assumed behavior. Small differences are not evidence of product impact and must not be presented as causal or real-customer results."}
    (DATA/"product_metrics.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))
if __name__=="__main__":main()
