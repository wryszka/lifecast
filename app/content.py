"""LifeCast Cockpit content — persona -> question -> card.

The cockpit is the demo runbook made live, indexed by "what am I showing, to
whom". Cards carry five fixed fields (brief §9): proves / where it lives /
build & control / go links / today -> tomorrow. Links use semantic keys that
app.py resolves into URLs (path-based where possible, ID-resolved best-effort).

No business logic lives here — curated structure and short annotations only.
"""

DEMO_GUIDE_URL = "https://docs.google.com/document/d/1daijoVb751CezD_qLQBEqLPbM4HePms7ScvBa24hxfg/edit"

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
  "text": "Economic scenario sets (your ESG provider's deliveries) versioned and gated — plus an illustrative QuantLib set.",
  "link": "folder:04_scenario_management"},
 {"n": "05", "title": "Projection migration",
  "text": "The workshop: same product in Python, tied out side by side, in seconds.",
  "link": "folder:05_projection_migration"},
 {"n": "06", "title": "Stochastic & boundaries",
  "text": "Valuing the book across 1,000 simulated futures in parallel — and an honest map of where the hard edges are.",
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
 "title": "Policy data → model point file",
 "use_for": "We use this for: valuing the liabilities — what the firm must hold to pay future claims.",
 # THE four-step skeleton — tabs 1 and 2 render it, tab 3 monitors it.
 "skeleton": [
  {"key": "data",           "title": "Data",           "plain": "Raw policy records — age, sex, smoker status, outstanding term."},
  {"key": "transformation", "title": "Transformation", "plain": "Group them into a few thousand representative model points."},
  {"key": "control",        "title": "Control",        "plain": "Check counts and totals reconcile before anything moves forward."},
  {"key": "result",         "title": "Result",         "plain": "The file the engine reads."},
 ],
 "tab1": {
  "lead": "Every valuation turns raw policy records into the summarised file the engine reads — that's model point creation, and it's the same four steps everywhere.",
 },
 "tab2": {
  "lead": "The same four steps as they run today, and what each becomes — the engine reads the exact same file at the end.",
  "swaps": [
   {"old": "Manual CSV pulled and emailed",
    "new": "Automated ingestion from the policy table",
    "links": [("Code — pipeline source", "nb_file:01_model_point_pipeline/00_model_point_pipeline.py"),
              ("The landing zone", "vol:")]},
   {"old": "Reshaping in one person's Excel workbook",
    "new": "A governed pipeline anyone can run; rejects quarantined, never lost",
    "links": [("Pipeline graph, live", "pipeline:lifecast_model_point_pipeline"),
              ("Quarantine — every reject, with reasons", "tbl:slv_policies_quarantine")]},
   {"old": "Eyeball check if there's time",
    "new": "An automatic gate; counts and totals reconciled; red stops the run",
    "links": [("Code — gate notebook", "nb:01_model_point_pipeline/01_quality_gate"),
              ("Gate history", "tbl:gld_quality_dashboard")]},
   {"old": "File dropped on a share, no lineage",
    "new": "The same engine file, full lineage policy → model point (+ read-only Excel for the eyeball habit)",
    "links": [("Code — export notebook", "nb:01_model_point_pipeline/02_export_model_point_file"),
              ("The exported file", "vol:export")],
    "peek": ("Peek inside the file — read-only", "#/file/mpf")},
  ],
  "handoff": {
   "ours": "Model point file",
   "theirs": "The engine reads it — downstream, unchanged",
   "text": "We rebuilt everything up to this file; the engine never moves. That's the no-risk transition.",
   "next_label": "Next: the assumptions",
   "next_link": "folder:02_assumption_governance",
  },
  "scope": ("Deliberately one product and one feed — this is the scaffold, not your estate. "
            "Your products, your rules and your admin systems map in during discovery; "
            "the structure they drop into is what you just saw."),
 },
 "tab3": {
  "lead": "Once it's live, here's how you run it and prove it's healthy.",
  "run_help": "The whole run takes about two minutes. Breaking it is allowed — that's what the bad feed button is for; restore puts everything back.",
  "agent": {
   "genie_title": "LifeCast — Run health",
   "intro": "A plain-English overseer on the run record — ask it anything an approver would ask.",
   "questions": [
    "Did the latest run complete, and was anything quarantined?",
    "Explain the rejects in quarantine — which rules failed, and how many rows each?",
    "Do the control totals reconcile with the previous run?",
    "Summarise the latest run for a sign-off note: verdict, volumes in and out, quarantine, movement and grouping checks, and the basis used.",
   ],
  },
 },
 "beat": [
  {"do": "Run the overnight job (≈2 min — yes, the 'overnight' run).",
   "expect": "GREEN. ~50,000 rows in, 0 quarantined, ~8,200 model points out.",
   "say": "The gate signs off — on the record, with the valuation date, the control totals and the basis in force."},
  {"do": "Open the Governance tab.",
   "expect": "The GREEN row: movement 0.0% vs the last good run, grouping PASS, signed off.",
   "say": "Which extract and which basis fed which run — recorded, not remembered."},
  {"do": "Inject the bad feed (button above, ≈1 min).",
   "expect": "A deliberately corrupted feed lands next to the clean one.",
   "say": "A corrupted extract has just arrived — exactly what happens at quarter end."},
  {"do": "Run the overnight job again (≈2 min).",
   "expect": "It FAILS at the quality gate — that is the success state of this demo: ~3,500 rows quarantined (≈6.5%), six rules firing.",
   "say": "The failed run is the control working. The rejects are parked with reasons, the model point file is untouched, and the engine never sees bad data."},
  {"do": "Ask the overseer: 'explain the rejects in quarantine'.",
   "expect": "A plain-English breakdown by rule, straight off the record.",
   "say": "Nobody signs a failed gate — and anyone can ask why it failed, in English."},
  {"do": "Restore (button above, ≈3 min), then run the overnight job once more.",
   "expect": "GREEN again. The whole loop took ten minutes.",
   "say": "Today this failure costs the actuary a morning. Here it cost one click and a coffee."},
 ],
},
]

