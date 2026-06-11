"""LifeCast Cockpit content — persona -> question -> card.

The cockpit is the demo runbook made live, indexed by "what am I showing, to
whom". Cards carry five fixed fields (brief §9): proves / where it lives /
build & control / go links / today -> tomorrow. Links use semantic keys that
app.py resolves into URLs (path-based where possible, ID-resolved best-effort).

No business logic lives here — curated structure and short annotations only.
"""

# ── Landing tiles: one per use case, simplest first. Tile 01 opens the first
# story-flow page; the rest link to their live assets until their story pages
# are written. ───────────────────────────────────────────────────────────────
TILES = [
 {"n": "01", "title": "Model point generator",
  "text": "Policy data → governed model point file. The existing actuarial engine runs downstream, unchanged.",
  "flow": "model-point-feed"},
 {"n": "02", "title": "Assumption governance",
  "text": "Mortality / lapse / expense as a versioned basis — Excel entry kept, maker/checker, audit trail.",
  "link": "folder:02_assumption_governance"},
 {"n": "03", "title": "Results & Genie",
  "text": "Engine output lands in Delta once; dashboard + Genie replace the pivot-table rebuild.",
  "link": "folder:03_results_and_genie"},
 {"n": "04", "title": "Scenario management",
  "text": "Your ESG's deliveries versioned and gated — plus an illustrative QuantLib set.",
  "link": "folder:04_scenario_management"},
 {"n": "05", "title": "Projection migration",
  "text": "The workshop: same product in Python, tied out side by side, in seconds.",
  "link": "folder:05_projection_migration"},
 {"n": "06", "title": "Stochastic & boundaries",
  "text": "1,000-path fan-out — and an honest map of where the hard edges are.",
  "link": "folder:06_stochastic_boundaries"},
]

# ── Flows: the story-first presentation. Each step pairs the current state
# ("how we think this runs today" — a deliberate discovery hook) with the same
# chunk here, code one click away. Copy never names a competitor (hard rule) —
# "the existing actuarial engine" carries the contrast. ──────────────────────
FLOWS = [
{
 "id": "model-point-feed",
 "eyebrow": "Use case 01 — model point generator",
 "title": "Policy data → model point file, governed",
 "story": ("Every liability run starts the same way: policy admin data has to become the "
           "model point file the existing actuarial engine reads. The engine itself is fine — "
           "it's everything in front of it that's fragile. Below, the journey as we typically "
           "see it run today, mapped step for step onto the same journey here: four small "
           "chunks, each a short notebook you can open and read. The engine doesn't change at all."),
 "now_intro": "How we think this runs today — tell us where your shop differs:",
 "steps": [
  {"n": "1", "title": "The feed lands",
   "now": "A scheduled SQL job pulls policies from the admin system; the extract lands wherever it lands, named by convention.",
   "text": "The nightly policy CSV drops on a governed volume and is ingested as-landed — bronze keeps the untouched record of what arrived.",
   "code": ("Code — pipeline source", "nb_file:01_model_point_pipeline/00_model_point_pipeline.py"),
   "live": ("The landing zone", "vol:")},
  {"n": "2", "title": "Clean & quarantine",
   "now": "An Excel workbook reshapes the extract into model points — formulas, paste areas, and one careful owner who knows its quirks.",
   "text": "Typed, deduplicated, seven quality rules. Every reject lands in quarantine with the exact rules it failed — visible, never silent.",
   "code": ("Code — same file, ~40 lines", "nb_file:01_model_point_pipeline/00_model_point_pipeline.py"),
   "live": ("Pipeline graph, live", "pipeline:lifecast_model_point_pipeline")},
  {"n": "3", "title": "The gate signs off",
   "now": "Validation is an eyeball check if there's time; a bad extract is usually discovered after the engine has already run.",
   "text": "GREEN goes on the record with the assumption basis in force. RED stops the run before the model point file is touched.",
   "code": ("Code — gate notebook", "nb:01_model_point_pipeline/01_quality_gate"),
   "live": ("Gate history", "tbl:gld_quality_dashboard")},
  {"n": "4", "title": "The file the engine expects",
   "now": "The file is dropped on a share; the existing actuarial engine picks it up in the overnight batch. No lineage from policy to model point.",
   "text": "Model points exported in the exact layout the engine reads today — downstream unchanged. Plus a read-only Excel extract for the eyeball check.",
   "code": ("Code — export notebook", "nb:01_model_point_pipeline/02_export_model_point_file"),
   "live": ("The exported file", "vol:export")},
 ],
 "lever": {
   "text": "Break it in front of them: inject a deliberately bad feed, run the overnight job, "
           "watch the gate go RED and stop the run — then restore and run it GREEN.",
   "links": [("Bad feed lever", "job:lifecast_bad_feed_day"),
             ("Overnight run", "job:lifecast_overnight_run")],
 },
},
]

