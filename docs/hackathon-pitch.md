# Hackathon pitch story

## Problem

Customers know their financial goals but often do not know whether a savings target fits their own spending behavior.

## Insight

A fixed savings calculator divides a target by time. It does not account for variable income, essential spending, unusual months, or a safety reserve.

## Solution

upaySave AI turns a savings target into a cash-flow decision: forecast expenses, estimate income, preserve a volatility-aware buffer, then show the possible monthly amount left for the goal. A user can change the timeline or explore reversible category scenarios. The ML model serves synthetic demo profiles; an imported profile uses its own recent-month baseline so a synthetic-trained model is not presented as validated on real transaction history.

## AI value

- Forecasts expenses with a time-aware model comparison.
- Estimates feasible savings with deterministic backend rules.
- Flags unusual personal category patterns and explains the comparison.
- Suggests reversible spending scenarios grounded in observed category totals.

## Customer action and outcome

The customer chooses a goal, inspects the plan, and changes assumptions in What-If. The outcome is a measurable monthly path and a visible remaining gap, without a promise of success.

## Customer and business measurement

The prototype's primary simulated outcome is six-month goal feasibility: the share of synthetic profiles whose reserve-aware estimated capacity covers a benchmark goal within six months. In the 250-profile bundled run, that measure moves from 86.0% to 86.4% (+0.4 percentage points) under an illustrative 8% Shopping reduction; positive-capacity share moves from 90.0% to 92.4%. Average projected six-month savings per profile moves from ৳7,332.67 to ৳7,510.64. The scorecard also reports synthetic occupation slices. These small modeled shifts are displayed as a scenario, not presented as a customer impact claim. A real pilot would instead measure user-understood plan completion and goal progress, while monitoring reserve shortfalls, opt-outs, and forecast errors as guardrails.

## Review-criteria fit

- **Problem relevance:** connects everyday spending uncertainty with a user-selected savings goal.
- **AI/ML depth:** chronological validation, baseline comparison, feature importance, empirical error ranges, and a synthetic subgroup error check.
- **Impact:** exposes defined, interpretable scenario metrics while separating simulation from actual customer evidence.
- **Prototype quality and innovation:** bilingual interface, local CSV preview/import, keyboard-accessible charts, volatility-aware reserve, and interactive What-If planning.
- **Scalability and integration:** documented API, bounded transaction queries, SQLite indexes, and a normalized import boundary provide a path to a governed future data adapter.
- **Responsible AI and security:** no payment or lending action, clear estimate labels, local data handling, explicit model scope, loopback default, host validation, and honest deployment limits.

## Track fit

Primary: **Customer Innovation & Financial Independence**. Secondary: Customer Intelligence, Operations & Service Intelligence, and Open Innovation.

## Evidence boundary

The bundled demo data, model scores, and product simulation are synthetic. Imported CSV data stays local and its estimates use a personal rolling baseline; imported records are not used as hackathon model-evaluation evidence. No account authentication or application-level database encryption is implemented, so this prototype must not be exposed to a network. Real validation would require governed, anonymized or aggregated data and controlled experimentation.