# ── Blocks (APP_STRUCTURE_SPEC.md §4): left-nav = blocks only. Every block
# except model points is an OPENLY-STUBBED placeholder — states intent, never
# fake-works. Underlying workspace assets are live and linked. ───────────────
BLOCKS = {
 "assumptions": {
  "title": "Assumptions", "section": "Inputs", "state": "live",
  "will_show": "The basis — mortality, lapse and expense — as a governed, versioned asset: drafted (still in Excel, deliberately), submitted, approved maker/checker, and every action on an append-only audit trail. Every run records which basis fed it.",
  "tabs": [
   ("What we're showing", "Setting mortality, lapse and expense — the basis every valuation uses — with a real approval workflow."),
   ("Old → new", "Excel workbooks one person owns → versioned Delta tables with a registry (DRAFT → PENDING → APPROVED → SUPERSEDED). The Excel entry sheet is kept — it reads and writes the governed tables live via DATABRICKS.SQL."),
   ("Management", "Maker/checker as two jobs (entry drafts a shocked basis; approval approves or rejects), asm_approval_log as the audit trail, and asm_*_active() as the single read path every consumer uses."),
  ],
  "posture": "Bring yours — the structure holds any basis. The demo's v2 basis (smoker loading, approved) is what the engine, the factory model and every valuation in this cockpit actually consume.",
  "assets": [("Assumption governance assets — live in the workspace", "folder:02_assumption_governance"),
             ("The registry — asm_assumption_sets (versions, status, approvers)", "tbl:asm_assumption_sets"),
             ("The Excel entry workbook on the volume (DATABRICKS.SQL round-trip)", "vol:excel"),
             ("Maker — draft and submit a shocked basis", "job:lifecast_assumption_entry"),
             ("Checker — approve or reject the pending basis", "job:lifecast_assumption_approval")],
  "agents": [("Experience — actual-vs-expected summary, proposes an assumption adjustment", "placeholder")],
 },
 "scenarios": {
  "title": "Scenarios (ESG)", "section": "Inputs", "state": "live",
  "will_show": "Economic scenarios governed like everything else: your licensed provider's deliveries validated, versioned and activated through a gate — plus an illustrative in-platform set (QuantLib, calibrated to the EIOPA curve, tracked in MLflow) that never activates itself.",
  "tabs": [
   ("What we're showing", "Economic scenarios for market-consistent runs — consumed from whoever generates them."),
   ("Old → new", "Provider file on a share → the esg/inbound folder as the plug point: deliveries are gated (grid completeness, sane discount factors), versioned in a registry (ACTIVE / AVAILABLE / SUPERSEDED), and consumers read one function — esg_scenarios_active()."),
   ("Management", "Broken deliveries fail the gate and never activate. The illustrative QuantLib set registers as AVAILABLE only; its calibration (Hull-White parameters, martingale diagnostics) is tracked in MLflow, run by run."),
  ],
  "posture": "Your ESG stays yours — whichever licensed vendor you run today delivers to the same folder unchanged. We are runtime and governance, not a scenario vendor.",
  "assets": [("Scenario management assets — live in the workspace", "folder:04_scenario_management"),
             ("The registry — esg_scenario_sets (versions, status, provenance)", "tbl:esg_scenario_sets"),
             ("Vendor ingest — validate, version and activate through the gate", "job:lifecast_scenario_ingest"),
             ("Illustrative generator — EIOPA curve → QuantLib Hull-White", "job:lifecast_esg_illustrative"),
             ("Calibration history in MLflow (params + martingale checks)", "exp:esg")],
  "agents": [],
 },
 "modelling": {
  "title": "Modelling", "section": "Modelling & results", "state": "live",
  "will_show": "The projection itself, three depths in: tied out side by side against the engine (use case 05), fanned across scenarios (06), and rebuilt as a governed Unity Catalog model — build → save to Unity → run from Unity, on a CPU grid or a GPU (07).",
  "tabs": [
   ("What we're showing", "Policies + assumptions → cashflows → reserve — and the model itself as a versioned, governed object."),
   ("Old → new", "Engine content → Python on the platform: validated per model point, registered in Unity Catalog (versions, aliases, a compare gate before any promotion), run from the registry on whatever compute the quarter needs."),
   ("Management", "MLflow run history, the registry's audit answer (who built which version, from which basis), validate-to-tolerance gates, run overseer + reconciliation agents."),
  ],
  "posture": "The deterministic term projection is live end to end: side-by-side tie-out, then the model factory — v1 vs v2 compared to the penny before @champion moves, the grid a job parameter (10 vs 100), and the same maths on serverless GPU compute when the book goes seriatim. Stochastic at scale remains the honest last mile.",
  "assets": [("Model factory — build → Unity → grid → GPU (use case 07)", "folder:07_model_factory"),
             ("The registered model — lifecast_engine_model, versions + aliases", "model:lifecast_engine_model"),
             ("Run the factory — build, compare, promote, grid", "job:lifecast_model_factory"),
             ("Run on GPU — @gpu from Unity on a serverless A10", "job:lifecast_model_factory_gpu"),
             ("Projection migration — the side-by-side tie-out (use case 05)", "folder:05_projection_migration"),
             ("Stochastic fan-out (use case 06)", "folder:06_stochastic_boundaries")],
  "agents": [("Run overseer — did it complete, anything quarantined, safe to release?", "specced"),
             ("Reconciliation — explains where the two engines differ, and why", "placeholder")],
 },
 "results": {
  "title": "Results", "section": "Modelling & results", "state": "live",
  "will_show": "The results desk: the engine's dumps land governed once, and minutes later the dashboard is current, Genie answers in English, the analytics the batch never had time for are on the shelf, and every number carries its papers.",
  "tabs": [
   ("What we're showing", "Engine output → one governed results layer → dashboard, ad-hoc analytics, Genie, the Excel pack — and the audit trail per run."),
   ("Old → new", "CSV dump + hand-rebuilt board pack → Delta + a two-page AI/BI dashboard (results · risk & audit) + Genie — with the ±100bp rate-risk map and concentration already answered from the engine's own runs."),
   ("Management", "gld_run_audit — one row per engine run: input file + gate verdict, basis version + approver, curve, operator, minutes-to-queryable. Delta history and VERSION AS OF for 'reproduce that number'."),
  ],
  "posture": "The CFO export is always offered — three sheets now: board pack, rate risk, and the audit sheet. Regulatory templates stay in Excel; even the spreadsheet carries its provenance.",
  "assets": [("The BEL Movement dashboard — page 2 is Risk & audit", "dashboard:"),
             ("Ask the results — Genie space (incl. the audit trail)", "genie:"),
             ("gld_run_audit — every number's papers, one row per run", "tbl:gld_run_audit"),
             ("The board pack on the volume (Excel, three sheets)", "vol:board_pack"),
             ("Results & Genie assets — live in the workspace", "folder:03_results_and_genie")],
  "agents": [("Movement & disclosure — movement attribution, drafts commentary", "placeholder")],
 },
}

