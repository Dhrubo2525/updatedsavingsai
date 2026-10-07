"""Deterministic savings-capacity, goal-plan and what-if calculations."""
import math
import statistics
from ..config import MIN_SAFETY_BUFFER, SAFETY_BUFFER_RATE

def _num(row, key, fallback=0):
    try: return float(row.get(key, fallback) or fallback)
    except (TypeError, ValueError): return float(fallback)

def category_bases(monthly_rows, total_prediction):
    mapping = {"Food":"food_expense", "Shopping":"shopping_expense", "Transport":"transport_expense",
      "Entertainment":"entertainment_expense", "Bills":"bill_expense", "Cash Out":"cashout_expense", "Other":"other_expense"}
    selected = monthly_rows[-3:]
    raw = {name: sum(_num(row, col) for row in selected) / max(1, len(selected)) for name, col in mapping.items()}
    # The model's Other feature retains entertainment for stability; separate it only for scenario math.
    if any("entertainment_expense" in row for row in selected):
        raw["Other"] = max(0, raw["Other"] - raw["Entertainment"])
    denom = sum(raw.values())
    if denom <= 0: return {k: 0 for k in raw}
    return {k: round(v * total_prediction / denom, 2) for k, v in raw.items()}

def calculate(goal, user, forecast, monthly_rows, reductions=None):
    reductions = reductions or {}
    remaining = max(0.0, _num(goal, "target_amount") - _num(goal, "current_saved_amount"))
    target = max(1, int(goal.get("target_months", 1)))
    raw_required = remaining / target
    required = round(raw_required, 2)
    weekly = round(remaining / max(1, target * 4.345), 2)
    progress = 100.0 if _num(goal, "target_amount") <= 0 else min(100.0, round(_num(goal,"current_saved_amount") / _num(goal,"target_amount") * 100, 1))
    income_values = [_num(x,"income",_num(user,"monthly_income")) for x in monthly_rows[-3:]]
    expected_income = float(statistics.median(income_values)) if income_values else _num(user,"monthly_income")
    income_mean = statistics.mean(income_values) if income_values else expected_income
    income_cv = (statistics.stdev(income_values) / max(income_mean, 1)) if len(income_values) > 1 else 0.0
    pred_expense = float(forecast.get("prediction", 0))
    if not monthly_rows:
        pred_expense = max(pred_expense, _num(user, "monthly_income") * .75)
    categories = category_bases(monthly_rows, pred_expense)
    savings_from_changes = 0.0
    clean_reductions = {}
    for category, pct in reductions.items():
        pct = max(0, min(.30, float(pct)))
        clean_reductions[category] = pct
        savings_from_changes += categories.get(category, 0) * pct
    adjusted_expense = max(0, pred_expense - savings_from_changes)
    # Volatile cash flow needs a larger reserve; the rate rises from 5% up to 20%.
    buffer_rate = max(SAFETY_BUFFER_RATE, min(.20, income_cv * .95))
    buffer = max(MIN_SAFETY_BUFFER, round(expected_income * buffer_rate))
    capacity = max(0, expected_income - adjusted_expense - buffer)
    raw_surplus = max(0, expected_income - adjusted_expense)
    if remaining <= 0:
        status = "On Track"; status_bn = "লক্ষ্য পূরণ হয়েছে"
        reason = "This goal is already funded based on the saved amount entered."
        reason_bn = "আপনার দেওয়া বর্তমান সঞ্চয় অনুযায়ী এই লক্ষ্য ইতিমধ্যে পূরণ হয়েছে।"
    elif capacity <= 0:
        status = "Difficult With Current Pattern"; status_bn = "বর্তমান খরচে কঠিন"
        reason = f"Estimated feasible saving is ৳0/month after a ৳{buffer:,.0f} safety buffer; the required amount is ৳{required:,.0f}/month."
        reason_bn = f"৳{buffer:,.0f} নিরাপত্তা বাফার রাখার পর আনুমানিক সঞ্চয় ক্ষমতা মাসে ৳০; দরকার ৳{required:,.0f}।"
    elif required <= capacity * .85:
        status = "On Track"; status_bn = "লক্ষ্যপথে আছে"
        reason = f"Required saving of ৳{required:,.0f}/month is within the estimated ৳{capacity:,.0f} monthly capacity, with room for variation."
        reason_bn = f"মাসে ৳{required:,.0f} সঞ্চয়ের লক্ষ্যটি আনুমানিক ৳{capacity:,.0f} সক্ষমতার মধ্যে; কিছু ওঠানামার সুযোগও আছে।"
    elif required <= capacity:
        status = "Tight"; status_bn = "কিছুটা চাপের"
        reason = f"The ৳{required:,.0f}/month target fits the ৳{capacity:,.0f} estimate, but leaves limited room for unexpected costs."
        reason_bn = f"মাসে ৳{required:,.0f} সঞ্চয় ৳{capacity:,.0f} অনুমানের মধ্যে পড়ে, তবে হঠাৎ খরচের জন্য জায়গা কম থাকবে।"
    elif required <= capacity * 1.5:
        status = "Needs Adjustment"; status_bn = "পরিকল্পনা বদলানো দরকার"
        reason = f"Required saving is ৳{required:,.0f}/month while estimated capacity is ৳{capacity:,.0f}/month."
        reason_bn = f"প্রয়োজন মাসে ৳{required:,.0f}, কিন্তু আনুমানিক সক্ষমতা মাসে ৳{capacity:,.0f}।"
    else:
        status = "Difficult With Current Pattern"; status_bn = "বর্তমান খরচে কঠিন"
        reason = f"Required saving is ৳{required:,.0f}/month, over 1.5× the estimated ৳{capacity:,.0f}/month capacity. Consider a longer timeline or a smaller target."
        reason_bn = f"প্রয়োজন মাসে ৳{required:,.0f}, যা আনুমানিক ৳{capacity:,.0f} সক্ষমতার দেড় গুণেরও বেশি। সময় বাড়ানো বা লক্ষ্য কমানোর কথা ভাবুন।"
    explain = f"Predicted next-month expenses are ৳{pred_expense:,.0f}, expected income is ৳{expected_income:,.0f}, and the protected safety buffer is ৳{buffer:,.0f} ({buffer_rate:.0%} of income). Estimated feasible saving is ৳{capacity:,.0f}/month."
    explain_bn = f"পরের মাসের সম্ভাব্য খরচ ৳{pred_expense:,.0f}, সম্ভাব্য আয় ৳{expected_income:,.0f} এবং নিরাপত্তা বাফার ৳{buffer:,.0f} (আয়ের {buffer_rate:.0%})। আনুমানিক সঞ্চয় ক্ষমতা মাসে ৳{capacity:,.0f}।"
    plan = []; cumulative = _num(goal,"current_saved_amount"); completion = None; remaining_sim = remaining
    multipliers = [.93, 1.04, .98, 1.08, .95, 1.02]
    for month_no in range(1, target + 1):
        planned = min(remaining_sim, max(0, math.floor(capacity * multipliers[(month_no-1) % len(multipliers)])))
        cumulative += planned; remaining_sim = max(0, remaining_sim - planned)
        plan.append({"month":month_no,"planned_amount":round(planned,2),"cumulative_amount":round(cumulative,2),
          "remaining_amount":round(remaining_sim,2),"monthly_buffer":round(max(buffer, raw_surplus-planned),2),
          "income_assumption":round(expected_income,2),"expense_prediction":round(adjusted_expense,2)})
        if remaining_sim <= 0: completion = month_no; break
    # Estimate the earliest reachable month using the same variable cash-flow pattern, up to three years.
    sim = remaining; months_to_goal = None
    if sim <= 0: months_to_goal = 0
    elif capacity > 0:
        for month_no in range(1, 37):
            sim -= max(0, math.floor(capacity * multipliers[(month_no-1)%len(multipliers)]))
            if sim <= 0: months_to_goal = month_no; break
    projected = round(sum(x["planned_amount"] for x in plan),2)
    explanation_type = "model prediction + deterministic calculation"
    return {"goal_id":goal.get("goal_id"),"goal_name":goal.get("goal_name",goal.get("name","Savings goal")),
      "target_amount":round(_num(goal,"target_amount"),2),"current_saved_amount":round(_num(goal,"current_saved_amount"),2),
      "remaining_amount":round(remaining,2),"target_months":target,"required_monthly_savings":required,
      "required_weekly_savings":weekly,"progress_pct":progress,"predicted_monthly_expenses":round(pred_expense,2),
      "adjusted_monthly_expenses":round(adjusted_expense,2),"expected_monthly_income":round(expected_income,2),
      "safety_buffer":buffer,"safety_buffer_rate_pct":round(buffer_rate*100,1),"income_volatility_cv":round(income_cv,4),
      "feasible_monthly_savings":round(capacity,2),"planning_status":status,"planning_status_bn":status_bn,
      "status_reason_en":reason,"status_reason_bn":reason_bn,"explanation_en":explain,"explanation_bn":explain_bn,
      "explanation_type":explanation_type,"assumption":"Income is estimated from the median of the latest three synthetic months. The buffer is at least 5% or ৳1,000 and rises with recent income volatility up to 20%." + (" With no transaction history, expenses default to 75% of profile income." if not monthly_rows else ""),
      "assumption_bn":"আয় সর্বশেষ তিন মাসের কৃত্রিম তথ্যের মধ্যমা থেকে অনুমান করা হয়েছে। বাফার অন্তত ৫% বা ৳১,০০০; আয়ের ওঠানামায় এটি সর্বোচ্চ ২০% পর্যন্ত বাড়ে।" + (" লেনদেনের ইতিহাস না থাকায় খরচ প্রোফাইল আয়ের ৭৫% ধরা হয়েছে।" if not monthly_rows else ""),
      "monthly_plan":plan,"projected_savings":projected,"remaining_gap_after_target":round(max(0, remaining-projected),2),
      "expected_completion_months":months_to_goal,"reduced_categories":clean_reductions,"category_forecast":categories,
      "recommendation":"recommendation","estimated":True}
