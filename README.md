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
| 3 | Results + AI/BI + Genie | Not started |
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
hands-on system, not a buried bundle tree. The numbered notebooks read first to last:

```
/Workspace/Shared/lifecast/
  00_synthetic_policy_book      Phase 0 — generate the synthetic term book + bad-feed file
  01_prophet_extract_mock      Phase 0 — the before-state model point extract
  02_model_point_pipeline.py   Phase 1 — SOURCE of the pipeline (runs inside it, not as a notebook)
  03_quality_gate              Phase 1 — gate verdict, sign-off, RED stops the run
  04_export_model_point_file   Phase 1 — MPF export + Excel validation extract
  05_bad_feed_day              demo lever — inject / restore the bad feed
  06_assumption_master         Phase 2 — asm_ tables, UC functions, seed basis, Excel template
  07_excel_entry_roundtrip     Phase 2 — maker: the Excel round-trip, headless
  08_assumption_approval       Phase 2 — checker: approve / reject, audited
  .bundle/                     bundle internals (state, artifacts) — ignore
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

## The demo beat

1. `lifecast_overnight_run` → gate **GREEN**, model point file exported. Lineage
   visible in Catalog Explorer from volume to gold.
2. `lifecast_bad_feed_day` (inject) → `lifecast_overnight_run` → gate **RED**, run
   stops, quarantine shows exactly which rows failed which rules. *The morning is no
   longer hostage to a broken extract.*
3. `lifecast_bad_feed_day` with `action=restore` → next run **GREEN** again.
4. **Assumption governance:** open the Excel template (or run `lifecast_assumption_entry`) —
   a +10% smoker loading becomes a draft basis, PENDING_APPROVAL. Run
   `lifecast_assumption_approval` → new basis live, old one SUPERSEDED, every step in
   `asm_approval_log`. The next overnight run records the new `assumption_set_id`.
   *No more filename-versioned workbooks and email-chain sign-off.*

**Today → tomorrow:** today, SQL extract → Excel transform → model point file, with
manual validation and no lineage. Tomorrow, a governed pipeline with a quality gate
and sign-off before a run is burned — and the downstream model untouched.
