# Project Report: upaySave AI

**Project type:** Student prototype for personal savings planning  
**Context:** DIU CPC × upay AI Hackathon 2026  
**Application:** Local web dashboard with a FastAPI backend  
**Primary currency:** Bangladeshi taka (৳ / BDT)  
**Report date:** 7 October 2026

## 1. Executive summary

upaySave AI is a personal savings planner designed to help someone judge whether a savings goal fits their recent cash-flow pattern. The user chooses a target and timeline. The application estimates next-month expenses, estimates income, protects a safety buffer, and calculates a possible monthly contribution. It explains the estimate and lets the user try alternative spending assumptions before deciding what to do.

The application is a local prototype, not a wallet or banking integration. It comes with generated demonstration profiles and can also import a user's transaction CSV into a separate profile in the local SQLite database. The interface presents estimates, calculations, recommendations, and assumptions as distinct things. Its financial calculations are deterministic; it does not use an LLM to decide how much a person can save.

## Rubric coverage at a glance

| Criterion | Implementation in this project | What still needs real-world work |
|---|---|---|
| Problem relevance | A user-selected savings goal is compared with recent cash flow and a protected reserve. | Validate the need, language, and assumptions with intended users. |
| AI/ML depth | Five chronological validation folds, model/baseline comparison, feature importance, synthetic subgroup errors, and an empirical model-error range. Imported profiles use a personal baseline rather than the synthetic-trained model. | Evaluate on permissioned representative data and calibrate uncertainty before real-world reliance. |
| Customer/business impact | A defined six-month synthetic scenario scorecard includes feasibility, positive capacity, projected savings, and synthetic occupation slices. | Run a controlled pilot; track real goal progress and safety guardrails. |
| Prototype quality | Bilingual UI, import preview/mapping, profile lifecycle, contributions, accessible chart interaction, model evidence, and explicit assumptions. | Add account flows, operations support, and broader accessibility review before deployment. |
| Innovation | Combines a volatility-adjusted reserve with user-controlled scenario exploration and local transaction import. | Test whether users understand and value this interaction. |
| Scalability & integration | Bounded/paginated API, query indexes, documented API surface, and normalized CSV import. | Replace local SQLite with managed storage and connect to an approved production data adapter if authorized. |
| Responsible AI & security | Discloses synthetic scope, uses the synthetic estimator only on demo profiles, applies host validation/security headers, and ignores local database files in Git. | Add authentication, encryption, consent/retention controls, monitoring, and a security review before network use. |

## 2. Goal and problem being addressed

### Project goal

The goal is to make savings planning more personal and understandable than a fixed calculator. A fixed calculator can divide a target by the number of months, but it does not consider whether income varies, how much the person typically spends, or how much money should remain available for unexpected costs.

The planner combines a next-month expense estimate with a recent-income estimate and a protected reserve. It then compares the remaining estimated capacity with the contribution required for the selected goal. The user can see why the goal appears manageable, tight, or in need of adjustment, and can explore a longer timeline or different spending assumptions.

### Intended value

- Help users think through a savings goal using their own recorded spending pattern.
- Make the main assumptions and arithmetic visible in plain language.
- Give users a way to compare scenarios without moving money or committing to a plan.
- Demonstrate a responsible, explainable personal-finance use of forecasting in a synthetic hackathon prototype.

### Out of scope

The project does not connect to production upay systems, initiate payments, transfer or hold funds, provide credit scores, make lending decisions, or guarantee that a savings target will be achieved. It is not evidence that the model works for real customers.

## 3. Who it is for and key use cases

The prototype is intended for people who want to set a savings target and understand how it relates to their income and spending. A user can:

1. Explore one of the bundled synthetic demonstration profiles.
2. Create a goal with an amount, current savings, timeline, and priority.
3. Review a monthly plan, required contribution, estimated feasible contribution, and remaining gap.
4. Adjust selected category assumptions in the What-If studio and compare the resulting plan.
5. Inspect category spending, monthly history, and unusual changes against the profile's own history.
6. Preview a CSV transaction export, map its columns, and save it as a separate local profile.
7. Filter, export, or delete an imported profile and its associated records.
8. Switch between English and Bangla explanations and labels.

## 4. Product and user-interface overview

The dashboard is a responsive HTML, CSS, and JavaScript application; it does not require a JavaScript package build step. Charts are drawn on Canvas.

| Area | What it provides |
|---|---|
| **Overview** | Profile context, planning status, savings and cash-flow figures, spending trend, category mix, and the current goal summary. |
| **Build a plan** | Goal entry and a detailed plan with monthly estimates, explanations, assumptions, and contribution history controls. |
| **What-If studio** | Recalculates the plan for selected reductions in Food, Shopping, Transport, or Entertainment spending. Scenario inputs are limited to 0–30%. |
| **Spending** | Category totals, month-over-month changes, a monthly bar chart, and personal unusual-pattern checks. |
| **Demo stories** | Three named synthetic profiles that illustrate different generated cash-flow patterns. |
| **Model evidence** | Model-to-baseline validation metrics, feature importance, and synthetic occupation-group error summaries. |
| **Transactions** | CSV preview/import, transaction filters, CSV export, and deletion controls for imported profiles. |
| **Responsible AI** | Explains the estimate labels, user control, synthetic evidence boundary, and responsible-use limits. |

The monthly bar chart uses a value-responsive vertical scale and compact taka labels, marks the latest month, and displays a date-range/latest-value summary. Its tooltip includes the month, total, and transaction count. Pointer interaction is supported, and keyboard navigation uses the arrow keys plus Home and End.

## 5. How the savings calculation works

The calculation is kept separate from the machine-learning prediction:

```text
estimated feasible monthly saving
  = max(0, expected monthly income
           - adjusted next-month expense estimate
           - protected safety buffer)
```

- Expected income is the median of up to the latest three monthly income values. If no history is present, the profile's stated monthly income is used.
- The selected forecasting model estimates next-month total expenses. If the serialized model is unavailable, inference falls back to a rolling-three-month expense average.
- With no transaction history, the planner uses a conservative expense estimate of 75% of profile income and discloses this assumption.
- The safety buffer is at least ৳1,000 or 5% of expected income, whichever is greater. Recent income volatility can increase the reserve rate up to 20%.
- Required monthly saving is the remaining goal amount divided by the chosen number of months. The service also calculates a weekly figure and a month-by-month illustrative contribution schedule.
- The What-If calculation reduces the category estimates by the chosen percentages, then recomputes expenses, buffer-adjusted capacity, and goal status.

Statuses such as **On Track**, **Tight**, **Needs Adjustment**, and **Difficult With Current Pattern** describe the relationship between the entered target and the estimate. They are not credit scores or judgments about the user. Recommendations are rule-based suggestions grounded in the estimate and are meant to be reversible.

## 6. Data and machine-learning workflow

### Bundled synthetic data

The generation script creates reproducible synthetic users, transactions, monthly features, persona descriptions, and assumption notes. The documented demo build contains 250 generated profiles and at least 10,000 transaction records spanning 12 months. The three demo stories use the first three generated profiles; the remaining profiles support model development and evaluation. Synthetic records are not production upay data and do not represent actual customers.

Monthly features include income, total and category expenses, transaction count, average transaction amount, previous-month expense, rolling-three-month expense, and seasonal month indicators. The supervised target is the same profile's following-month total expense.

### Forecast model and evaluation

The training pipeline compares Gradient Boosting, Extra Trees, and Random Forest regressors with two simple baselines: last month's expense and the rolling-three-month mean. Evaluation uses five expanding-window, one-month-ahead chronological folds so later target months are not randomly mixed into training. The selected model is the machine-learning candidate with the lowest mean validation MAE. The pipeline reports MAE, RMSE, R², and MAPE, then saves the fitted model and its feature list. Permutation importance is calculated on the final two chronological target months.

