# 03 — Results, AI/BI & Genie (use case 3 — end of Track 1)

**The story:** *"I ask 'show me BEL movement vs last quarter by product line' and
get an answer — instead of rebuilding a pivot table."* The engine runs, dumps its
CSVs (because that is what engines do), and the dumps land in Delta once,
governed. AI/BI and Genie replace the downstream Excel stack; the CFO export is
**always offered**; QRT/XBRL templates stay in Excel.

**The coherent chain:** TERM_LEVEL results come from the *real* governed path —
policy → model point file → the (mock) engine → results — so the dashboard
number reconciles to the tie-out, to the model points, to the policies. The
other two product lines are still "legacy-fed" (synthesised), exactly how a
partially-migrated estate looks.

**Drive it with `lifecast_quarter_close`** — the whole close as one workflow:
overnight run → engine run → results run. Or piecewise: `lifecast_engine_run`,
then `lifecast_results_run`.

| # | Asset | What it does |
|---|---|---|
| 00 | `00_engine_run` | **The mock engine, orchestrated** (job `lifecast_engine_run`): picks up the exported MPF, reads the approved basis + EIOPA curve, values the term book per model point — base **and ±100bp sensitivity runs** — synthesises the two legacy-fed lines, dumps estate CSVs to `prophet/results/` + per-MP detail to `prophet/results_detail/` + its **run log** to `prophet/run_log/`. |
| 01 | `01_results_pipeline.py` | **Source of pipeline `lifecast_results_pipeline`**: summary dumps → `brz_prophet_results` → `slv_projection_results` (typed, checked, **latest engine run wins** — engines re-run quarters) → `gld_results_by_product` + `gld_bel_movement`; detail dumps → `brz_engine_mp_results` → `slv_engine_mp_results`; run logs → `brz_engine_run_log` → `slv_engine_run_log`. |
| 02 | `02_cfo_export` | The board pack as Excel + CSV to `export/board_pack/` on every run — board sheet + **rate-risk sheet + audit sheet** (even the spreadsheet carries its provenance). Connect, don't replace. |
| 03 | `03_create_dashboard` | Creates/updates the **`LifeCast — BEL Movement`** dashboard (idempotent, runtime warehouse) — page 1 *Results*, page 2 *Risk & audit* (rate-risk map, concentration, cohort movers, run audit). |
| 04 | `04_create_genie_space` | Creates the **`LifeCast — Results`** Genie space over the results + analytics + audit layer (create-if-missing). |
| 05 | `05_bel_analytics` | **The analytics case:** the rate-risk map (BEL sensitivity by attained age × outstanding term, from the engine's own ±100bp runs), concentration (top cells + cumulative share), and movement drilled to cohort level → `gld_bel_sensitivity`, `gld_bel_concentration`, `gld_movement_by_cohort`. Ran in seconds on results you already had — that's the point. |
| 06 | `06_run_audit` | **The audit trail:** `gld_run_audit` — one row per engine run: input file + gate verdict, basis version + who approved it and when, curve date, operator, timings, minutes-to-queryable. Closes with Delta history + `VERSION AS OF` (reproduce any published number). The audit trail is a join, not a project. |

**Where to look while presenting:** the quarter-close workflow graph (the whole
close, orchestrated), the dashboard (both pages), then Genie — *"which product
line drove the BEL increase?"* (GROUP_PROTECTION, the planted jump), *"where is
my rate risk concentrated?"* (the sensitivity table), *"who ran the latest
engine run and which basis did it use?"* (the audit trail), and *"which
assumption basis is currently approved?"* to tie back to use case 02.

**Today → tomorrow:** today, the engine dumps CSVs and the board pack is rebuilt
in Excel each quarter; a sensitivity question waits for next quarter's batch.
Tomorrow, the dumps land governed, the dashboard and Genie answer instantly, and
the ±100bp runs are already on the shelf.
