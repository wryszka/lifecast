# Bricksurance LifeCast — Build Brief & Go-to-Market Plan

| | |
|---|---|
| **Repo** | `wryszka/lifecast` |
| **Entity** | Bricksurance Life — synthetic life / savings / protection insurer, sister to Bricksurance SE & Re |
| **Name token** | `lifecast` — used as the single prefix across every asset (see §10) |
| **App** | `lifecast-workbench` — the LifeCast Cockpit (see §9) |
| **Status** | Phases 0–2 built & verified on dev. Phase 3 next. |
| **Last updated** | 11 June 2026 |

> Supersedes `ACTUARIAL_MODELLING_WORKBENCH_BUILD_BRIEF.md`.

---

## 1. In one line

A ready-to-run synthetic POC that shows what it looks like to move actuarial liability modelling off Prophet onto Databricks — and the repeatable pattern to get there. Modular by design: start with one small process, implemented in Databricks, and build up only as the client asks the next question.

---

## 2. Who this is for

Written from two seats. Every phase is described from both, because if neither of them can see what a piece is *for*, it does not belong here.

**The actuary.** Owns the methodology and the numbers. Cares whether results tie out to Prophet; whether assumptions can be entered, reviewed and versioned; whether results can be interrogated without rebuilding a pivot table; whether it's reproducible for IFRS 17 and Solvency II sign-off. Does **not** want to be told how to model.

**The actuarial process / systems manager.** Owns the run. Cares whether the overnight batch completes reliably; whether the data is clean before a run is burned; who changed what and which extract fed which run; orchestration, scheduling, SLAs, failure handling; cost and run time; and getting off one-person dependencies.

---

## 3. Positioning

**Client-facing — the story is *integration*.** We sit around the existing Prophet estate: fix the data layer, govern the assumptions, add AI on top. We never name a competitor. The demo contains no reference to AXIS, RAFM, Moody's, Conning, or any other named suite.

**Internal — the actual motion.** Integration is the land; migration is the expand; the workbench is the Trojan horse. Once we are the data, governance, lineage and AI layer underneath Prophet, the conversation *inside the client's own team* shifts from "should we move to Databricks" to "why are we still paying for Prophet." Migration self-selects.

**Internal targeting map** (never surfaced to the client):

| Workbench layer | Client-facing framing | What it actually hits |
|---|---|---|
| Model point pipeline | "connect your policy admin system" | Prophet / AXIS / Moses input dependency |
| Assumption governance | "import your assumption workbooks" | Every suite's Excel assumption module |
| ESG / scenario management | "consume your scenario provider" | Moody's (B&H), Conning GEMS |
| Projection run tracking | "orchestrate your model runs" | Prophet, AXIS, RiskAgility FM |
| Capital feed (later) | "publish to your capital platform" | Igloo, ResQ, Remetrica |
| Results & reporting | "aggregate across your estate" | Every suite's CSV-dump problem |

---

## 4. The two tracks — the commercial motion

**Track 1 — Integration.** Data layer, governance, lineage and AI around the existing Prophet runs. Universal, low-risk, and it makes their Prophet runs *better* — protecting the investment, not threatening it. C-suite hook: audit readiness — IFRS 17 and Solvency II both demand lineage and reproducibility Prophet alone can't provide. **This is the land.**

**Track 2 — Migration.** Take models into Databricks: cheaper, faster, no scaling limits. Self-selecting, actuary-driven, workshop-led. The POC is deliberately simple — one product, deterministic, well-understood. The point is the scaffold, not actuarial complexity. **This is the expand.**

---

## 5. The two experiences — how the workbench presents

**Developer experience.** Notebook-first development; Genie-assisted scaffolding from schema or sample data; Git / PR promotion across dev → staging → prod; MLflow tracking of runs and data-quality metrics.

**Production orchestration.** Lakeflow Designer for the visual pipeline; Workflows with SLA monitoring, alerting and retry; the LifeCast Cockpit as the SA-facing surface; Unity Catalog lineage end to end.