For synthetic demo forecasts, the project also displays an empirical range based on the 90th percentile of selected-model walk-forward absolute errors. This range is descriptive and explicitly not a calibrated probability interval. Imported profiles use their own recent three-month expense mean and observed month range; the synthetic-trained model is not applied to imported transactions.

The checked-in metrics file reports this synthetic-data snapshot:

| Candidate | MAE (৳) | RMSE (৳) | R² | MAPE |
|---|---:|---:|---:|---:|
| Gradient Boosting | 2,703.69 | 3,536.03 | 0.9517 | 7.69% |
| Extra Trees | 2,680.87 | 3,527.53 | 0.9517 | 7.41% |
| Random Forest (selected ML model) | 2,652.80 | 3,524.22 | 0.9519 | 7.28% |
| Last-month baseline | 3,183.35 | 4,263.34 | 0.9297 | 8.58% |
| Rolling-three-month baseline | 2,604.08 | 3,472.33 | 0.9532 | 7.08% |

In this run Random Forest has 16.67% lower MAE than the last-month baseline, but its MAE is 1.87% higher than the rolling-three-month baseline. The app displays both comparisons. These are generated-data results only; they do not establish performance on imported users or real customers. Re-generating data or changing training settings can change the metrics.

The refreshed bundle's 90th-percentile absolute walk-forward error is ৳5,744.04. The app uses it as a global descriptive error band around synthetic-profile forecasts, not as an individual confidence interval or a guarantee.

### Spending patterns and recommendations

Spending summaries aggregate non-income transactions by month and category. When there is enough monthly history, the anomaly check compares the latest month's category vector with that profile's earlier pattern using an Isolation Forest and a robust median-based category threshold. It is a prompt to review an unusual personal pattern, not fraud detection. Recommendation text is produced with deterministic rules and provided in English and Bangla.

### Product simulation

The product evaluation script compares a synthetic control scenario with an illustrative scenario that reduces Shopping expenses by 8%, while keeping the same volatility-aware reserve in both scenarios. In the bundled 250-profile run, six-month benchmark-goal feasibility moves from 86.0% to 86.4% (+0.4 percentage points); positive monthly capacity moves from 90.0% to 92.4%. Average projected six-month savings per profile is ৳7,332.67 to ৳7,510.64. The scorecard also shows occupation slices. The result is a mathematical simulation with fixed assumptions, not a controlled field study, causal estimate, or claim about customer impact. The small goal-feasibility change is shown as measured output rather than marketed as a large benefit.

## 7. CSV import and transaction handling

The transaction page supports a local, preview-first workflow:

1. The user selects a CSV file and enters a profile name, stated monthly income, current savings, and optional region.
2. The app reads the header and suggests mappings for common date, amount, debit, credit, category, transaction type, merchant, location, and channel names. The user can adjust mappings.
3. The preview validates rows and shows a sample, month coverage, row counts, income/expense counts, and expense total.
4. On save, the backend normalizes dates and amounts, classifies income/payment/cash-out/transfer rows, maps categories using the supplied category or recognizable header/merchant terms, and derives per-month features.
5. A database transaction creates a separate imported profile and inserts its transactions, monthly features, and import-batch metadata together. Income rows are retained in the ledger but excluded from expense totals.

Imports are limited to 8 MB, 50,000 transaction rows, and 80 columns. The parser checks for named and nonduplicate headers, required date and amount (or debit/credit) fields, malformed dates or values, oversized amounts, and extra values beyond the headers. The same CSV content cannot be imported twice while its import batch exists. Imported rows are stored in the local SQLite database when the app is run locally; they are not sent to an external service by this prototype. An imported profile can be exported as CSV or deleted with its dependent goals, contributions, plans, recommendations, feature rows, transactions, and batch metadata.

