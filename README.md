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
| 2 | Assumption governance | Not started |
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

All workspace assets land under `/Workspace/Shared/lifecast/dev`, all data in
`<catalog>.lifecast` (single schema; medallion via `brz_`/`slv_`/`gld_` prefixes),
all files in the `lifecast_files` volume.

## What's here

| Asset | What it is |
|---|---|
| Job `lifecast_synthetic_foundation` | Phase 0: synthetic term book as a file-shaped policy-admin feed + the mock downstream model point extract (the before-state) + the parked bad-feed-day file |
| Pipeline `lifecast_model_point_pipeline` | Phase 1: Auto Loader → `brz_policy_admin` → `slv_policies` (expectations) + `slv_policies_quarantine` → `gld_model_points`. Full UC lineage |
| Job `lifecast_overnight_run` | The governed run: pipeline refresh → quality gate (RED stops the run **before** export) → model point file + Excel validation extract |
| Job `lifecast_bad_feed_day` | Demo lever: `action=inject` drops a defective feed into the landing path; `action=restore` removes it + full-refreshes |
| `gld_run_quality` / `gld_run_signoff` / view `gld_quality_dashboard` | Gate history and sign-off — the auditable destination |

## The demo beat

1. `lifecast_overnight_run` → gate **GREEN**, model point file exported. Lineage
   visible in Catalog Explorer from volume to gold.
2. `lifecast_bad_feed_day` (inject) → `lifecast_overnight_run` → gate **RED**, run
   stops, quarantine shows exactly which rows failed which rules. *The morning is no
   longer hostage to a broken extract.*
3. `lifecast_bad_feed_day` with `action=restore` → next run **GREEN** again.

**Today → tomorrow:** today, SQL extract → Excel transform → model point file, with
manual validation and no lineage. Tomorrow, a governed pipeline with a quality gate
and sign-off before a run is burned — and the downstream model untouched.