# ── Governance: what gets recorded for the governed process, and why. Today
# this covers use case 01 only; assumptions / scenarios / projections join the
# tab as their story pages are added. ────────────────────────────────────────
GOVERNANCE_SCOPE = ("Governing the model point generator (use case 01) today. Assumptions, "
                    "scenarios and projection runs already keep the same kind of record — "
                    "they join this tab as their story pages are added.")

GOVERNANCE_INVENTORY = [
 {"what": "Every row, exactly as it arrived",
  "where": ("brz_policy_admin", "tbl:brz_policy_admin"),
  "why": "The untouched record: source file and ingest time on every row. Whatever happens downstream, what arrived is never in dispute."},
 {"what": "Every reject, with the rules it failed",
  "where": ("slv_policies_quarantine", "tbl:slv_policies_quarantine"),
  "why": "Quality failures are quarantined, not silently dropped — each row carries the exact rules it broke."},
 {"what": "Every run: verdict, volumes, and the basis in force",
  "where": ("gld_run_quality", "tbl:gld_run_quality"),
  "why": "GREEN or RED with row counts, quarantine rate, per-rule breakdown — and which approved assumption basis was live. Which extract and which basis fed which run, recorded, not remembered."},
 {"what": "The sign-off",
  "where": ("gld_run_signoff", "tbl:gld_run_signoff"),
  "why": "Who signed the gate, when. Automated today; the human approval workflow is the same pattern assumption governance already uses."},
 {"what": "Lineage, end to end",
  "where": ("gld_model_points (open the Lineage tab)", "tbl:gld_model_points"),
  "why": "Volume → bronze → silver → gold, captured automatically by Unity Catalog. Nobody maintains this; it cannot drift from reality."},
]

PERSONAS = [
    {"id": "actuary", "title": "Actuary",
     "blurb": "Owns the methodology and the numbers. Wants tie-outs, governed assumptions, "
              "interrogable results — and nobody telling them how to model."},
    {"id": "process", "title": "Process Manager",
     "blurb": "Owns the run. Wants reliable overnights, clean data before a run is burned, "
              "who-changed-what, and an end to one-person dependencies."},
    {"id": "developer", "title": "Developer / Quant",
     "blurb": "Builds the thing. Wants to see the code, the control plane, and exactly "
              "where the hard edges are."},
    {"id": "exec", "title": "Exec",
     "blurb": "Owns the budget and the audit exposure. Wants the IFRS 17 / Solvency II "
              "story, the cost line, and the path from POC to production."},
]