# Governance block — the cross-cutting showcase (one live view, four stubs).
GOV_SHOWCASE = [
 {"title": "Sign-off gates", "state": "live",
  "text": "Assumption sign-off and run-release — every run's verdict, control totals and approver on the record.",
  "route": "#/governance/record"},
 {"title": "Trace this number", "state": "coming",
  "text": "Lineage policy → assumption → cashflow → FCF: pick a number, walk back to everything that fed it."},
 {"title": "Version & reproduce", "state": "live",
  "text": "Every engine run's papers in one row — input file, gate verdict, basis version + approver, curve, operator (gld_run_audit); Delta time travel re-derives any past number. Model versions freeze their basis and curve inside them.",
  "route": "#/block/results"},
 {"title": "Model risk register", "state": "live",
  "text": "The registry's spine is live: lifecast_engine_model versions with who-built-what, the per-model-point compare gate before promotion, and aliases marking what production trusts. The full register view is the roadmap on top.",
  "route": "#/block/modelling"},
 {"title": "Roles & segregation of duties", "state": "coming",
  "text": "Preparer / reviewer / approver — who may enter, who may approve, who may release."},
]
GOV_AGENT = ("Audit & documentation — drafts model docs, the sign-off note, and answers 'what fed this number'", "placeholder")

ROADMAP = {
 "title": "Roadmap / wider solution", "state": "roadmap",
 "will_show": "Where this plugs into the business process — every connection point marked openly as roadmap.",
 "groups": [
  ("Downstream", ["→ IFRS 17 CSM engine / sub-ledger", "→ capital (SCR)", "→ general ledger",
                  "→ reporting & disclosures", "→ ALM / treasury"]),
  ("Upstream", ["← policy admin", "← finance data"]),
  ("The loop", ["experience analysis → back into assumptions"]),
  ("The suite", ["sibling Bricksurance workbenches — pricing, claims"]),
 ],
}

