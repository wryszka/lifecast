# Bricksurance LifeCast

A synthetic, ready-to-run demo of moving actuarial liability modelling onto Databricks
for **Bricksurance Life** — starting with the data layer around the existing estate:
governed model point pipeline, quality gate, lineage. The downstream liability model
runs unchanged.

Spec: [`LIFECAST_BUILD_BRIEF.md`](LIFECAST_BUILD_BRIEF.md) · Hard rules: [`CLAUDE.md`](CLAUDE.md)

> **About this demo** — Bricksurance Life is a fictional insurer; every policy, premium
> and extract here is synthetic. The demo shows *how to model* on Databricks; it contains
> no client data, no pricing logic and no actuarial formulae.

## Status

| Phase | Name | Status |
|---|---|---|
| 0 | Synthetic foundation | ✅ Built |
| 1 | Model point pipeline | ✅ Built |
| 2 | Assumption governance | ✅ Built |
| 3 | Results + AI/BI + Genie | ✅ Built |
| 4 | ESG / scenario management | ✅ Built |
| 5 | Projection migration POC | ✅ Built |
| 6 | Stochastic + boundaries | ✅ Built |
| — | LifeCast Cockpit (app) | ✅ Built |

## Install — one edit

The target UC catalog is the **only** thing that changes between workspaces
(`databricks.yml`, variable `catalog`, default `lr_dev_aws_us_catalog`). The
workspace host comes from your CLI profile. Everything is serverless.

Notebook `catalog` widgets carry the same default so hands-on interactive runs
work out of the box (jobs always pass `${var.catalog}`). Porting: change the
bundle variable, then update the widget defaults in one pass:
`grep -rl lr_dev_aws_us_catalog 0*/ app/ | xargs sed -i '' 's/lr_dev_aws_us_catalog/<your_catalog>/'`

```bash
databricks bundle deploy -t dev --profile <PROFILE>
databricks bundle run lifecast_synthetic_foundation -t dev --profile <PROFILE>   # once
databricks bundle run lifecast_overnight_run -t dev --profile <PROFILE>
databricks bundle run lifecast_workbench -t dev --profile <PROFILE>              # start the Cockpit
```

After first app start, grant its service principal read access (one-time;
SP id from `databricks apps get lifecast-workbench`): `USE CATALOG` /
`USE SCHEMA` / `SELECT` on `<catalog>.lifecast` for the status tiles, and
`CAN_VIEW` on the `lifecast_*` jobs and pipelines for deep-link resolution
(links degrade gracefully to path URLs without them).

All workspace assets land **directly in `/Workspace/Shared/lifecast`** — a live
hands-on system organised by use case, simplest first. Each folder is one user
story with its own README and numbered assets in run order:

```
/Workspace/Shared/lifecast/
  00_foundation/             run once — builds the synthetic world
    00_synthetic_policy_book · 01_prophet_extract_mock
  01_model_point_pipeline/   use case 1 — the governed overnight feed + quality gate
    00_model_point_pipeline.py (pipeline source) · 01_quality_gate
    02_export_model_point_file · 03_bad_feed_day (demo lever)
  02_assumption_governance/  use case 2 — versioned basis, maker/checker, Excel round-trip
    00_assumption_master · 01_excel_entry_roundtrip · 02_assumption_approval
  03_results_and_genie/      use case 3 — governed results layer, dashboard, Genie (end of Track 1)
    00_prophet_results_mock · 01_results_pipeline.py (pipeline source)
    02_cfo_export · 03_create_dashboard · 04_create_genie_space
    + LifeCast — BEL Movement (AI/BI dashboard lives here)
  04_scenario_management/    use case 4 — scenarios governed: consume the vendor's, illustrate with QuantLib
    00_external_scenarios_mock · 01_scenario_ingest · 02_eiopa_rfr
    03_quantlib_hull_white · sample_data/ (EIOPA-format workbook)
  05_projection_migration/   use case 5 — the workshop: same product in Python, tied out side by side
    00_prophet_baseline_mock · 01_term_projection (the workshop notebook)
    02_projection_validation
  06_stochastic_boundaries/  use case 6 — the fan-out demo + three honest explainers
    00_stochastic_fan_out · 01_vectorisation_boundary
    02_nested_stochastic_costing · 03_esg_plugin
  .bundle/                   bundle internals — ignore
```

All data in `<catalog>.lifecast` (single schema; medallion via `brz_`/`slv_`/`gld_`
prefixes), all files in the `lifecast_files` volume.

## What's here

