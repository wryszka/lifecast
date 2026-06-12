"""LifeCast Cockpit — lifecast-workbench.

A presenter's cockpit, not a business-process simulation (CLAUDE.md hard rule):
curated structure, deep links, short annotations, and a handful of read-only
status pulls from UC. No business logic, no simulated processing. Genie,
dashboards and jobs are destinations we link to — never reimplemented here.
"""

import os
import time

from databricks.sdk import WorkspaceClient
from fastapi import FastAPI
from fastapi.responses import FileResponse

from content import CARDS, FLOWS, GOVERNANCE_INVENTORY, GOVERNANCE_SCOPE, PERSONAS, POC_PLAN, TERMS, TILES

CATALOG = os.environ.get("CATALOG", "lr_dev_aws_us_catalog")
SCHEMA = "lifecast"
WAREHOUSE_ID = os.environ.get("WAREHOUSE_ID", "")
HOST = (os.environ.get("DATABRICKS_HOST") or "").rstrip("/")
if HOST and not HOST.startswith("http"):
    HOST = f"https://{HOST}"

app = FastAPI(title="LifeCast Cockpit")
_w = None


def w() -> WorkspaceClient:
    global _w
    if _w is None:
        _w = WorkspaceClient()
    return _w


# ── link resolution ──────────────────────────────────────────────────────────
# Path-based links need no permissions. IDs (jobs, pipelines, dashboard, genie,
# experiments) are resolved best-effort with the app's identity and fall back
# to a sensible path link, so the cockpit degrades gracefully, never breaks.
_links_cache: dict = {"at": 0.0, "ids": {}}


def _resolve_ids() -> dict:
    now = time.time()
    if now - _links_cache["at"] < 300 and _links_cache["ids"]:
        return _links_cache["ids"]
    ids: dict = {"jobs": {}, "pipelines": {}, "dashboard": None, "genie": None,
                 "genie_runhealth": None, "experiments": {}}
    try:
        for j in w().jobs.list():
            name = j.settings.name or ""
            if name.startswith("lifecast_"):
                ids["jobs"][name] = j.job_id
    except Exception:
        pass
    try:
        for p in w().pipelines.list_pipelines(filter="name LIKE 'lifecast%'"):
            ids["pipelines"][p.name] = p.pipeline_id
    except Exception:
        pass
    try:
        for obj in w().workspace.list("/Workspace/Shared/lifecast/03_results_and_genie"):
            if obj.object_type and obj.object_type.value == "DASHBOARD":
                ids["dashboard"] = obj.resource_id
    except Exception:
        pass
    try:
        spaces = w().api_client.do("GET", "/api/2.0/genie/spaces").get("spaces", [])
        for s in spaces:
            if s.get("title") == "LifeCast — Results":
                ids["genie"] = s["space_id"]
            if s.get("title") == "LifeCast — Run health":
                ids["genie_runhealth"] = s["space_id"]
    except Exception:
        pass
    for key, path in [("projection", "/Shared/lifecast/05_projection_migration/projection"),
                      ("esg", "/Shared/lifecast/04_scenario_management/esg_calibration"),
                      ("stochastic", "/Shared/lifecast/06_stochastic_boundaries/stochastic")]:
        try:
            exp = w().api_client.do(
                "GET", "/api/2.0/mlflow/experiments/get-by-name",
                query={"experiment_name": path})
            ids["experiments"][key] = exp["experiment"]["experiment_id"]
        except Exception:
            pass
    _links_cache.update(at=now, ids=ids)
    return ids


def resolve_link(key: str) -> str:
    """Semantic link key -> URL. Path-based first; ID-resolved with fallback."""
    ids = _resolve_ids()
    kind, _, arg = key.partition(":")
    if kind == "tbl":
        return f"{HOST}/explore/data/{CATALOG}/{SCHEMA}/{arg}"
    if kind == "vol":
        sub = {"excel": "/excel", "export": "/export/model_point_file", "board_pack": "/export/board_pack"}.get(arg, "")
        return f"{HOST}/explore/data/volumes/{CATALOG}/{SCHEMA}/lifecast_files{sub}"
    if kind == "model":
        return f"{HOST}/explore/data/models/{CATALOG}/{SCHEMA}/lifecast_term_projection"
    if kind in ("nb", "nb_file", "folder"):
        return f"{HOST}/#workspace/Shared/lifecast/{arg}".rstrip("/")
    if kind == "job":
        jid = ids["jobs"].get(arg)
        return f"{HOST}/jobs/{jid}" if jid else f"{HOST}/jobs"
    if kind == "jobs_list":
        return f"{HOST}/jobs"
    if kind == "pipeline":
        pid = ids["pipelines"].get(arg)
        return f"{HOST}/pipelines/{pid}" if pid else f"{HOST}/pipelines"
    if kind == "dashboard":
        return (f"{HOST}/dashboardsv3/{ids['dashboard']}/published" if ids["dashboard"]
                else f"{HOST}/#workspace/Shared/lifecast/03_results_and_genie")
    if kind == "genie":
        return (f"{HOST}/genie/rooms/{ids['genie']}" if ids["genie"]
                else f"{HOST}/#workspace/Shared/lifecast/03_results_and_genie")
    if kind == "genie_runhealth":
        return (f"{HOST}/genie/rooms/{ids['genie_runhealth']}" if ids["genie_runhealth"]
                else f"{HOST}/#workspace/Shared/lifecast/01_model_point_pipeline")
    if kind == "exp":
        eid = ids["experiments"].get(arg)
        return f"{HOST}/ml/experiments/{eid}" if eid else f"{HOST}/ml/experiments"
    if kind == "github":
        return "https://github.com/wryszka/lifecast"
    if kind == "status_strip":
        return "#/"
    return HOST