# ── AI desk (spec §5: agents contextual in management tabs; this is the light
# index showcasing them together). All placeholders except the run overseer,
# which is live inside the model points beat. Nothing is plumbed here. ───────
AI_PAGE = {
 "headline": "One desk, five specialists",
 "lead": ("Ask in plain English; the question routes to the specialist that owns the answer. "
          "One specialist is live today — the rest are stated openly, not simulated."),
 "note": ("Every specialist works the same way: a governed agent over the recorded tables, "
          "answering with the data and showing its working. They appear inside the beat they "
          "serve — this page is just the roster."),
 "agents": [
  {"name": "Run overseer", "color": "blue", "status": "live",
   "what": "Did it complete, anything quarantined, safe to release? Summarises run status, explains rejects, drafts the sign-off note.",
   "lives": "Model points · management tab", "route": "#/flow/model-point-feed/manage",
   "questions": ["Did the latest run complete, and was anything quarantined?",
                 "Summarise the latest run for a sign-off note."]},
  {"name": "Reconciliation", "color": "violet", "status": "placeholder",
   "what": "Explains where the platform and the engine differ on a product — and why, per model point.",
   "lives": "Modelling", "route": "#/block/modelling",
   "questions": ["Where do the two engines differ on this product, and why?"]},
  {"name": "Movement & disclosure", "color": "green", "status": "placeholder",
   "what": "IFRS 17 movement attribution; drafts the disclosure commentary from the recorded movement.",
   "lives": "Results", "route": "#/block/results",
   "questions": ["Attribute this quarter's movement and draft the commentary."]},
  {"name": "Experience", "color": "amber", "status": "placeholder",
   "what": "Actual-vs-expected summary; proposes an assumption adjustment for the maker-checker workflow.",
   "lives": "Assumptions", "route": "#/block/assumptions",
   "questions": ["How did actual mortality run against the basis — and what adjustment would you propose?"]},
  {"name": "Audit & documentation", "color": "slate", "status": "placeholder",
   "what": "Drafts model documentation and the sign-off note; answers 'what fed this number' from lineage and the audit trail.",
   "lives": "Governance", "route": "#/governance",
   "questions": ["What fed this number? Walk me back to everything behind it."]},
 ],
 "dev_help": {
  "lead": ("And the AI that helps you build all of this in the first place — not our agents, "
           "the platform's own assistance, there from day one of the workshop."),
  "items": [
   {"name": "Genie Code — in the notebook",
    "what": "A pair-programmer where the work happens: scaffolds the pipeline, drafts the projection code, explains an error, refactors your actuaries' Python as they write it."},
   {"name": "Dashboards from a prompt",
    "what": "Describe the view — BEL by product, movement by quarter — and AI/BI drafts the dashboard over the governed tables. Tweak, don't build."},
   {"name": "Ask the data in English",
    "what": "Genie spaces over any governed table — the same capability behind the run overseer, available on every dataset you land."},
  ],
 },
}

