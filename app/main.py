"""upaySave AI REST API and single-page demo frontend."""
from contextlib import asynccontextmanager
import csv
import hashlib
import io
import json
import re
import sqlite3
import uuid
from datetime import datetime
from fastapi import FastAPI, HTTPException, Query
from starlette.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from .config import DATA_DIR, DB_PATH, FEATURES_PATH, METRICS_PATH, STATIC_DIR
from .db import connect, initialize
from .ml.inference import forecast_for_user, load_model, read_json
from .schemas import CSVImport, CSVPreview, GoalContributionCreate, GoalCreate, WhatIfRequest
from .services.planning import calculate
from .services.spending import summarize
from .services.recommendations import build_recommendations
from .services.explanations import prediction_note
from .services.imports import CSVImportError, csv_columns, monthly_features, parse_csv, preview_stats

@asynccontextmanager
async def lifespan(_app):
    initialize(seed=True)
    yield

app = FastAPI(title="upaySave AI", version="1.0.0", description="Synthetic-data savings planning prototype.", lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "testserver"])
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return response

def _csv_fingerprint(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def _safe_filename(value):
    name = str(value or "transactions.csv").replace("\\", "/").rsplit("/", 1)[-1]
    name = re.sub(r"[^A-Za-z0-9_. -]", "", name).strip(" .")
    return name[:120] or "transactions.csv"

def _safe_csv_cell(value):
    text = str(value or "")
    return "'" + text if text.startswith(("=", "+", "-", "@", "\t", "\r")) else text

def _write_csv_rows(rows):
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(("timestamp", "amount", "transaction_type", "category", "merchant", "location", "channel"))
    yield output.getvalue()
    output.seek(0); output.truncate(0)
    for row in rows:
        writer.writerow((row["timestamp"], row["amount"], row["transaction_type"], row["category"],
                         _safe_csv_cell(row["merchant"]), _safe_csv_cell(row["location"]), _safe_csv_cell(row["channel"])))
        yield output.getvalue()
        output.seek(0); output.truncate(0)

def ok(data): return {"data":data,"error":None}
def user_or_404(conn, user_id):
    row=conn.execute("SELECT * FROM users WHERE user_id=?",(user_id,)).fetchone()
    if not row: raise HTTPException(404,detail={"code":"user_not_found","message":"Profile not found."})
    return dict(row)
def latest_monthly(conn, user_id):
    return [dict(r) for r in conn.execute("SELECT * FROM monthly_features WHERE user_id=? ORDER BY month",(user_id,)).fetchall()]
def tx_rows(conn, user_id):
    return [dict(r) for r in conn.execute("SELECT * FROM transactions WHERE user_id=? ORDER BY timestamp",(user_id,)).fetchall()]
def get_goal(conn, goal_id):
    row=conn.execute("SELECT * FROM goals WHERE goal_id=?",(goal_id,)).fetchone()
    if not row: raise HTTPException(404,detail={"code":"goal_not_found","message":"Goal not found."})
    return dict(row)
def make_plan(conn, goal, user, reductions=None, spending=None):
    history=latest_monthly(conn,user["user_id"])
    forecast=forecast_for_user(history,is_imported=bool(user.get("is_imported")))
    result=calculate(goal,user,forecast,history,reductions)
    if user.get("is_imported"):
        result["assumption"]="Income is estimated from the median of the latest three imported months. The buffer is at least 5% or ৳1,000 and rises with recent income volatility up to 20%."
        result["assumption_bn"]="আয় সর্বশেষ তিন মাসের আমদানি করা তথ্যের মধ্যমা থেকে অনুমান করা হয়েছে। বাফার অন্তত ৫% বা ৳১,০০০; আয়ের ওঠানামায় এটি সর্বোচ্চ ২০% পর্যন্ত বাড়ে।"
    if spending is None and reductions is None:
        spending=summarize(tx_rows(conn,user["user_id"]),history)
    recommendations=build_recommendations(spending,result) if spending is not None else []
    result["recommendations"]=recommendations
    result["prediction_note"]=prediction_note(forecast)
    result["forecast"]={k:forecast.get(k) for k in ("prediction","model","last_month_expense","rolling_3m_expense","available","history_months","data_origin","estimate_range")}
    return result, recommendations

@app.get("/")
def home(): return FileResponse(STATIC_DIR / "index.html")

@app.get("/api/health")
def health():
    initialize(seed=True)
    with connect() as conn:
        counts={t:conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("users","transactions","goals","monthly_features")}
        imported_profiles=conn.execute("SELECT COUNT(*) FROM users WHERE is_imported=1").fetchone()[0]
    return ok({"status":"ok","database":"sqlite","database_path":str(DB_PATH.name),"model_loaded":load_model() is not None,
      "counts":counts,"synthetic_data_only":imported_profiles==0,"demo_data_synthetic":True,"imported_profiles":imported_profiles})

@app.get("/api/users")
def users():
    with connect() as conn:
        rows=conn.execute("SELECT user_id,occupation,age_group,monthly_income,current_savings,language,region,city,display_name,is_imported FROM users ORDER BY user_id").fetchall()
    return ok([dict(r) for r in rows])

@app.post("/api/import/columns")
def import_columns(payload:CSVPreview):
    try:
        columns,suggested=csv_columns(payload.csv_text)
    except CSVImportError as exc:
        raise HTTPException(422,detail={"code":"invalid_csv","message":str(exc)}) from exc
    return ok({"columns":columns,"suggested_mapping":suggested})

@app.post("/api/import/preview")
def preview_import(payload:CSVPreview):
    try:
        rows,columns=parse_csv(payload.csv_text,payload.region,payload.column_map)
    except CSVImportError as exc:
        raise HTTPException(422,detail={"code":"invalid_csv","message":str(exc)}) from exc
    fingerprint=_csv_fingerprint(payload.csv_text)
    with connect() as conn:
        duplicate=conn.execute("SELECT 1 FROM import_batches WHERE fingerprint=?",(fingerprint,)).fetchone() is not None
    result=preview_stats(rows,columns)
    result["duplicate_file"]=duplicate
    result["fingerprint"]=fingerprint
    return ok(result)

@app.post("/api/import",status_code=201)
def import_csv(payload:CSVImport):
    try:
        rows,_=parse_csv(payload.csv_text,payload.region,payload.column_map)
    except CSVImportError as exc:
        raise HTTPException(422,detail={"code":"invalid_csv","message":str(exc)}) from exc
    fingerprint=_csv_fingerprint(payload.csv_text)
    user_id="IMP-"+uuid.uuid4().hex[:16].upper()
    import_id="IB-"+uuid.uuid4().hex
    months=sorted({row["timestamp"][:7] for row in rows})
    expense_rows=[row for row in rows if row["transaction_type"]!="income"]
    features=monthly_features(user_id,rows,payload.monthly_income)
    dates=[datetime.fromisoformat(row["timestamp"][:10]) for row in rows]
    age_days=max(0,(max(dates)-min(dates)).days)
    region=payload.region or "Not provided"
    try:
        with connect() as conn:
            if conn.execute("SELECT 1 FROM import_batches WHERE fingerprint=?",(fingerprint,)).fetchone():
                raise HTTPException(409,detail={"code":"duplicate_import","message":"This CSV was already imported. Choose the existing profile or remove it before importing again."})
            conn.execute("INSERT INTO users (user_id,occupation,age_group,monthly_income,current_savings,language,region,city,account_age_days,average_monthly_transactions,display_name,is_imported) VALUES (?,?,?,?,?,?,?,?,?,?,?,1)",
              (user_id,payload.occupation or "Not provided","Not provided",payload.monthly_income,payload.current_savings,payload.language,region,region,age_days,len(expense_rows)/max(1,len(months)),payload.display_name))
            conn.executemany("INSERT INTO transactions VALUES (?,?,?,?,?,?,?,?,?,?)",[
              ("CSV-"+uuid.uuid4().hex,user_id,row["timestamp"],row["amount"],row["transaction_type"],row["category"],row["merchant"],row["device_type"],row["location"],row["channel"])
              for row in rows])
            conn.executemany("INSERT INTO monthly_features VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",features)
            conn.execute("INSERT INTO import_batches (import_id,user_id,filename,fingerprint,row_count) VALUES (?,?,?,?,?)",
              (import_id,user_id,_safe_filename(payload.filename),fingerprint,len(rows)))
    except sqlite3.IntegrityError as exc:
        raise HTTPException(409,detail={"code":"duplicate_import","message":"This CSV could not be saved because it duplicates an existing import or violates a data constraint."}) from exc
    return ok({"user_id":user_id,"display_name":payload.display_name,"rows_imported":len(rows),"months_imported":len(months)})

@app.get("/api/users/{user_id}/transactions/export")
def export_imported_transactions(user_id:str):
    with connect() as conn:
        user=user_or_404(conn,user_id)
        if not user.get("is_imported"):
            raise HTTPException(404,detail={"code":"import_not_found","message":"Only imported profiles can be exported here."})
        rows=[dict(row) for row in conn.execute("SELECT timestamp,amount,transaction_type,category,merchant,location,channel FROM transactions WHERE user_id=? ORDER BY timestamp",(user_id,)).fetchall()]
    return StreamingResponse(_write_csv_rows(rows),media_type="text/csv; charset=utf-8",
      headers={"Content-Disposition":"attachment; filename=transactions.csv"})

@app.delete("/api/import/{user_id}")
def delete_imported_profile(user_id:str):
    with connect() as conn:
        user=user_or_404(conn,user_id)
        if not user.get("is_imported"):
            raise HTTPException(404,detail={"code":"import_not_found","message":"Only imported profiles can be deleted here."})
        goal_ids=[row[0] for row in conn.execute("SELECT goal_id FROM goals WHERE user_id=?",(user_id,)).fetchall()]
        if goal_ids:
            marks=",".join("?" for _ in goal_ids)
            conn.execute(f"DELETE FROM goal_contributions WHERE goal_id IN ({marks})",goal_ids)
            conn.execute(f"DELETE FROM goal_plans WHERE goal_id IN ({marks})",goal_ids)
            conn.execute(f"DELETE FROM goals WHERE goal_id IN ({marks})",goal_ids)
        conn.execute("DELETE FROM recommendations WHERE user_id=?",(user_id,))
        conn.execute("DELETE FROM monthly_features WHERE user_id=?",(user_id,))
        conn.execute("DELETE FROM transactions WHERE user_id=?",(user_id,))
        conn.execute("DELETE FROM import_batches WHERE user_id=?",(user_id,))
        conn.execute("DELETE FROM users WHERE user_id=?",(user_id,))
    return ok({"user_id":user_id,"deleted":True})

@app.get("/api/users/{user_id}")
def get_user(user_id:str):
    with connect() as conn: return ok(user_or_404(conn,user_id))

@app.get("/api/users/{user_id}/summary")
def user_summary(user_id:str):
    with connect() as conn:
        user=user_or_404(conn,user_id); history=latest_monthly(conn,user_id); spending=summarize(tx_rows(conn,user_id),history)
        forecast=forecast_for_user(history,is_imported=bool(user.get("is_imported")))
        goals=[dict(r) for r in conn.execute("SELECT * FROM goals WHERE user_id=? ORDER BY goal_id DESC",(user_id,)).fetchall()]
        selected=goals[0] if goals else {"goal_name":"Emergency Fund","target_amount":30000,"current_saved_amount":user["current_savings"],"target_months":6,"goal_id":None}
        plan,_=make_plan(conn,selected,user,spending=spending)
    return ok({"user":user,"monthly_income_estimate":plan["expected_monthly_income"],"current_savings":user["current_savings"],
      "monthly_spending":spending["monthly_total"],"spending":spending,"forecast":forecast,"planning":plan,
      "goals":goals,"latest_month":spending["latest_month"],"transaction_count":spending["transaction_count"]})

@app.get("/api/users/{user_id}/transactions")
def user_transactions(user_id:str, date_from:str|None=None,date_to:str|None=None,category:str|None=None,
    amount_min:float|None=Query(default=None,ge=0),amount_max:float|None=Query(default=None,ge=0),
    transaction_type:str|None=None,limit:int=Query(default=100,ge=1,le=500),offset:int=Query(default=0,ge=0)):
    clauses=["user_id=?"]; args=[user_id]
    if date_from: clauses.append("timestamp>=?"); args.append(date_from)
    if date_to: clauses.append("timestamp<=?"); args.append(date_to+"T23:59:59" if len(date_to)==10 else date_to)
    if category: clauses.append("category=?"); args.append(category)
    if amount_min is not None: clauses.append("CAST(amount AS REAL)>=?"); args.append(amount_min)
    if amount_max is not None: clauses.append("CAST(amount AS REAL)<=?"); args.append(amount_max)
    if transaction_type: clauses.append("transaction_type=?"); args.append(transaction_type)
    with connect() as conn:
        user_or_404(conn,user_id)
        where=" AND ".join(clauses)
        total=conn.execute(f"SELECT COUNT(*) FROM transactions WHERE {where}",args).fetchone()[0]
        rows=conn.execute(f"SELECT * FROM transactions WHERE {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?",[*args,limit,offset]).fetchall()
    return ok({"items":[dict(r) for r in rows],"total":total,"limit":limit,"offset":offset})

@app.get("/api/users/{user_id}/spending")
def user_spending(user_id:str):
    with connect() as conn:
        user_or_404(conn,user_id); result=summarize(tx_rows(conn,user_id),latest_monthly(conn,user_id))
    return ok(result)

@app.get("/api/users/{user_id}/forecast")
def user_forecast(user_id:str):
    with connect() as conn:
        user=user_or_404(conn,user_id); result=forecast_for_user(latest_monthly(conn,user_id),is_imported=bool(user.get("is_imported")))
    result["prediction_note"]=prediction_note(result)
    return ok(result)

@app.post("/api/goals",status_code=201)
def create_goal(payload:GoalCreate):
    try:
        with connect() as conn:
            user_or_404(conn,payload.user_id)
            cur=conn.execute("INSERT INTO goals (user_id,goal_name,target_amount,current_saved_amount,target_months,deadline,priority) VALUES (?,?,?,?,?,?,?)",
                (payload.user_id,payload.goal_name,payload.target_amount,payload.current_saved_amount,payload.target_months,payload.deadline,payload.priority))
            result=get_goal(conn,cur.lastrowid)
    except sqlite3.IntegrityError as exc: raise HTTPException(422,detail={"code":"invalid_goal","message":str(exc)}) from exc
    return ok(result)

@app.post("/api/goals/{goal_id}/contributions",status_code=201)
def record_goal_contribution(goal_id:int,payload:GoalContributionCreate):
    with connect() as conn:
        goal=get_goal(conn,goal_id)
        updated=goal["current_saved_amount"]+payload.amount
        if updated>goal["target_amount"]:
            raise HTTPException(422,detail={"code":"contribution_exceeds_goal","message":"This contribution is more than the remaining goal amount."})
        conn.execute("UPDATE goals SET current_saved_amount=? WHERE goal_id=?",(updated,goal_id))
        cur=conn.execute("INSERT INTO goal_contributions (goal_id,amount,note) VALUES (?,?,?)",(goal_id,payload.amount,payload.note))
        row=conn.execute("SELECT contribution_id,amount,note,created_at FROM goal_contributions WHERE contribution_id=?",(cur.lastrowid,)).fetchone()
    return ok({"goal_id":goal_id,"current_saved_amount":updated,"progress_pct":round(updated/goal["target_amount"]*100,1),"contribution":dict(row)})

@app.get("/api/goals/{goal_id}/history")
def goal_progress_history(goal_id:int):
    with connect() as conn:
        goal=get_goal(conn,goal_id)
        contributions=[dict(row) for row in conn.execute("SELECT contribution_id,amount,note,created_at FROM goal_contributions WHERE goal_id=? ORDER BY contribution_id",(goal_id,)).fetchall()]
    starting=max(0,goal["current_saved_amount"]-sum(row["amount"] for row in contributions))
    running=starting
    events=[{"kind":"starting_balance","amount":round(starting,2),"cumulative_amount":round(starting,2),"created_at":goal["created_at"],"note":"Starting balance"}]
    for item in contributions:
        running+=item["amount"]
        events.append({"kind":"contribution","amount":item["amount"],"cumulative_amount":round(running,2),"created_at":item["created_at"],"note":item["note"]})
    return ok({"goal_id":goal_id,"goal_name":goal["goal_name"],"target_amount":goal["target_amount"],"current_saved_amount":goal["current_saved_amount"],"events":events})

@app.get("/api/goals/{goal_id}")
def get_goal_by_id(goal_id:int):
    with connect() as conn: return ok(get_goal(conn,goal_id))

@app.post("/api/goals/{goal_id}/plan")
def generate_goal_plan(goal_id:int):
    with connect() as conn:
        goal=get_goal(conn,goal_id); user=user_or_404(conn,goal["user_id"])
        result,recommendations=make_plan(conn,goal,user)
        conn.execute("INSERT INTO goal_plans (goal_id,plan_json) VALUES (?,?)",(goal_id,json.dumps(result,ensure_ascii=False)))
        for r in recommendations:
            conn.execute("INSERT INTO recommendations (user_id,kind,text_en,text_bn,reason_en,reason_bn) VALUES (?,?,?,?,?,?)",
                (user["user_id"],r["kind"],r["text_en"],r["text_bn"],r["reason_en"],r["reason_bn"]))
    return ok(result)

@app.post("/api/goals/{goal_id}/what-if")
def what_if(goal_id:int,payload:WhatIfRequest):
    with connect() as conn:
        goal=get_goal(conn,goal_id); user=user_or_404(conn,goal["user_id"])
        result,_=make_plan(conn,goal,user,payload.reductions)
    return ok(result)

@app.get("/api/personas")
def personas(): return ok(read_json(DATA_DIR/"personas.json",[]))

@app.get("/api/personas/{persona_id}")
def persona(persona_id:str):
    rows=read_json(DATA_DIR/"personas.json",[])
    match=next((p for p in rows if p["persona_id"]==persona_id),None)
    if match is None: raise HTTPException(404,detail={"code":"persona_not_found","message":"Demo persona not found."})
    return ok(match)

@app.get("/api/model/metrics")
def model_metrics():
    result=read_json(METRICS_PATH,read_json(DATA_DIR/"model_metrics.json",{}))
    return ok(result)

@app.get("/api/model/features")
def model_features(): return ok(read_json(FEATURES_PATH,{"method":"Train the model to calculate importance.","features":[]}))

@app.get("/api/product-metrics")
def product_metrics(): return ok(read_json(DATA_DIR/"product_metrics.json",{"label":"Synthetic simulation — not real customer evidence","status":"Run scripts/evaluate_product.py to calculate."}))

@app.get("/api/responsible-ai")
def responsible_ai():
    return ok({"privacy":"Bundled demo records are generated synthetically. User-imported CSV records stay in the local SQLite database and are not sent to external services.",
      "explainability":"Forecast, calculation, recommendation and assumption are returned as distinct fields.",
      "fairness":"Model error is summarized across synthetic occupation groups in the evaluation report.",
      "human_oversight":"Plans are suggestions only. The app does not move money or make lending decisions.",
      "limitations":"Synthetic evidence is not real-customer validation; real validation needs governed anonymized/aggregated data and controlled experiments.",
      "model_scope":"The trained estimator is used only for synthetic demo profiles. Imported profiles use a personal rolling-three-month baseline until a governed real-data evaluation exists.",
      "security":"This is a local prototype. It binds to loopback by default and restricts accepted host names, but it has no account authentication or application-level database encryption. Do not expose it to a network or public users.",
      "privacy_bn":"ডেমোর তথ্য কৃত্রিমভাবে তৈরি। ব্যবহারকারীর CSV স্থানীয় SQLite ডেটাবেসে থাকে এবং বাইরের কোনো সেবায় পাঠানো হয় না।",
      "explainability_bn":"পূর্বাভাস, হিসাব, পরামর্শ এবং অনুমান আলাদাভাবে দেখানো হয়।",
      "fairness_bn":"কৃত্রিম পেশাভিত্তিক গ্রুপে মডেলের ভুলের হার দেখানো হয়; এটি বাস্তব গ্রাহকের ন্যায্য ফলের প্রমাণ নয়।",
      "oversight_bn":"পরিকল্পনাগুলো কেবল পরামর্শ। অ্যাপ টাকা সরায় না বা ঋণের সিদ্ধান্ত নেয় না।",
      "model_scope_bn":"প্রশিক্ষিত মডেলটি শুধু কৃত্রিম ডেমো প্রোফাইলে ব্যবহৃত হয়। বাস্তব তথ্য দিয়ে নিয়ন্ত্রিত মূল্যায়ন না হওয়া পর্যন্ত আমদানি করা প্রোফাইলে ব্যক্তিগত তিন মাসের গড় ব্যবহার করা হয়।",
      "security_bn":"এটি স্থানীয় প্রোটোটাইপ। এটি ডিফল্টভাবে শুধু নিজের কম্পিউটারে চলে, তবে এতে অ্যাকাউন্ট লগইন বা ডেটাবেসের অ্যাপ-স্তরের এনক্রিপশন নেই। নেটওয়ার্কে বা জনসাধারণের জন্য চালু করবেন না।"})
