"""Rule-based recommendations grounded in the computed summary and forecast."""
def build_recommendations(spending, plan):
    out=[]
    anomalies=spending.get("anomalies",[])
    for anomaly in anomalies[:2]:
        if anomaly["category"] in ("Shopping","Food","Entertainment","Transport"):
            cat=anomaly["category"]
            out.append({"kind":"unusual_spending","text_en":f"Review this month's {cat.lower()} spending before committing to a higher contribution.",
              "text_bn":f"বেশি সঞ্চয়ের প্রতিশ্রুতি দেওয়ার আগে এই মাসের {cat} খরচটি দেখে নিন।",
              "reason_en":anomaly["explanation_en"],"reason_bn":anomaly["explanation_bn"]})
    cat=plan.get("category_forecast",{}).get("Shopping",0)
    if cat>0:
        saving=round(cat*.10)
        out.append({"kind":"scenario","text_en":f"Try a 10% shopping reduction (about ৳{saving:,.0f}/month) in the What-If simulator.",
          "text_bn":f"What-If সিমুলেটরে শপিং খরচ ১০% (প্রায় ৳{saving:,.0f}/মাস) কমিয়ে দেখুন।",
          "reason_en":f"Shopping is forecast at about ৳{cat:,.0f}/month; a 10% change would free approximately ৳{saving:,.0f} if the pattern holds.",
          "reason_bn":f"শপিং খরচ মাসে প্রায় ৳{cat:,.0f} হতে পারে; একই ধারা থাকলে ১০% কমালে প্রায় ৳{saving:,.0f} হাতে থাকতে পারে।"})
    if plan["planning_status"] in ("Needs Adjustment","Difficult With Current Pattern"):
        out.append({"kind":"goal_feasibility","text_en":"Consider extending the timeline or lowering the target to keep the protected buffer.",
          "text_bn":"নিরাপত্তা বাফার বজায় রাখতে সময় বাড়ানো বা লক্ষ্য কমানোর কথা ভাবুন।",
          "reason_en":plan["status_reason_en"],"reason_bn":plan["status_reason_bn"]})
    if not out:
        out.append({"kind":"positive","text_en":"Keep this contribution flexible and review it after your next month of spending.",
          "text_bn":"এই সঞ্চয়ের পরিমাণ নমনীয় রাখুন এবং পরের মাসের খরচ দেখে আবার ঠিক করুন।",
          "reason_en":"The estimate is based on synthetic history and real expenses may vary.",
          "reason_bn":"এই অনুমান কৃত্রিম আগের তথ্য থেকে করা; বাস্তব খরচ বদলাতে পারে।"})
    return out
