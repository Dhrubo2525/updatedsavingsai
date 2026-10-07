"""Bilingual labels and explicitly typed AI-style explanations."""
def prediction_note(forecast):
    amount=forecast.get("prediction",0)
    estimate_range=forecast.get("estimate_range") or {}
    if forecast.get("data_origin")=="user_import":
        if estimate_range:
            low,high=estimate_range["lower"],estimate_range["upper"]
            en=f"Personal baseline: about ৳{amount:,.0f} next month, using your recent imported months. Recent monthly spending ranged from ৳{low:,.0f} to ৳{high:,.0f}; this describes past variation, not a prediction interval."
            bn=f"ব্যক্তিগত ভিত্তি: আমদানি করা সাম্প্রতিক মাসগুলোর হিসাবে পরের মাসে প্রায় ৳{amount:,.0f}। সাম্প্রতিক মাসিক খরচ ৳{low:,.0f} থেকে ৳{high:,.0f} ছিল; এটি অতীতের ওঠানামা, পূর্বাভাসের নিশ্চিত সীমা নয়।"
        else:
            en=f"Personal baseline: about ৳{amount:,.0f} next month from the available imported history. More months would make the recent pattern easier to judge."
            bn=f"ব্যক্তিগত ভিত্তি: আমদানি করা উপলব্ধ তথ্য থেকে পরের মাসে প্রায় ৳{amount:,.0f}। আরও মাসের তথ্য থাকলে সাম্প্রতিক ধারা বোঝা সহজ হবে।"
    elif estimate_range.get("kind")=="historical":
        low,high=estimate_range["lower"],estimate_range["upper"]
        en=f"Rolling baseline: about ৳{amount:,.0f} next month from recent synthetic months. Recent spending ranged from ৳{low:,.0f} to ৳{high:,.0f}; this describes history, not a prediction interval."
        bn=f"সাম্প্রতিক কৃত্রিম মাসের গড়: পরের মাসে প্রায় ৳{amount:,.0f}। সাম্প্রতিক খরচ ৳{low:,.0f} থেকে ৳{high:,.0f} ছিল; এটি অতীতের তথ্য, পূর্বাভাসের সীমা নয়।"
    elif estimate_range:
        low,high=estimate_range["lower"],estimate_range["upper"]
        en=f"The selected model estimates next-month expenses at about ৳{amount:,.0f}; its empirical range is ৳{low:,.0f}–৳{high:,.0f}. This range comes from synthetic walk-forward errors and is not a calibrated probability interval."
        bn=f"নির্বাচিত মডেলে পরের মাসের খরচ প্রায় ৳{amount:,.0f}; অভিজ্ঞতালব্ধ পরিসর ৳{low:,.0f}–৳{high:,.0f}। এই পরিসর কৃত্রিম তথ্যের সময়ভিত্তিক যাচাইয়ের ভুল থেকে এসেছে; এটি সম্ভাব্যতার নিশ্চয়তাপূর্ণ সীমা নয়।"
    else:
        en=f"The selected model estimates next-month expenses at about ৳{amount:,.0f}. An error range is unavailable for this model artifact."
        bn=f"নির্বাচিত মডেলে পরের মাসের খরচ প্রায় ৳{amount:,.0f} হতে পারে। এই মডেল ফাইলে ত্রুটির পরিসর নেই।"
    return {"type":"Prediction","en":en,"bn":bn}