# ── POC plan (brief §12.3, narrowed to one term product). Canonical copy also
# ships as POC_TERM_PRODUCT.md in the repo. ──────────────────────────────────
POC_PLAN = {
 "title": "POC — one product, fully off the engine",
 "lead": "One deterministic term product, valued end to end on the platform in 4–6 weeks — with the engine reduced, for that product, to a comparison reference. The engine itself is untouched and keeps running everything else.",
 "objective": "At exit, the term product values end to end here — feed → model points → approved basis → projection → results → audit — and the evidence pack is strong enough that your validation function can defend switching this product's engine run off.",
 "scope_out": "Out of scope (mapped, not built): complex products and guarantees · capital model integration · IFRS 17 engine feeds · any licence decision. Hybrid is a perfectly good end state.",
 "reuse": [
  ("Ingestion + quality gate + quarantine", "Your policy extract (spec + 2 historical valuation dates)"),
  ("Model point grouping with control-total proof", "Your grouping bands and quality rules"),
  ("Assumption registry, Excel round-trip, approvals", "Your assumption workbooks"),
  ("Projection scaffold + MLflow + UC model registry", "Your product logic — written by your actuaries (the workshop)"),
  ("Per-MP validation harness with tolerance gate", "Your engine's output files as the baseline"),
  ("Results layer, dashboards, Genie, run overseer", "Your reporting cuts"),
 ],
 "weeks": [
  ("Week 1 — your data lands", "Extract connected, landed, gated; your quality rules in the gate; control totals reconcile extract → model points against your current file exactly."),
  ("Week 2 — your basis, your logic", "Assumption workbooks imported through the Excel round-trip; basis approved on the record. Workshop: your actuaries delete our illustrative product logic and write yours in the scaffold."),
  ("Week 3 — first side-by-side", "Python projection vs a real engine run on identical model points, basis and curve. Iterate until the per-model-point tie-out passes tolerance — the gate fails loudly until it does."),
  ("Week 4 — the second date", "Repeat on the second valuation date. Analysis of change: the movement between dates ties out, not just the levels. Schedule, alerting, access controls, the bad-feed drill run deliberately."),
  ("Weeks 5–6 — evidence and exit", "Documentation pack assembled from the record (it already exists); independent reviewer walkthrough; downstream consumers of this product's BEL mapped; exit review."),
 ],
 "exit": [
  ("Per-model-point tie-out vs engine", "100% of MPs within agreed tolerance (default £0.01) on ≥ 2 valuation dates"),
  ("Analysis of change", "movement between the two dates within agreed tolerance"),
  ("Control totals", "policy count + sum assured reconcile exactly, end to end"),
  ("Run time", "full valuation of the product in minutes, demonstrated live"),
  ("Reproducibility", "any past run re-executed from its recorded basis + curve + code version — same numbers"),
  ("Operability", "scheduled run with gate + alerting; a deliberately bad feed stopped before the file (the RED drill)"),
  ("Ownership", "product logic written and documented by your actuaries; independent validation walkthrough completed"),
 ],
 "decision": "Move this product's engine run to 'comparison only', then off — for this product. Nothing else changes: the engine, every other product and all downstream consumers continue exactly as today. The next product starts from a proven scaffold and a faster week 1.",
 "needs": [
  "Extract spec + two historical valuation-date extracts",
  "The assumption workbooks for the product",
  "Two matching engine output files (same dates) as the baseline",
  "2–3 actuaries for the workshop — the logic is theirs",
  "A named contact in validation, involved from week 1",
 ],
}

