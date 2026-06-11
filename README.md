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
| 4–6 | Demand-driven | Not started |

## Install — one edit

The target UC catalog is the **only** thing that changes between workspaces
(`databricks.yml`, variable `catalog`, default `lr_dev_aws_us_catalog`). The
workspace host comes from your CLI profile. Everything is serverless.

```bash
databricks bundle deploy -t dev --profile <PROFILE>
databricks bundle run lifecast_synthetic_foundation -t dev --profile <PROFILE>   # once
databricks bundle run lifecast_overnight_run -t dev --profile <PROFILE>
```

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
  .bundle/                   bundle internals — ignore
```

All data in `<catalog>.lifecast` (single schema; medallion via `brz_`/`slv_`/`gld_`
prefixes), all files in the `lifecast_files` volume.

## What's here

| Asset | What it is |
|---|---|
| Job `lifecast_synthetic_foundation` | Phase 0: synthetic term book as a file-shaped policy-admin feed + the mock downstream model point extract (the before-state) + the parked bad-feed-day file |
| Pipeline `lifecast_model_point_pipeline` | Phase 1: Auto Loader → `brz_policy_admin` → `slv_policies` (expectations) + `slv_policies_quarantine` → `gld_model_points`. Full UC lineage |
| Job `lifecast_overnight_run` | The governed run: pipeline refresh → quality gate (RED stops the run **before** export) → model point file + Excel validation extract |
| Job `lifecast_bad_feed_day` | Demo lever: `action=inject` drops a defective feed into the landing path; `action=restore` removes it + full-refreshes |
| `gld_run_quality` / `gld_run_signoff` / view `gld_quality_dashboard` | Gate history and sign-off — the auditable destination. Each run records the `assumption_set_id` in force (which extract *and* which basis fed which run) |
| `asm_mortality` / `asm_lapse` / `asm_expense` + `asm_assumption_sets` + `asm_approval_log` | Phase 2: versioned assumption master with registry and append-only audit trail. UC functions `asm_active_set_id()` / `asm_*_active()` are the single read path to the approved basis |
| Job `lifecast_assumption_entry` | The maker step — runs exactly the SQL the Excel template submits via `DATABRICKS.SQL` (drafts a shocked basis, submits for approval) |
| Job `lifecast_assumption_approval` | The checker step — approve (old basis → SUPERSEDED) or reject, fully audited. View `asm_governance_dashboard` |
| `lifecast_files/excel/lifecast_assumption_entry.xlsx` | The Excel connection point: live `DATABRICKS.SQL` reads of the approved basis + the submit-shock entry sheet |
| Pipeline `lifecast_results_pipeline` + job `lifecast_results_run` | Phase 3: quarterly results CSV dumps → `brz_prophet_results` → `slv_projection_results` → `gld_results_by_product` + `gld_bel_movement`; then CFO export (Excel+CSV board pack), dashboard publish, Genie space |
| `LifeCast — BEL Movement` dashboard · `LifeCast — Results` Genie space | The reporting destinations: counters/trend/movement live from the governed layer; Genie answers "BEL movement vs last quarter by product line" |

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
5. **Assumption governance:** open the Excel template (or run `lifecast_assumption_entry`) —
   a +10% smoker loading becomes a draft basis, PENDING_APPROVAL. Run
   `lifecast_assumption_approval` → new basis live, old one SUPERSEDED, every step in
   `asm_approval_log`. The next overnight run records the new `assumption_set_id`.
   *No more filename-versioned workbooks and email-chain sign-off.*

**Today → tomorrow:** today, SQL extract → Excel transform → model point file, with
manual validation and no lineage. Tomorrow, a governed pipeline with a quality gate
and sign-off before a run is burned — and the downstream model untouched.