---

## 6. The migration frame

Every phase carries a plain-language **"today → tomorrow"** annotation, in the actuary's and process manager's own words. The effect is a self-service migration roadmap: the prospect maps their own pain to the solution. Annotations are embedded per phase in §8.

---

## 7. What we are explicitly NOT doing

State this early and often — it is what lets the actuary relax and keeps the partner relationship clean.

- We do **not** write the client's product cashflow logic or actuarial formulae. They do, or a partner does.
- We do **not** ship an ESG. We consume theirs, or show an illustrative one (QuantLib).
- We do **not** replace Excel where it is load-bearing or regulatory. We connect to it.
- We do **not** touch the UI debate — it is all Databricks: Apps, AI/BI, Lakeflow Designer.
- **The app is a cockpit for the presenter, not a simulation of a business process.** (See §9.)
- We do **not** name a competitor, anywhere.
- We do **not** lead with "replace Prophet." Ever.

Partners (Milliman, Moody's, boutique quant firms) slot in at the projection-logic layer.

---

## 8. Build phases

| Phase | Name | Track | Ships in core POC? | Status |
|---|---|---|---|---|
| 0 | Synthetic foundation | — | Yes | ✅ Built |
| 1 | Model point pipeline | 1 — land | Yes | ✅ Built |
| 2 | Assumption governance | 1 — land | Yes | ✅ Built |
| 3 | Results + AI/BI + Genie | 1 — land | Yes | Not started |
| 4 | ESG / scenario management | bridge | Demand-driven | Not started |
| 5 | Projection migration POC | 2 — expand | Demand-driven | Not started |
| 6 | Stochastic + boundaries | 2 — expand | Discuss, don't sell | Not started |

### Phase 0 — Synthetic foundation
**What it is.** Bricksurance Life as a synthetic entity, a synthetic policy book, one product line in scope (term or credit life). Plus one mock "Prophet" model point extract to migrate *from* — the before-state anchor.
**Actuary's view.** "This looks like my book and my product. The starting point is the extract I recognise."
**Process manager's view.** "Synthetic, but it behaves like the real overnight feed — what's proven here, I can trust against my estate."

### Phase 1 — Model point pipeline *(the POC, the land)*
**What it is.** Rebuild the policy-data → model-point-file pipeline as a governed Lakeflow/DLT pipeline: UC governance, lineage, a data-quality gate. The quality gate and sign-off are a real but lightweight destination (a notebook + job + UC view) that the **Cockpit links to** — they are not built *inside* the app. Prophet runs downstream **unchanged**.
**Actuary's view.** "I can see the quality checks and sign off before anything runs. My morning isn't hostage to a broken extract."
**Process manager's view.** "Governed pipeline, quality gate before we burn a run, full lineage from extract to model point file. The audit story I don't have today."
**Today → tomorrow.** *Today:* SQL extract → Excel transform → Prophet model point file; overnight batch, manual validation, no lineage. *Tomorrow:* governed pipeline, quality gate, sign-off, full lineage — Prophet unchanged.
**Excel.** Read-only validation export for actuaries who want to eyeball the extract.

### Phase 2 — Assumption governance
**What it is.** Versioned Delta tables in UC for mortality / lapse / expense, with an approval workflow. Actuary still enters in Excel; Databricks is master, with audit trail. Reuses the `DATABRICKS.SQL` round-trip from the actuarial Excel accelerator / SCR demo.
**Actuary's view.** "I still enter shocks and loadings in Excel where I peer-review them — now there's version history and an approval step, not a filename and an email chain."
**Process manager's view.** "Every assumption set versioned and signed off; I can tie which set fed which run. Reproducibility for SII and IFRS 17."
**Today → tomorrow.** *Today:* standalone Excel workbooks, version-controlled by filename. *Tomorrow:* versioned Delta tables in UC with approval workflow; Excel entry preserved, Databricks as master.
**Excel.** Load-bearing — keep. First Excel connection point: Excel template → `DATABRICKS.SQL` → UC Function → Delta master.

### Phase 3 — Results + AI/BI + Genie
**What it is.** Prophet outputs land in Delta. AI/BI dashboards and Genie replace the downstream Excel reporting stack. End of phase = Track 1 complete, **zero actuarial maths written**.
**Actuary's view.** "I ask 'show me BEL movement vs last quarter by product line' and get an answer — instead of rebuilding a pivot table."
**Process manager's view.** "One governed results layer the whole team queries. No more reconciling five versions of the board pack."
**Today → tomorrow.** *Today:* Prophet dumps CSVs; the board pack is rebuilt in Excel each quarter. *Tomorrow:* outputs in Delta, AI/BI + Genie answer instantly; CFO export always offered.
**Excel.** CFO export always available. QRT / XBRL templates stay in Excel — connect, don't replace.

> **— End of first shippable POC. Phases 0–3 are what we demo and what the client can run. Everything below is demand-driven and self-selecting. —**

### Phase 4 — ESG / scenario management *(bridge)*
**What it is.** Two patterns. *(a) Consume:* land an external ESG scenario file into Delta, version in UC, feed a run — zero friction for licensed firms. *(b) Illustrate:* Hull-White 1-factor + Black-Scholes/Heston in QuantLib, calibrated live to the EIOPA RFR curve, versioned in UC, calibration params tracked in MLflow.
**Actuary's view.** "My production scenarios are governed for the first time. And I can generate a quick market-consistent set for testing — without it pretending to be my licensed ESG."
**Process manager's view.** "Scenario sets versioned alongside everything else; I can trace set → calibration → run."
**Today → tomorrow.** *Today:* scenario files on a network share, no version control. *Tomorrow:* versioned in UC, calibration tracked in MLflow — or generated illustratively in QuantLib.
**Reuse.** EIOPA RFR ingestion from the actuarial Excel accelerator.

### Phase 5 — Projection migration POC *(the expand)*
**What it is.** One deterministic product, projected in Python in a notebook, tracked in MLflow alongside the existing Prophet run, validated side by side on the same model points. Delivered as a **workshop**: we bring the scaffold; the client writes the product logic.
**Actuary's view.** "The numbers tie out — and the 4-hour run takes minutes. And I wrote the product logic, so I own it and trust it."
**Process manager's view.** "Same governance and lineage as Track 1 — but it's *our* model, on *our* platform, at a fraction of the run time and cost."
**Today → tomorrow.** *Today:* a 4-hour Prophet run for a well-understood deterministic product. *Tomorrow:* the same product in Python in minutes, tracked in MLflow beside Prophet, validated side by side.

### Phase 6 — Stochastic + boundaries *(discuss, don't sell)*
**What it is.** Show that stochastic runs are embarrassingly parallel (`mapInPandas` fan-out — where Prophet struggles at volume). Plus honest technical explainers, *not* demos:
- **Vectorisation breakdown** — simple projection vectorises beautifully; add a path-dependent guarantee (e.g. a GMAB ratchet) and it falls apart; then Numba/JAX on the hot loop. Solvable, not free.
- **Nested stochastic** — inner/outer structure, why it's O(n²) in scenarios, rough cluster cost. Honest on sizing and where a partner's engine fits.
- **ESG plug-in** — reinforces §Phase 4: we are runtime and governance; the ESG is the client's choice.
**Today → tomorrow.** *Today:* stochastic and nested runs queued overnight, compute-bound. *Tomorrow:* parallel scenario fan-out across a cluster, with an honest map of the hard edges.
**Partners.** Slot in at the projection-logic layer.

---

## 9. The App — LifeCast Cockpit

**Purpose: a presenter's cockpit, not a business-process simulation.** The Databricks SA in the room picks the persona they're presenting to and the question that just came up, and the app routes them straight to the right place in Databricks, tells them what it proves, and — critically — shows *how the thing is actually built and controlled* beneath the demo. It is the demo runbook made live, indexed by "what am I showing, to whom." It is also the artifact that lets **any SA run this demo, not just the author**.

**Thin layer.** Curated structure, deep links, short annotations, and at most a couple of read-only status pulls from UC (last run, current version). **No business logic, no simulated processing.**

**Graphical language.** Reuse the existing **Bricksurance design system and app framework** from `claims_workbench` / `reinsurance_workbench` — same component library, tokens, layout shell. Do **not** invent a new visual language. (When building in Claude Code, point it at the existing workbench app as the reference.)

**Structure — persona → task → demo card.**
Landing = the personas you present to: **Actuary · Process Manager · Developer/Quant · Exec**. Pick one → the list of questions for that seat. Each resolves to a card:

- **Proves** — one line, what this beat demonstrates.
- **Where it lives** — the actual assets by name (`${catalog}.lifecast.slv_model_points`, job `lifecast_overnight_run`, `LifeCast — BEL Movement` dashboard…), all discoverable under `/Workspace/Shared/lifecast/`.
- **Build & control** — the architecture beneath the demo. This is the part that answers "how do I actually build and control this."
- **Go** — deep links to the notebook / job run / Genie space / dashboard / MLflow experiment / UC object.
- **Today → tomorrow** — the Prophet-migration line to say out loud.

**Worked card (Developer/Quant seat):**

> **"You've shown me the model running — how do I actually build and control it?"**
> **Proves:** it's not a black box — it's your Python, versioned and orchestrated.
> **Where it lives:** notebook `lifecast_term_projection` · experiment `/Shared/lifecast/projection` · model `${catalog}.lifecast.lifecast_term_projection` · job `lifecast_overnight_run`.
> **Build & control:** logic lives in the notebook (you own the formulae) → every run logged to MLflow with params, scenario set and results, compared vs Prophet → registered as a versioned model in UC with lineage → orchestrated by the Workflow with schedule, retry and SLA → promoted dev→prod via DAB/Git. *That chain is the control plane.*
> **Go:** `[Open notebook]` `[Open MLflow]` `[Open model in UC]` `[Open job]`
> **Today → tomorrow:** today it's a 4-hour run you can't see inside; tomorrow it's your code, tracked, governed, in minutes.

Cards are authored per phase as each beat is built. Genie spaces, dashboards and agents are destinations the Cockpit links to — never reimplemented inside it.

---

## 10. Naming & asset convention

**One token — `lifecast` — on every named object, across every surface.** This is what keeps LifeCast distinguishable from the other Bricksurance demos when presenting at the asset level. It is a hard rule.

| Surface | Convention | Example |
|---|---|---|
| GitHub repo | `wryszka/lifecast` | — |
| DAB bundle | `lifecast` | `bundle: name: lifecast` |
| UC catalog | **existing catalog**, via one config variable | `${var.catalog}` (default = dev catalog) |
| UC schema | one schema, the token | `lifecast` |
| Tables — bronze/silver/gold | `brz_` / `slv_` / `gld_` | `${catalog}.lifecast.slv_model_points` |
| Assumption tables | `asm_` | `asm_mortality`, `asm_lapse`, `asm_expense` |
| Scenario tables | `esg_` | `esg_hull_white_paths` |
| Volume | the token | `${catalog}.lifecast.lifecast_files` |
| Lakeflow / DLT pipeline | `lifecast_` | `lifecast_model_point_pipeline` |
| Workflows / Jobs | `lifecast_` | `lifecast_overnight_run` |
| Registered model (UC) | in-schema, clear name | `${catalog}.lifecast.lifecast_term_projection` |
| MLflow experiment | under Shared | `/Shared/lifecast/projection` |
| Workspace assets (notebooks, app, code) | under Shared | `/Workspace/Shared/lifecast/…` |
| Databricks App | `lifecast-workbench` | thin cockpit; one hyphen exception (apps require URL-safe names) |
| Genie space | `LifeCast — <topic>` | `LifeCast — Results` |
| AI/BI dashboard | `LifeCast — <topic>` | `LifeCast — BEL Movement` |
| Agent (Agent Bricks) | `lifecast_` | `lifecast_assumption_assistant` |
| Secret scope | `lifecast` | — |
| Compute tags | `project=lifecast` | — |

Rules:
- **Single schema.** Medallion layers are separated by table prefix inside the one `lifecast` schema, not by extra schemas.
- **Existing catalog.** We do not create a catalog. The catalog is a single config variable (§11), defaulted to the dev workspace catalog.
- **Underscores only in UC.** The App name (`lifecast-workbench`) is the one deliberate hyphen exception.
- **Everything is real.** Every row is a real Databricks object type.

---

## 11. Portability & install

Designed to move and reinstall in any workspace with **one edit**.

- **One config point — the catalog.** A single bundle variable holds the target catalog, defaulted to the dev workspace catalog and overridable per target:

  ```yaml
  bundle:
    name: lifecast

  variables:
    catalog:
      description: "Target UC catalog (existing). Set once per workspace."

  targets:
    dev:
      # No `mode: development` — it prefixes every resource name (including the
      # UC schema) with dev_<user>_, breaking the naming hard rule. One version,
      # exact names, everywhere.
      default: true
      workspace:
        root_path: /Workspace/Shared/lifecast/${bundle.target}
      variables:
        catalog: <YOUR_DEV_CATALOG>   # <-- the only required edit
    # To move to another workspace: add a target and override `catalog`.
  ```

- **Shared-folder discoverability.** `workspace.root_path` is pinned under `/Workspace/Shared/lifecast/` (not a per-user path), so all notebooks, the app and experiments land in one place any SA can find. MLflow experiments under `/Shared/lifecast/`.
- **Schema fixed, catalog variable.** Schema is always `lifecast`; only the catalog changes between workspaces.
- **No hardcoded references.** No workspace URLs, no absolute IDs. Everything derives from the bundle target and the `catalog` variable.
- **Reinstall.** `databricks bundle deploy -t <target>`. Serverless throughout.

---

## 12. Go-to-market assets *(living — placeholders to expand on the way)*

The synthetic POC (Phases 0–3) is the artifact. These wrap around it.

### 12.1 Synthetic POC — *the artifact* ✅ scoped
Phases 0–3. What the client runs to see what they'll get.

### 12.2 One-day workshop — `[PLACEHOLDER — TBD]`
Primarily for Track 2 (Phase 5). We bring the scaffold; the client writes the product logic.
- Agenda · pre-reqs / environment setup · hands-on exercises · partner involvement model — *to be written*

### 12.3 POC doc & run instructions — `[PLACEHOLDER — TBD]`
Ships with the synthetic POC.
- Deployment (the one-edit install) · what to swap for client data · validation-against-Prophet checklist · 4–6 week success criteria — *to be written*

### 12.4 Discovery questions — *starter set; expand per engagement*
Run before scoping. Tag every answer: **Mandatory** (in the POC) / **Good-to-have** (Phase 2+) / **Unimportant** (don't build).

**Actuary:** which product lines / model points are in scope, which is simplest to start? · what does the current extract look like (source, format, frequency)? · where do assumptions live, who signs them off? · what results, in what form, for whom? · what must tie out to Prophet *exactly* vs directional? · what's eyeballed in Excel before a run? · what's regulatory-mandated to stay in a format (QRT, XBRL)?

**Process / systems manager:** current run schedule and run time? · what breaks most often, and what happens to the actuary's day? · lineage / audit story today for IFRS 17 / SII? · access governance? · how are model and assumption versions tracked against runs? · compute footprint / cost of current runs? · how many people can run it end to end — where's the handover pain?

---

## 13. Sequencing — what ships first

**Phases 0–3 are the shippable core** — the ready synthetic POC, the full Track 1 integration story, zero actuarial maths. This is what we demo and what proves the land.

**Phases 4–6 are demand-driven** — mostly workshop- and instruction-led; they self-select as the actuaries get comfortable.

Two tracks, one platform, one entry point. Track 1 sells itself. Track 2 closes itself.