# ── Learn: the basics for someone new to this — what the business is, how the
# process runs, why it hurts, what LifeCast shows. Client-safe, plain words. ──
LEARN = {
 "title": "The basics — what this is about",
 "lead": "Ten minutes of background so the rest of the cockpit makes sense. No Databricks "
         "here yet — just the business, the process, and where it creaks.",
 "sections": [
  {"h": "The business, in one paragraph",
   "body": "A life insurer takes premiums today and promises payments that may fall due "
           "decades from now. Regulators require it to hold reserves against those promises, "
           "so every quarter actuaries value them: project each policy's future premiums, "
           "claims and expenses year by year, using assumptions about mortality, lapse and "
           "expenses, then discount back with a market curve. The headline output is the "
           "best estimate liability (BEL) — the number the board pack, the regulator and "
           "the capital calculation all stand on."},
  {"h": "The process, in five steps", "steps": [
     ("Policy data", "Millions of admin-system records are extracted, cleaned and checked. Bad rows must be caught here — a rejected policy still has a liability."),
     ("Model points", "Policies are grouped into a few thousand representative records (by age, sex, smoker status, outstanding term) so the engine can finish overnight. Control totals prove nothing was lost."),
     ("The engine", "A licensed actuarial modelling system reads the model point file, the approved assumptions and the curve, and projects everything decades ahead. It runs in batches and dumps result files."),
     ("Results", "The dumps become the quarter's numbers: BEL by product, movement vs last quarter, sensitivities. Traditionally rebuilt into a board pack by hand, in Excel."),
     ("Reporting & audit", "The numbers flow to the board, the regulator and the auditors — who ask: which data, which basis, who approved it, can you reproduce it?"),
  ]},
  {"h": "Where it hurts today", "bullets": [
     "The overnight window: one batch per day means one question answered per day — a sensitivity you didn't schedule waits until next quarter.",
     "Excel around the edges: assumptions entered in workbooks, board packs rebuilt by hand, five versions of the same number in circulation.",
     "One specialist tool, one bottleneck: the engine's queue, its licence, and the few people who can operate it shape everyone's calendar.",
     "Audit by archaeology: 'which basis fed that number' is an email thread, not a query.",
  ]},
  {"h": "What LifeCast shows",
   "body": "Two moves, in order. First — the integration: everything around the engine "
           "(data, model points, assumptions, scenarios, results, governance) moves onto "
           "one governed platform while the engine itself runs unchanged, reading the exact "
           "same file it reads today. That is most of the pain gone, at no transition risk. "
           "Second — beside the engine: the projection itself rebuilt in Python, tied out "
           "against the engine per model point, versioned in Unity Catalog, and run from "
           "the registry on whatever compute the quarter needs — a CPU grid or a GPU. "
           "Whether a product ever moves engines is the client's decision, made on evidence "
           "the platform produces run by run."},
  {"h": "Where to go next", "bullets": [
     "Terms — the eight words you'll hear, one line each (sidebar).",
     "Overview — the process map; every block opens the part of the demo that proves it.",
     "Model points — the first live beat: break the feed, watch the gate stop the run.",
     "The demo guide (sidebar) — the full 15-minute script with what to say and expect.",
  ]},
 ],
}