| Asset | What it is |
|---|---|
| Job `lifecast_synthetic_foundation` | Phase 0: synthetic term book as a file-shaped policy-admin feed + the mock downstream model point extract (the before-state) + the parked bad-feed-day file |
| Pipeline `lifecast_model_point_pipeline` | Phase 1: Auto Loader → `brz_policy_admin` → `slv_policies` (expectations + duration/attained-age/outstanding-term at the valuation date) + `slv_policies_quarantine` → `gld_model_points` (attained age × outstanding term grouping). Full UC lineage |
| Job `lifecast_overnight_run` | The governed run: pipeline refresh → quality gate (row rules + movement check vs last good run + grouping control-total proof; RED stops the run **before** export) → model point file + Excel validation extract |
| Job `lifecast_bad_feed_day` | Demo lever: `action=inject` drops a defective feed into the landing path; `action=restore` removes it + full-refreshes |
| `gld_run_quality` / `gld_run_signoff` / view `gld_quality_dashboard` | Gate history and sign-off — the auditable destination. Each run records the `assumption_set_id` in force (which extract *and* which basis fed which run) |
| `asm_mortality` / `asm_lapse` / `asm_expense` + `asm_assumption_sets` + `asm_approval_log` | Phase 2: versioned assumption master with registry and append-only audit trail. UC functions `asm_active_set_id()` / `asm_*_active()` are the single read path to the approved basis |
| Job `lifecast_assumption_entry` | The maker step — runs exactly the SQL the Excel template submits via `DATABRICKS.SQL` (drafts a shocked basis, submits for approval) |
| Job `lifecast_assumption_approval` | The checker step — approve (old basis → SUPERSEDED) or reject, fully audited. View `asm_governance_dashboard` |
| `lifecast_files/excel/lifecast_assumption_entry.xlsx` | The Excel connection point: live `DATABRICKS.SQL` reads of the approved basis + the submit-shock entry sheet |
| Pipeline `lifecast_results_pipeline` + job `lifecast_results_run` | Phase 3: quarterly results CSV dumps → `brz_prophet_results` → `slv_projection_results` → `gld_results_by_product` + `gld_bel_movement`; then CFO export (Excel+CSV board pack), dashboard publish, Genie space |
| `LifeCast — BEL Movement` dashboard · `LifeCast — Results` Genie space | The reporting destinations: counters/trend/movement live from the governed layer; Genie answers "BEL movement vs last quarter by product line" |
| Job `lifecast_scenario_ingest` | Phase 4 consume: vendor scenario delivery → validation gate → `esg_scenarios` + versioned `esg_scenario_sets` registry → ACTIVE. Feed point: `esg_active_set_id()` / `esg_scenarios_active()` |
| Job `lifecast_esg_illustrative` | Phase 4 illustrate: EIOPA RFR ingest (`esg_rfr_curve`, reused from the Excel accelerator) → QuantLib HW1F + Black-Scholes → `esg_hull_white_paths`, AVAILABLE; calibration + martingale diagnostics in MLflow (`/Shared/lifecast/04_scenario_management/esg_calibration`) |
| Job `lifecast_projection_run` | Phase 5 (the expand): legacy baseline per model point → Python projection on governed inputs (`gld_term_projection`, MLflow-tracked, UC model `lifecast_term_projection` @champion) → per-MP tie-out gate (`gld_projection_validation`, £0.01 tolerance, drift fails the run) |
| Job `lifecast_stochastic_run` | Phase 6: the term book across 1,000 governed scenario paths via `mapInPandas` (`gld_stochastic_bel`); distribution + curve-reconciliation metric to MLflow — run it on both scenario sets to show the basis difference. Explainers (vectorisation boundary, nested-stochastic costing, ESG plug-in) live in the folder |
| App `lifecast-workbench` — **the LifeCast Cockpit** | The presenter's cockpit (brief §9): persona → question → card (proves / where it lives / build & control / Go deep links / today→tomorrow), plus four read-only status tiles pulled live from UC. Thin by design — no business logic; every Go button opens the real asset. Lets **any SA run this demo, not just the author** |

## The demo beat

1. `lifecast_overnight_run` → gate **GREEN**, model point file exported. Lineage
   visible in Catalog Explorer from volume to gold.
2. `lifecast_bad_feed_day` (inject) → `lifecast_overnight_run` → gate **RED**, run
   stops, quarantine shows exactly which rows failed which rules. *The morning is no
   longer hostage to a broken extract.*
3. `lifecast_bad_feed_day` with `action=restore` → next run **GREEN** again.
4. **Results & Genie:** run `lifecast_results_run`, open the dashboard, then ask Genie
   *"Which product line drove the BEL increase in the latest quarter?"* — GROUP_PROTECTION,
   +£8.8m, straight off the governed layer. CFO export lands in `export/board_pack/`.
   *Track 1 complete — zero actuarial maths written.*
5. **Projection migration:** run `lifecast_projection_run` — the same term product in
   Python, on the governed basis and curve, **ties out to the penny per model point**
   (8,185/8,185, duration-aware) in ~0.2 seconds against a multi-hour anchor. Registered in UC, every
   run on the record. *The workshop beat: the client writes the product logic.*
6. **Stochastic + boundaries:** run `lifecast_stochastic_run` twice — once on the vendor
   set, once on the QuantLib set. 1,000 path valuations in ~20s; the MLflow reconciliation
   metric shows the martingale set reproducing the curve (−0.4%) and the vendor set
   pricing its own basis (+1.7%). Then the explainers: where vectorisation breaks, what
   nested stochastic costs, why the ESG stays the client's. *Discuss, don't sell.*
7. **Assumption governance:** open the Excel template (or run `lifecast_assumption_entry`) —
   a +10% smoker loading becomes a draft basis, PENDING_APPROVAL. Run
   `lifecast_assumption_approval` → new basis live, old one SUPERSEDED, every step in
   `asm_approval_log`. The next overnight run records the new `assumption_set_id`.
   *No more filename-versioned workbooks and email-chain sign-off.*

**Today → tomorrow:** today, SQL extract → Excel transform → model point file, with
manual validation and no lineage. Tomorrow, a governed pipeline with a quality gate
and sign-off before a run is burned — and the downstream model untouched.
