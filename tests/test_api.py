from .conftest import client

def data(response):
    assert response.status_code < 400, response.text
    body=response.json(); assert body["error"] is None
    return body["data"]

def test_database_and_health():
    d=data(client.get("/api/health"))
    assert d["status"]=="ok" and d["counts"]["users"]==250
    assert d["counts"]["transactions"]>=10_000

def test_personas_and_user_summary():
    personas=data(client.get("/api/personas"))
    assert len(personas)==3
    assert {p["name"] for p in personas}=={"Nadia","Arif","Rafi"}
    summary=data(client.get("/api/users/SYN-0001/summary"))
    assert summary["transaction_count"]>0
    assert summary["planning"]["feasible_monthly_savings"]>=0

def test_create_plan_and_what_if():
    goal=data(client.post("/api/goals",json={"user_id":"SYN-0002","goal_name":"Laptop test","target_amount":60000,
      "current_saved_amount":27000,"target_months":6,"priority":"medium"}))
    plan=data(client.post(f"/api/goals/{goal['goal_id']}/plan",json={}))
    assert plan["goal_name"]=="Laptop test"
    assert plan["safety_buffer"]>=1000
    scenario=data(client.post(f"/api/goals/{goal['goal_id']}/what-if",json={"reductions":{"Shopping":.15,"Food":.05,"Entertainment":.15}}))
    assert scenario["feasible_monthly_savings"]>=plan["feasible_monthly_savings"]
    assert scenario["projected_savings"]>=0

def test_forecast_model_evidence_and_filters():
    forecast=data(client.get("/api/users/SYN-0002/forecast"))
    assert forecast["prediction"]>0
    metrics=data(client.get("/api/model/metrics"))
    assert metrics["models"] and metrics["folds"]>=1
    tx=data(client.get("/api/users/SYN-0002/transactions?category=Shopping&limit=5"))
    assert len(tx["items"])<=5 and all(x["category"]=="Shopping" for x in tx["items"])

def test_spending_anomaly_product_evidence_and_responsible_ai():
    spending=data(client.get("/api/users/SYN-0002/spending"))
    assert any(x["category"]=="Shopping" for x in spending["anomalies"])
    features=data(client.get("/api/model/features"))
    assert features["features"] and "Permutation" in features["method"]
    product=data(client.get("/api/product-metrics"))
    assert product["sample_users"]==250 and "not real customer" in product["label"]
    responsible=data(client.get("/api/responsible-ai"))
    assert "synthetically" in responsible["privacy"] and "lending" in responsible["human_oversight"]

def test_goal_input_validation():
    response=client.post("/api/goals",json={"user_id":"SYN-0001","goal_name":"Bad","target_amount":-1,
      "current_saved_amount":0,"target_months":6})
    assert response.status_code==422

