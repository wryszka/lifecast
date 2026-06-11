# 06 — Stochastic + boundaries (use case 6 — discuss, don't sell)

**The story:** *"Today, stochastic and nested runs are queued overnight and
quietly descoped because the window can't fit them. Tomorrow, scenarios fan out
across a cluster — with an honest map of where the hard edges are."* One real
demo, three honest explainers. The candour **is** the pitch: an actuary who has
been oversold to before relaxes when shown the boundaries.

**Drive the demo with job `lifecast_stochastic_run`** (param `scenario_source`:
`active` vendor set · `latest_illustrative` QuantLib set).

| # | Asset | What it is |
|---|---|---|
| 00 | `00_stochastic_fan_out` | **The demo:** the term book valued across 1,000 governed scenario paths via `mapInPandas` — embarrassingly parallel, scale from workers not hours. Per-scenario BELs → `gld_stochastic_bel`; distribution percentiles + the **reconciliation metric** (mean stochastic vs deterministic curve BEL — tight on a martingale set, visibly off on a vendor basis) → MLflow. |
| 01 | `01_vectorisation_boundary` | **Explainer:** simple projection vectorises (runnable: ~100× speedup live); a pure ratchet *still* vectorises (`cummax`); decision feedback (management actions, dynamic hedging) genuinely breaks it — loop over time, vectorise across paths; compile the hot loop (Numba/JAX) — *solvable, not free*. |
| 02 | `02_nested_stochastic_costing` | **Explainer:** inner × outer is multiplicative — widget arithmetic turns "1,000 × 1,000" into core-hours and wall-clock on N cores live in the room. Parallelism makes it feasible, not cheap; proxies/LSMC are the industry answer, and that fitting workflow is exactly use case 05's MLflow pattern. |
| 03 | `03_esg_plugin` | **Explainer:** we never ship an ESG — drop, gate, registry, single feed point (use case 04); any engine consuming it inherits the governance. Run the demo on both scenario sets to prove the swap. |

**Where to look while presenting:** run 00 live (seconds), then the MLflow
experiment (`/Shared/lifecast/06_stochastic_boundaries/stochastic`) — two runs,
two scenario sets, the reconciliation metric telling the basis story. The
explainers are for the whiteboard conversation afterwards.

**Partners** slot in at the projection-logic layer — the data, governance and
fan-out underneath them is what was just demonstrated.

**Today → tomorrow:** today, compute-bound overnight queues. Tomorrow, parallel
scenario fan-out sized per run — and an honest conversation about scenario
budgets, proxies and hot loops instead of server queues.
