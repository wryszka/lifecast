# 01 — The governed model point feed (use case 1, start here)

**The story:** *"My morning is no longer hostage to a broken extract."* The
policy-data → model-point-file pipeline rebuilt as a governed Lakeflow pipeline:
quality gate before a run is burned, full lineage from extract to model point
file, sign-off on record. The downstream liability model runs **unchanged**.

**Drive it with job `lifecast_overnight_run`:** pipeline refresh → quality gate
→ export. A bad feed turns the gate RED and **stops the run before the model
point file is touched**.

| # | Asset | What it does |
|---|---|---|
| 00 | `00_model_point_pipeline.py` | **Source of pipeline `lifecast_model_point_pipeline`** (don't run as a notebook). Auto Loader → `brz_policy_admin` → `slv_policies` + `slv_policies_quarantine` (every reject, with the rules it failed) → `gld_model_points` — grouped by **attained age × outstanding term** (with duration in force) at the valuation date, as an in-force valuation requires. |
| 01 | `01_quality_gate` | The gate: row rules, **movement check** (policy count + sum assured vs the last GREEN run), **grouping proof** (control totals survive policies→model-points), verdict + valuation date + basis in force into `gld_run_quality`, sign-off into `gld_run_signoff`. RED fails the run, loudly. |
| 02 | `02_export_model_point_file` | Only reached on GREEN: model point file in the exact before-state MPF layout + the read-only validation CSV for the actuary's Excel eyeball check. |
| 03 | `03_bad_feed_day` | **Demo lever** (job `lifecast_bad_feed_day`): `action=inject` drops a defective feed into the landing path → next run goes RED; `action=restore` removes it and full-refreshes → GREEN again. |

**Where to look while presenting:** the pipeline graph (expectations firing),
Catalog Explorer lineage on `gld_model_points` (volume → bronze → silver → gold),
and `gld_quality_dashboard` for the GREEN/RED history.

**Today → tomorrow:** today, SQL extract → Excel transform → model point file,
manual validation, no lineage. Tomorrow, a governed pipeline with a quality gate
and sign-off — and the downstream model untouched.