# ── API ──────────────────────────────────────────────────────────────────────
@app.get("/api/content")
def content():
    flows = []
    for f in FLOWS:
        swaps = []
        for sw in f["tab2"]["swaps"]:
            swaps.append({
                "old": sw["old"], "new": sw["new"],
                "links": [{"label": lbl, "url": resolve_link(k)} for lbl, k in sw["links"]],
                **({"peek": {"label": sw["peek"][0], "hash": sw["peek"][1]}} if "peek" in sw else {}),
            })
        h = f["tab2"]["handoff"]
        flows.append({
            "id": f["id"], "eyebrow": f["eyebrow"], "title": f["title"], "use_for": f["use_for"],
            "skeleton": f["skeleton"],
            "tab1": f["tab1"],
            "tab2": {"lead": f["tab2"]["lead"], "swaps": swaps, "scope": f["tab2"]["scope"],
                     "handoff": {"ours": h["ours"], "theirs": h["theirs"], "text": h["text"],
                                 "next_label": h["next_label"], "next_url": resolve_link(h["next_link"])}},
            "tab3": {"lead": f["tab3"]["lead"], "run_help": f["tab3"]["run_help"],
                     "agent": {**f["tab3"]["agent"], "genie_url": resolve_link("genie_runhealth")}},
            "beat": f["beat"],
        })
    personas = []
    for p in PERSONAS:
        cards = []
        for c in CARDS[p["id"]]:
            cards.append({
                "id": c["id"],
                "question": c["question"],
                "proves": c["proves"],
                "where": [{"label": lbl, "url": resolve_link(k)} for lbl, k in c["where"]],
                "build": c["build"],
                "links": [{"label": lbl, "url": resolve_link(k)} for lbl, k in c["links"]],
                "today": c["today"],
                "tomorrow": c["tomorrow"],
            })
        personas.append({**p, "cards": cards})
    tiles = [{**{k: v for k, v in t.items() if k != "link"},
              **({"url": resolve_link(t["link"])} if "link" in t else {})} for t in TILES]
    return {"tiles": tiles, "flows": flows, "personas": personas,
            "terms": [{"term": t, "text": x} for t, x in TERMS],
            "poc": POC_PLAN,
            "host": HOST, "catalog": CATALOG}


def _sql_one(query: str):
    r = w().statement_execution.execute_statement(
        statement=query, warehouse_id=WAREHOUSE_ID, wait_timeout="30s")
    if r.result and r.result.data_array:
        return r.result.data_array[0]
    return None


@app.get("/api/status")
def status():
    """The 'at most a couple of read-only status pulls' the brief allows."""
    T = f"`{CATALOG}`.`{SCHEMA}`"
    tiles = []
    for label, query, fmt in [
        ("Last overnight run",
         f"SELECT verdict, date_format(run_ts,'dd MMM HH:mm'), assumption_set_id FROM {T}.gld_quality_dashboard LIMIT 1",
         lambda r: {"value": r[0], "detail": f"{r[1]} · basis {r[2]}"}),
        ("Approved basis",
         f"SELECT assumption_set_id, basis_name FROM {T}.asm_assumption_sets WHERE status='APPROVED' ORDER BY approved_at DESC LIMIT 1",
         lambda r: {"value": r[0], "detail": r[1]}),
        ("Active scenario set",
         f"SELECT scenario_set_id, concat(source,' · ',n_scenarios,' paths') FROM {T}.esg_scenario_sets WHERE status='ACTIVE' ORDER BY created_at DESC LIMIT 1",
         lambda r: {"value": r[0], "detail": r[1]}),
        ("Projection tie-out",
         f"SELECT verdict, concat(mp_compared,' MPs · max diff £',round(max_abs_diff,4)) FROM {T}.gld_projection_validation ORDER BY run_ts DESC LIMIT 1",
         lambda r: {"value": r[0], "detail": r[1]}),
    ]:
        try:
            row = _sql_one(query)
            tiles.append({"label": label, **(fmt(row) if row else {"value": "—", "detail": "no runs yet"})})
        except Exception:
            tiles.append({"label": label, "value": "—", "detail": "status unavailable (grant pending?)"})
    return {"tiles": tiles}


