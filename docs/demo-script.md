# 3–5 minute judge demo

## Opening (20 sec)

“People can calculate how much they need to save, but they often do not know whether that amount is realistic for their own spending behavior. upaySave AI turns synthetic transaction patterns into an explainable plan while protecting a financial buffer.”

## Flow (about 3 minutes)

1. Start on **Overview** with Nadia. Point out monthly income and spending, forecast expenses, and the planning status.
2. Open **Build my plan**. Her Emergency Fund goal is prefilled; generate it and show required contribution, predicted capacity, safety buffer, month-by-month amounts, and the reason.
3. Open **What-If studio**. Reduce Shopping by 10%, then add a Food reduction. Show the live change in savings capacity, estimated months, and gap. Say these are scenarios she controls.
4. Switch to Arif. Open **Spending** and show the latest synthetic shopping spike against his own history. Read the anomaly explanation and the What-If suggestion.
5. Switch to Rafi. Point out variable monthly income in his profile and the plan's conservative recent-income estimate. Explain if the goal needs more time under the current pattern.
6. Open **Responsible AI**: synthetic demo data, safety buffer, suggestions only, no credit score or autonomous action.
7. Open **Model evidence**. Show the expanding-window design, selected model, baseline errors, feature importance, and synthetic-evaluation caveat.

## Close (20 sec)

“The customer chooses the action. The measurable outcome is a goal path they can review and adjust. This prototype demonstrates the method on generated data; real-customer validation would require governed, anonymized or aggregated data and controlled experimentation.”

## Before presenting

- Follow the Windows setup in the root README.
- Confirm `/api/health` shows 250 users and 10,000+ transactions and `model_loaded: true`.
- Keep the server running and browser on `/`.
- Use EN/বাং if judges want to see the Bengali experience.
