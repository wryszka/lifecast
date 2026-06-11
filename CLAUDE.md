# CLAUDE.md — Bricksurance LifeCast

LifeCast is a **synthetic demo** showing how to move actuarial liability modelling off Prophet onto Databricks, for the **Bricksurance Life** entity. It is publicly publishable, not client-specific.

**Full spec:** `LIFECAST_BUILD_BRIEF.md`. Read it before building. **Build phase by phase and stop for review** — do not attempt multiple phases at once.

---

## Naming — hard rule

One token, `lifecast`, on every named object. This is how LifeCast stays distinguishable from the other Bricksurance demos in a shared workspace. No exceptions except the one noted.

- UC catalog: **existing**, via the `catalog` bundle variable (never create a catalog).
- UC schema: always `lifecast` (single schema; medallion layers via table prefix, not extra schemas).
- Tables: `brz_` / `slv_` / `gld_`; assumptions `asm_`; scenarios `esg_`. Fully qualified `${catalog}.lifecast.<table>`.
- Volume: `${catalog}.lifecast.lifecast_files`.
- Jobs, pipelines, agents: `lifecast_` prefix.
- Registered models: `${catalog}.lifecast.lifecast_<name>`.
- MLflow experiments + all workspace assets: under `/Workspace/Shared/lifecast/`.
- App: `lifecast-workbench` (the one hyphen exception — apps need URL-safe names).
- Genie spaces & AI/BI dashboards: `LifeCast — <topic>`.
- Secret scope: `lifecast`. Compute tag: `project=lifecast`.
- **Underscores only** in UC identifiers.

## Portability — hard rule

- **One edit to move workspaces: the `catalog` variable.** Default it to the dev catalog; override per target.
- Pin `workspace.root_path` under `/Workspace/Shared/lifecast/` so all assets are discoverable by any SA (not per-user paths).
- Schema fixed (`lifecast`), only catalog varies.
- No hardcoded workspace URLs or absolute IDs. Everything derives from the bundle target + `catalog`.
- Notebook `catalog` widgets default to the dev catalog so interactive runs work out of the box (jobs always pass `${var.catalog}`). When porting, update the widget default across notebooks in one sed pass.
- Serverless throughout. Reinstall: `databricks bundle deploy -t <target>`.
- Serverless base env is slim: any non-base library a notebook needs (openpyxl, QuantLib, mlflow) gets an explicit `%pip install` cell — never rely on the ambient environment version.

## The app — hard rule

- It is a **presenter's cockpit**, not a business-process simulation. Persona → task → card (proves / where it lives / build & control / deep links / today→tomorrow).
- **Thin layer**: curated structure, deep links, short annotations, at most read-only status pulls from UC. No business logic, no simulated processing.
- **Reuse the existing Bricksurance design system and app framework** (`claims_workbench` / `reinsurance_workbench`). Do not invent a new visual language.
- Genie / dashboards / agents are destinations the cockpit links to — never reimplemented inside it.

## Do NOT

- Write client product cashflow logic or actuarial formulae. We show *how to model*, not the model.
- Ship an ESG — consume the client's, or show an illustrative QuantLib one.
- Replace Excel where it's load-bearing or regulatory — connect to it (`DATABRICKS.SQL` round-trip).
- Name any competitor (Prophet, AXIS, RAFM, Moody's, Conning) anywhere in client-facing surfaces.
- Lead with "replace Prophet."

## Everything must be real

Every asset is a real Databricks object that works on a live workspace with serverless. No mocks of platform behaviour.