# ── Management tab: run control, trigger, and the Genie overseer proxy ──────
RUN_JOBS = {"overnight": "lifecast_overnight_run", "bad_feed": "lifecast_bad_feed_day"}


@app.get("/api/runcontrol")
def runcontrol():
    """Read: last run state + schedule for the overnight job, latest gate
    verdict and quarantine picture. Tab 3's live panel."""
    out = {"job": None, "gate": None, "quarantine": None}
    try:
        jid = _resolve_ids()["jobs"].get(RUN_JOBS["overnight"])
        if jid:
            job = w().jobs.get(jid)
            sched = "On demand (schedule it when you go live — it's one block of config)"
            if job.settings.schedule:
                sched = f"Scheduled: {job.settings.schedule.quartz_cron_expression}"
            runs = list(w().jobs.list_runs(job_id=jid, limit=1))
            last = None
            if runs:
                r = runs[0]
                import datetime
                state = (r.state.result_state.value if r.state and r.state.result_state
                         else (r.state.life_cycle_state.value if r.state else "—"))
                last = {"state": state,
                        "when": datetime.datetime.fromtimestamp((r.start_time or 0) / 1000).strftime("%d %b %H:%M"),
                        "url": f"{HOST}/jobs/{jid}/runs/{r.run_id}"}
            out["job"] = {"name": RUN_JOBS["overnight"], "url": f"{HOST}/jobs/{jid}",
                          "schedule": sched, "last": last}
    except Exception:
        pass
    try:
        T = f"`{CATALOG}`.`{SCHEMA}`"
        r = _sql_one(f"SELECT verdict, date_format(run_ts,'dd MMM HH:mm'), rows_quarantined, "
                     f"rule_breakdown, movement_check, grouping_check FROM {T}.gld_quality_dashboard LIMIT 1")
        if r:
            out["gate"] = {"verdict": r[0], "when": r[1], "quarantined": int(r[2]),
                           "rules": r[3], "movement": r[4], "grouping": r[5]}
    except Exception:
        pass
    return out


from pydantic import BaseModel


class TriggerReq(BaseModel):
    action: str  # run | inject | restore


@app.post("/api/run/trigger")
def trigger(req: TriggerReq):
    """Action: start an allowlisted job. The only writes the cockpit makes."""
    ids = _resolve_ids()["jobs"]
    try:
        if req.action == "run":
            jid = ids.get(RUN_JOBS["overnight"])
            run = w().jobs.run_now(jid)
        elif req.action in ("inject", "restore"):
            jid = ids.get(RUN_JOBS["bad_feed"])
            run = w().jobs.run_now(jid, job_parameters={"action": req.action})
        else:
            return {"error": "unknown action"}
        return {"ok": True, "url": f"{HOST}/jobs/{jid}/runs/{run.run_id}"}
    except Exception:
        return {"error": "Could not start the job — does the app have CAN_MANAGE_RUN on it?"}


class AskReq(BaseModel):
    question: str


@app.post("/api/ask")
def ask(req: AskReq):
    """Proxy to the LifeCast — Run health Genie space. Nothing is computed here;
    the overseer is the real Genie agent, rendered verbatim."""
    import time as _time

    sid = _resolve_ids().get("genie_runhealth")
    if not sid:
        return {"error": "Run-health Genie space not found — run the foundation job's genie task."}
    try:
        start = w().api_client.do("POST", f"/api/2.0/genie/spaces/{sid}/start-conversation",
                                  body={"content": req.question[:500]})
        cid, mid = start["conversation_id"], start["message_id"]
        for _ in range(40):
            msg = w().api_client.do("GET", f"/api/2.0/genie/spaces/{sid}/conversations/{cid}/messages/{mid}")
            if msg.get("status") in ("COMPLETED", "FAILED"):
                break
            _time.sleep(3)
        if msg.get("status") != "COMPLETED":
            return {"error": "The overseer didn't answer in time — open the Genie space directly."}
        out = {"texts": [], "sql": None, "table": None}
        for a in msg.get("attachments", []):
            if "text" in a:
                out["texts"].append(a["text"].get("content", ""))
            if "query" in a:
                out["sql"] = a["query"].get("query")
                if a["query"].get("description"):
                    out["texts"].insert(0, a["query"]["description"])
                try:
                    qr = w().api_client.do(
                        "GET",
                        f"/api/2.0/genie/spaces/{sid}/conversations/{cid}/messages/{mid}"
                        f"/attachments/{a['attachment_id']}/query-result")
                    sr = qr.get("statement_response", {})
                    cols = [c["name"] for c in sr.get("manifest", {}).get("schema", {}).get("columns", [])]
                    rows = (sr.get("result", {}) or {}).get("data_array", [])[:20]
                    if cols:
                        out["table"] = {"columns": cols, "rows": rows}
                except Exception:
                    pass
        return out
    except Exception:
        return {"error": "Could not reach the overseer — does the app have access to the Genie space?"}


