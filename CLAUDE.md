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
- **Serverless environment policy:** every job pins `environment_version: "5"` via a job-level `environments` block + `environment_key` on each notebook task. ML tasks use `environment_key: ml` → `environments/lifecast_ml.yml` (v5 + QuantLib/openpyxl; mlflow ships in the v5 base — swap for the Databricks AI base-env ID once those are enabled, this workspace currently accepts only custom yaml paths). Interactively, select that same yaml as the notebook's base environment.
- Serverless base env is slim: any library genuinely missing from the v5 base (openpyxl, QuantLib — NOT mlflow, which v5 includes) still gets an explicit `%pip install` cell, so notebooks survive interactive sessions on unpinned environments. Verify membership empirically before adding.
- Requires Databricks CLI ≥ v1.x — older CLIs silently drop job `environments` on deploy.

## The app — hard rule

- It is a **presenter's cockpit**, not a business-process simulation.
- **Thin layer**: curated structure, deep links, short annotations, at most read-only status pulls from UC (plus explicit run-control actions — trigger/rerun of allowlisted jobs). No business logic, no simulated processing.
- **Reuse the existing Bricksurance design system and app framework** (`claims_workbench` / `reinsurance_workbench`). Do not invent a new visual language. Sentence case throughout.
- Genie / dashboards / agents are destinations the cockpit links to — never reimplemented inside it.

### The cockpit standard — every flow/beat uses the same three tabs

1. **"What we're showing"** — the business process in plain, tool-free language. No Databricks, no old/new, no product names.
2. **"Old → new"** — the same process mapped to tech: what each step is today and what it becomes. Shows what-becomes-what, code one click away on the new side.
3. **"Management"** — run control (schedule, last-run status, trigger/rerun), issues (quarantine, failures, what to do), and an agent that oversees runs.

Rules, all flows:
- Tabs 1 and 2 share **one four-step skeleton — data → transformation → control → result** — and Tab 3 monitors that same skeleton. One mental model, three depths: what it is → what changes → how you run it.
- Each tab opens with **one plain, speakable lead sentence** (jargon-free). No "Say this" label — the copy itself is the script.
- Every flow must land three messages: **it's easy · it's much better · you can transition with no issues.**
- The last block of the Tab 2 diagram is a **scope/handoff block**: "[this input] → into the engine → next: [next input]", with a **visible scope boundary** — our scope ends at the file; the engine is downstream and unchanged. The engine never moves; that's the no-risk-transition proof.
- **No money or cost framing** anywhere in these flows.
- Cockpit nav threads the flows in order: model points → assumptions → results → scenarios → projection → stochastic.

## Do NOT

- Write client product cashflow logic or actuarial formulae. We show *how to model*, not the model.
- Ship an ESG — consume the client's, or show an illustrative QuantLib one.
- Replace Excel where it's load-bearing or regulatory — connect to it (`DATABRICKS.SQL` round-trip).
- Name any competitor (Prophet, AXIS, RAFM, Moody's, Conning) anywhere in client-facing surfaces.
- Lead with "replace Prophet."

## Everything must be real

Every asset is a real Databricks object that works on a live workspace with serverless. No mocks of platform behaviour.