CARDS = {
# ───────────────────────────── ACTUARY ─────────────────────────────
"actuary": [
{
 "id": "trust-the-feed",
 "question": "Can I trust the extract before a run is burned?",
 "proves": "A quality gate stands between the policy feed and the model point file — a bad extract stops the run before it costs you a morning.",
 "where": [("Pipeline", "pipeline:lifecast_model_point_pipeline"),
           ("Gate history", "tbl:gld_quality_dashboard"),
           ("Quarantine (every reject, with reasons)", "tbl:slv_policies_quarantine"),
           ("Overnight run", "job:lifecast_overnight_run")],
 "build": "Auto Loader lands the feed → expectations on the silver layer enforce seven rules row-by-row → rejects go to a quarantine table, never silently dropped → the gate task turns RED above threshold and fails the run before export. Demo lever: lifecast_bad_feed_day injects a defective feed; restore puts it back.",
 "links": [("Open pipeline", "pipeline:lifecast_model_point_pipeline"),
           ("Gate notebook", "nb:01_model_point_pipeline/01_quality_gate"),
           ("Bad feed lever", "job:lifecast_bad_feed_day"),
           ("Use case folder", "folder:01_model_point_pipeline")],
 "today": "SQL extract → Excel transform → model point file; manual validation; a broken feed is discovered when the numbers look wrong.",
 "tomorrow": "Governed pipeline, quality gate, sign-off on record — and the downstream model untouched.",
},
{
 "id": "assumptions-governed",
 "question": "Where do my assumptions live, and who signed them off?",
 "proves": "Mortality / lapse / expense are versioned tables with a maker-checker workflow — you still enter in Excel; Databricks is master.",
 "where": [("Governance dashboard", "tbl:asm_governance_dashboard"),
           ("Audit trail", "tbl:asm_approval_log"),
           ("Excel entry template", "vol:excel"),
           ("Maker / checker jobs", "job:lifecast_assumption_entry")],
 "build": "Excel template submits via DATABRICKS.SQL → draft basis lands PENDING_APPROVAL → a separate approval action makes it live and supersedes the old one → every step appends to an audit log. The UC functions asm_*_active() are the single read path — pipeline, Genie and Excel all resolve the same approved basis.",
 "links": [("Governance dashboard", "tbl:asm_governance_dashboard"),
           ("Approval job", "job:lifecast_assumption_approval"),
           ("Excel template (volume)", "vol:excel"),
           ("Use case folder", "folder:02_assumption_governance")],
 "today": "Standalone workbooks, version-controlled by filename, signed off by email chain.",
 "tomorrow": "Versioned basis with an approval step and full history — Excel entry preserved.",
},
{
 "id": "interrogate-results",
 "question": "Can I interrogate results without rebuilding a pivot table?",
 "proves": "Ask Genie 'which product line drove the BEL increase last quarter?' and get the answer — straight off the governed results layer.",
 "where": [("Genie space", "genie"),
           ("BEL Movement dashboard", "dashboard"),
           ("Results layer", "tbl:gld_bel_movement"),
           ("CFO export (always offered)", "vol:board_pack")],
 "build": "The liability model's quarterly CSV dumps land in Delta once (results pipeline) → AI/BI dashboard and Genie query the same governed layer → the CFO export regenerates as Excel+CSV on every run. QRT/XBRL templates stay in Excel — connect, don't replace.",
 "links": [("Ask Genie", "genie"), ("Open dashboard", "dashboard"),
           ("Results run", "job:lifecast_results_run"),
           ("Use case folder", "folder:03_results_and_genie")],
 "today": "CSV dumps; the board pack is rebuilt in Excel every quarter; five versions of the truth.",
 "tomorrow": "One governed layer; Genie answers in seconds; the export is one click and always current.",
},
{
 "id": "numbers-tie-out",
 "question": "Do the migrated numbers actually tie out?",
 "proves": "The Python projection matches the legacy engine per model point, to the penny — 1,623 of 1,623 — on the same governed basis and curve. And it runs in a fifth of a second.",
 "where": [("Validation record", "tbl:gld_projection_validation"),
           ("Python results", "tbl:gld_term_projection"),
           ("MLflow side-by-side", "exp:projection"),
           ("Projection run", "job:lifecast_projection_run")],
 "build": "Both engines read the same inputs — model points from the pipeline, the approved basis, the EIOPA curve. The validation task joins them per model point with a £0.01 tolerance and fails the run loudly on drift. The tie-out is a gate, not a slide.",
 "links": [("Validation table", "tbl:gld_projection_validation"),
           ("Workshop notebook", "nb:05_projection_migration/01_term_projection"),
           ("MLflow experiment", "exp:projection"),
           ("Use case folder", "folder:05_projection_migration")],
 "today": "Parallel runs during migration mean weeks of manual reconciliation in spreadsheets.",
 "tomorrow": "Side-by-side on every run, on the record, with drift failing the job — trust earned mechanically.",
},
{
 "id": "my-scenarios",
 "question": "What happens to my ESG and my scenarios?",
 "proves": "You keep your ESG and your licence. Every scenario set gets a version, a validation gate, an audit trail and one feed point — whoever generated it.",
 "where": [("Scenario registry", "tbl:esg_governance_dashboard"),
           ("Ingest (consume pattern)", "job:lifecast_scenario_ingest"),
           ("Illustrative generator (QuantLib)", "job:lifecast_esg_illustrative"),
           ("ESG plug-in explainer", "nb:06_stochastic_boundaries/03_esg_plugin")],
 "build": "A vendor delivery lands on the volume → validated (a broken delivery is never activated) → versioned ACTIVE in the registry. The illustrative QuantLib set is calibrated to the EIOPA curve, tracked in MLflow, and registered AVAILABLE — it never pretends to be your licensed set.",
 "links": [("Scenario registry", "tbl:esg_governance_dashboard"),
           ("Calibration runs (MLflow)", "exp:esg"),
           ("Use case folder", "folder:04_scenario_management")],
 "today": "Scenario files on a network share; nobody can say which set fed which run.",
 "tomorrow": "Versioned in UC next to assumptions and runs; calibration on the record.",
},
],
# ───────────────────────── PROCESS MANAGER ─────────────────────────
"process": [
{
 "id": "overnight-reliable",
 "question": "Does the overnight run complete reliably — and what happens when it doesn't?",
 "proves": "The run is an orchestrated workflow with a gate that fails loudly and early — a bad feed stops the run before the model point file is touched.",
 "where": [("Overnight run (history of GREEN/RED)", "job:lifecast_overnight_run"),
           ("Gate verdicts per run", "tbl:gld_quality_dashboard"),
           ("Bad feed demo lever", "job:lifecast_bad_feed_day")],
 "build": "Workflow: pipeline refresh → quality gate → export, serverless, with retries and alerts available per task. RED at the gate skips the export task — the failure is visible in the run history with the exact rule counts, not discovered downstream.",
 "links": [("Run history", "job:lifecast_overnight_run"),
           ("Gate notebook", "nb:01_model_point_pipeline/01_quality_gate"),
           ("Use case folder", "folder:01_model_point_pipeline")],
 "today": "Overnight batch on a box; failure discovered at 9am by the actuary whose morning it just ate.",
 "tomorrow": "Orchestrated, gated, alerting — and the failure mode is 'stopped safely', not 'produced wrong numbers'.",
},
{
 "id": "which-fed-which",
 "question": "Which extract and which basis fed which run?",
 "proves": "Every run record carries the assumption basis in force; every basis carries who approved it; lineage runs from the landing file to the export. Reproducibility is recorded, not remembered.",
 "where": [("Run records (with basis stamp)", "tbl:gld_run_quality"),
           ("Sign-off record", "tbl:gld_run_signoff"),
           ("Basis registry + audit", "tbl:asm_governance_dashboard"),
           ("Lineage (Catalog Explorer)", "tbl:gld_model_points")],
 "build": "The gate stamps asm_active_set_id() onto each run row. UC lineage links volume → bronze → silver → gold automatically. The audit trail is queryable — the IFRS 17 / SII evidence pack is a SELECT, not an archaeology project.",
 "links": [("Run quality table", "tbl:gld_run_quality"),
           ("Open lineage on gold", "tbl:gld_model_points"),
           ("Audit log", "tbl:asm_approval_log")],
 "today": "Filename conventions and the memory of the one person who ran it.",
 "tomorrow": "Which extract, which basis, which sign-off — on every run record, queryable.",
},
{
 "id": "orchestrate-promote",
 "question": "How do I schedule it, retry it, and promote changes safely?",
 "proves": "Everything here is code in one bundle: deploy to a new workspace with one variable change, schedule and retry per task, promote dev → prod through Git.",
 "where": [("All jobs (filter: lifecast)", "jobs_list"),
           ("The bundle on GitHub", "github"),
           ("Workspace folder (everything in one place)", "folder:")],
 "build": "Databricks Asset Bundle: jobs, pipelines, schema, volume, app — declared in YAML, versioned in Git, deployed with one command. Serverless throughout: nothing idles, nothing to patch. The same artefact reinstalls on any workspace by changing the catalog variable.",
 "links": [("Jobs", "jobs_list"), ("Repo", "github"),
           ("Bundle config", "nb_file:databricks.yml")],
 "today": "Hand-tended scheduler entries and an environment only one person can rebuild.",
 "tomorrow": "One bundle, one command, any workspace — and the run schedule is config, not folklore.",
},
{
 "id": "stochastic-cost",
 "question": "What would a stochastic or nested run actually cost us?",
 "proves": "Scenarios fan out across workers — 1,000 path valuations in ~20 seconds here — and the nested-stochastic arithmetic is shown honestly rather than hand-waved.",
 "where": [("Fan-out demo + timings (MLflow)", "exp:stochastic"),
           ("Per-scenario results", "tbl:gld_stochastic_bel"),
           ("Costing explainer (live arithmetic)", "nb:06_stochastic_boundaries/02_nested_stochastic_costing")],
 "build": "mapInPandas distributes independent scenario valuations; wall time scales with workers, not hours. The costing notebook turns outer × inner × model points into core-hours in front of the room — parallelism makes nested feasible, proxies make it affordable.",
 "links": [("Stochastic run", "job:lifecast_stochastic_run"),
           ("Costing explainer", "nb:06_stochastic_boundaries/02_nested_stochastic_costing"),
           ("Use case folder", "folder:06_stochastic_boundaries")],
 "today": "Stochastic runs queued overnight; nested runs quietly descoped because the window can't fit them.",
 "tomorrow": "Sized per run, scaled by workers — and an honest conversation about scenario budgets.",
},
],
# ───────────────────────── DEVELOPER / QUANT ─────────────────────────
"developer": [
{
 "id": "build-and-control",
 "question": "You've shown me the model running — how do I actually build and control it?",
 "proves": "It's not a black box — it's your Python, versioned and orchestrated.",
 "where": [("Workshop notebook", "nb:05_projection_migration/01_term_projection"),
           ("MLflow experiment", "exp:projection"),
           ("Model in UC (@champion)", "model"),
           ("Orchestrating job", "job:lifecast_projection_run")],
 "build": "Logic lives in the notebook (you own the formulae) → every run logged to MLflow with basis, curve and results, compared against the legacy engine → registered as a versioned model in UC with lineage → orchestrated by the workflow with schedule and retry → promoted dev→prod via the bundle and Git. That chain is the control plane.",
 "links": [("Open notebook", "nb:05_projection_migration/01_term_projection"),
           ("Open MLflow", "exp:projection"),
           ("Open model in UC", "model"),
           ("Open job", "job:lifecast_projection_run")],
 "today": "A multi-hour run you can't see inside.",
 "tomorrow": "Your code, tracked, governed, in seconds.",
},
{
 "id": "pipeline-internals",
 "question": "How is the pipeline actually defined — and how do I test a change?",
 "proves": "The pipeline is ~150 lines of declarative Python: tables, expectations, quarantine. A change is a Git branch, not a change request to a vendor.",
 "where": [("Pipeline source", "nb_file:01_model_point_pipeline/00_model_point_pipeline.py"),
           ("Pipeline (graph + expectation metrics)", "pipeline:lifecast_model_point_pipeline"),
           ("Quality rules in action", "tbl:slv_policies_quarantine")],
 "build": "Lakeflow declarative pipelines: @dlt.table + expectations; quality rules are a dict evaluated both as gates and as quarantine reasons. Bad-feed test fixture ships with the demo — inject, watch it fail correctly, restore. Develop on a branch, deploy to your own target, promote by PR.",
 "links": [("Pipeline source", "nb_file:01_model_point_pipeline/00_model_point_pipeline.py"),
           ("Open pipeline", "pipeline:lifecast_model_point_pipeline"),
           ("Repo", "github")],
 "today": "ETL logic frozen inside a closed tool and a key-person dependency.",
 "tomorrow": "Declarative source in Git; the test fixture is part of the demo.",
},
{
 "id": "vectorisation-edge",
 "question": "Where does the fast-Python story actually break?",
 "proves": "We'll show you the boundary rather than sell past it: ratchets still vectorise; decision feedback doesn't; the fix is engineering, not magic.",
 "where": [("Vectorisation explainer (runnable)", "nb:06_stochastic_boundaries/01_vectorisation_boundary"),
           ("Fan-out demo", "nb:06_stochastic_boundaries/00_stochastic_fan_out")],
 "build": "Live in the room: vectorised vs Python loop (~100×), a GMAB-style ratchet via cummax (still fast), then a management-action loop where time-stepping is irreducible — vectorise across paths, loop over time, compile the hot loop (Numba/JAX) only where profiling says so. Solvable, not free.",
 "links": [("Run the explainer", "nb:06_stochastic_boundaries/01_vectorisation_boundary"),
           ("Use case folder", "folder:06_stochastic_boundaries")],
 "today": "Either 'the tool handles it' (opaque) or 'rewrite everything in C++' (never finished).",
 "tomorrow": "A profiled hot loop and an honest map of which products need real engineering.",
},
{
 "id": "esg-feed-point",
 "question": "How do I plug our scenario provider in?",
 "proves": "One function — esg_scenarios_active() — is the feed point. Your delivery lands, passes the gate, gets versioned, goes live; every consumer follows without a code change.",
 "where": [("Feed function + registry", "tbl:esg_governance_dashboard"),
           ("Ingest with validation gate", "nb:04_scenario_management/01_scenario_ingest"),
           ("A consumer that doesn't care who made the paths", "nb:06_stochastic_boundaries/00_stochastic_fan_out")],
 "build": "Drop (volume today; SFTP/API tomorrow, same landing) → gate (grid completeness, sane DFs) → registry (ACTIVE / AVAILABLE / SUPERSEDED) → feed point. Run the stochastic job against the vendor set and the QuantLib set: same code path, different governed set — the MLflow reconciliation metric shows exactly what changed.",
 "links": [("Scenario ingest", "job:lifecast_scenario_ingest"),
           ("Stochastic run (swap the set)", "job:lifecast_stochastic_run"),
           ("MLflow comparison", "exp:stochastic")],
 "today": "Scenario files copied between shares; consumers hard-wired to file paths.",
 "tomorrow": "One governed feed point; swapping providers is a registry action.",
},
],
# ─────────────────────────────── EXEC ───────────────────────────────
"exec": [
{
 "id": "audit-story",
 "question": "What's our audit story for IFRS 17 and Solvency II?",
 "proves": "Lineage from landing file to board pack, every assumption basis versioned and signed off, every run stamped with what fed it — evidence as a query, not a quarterly scramble.",
 "where": [("Lineage end to end", "tbl:gld_model_points"),
           ("Assumption audit trail", "tbl:asm_approval_log"),
           ("Run records with basis stamps", "tbl:gld_run_quality"),
           ("Side-by-side validation record", "tbl:gld_projection_validation")],
 "build": "Unity Catalog records lineage automatically; the governance tables (assumptions, scenarios, runs, sign-offs) are append-only and queryable. Nothing here was built specially for audit — the audit story is a by-product of running this way.",
 "links": [("Open lineage", "tbl:gld_model_points"),
           ("Audit trail", "tbl:asm_approval_log"),
           ("Run records", "tbl:gld_run_quality")],
 "today": "Reproducibility depends on filenames, shared drives and the memory of key people.",
 "tomorrow": "The regulator's question is a SELECT statement.",
},
{
 "id": "what-it-replaces",
 "question": "What does this replace — and, as importantly, what doesn't it?",
 "proves": "This is an integration play: we fix the data layer, govern the assumptions and add AI around your existing estate. The liability engine runs unchanged; Excel stays where it's load-bearing; your ESG stays yours.",
 "where": [("The unchanged downstream: exported model point file", "vol:export"),
           ("Excel kept: entry template + CFO export", "vol:excel"),
           ("ESG kept: the consume pattern", "tbl:esg_governance_dashboard")],
 "build": "Track 1 (everything on the landing page through results) was delivered with zero actuarial maths written. Migration (Track 2) exists as a workshop the actuaries choose when they're ready — the platform doesn't force the question.",
 "links": [("Results & reporting", "folder:03_results_and_genie"),
           ("Workshop POC", "folder:05_projection_migration")],
 "today": "A modernisation decision framed as rip-and-replace — high risk, so it never starts.",
 "tomorrow": "Land low-risk around the estate; let migration self-select, team by team.",
},
{
 "id": "cost-speed",
 "question": "Why is this faster and cheaper?",
 "proves": "The migrated product runs in a fifth of a second against a multi-hour anchor; 1,000 stochastic paths take ~20 seconds; and everything is serverless — compute exists only while a run is executing.",
 "where": [("Runtime metrics on the record", "exp:projection"),
           ("Stochastic timings", "exp:stochastic"),
           ("Live status", "status_strip")],
 "build": "Serverless jobs, pipelines, warehouse and app — no clusters to own, size or patch. Scale is per-run: the stochastic fan-out gets more workers, not a bigger overnight window. The numbers on this page are pulled live from the run records, not typed onto a slide.",
 "links": [("MLflow timings", "exp:projection"),
           ("Stochastic runs", "exp:stochastic")],
 "today": "Fixed-capacity overnight estate, sized for the worst night of the quarter.",
 "tomorrow": "Pay for the minutes a run actually takes.",
},
{
 "id": "poc-to-production",
 "question": "What's the path from this demo to production?",
 "proves": "The whole demo is one redeployable bundle — the same artefact a 4-6 week POC starts from: swap the synthetic feed for an extract of yours, keep everything else.",
 "where": [("The bundle (one-edit install)", "github"),
           ("Everything in one folder", "folder:"),
           ("Discovery questions (brief §12.4)", "github")],
 "build": "Phases 0-3 are the POC scope: connect your policy admin extract, import your assumption workbooks, land your results. The workshop (Phase 5) is where your actuaries write the product logic with our scaffold. Partners slot in at the projection-logic layer.",
 "links": [("Repo + brief", "github"), ("Workspace folder", "folder:")],
 "today": "POCs that start from a blank workspace and spend week one on plumbing.",
 "tomorrow": "Deploy this, swap the inputs, spend the POC on your data and your questions.",
},
],
}