# Read-only file previews — the actual exported artifacts, first rows only.
# Still a thin layer: display, never edit; download stays in the workspace.
PREVIEW_FILES = {
    "mpf": {"dir": "export/model_point_file", "title": "Model point file",
            "note": "The exact file the existing actuarial engine ingests — produced by the export step, unchanged in layout."},
    "validation": {"dir": "export/validation", "title": "Validation extract (Excel-ready)",
                   "note": "The read-only policy-level extract for the actuary's eyeball check — open it in Excel from the volume."},
}


@app.get("/api/file/{key}")
def file_preview(key: str, rows: int = 60):
    import csv
    import io

    spec = PREVIEW_FILES.get(key)
    if not spec:
        return {"error": "unknown file"}
    base = f"/Volumes/{CATALOG}/{SCHEMA}/lifecast_files/{spec['dir']}"
    try:
        entries = [e for e in w().files.list_directory_contents(base)
                   if (e.name or "").endswith(".csv")]
        entries.sort(key=lambda e: e.last_modified or 0, reverse=True)
        if not entries:
            return {"error": f"No file in {spec['dir']} yet — run the overnight job."}
        f = entries[0]
        raw = w().files.download(f.path).contents.read(1_000_000).decode("utf-8", "replace")
        lines = raw.splitlines()
        if not raw.endswith("\n") and len(lines) > 1:
            lines = lines[:-1]  # drop a possibly-truncated last line
        reader = list(csv.reader(io.StringIO("\n".join(lines[: rows + 1]))))
        import datetime
        mod = datetime.datetime.fromtimestamp((f.last_modified or 0) / 1000).strftime("%d %b %Y %H:%M")
        return {"title": spec["title"], "note": spec["note"], "name": f.name,
                "modified": mod, "size_kb": round((f.file_size or 0) / 1024),
                "columns": reader[0] if reader else [],
                "rows": reader[1:], "truncated": True,
                "volume_url": resolve_link("vol:export" if key == "mpf" else "vol:"),
                "keys": [{"key": k, "title": v["title"]} for k, v in PREVIEW_FILES.items()]}
    except Exception:
        return {"error": "Preview unavailable — does the app have READ VOLUME on lifecast_files?"}


@app.get("/api/governance")
def governance():
    """The record for the governed process — read-only, straight from the tables."""
    T = f"`{CATALOG}`.`{SCHEMA}`"
    runs, error = [], None
    try:
        r = w().statement_execution.execute_statement(
            statement=f"""
                SELECT date_format(q.run_ts,'dd MMM yyyy HH:mm') AS run,
                       q.verdict, q.rows_bronze, q.rows_silver, q.rows_quarantined,
                       round(100*q.quarantine_rate,2) AS quarantine_pct,
                       q.assumption_set_id, q.rule_breakdown,
                       coalesce(s.signed_off_by, '—') AS signed_off_by,
                       q.valuation_date, q.policies_in_scope, q.model_points,
                       q.movement_policies_pct, q.movement_sa_pct,
                       coalesce(q.movement_check,'—') AS movement_check,
                       coalesce(q.grouping_check,'—') AS grouping_check
                FROM {T}.gld_run_quality q
                LEFT JOIN {T}.gld_run_signoff s
                  ON q.job_run_id = s.job_run_id AND q.run_ts = s.run_ts
                ORDER BY q.run_ts DESC LIMIT 15""",
            warehouse_id=WAREHOUSE_ID, wait_timeout="30s")
        cols = [c.name for c in r.manifest.schema.columns]
        runs = [dict(zip(cols, row)) for row in (r.result.data_array or [])]
    except Exception as e:
        error = "Run history unavailable — has the overnight run executed, and does the app have SELECT on the schema?"
    inventory = [{"what": i["what"],
                  "where": {"label": i["where"][0], "url": resolve_link(i["where"][1])},
                  "why": i["why"]} for i in GOVERNANCE_INVENTORY]
    return {"scope": GOVERNANCE_SCOPE, "runs": runs, "error": error, "inventory": inventory}


@app.get("/")
def index():
    # no-cache: the UI iterates fast — browsers must revalidate, not reuse.
    return FileResponse(
        os.path.join(os.path.dirname(__file__), "static", "index.html"),
        headers={"Cache-Control": "no-cache"},
    )
