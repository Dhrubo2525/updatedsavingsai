from app.services.planning import calculate

def test_goal_already_reached_and_zero_current_savings():
    user={"monthly_income":30000}; forecast={"prediction":22000}
    complete=calculate({"goal_name":"Done","target_amount":10000,"current_saved_amount":10000,"target_months":6},user,forecast,[])
    assert complete["planning_status"]=="On Track" and complete["remaining_amount"]==0
    zero=calculate({"goal_name":"New","target_amount":60000,"current_saved_amount":0,"target_months":6},user,forecast,[])
    assert zero["remaining_amount"]==60000 and zero["monthly_plan"]

def test_low_income_high_goal_missing_history_and_empty_categories():
    result=calculate({"goal_name":"Stretch","target_amount":80000,"current_saved_amount":0,"target_months":4},
      {"monthly_income":5000},{"prediction":0},[])
    assert result["predicted_monthly_expenses"]>=3750
    assert result["feasible_monthly_savings"]==250
    assert result["feasible_monthly_savings"]<result["required_monthly_savings"]
    assert result["planning_status"]=="Difficult With Current Pattern"
    assert result["expected_completion_months"] is None

def test_variable_income_uses_recent_median():
    history=[{"income":20000},{"income":60000},{"income":30000}]
    result=calculate({"goal_name":"Reserve","target_amount":10000,"current_saved_amount":0,"target_months":5},
      {"monthly_income":30000},{"prediction":20000},history)
    assert result["expected_monthly_income"]==30000

def test_variable_income_gets_a_larger_reserve():
    history=[{"income":38278.26},{"income":58391.78},{"income":46413.79}]
    result=calculate({"goal_name":"Reserve","target_amount":80000,"current_saved_amount":4000,"target_months":9},
      {"monthly_income":42000,"occupation":"Freelancer"},{"prediction":32033},history)
    assert result["safety_buffer_rate_pct"]==20
    assert result["planning_status"]=="Difficult With Current Pattern"