## 8. Technical architecture

```text
Generated files ──> SQLite seed ──┐
                                  ├──> FastAPI / Pydantic ──> HTML/CSS/JS dashboard
User CSV ──> parse/validate ──────┘             │
                                                ├──> planning and spending services
                                                └──> scikit-learn inference artifact
```

| Layer | Implementation |
|---|---|
| Web API | FastAPI routes and Pydantic request validation in `app/main.py` and `app/schemas.py`. |
| Database | SQLite through Python's standard `sqlite3` driver; schema creation and lightweight column migrations are in `app/db.py`. |
| Business logic | Planning, import normalization, spending aggregation, recommendation rules, and explanation strings are in `app/services/`. |
| Machine learning | Temporal feature preparation, model comparison/training, and inference are in `app/ml/`; the serialized model and JSON evidence are in `models/`. |
| Frontend | Static responsive assets in `app/static/`; frontend API calls use the FastAPI application. |
| Data and scripts | Synthetic input/evidence under `data/`; generation, training, evaluation, and database setup under `scripts/`. |

### Main SQLite records

The schema includes `users`, `transactions`, `monthly_features`, `import_batches`, `goals`, `goal_contributions`, `goal_plans`, `recommendations`, and `model_metrics`. Imported profiles are marked separately from generated profiles. The `UPAYSAVE_DB_PATH` environment variable can point the application at a different local database file.

## 9. API capabilities

Successful responses use a `{ "data": ..., "error": null }` envelope. FastAPI publishes interactive documentation at `/docs` when the server is running.

| Route group | Endpoints | Purpose |
|---|---|---|
| Runtime | `GET /api/health` | Health, database counts, and model availability. |
| Profiles | `GET /api/users`, `GET /api/users/{user_id}`, `GET /api/users/{user_id}/summary` | List profiles and retrieve profile or dashboard summary. |
| CSV import | `POST /api/import/columns`, `POST /api/import/preview`, `POST /api/import` | Inspect/map columns, preview and validate, then save an imported profile. |
| Imported data lifecycle | `GET /api/users/{user_id}/transactions/export`, `DELETE /api/import/{user_id}` | Export transactions or delete an imported profile and associated data. |
| Transactions and spending | `GET /api/users/{user_id}/transactions`, `GET /api/users/{user_id}/spending` | Filter ledger rows and retrieve category/month/anomaly summaries. |
| Forecast | `GET /api/users/{user_id}/forecast` | Retrieve the next-month estimate and model label. |
| Goals | `POST /api/goals`, `GET /api/goals/{goal_id}`, `POST /api/goals/{goal_id}/plan` | Create and inspect a goal and calculate/save its plan. |
| Goal progress | `POST /api/goals/{goal_id}/contributions`, `GET /api/goals/{goal_id}/history` | Record a contribution and retrieve progress history. |
| Scenarios | `POST /api/goals/{goal_id}/what-if` | Recalculate a goal with validated category reductions. |
| Demo and evidence | `GET /api/personas`, `GET /api/personas/{persona_id}`, `GET /api/model/metrics`, `GET /api/model/features`, `GET /api/product-metrics`, `GET /api/responsible-ai` | Supply demo profile details, validation evidence, simulation results, and responsible-use notes. |

## 10. Running the project

Python 3.12 is the documented target. From the project directory in PowerShell:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
python scripts/generate_data.py
python scripts/train_model.py
python scripts/evaluate_product.py
python scripts/setup_db.py
python run.py
```

The dashboard is served at `http://localhost:8000`, the API docs at `http://localhost:8000/docs`, and the health route at `http://localhost:8000/api/health`. The runner binds to `127.0.0.1` by default. The database is seeded only when its `users` table is empty. Follow the README's regeneration guidance when rebuilding generated data and database contents.