# ── Terms: eight client-safe one-liners — the anchor for the planned
# learn-this-first link. ─────────────────────────────────────────────────────
TERMS = [
 ("Model point", "A grouped, representative policy record. ~50,000 policies compress to ~8,200 model points (by attained age, sex, smoker status, outstanding term) so the engine has less to chew on, with control totals preserved."),
 ("Model point file (MPF)", "The fixed-layout file of model points the actuarial engine ingests. The contract between the data world and the modelling world."),
 ("The engine", "The licensed actuarial modelling software that projects premiums, claims and expenses decades ahead to value liabilities. Runs in overnight batches. We connect to it; we don't change it."),
 ("Basis / assumptions", "The approved set of mortality, lapse and expense tables a valuation uses. Versioned and signed off here — which basis fed which run is always on the record."),
 ("BEL", "Best Estimate Liability — the present value of expected future outgo minus future premiums. The number the board pack is built on. For protection business it can legitimately be negative."),
 ("ESG / scenario set", "An Economic Scenario Generator produces thousands of simulated futures (rates, equities) for market-consistent valuation. The client's ESG stays theirs — sets are versioned and gated here."),
 ("Quarantine", "Where rows that fail quality rules go — with the exact rules they failed. Parked for repair and resubmission, never silently dropped: a rejected policy still has a liability."),
 ("Valuation date & duration", "An in-force valuation values each policy as at a date: how long it has run (duration), the holder's attained age, and the term outstanding. Entry age alone would value everything as new business — wrong."),
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
 "id": "engine-endgame",
 "question": "What happens to our engine licence, long-term?",
 "proves": "That's your decision, made product by product — the platform's job is to make the evidence undeniable either way.",
 "where": [("The side-by-side tie-out record", "tbl:gld_projection_validation"),
           ("The migrated product, versioned in UC", "model"),
           ("Run-by-run comparison (MLflow)", "exp:projection"),
           ("The workshop notebook — your logic, not ours", "nb:05_projection_migration/01_term_projection")],
 "build": "Nothing upstream or downstream of the engine is engine-specific — the engine is a slot in the middle of the process map. A product migrates when its Python twin has tied out beside the engine for enough valuation cycles that renewal becomes a finance question instead of a risk question. For a simple deterministic product, everything a full-replacement POC needs already exists here: governed inputs, the projection scaffold (your actuaries write the product logic), per-model-point validation with a tolerance gate, results, audit. Complex blocks can stay on the engine for years — hybrid is a perfectly good end state, and the engine keeps running either way.",
 "links": [("Tie-out record", "tbl:gld_projection_validation"),
           ("Projection run", "job:lifecast_projection_run"),
           ("Workshop scaffold", "folder:05_projection_migration")],
 "today": "An all-or-nothing licence decision nobody can de-risk, so it never gets made.",
 "tomorrow": "A per-product evidence base — each product moves when its numbers have earned it, or doesn't.",
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