To run the automated test suite after installing dependencies and generating the expected model/data artifacts:

```powershell
python -m pytest -q
```

The existing suite covers API/health behavior, seeded profiles, summaries, forecast evidence, goal validation and planning, What-If scenarios, spending and responsible-AI responses, CSV preview and validation, duplicate import handling, export/deletion, database migration, and planning edge cases such as variable income or missing history.

## 11. Privacy, safety, and responsible-use boundaries

- Bundled profiles, transactions, validation scores, and product-simulation outputs are synthetic.
- A locally run app stores imported CSV-derived data in its local SQLite database. The application code does not call an external AI service or upay production API.
- The trained synthetic estimator is used only on generated demo profiles. Imported profiles use their own recent transaction history with a simple rolling baseline.
- The app defaults to localhost, restricts accepted host names, and adds basic browser security headers. It does not provide user authentication or authorization for public multi-user hosting.
- The SQLite database is not encrypted by the application. Users should treat the local database file as sensitive and protect it with the device's normal access controls.
- Forecasts are estimates and may be inaccurate, particularly when a person's data is sparse, income changes, or spending patterns differ from the generated training data.
- The savings plan is informational, not a guarantee or professional financial advice. Users choose whether any scenario is appropriate for them.
- Unusual-spending detection is not fraud detection, and the planning status is not a credit or eligibility score.
- Before any real-customer deployment, the project would need appropriate consent, security and retention controls, access management, governed data, and real-world evaluation.

## 12. Current limitations and next steps

The current prototype is intentionally small and local. The trained forecast model is evaluated on synthetic generated data; it is not trained or validated on a representative real-customer dataset. Its empirical error range is not a calibrated probability interval. CSV formats and category recognition are practical but cannot infer every institution's conventions; preview and column mapping help users inspect the interpretation. Authentication, encryption at rest, multi-user access controls, production monitoring, and a live wallet integration are not part of the current app.

Reasonable next steps, subject to privacy and governance review, include:

1. Add consent, retention, authentication, encryption, and secure account/access controls before supporting hosted or shared use.
2. Build a governed data adapter and obtain permissioned, privacy-protected data for evaluation.
3. Evaluate forecast errors and calibration across time and user groups using approved data and a documented protocol.
4. Add prediction ranges and make sparse-history uncertainty easier to understand.
5. Improve institution-specific CSV mapping while preserving the preview-before-save workflow.
6. Conduct controlled user research or experimentation before making customer-impact claims.

## 13. Project file map

| Path | Role |
|---|---|
| `app/main.py` | FastAPI application, HTTP endpoints, and database-facing orchestration. |
| `app/db.py` | SQLite schema initialization, migrations, and connection handling. |
| `app/schemas.py` | Validated request models and field constraints. |
| `app/services/` | Goal planning, CSV parsing/features, spending analysis, explanations, and recommendations. |
| `app/ml/` | Temporal examples, candidate evaluation, model training, and inference. |
| `app/static/` | Dashboard markup, styles, and browser-side interactions/charts. |
| `data/` | Synthetic profile/transaction inputs and generated evaluation artifacts. |
| `models/` | Serialized forecast model plus validation metrics and feature importance. |
| `scripts/` | Data generation, training, product simulation, and database setup commands. |
| `sql/schema.sql` | Readable SQL reference for the database tables. |
| `tests/` | API, CSV import, and planning edge-case coverage. |
| `docs/` | Demo/pitch material and this project report. |

## Conclusion

upaySave AI demonstrates a clear personal-savings planning flow: a user defines a goal, sees an expense estimate and a buffer-aware calculation, and can examine how alternative assumptions affect the plan. The combination of synthetic demo profiles, optional local CSV imports, bilingual explanations, transaction views, and visible model evidence makes the prototype suitable for demonstrating the concept. Its main goal is to support informed, user-controlled planning; production financial use would require a separate phase of security, privacy, governance, and real-world validation.
