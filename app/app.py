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

from content import CARDS, FLOWS, PERSONAS, TILES

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
    ids: dict = {"jobs": {}, "pipelines": {}, "dashboard": None, "genie": None, "experiments": {}}
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
        flows.append({
            "id": f["id"], "eyebrow": f["eyebrow"], "title": f["title"], "story": f["story"],
            "now_intro": f["now_intro"],
            "steps": [{
                "n": s["n"], "title": s["title"], "now": s["now"], "text": s["text"],
                "code": {"label": s["code"][0], "url": resolve_link(s["code"][1])},
                "live": {"label": s["live"][0], "url": resolve_link(s["live"][1])},
            } for s in f["steps"]],
            "lever": {"text": f["lever"]["text"],
                      "links": [{"label": lbl, "url": resolve_link(k)} for lbl, k in f["lever"]["links"]]},
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
    return {"tiles": tiles, "flows": flows, "personas": personas, "host": HOST, "catalog": CATALOG}


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


@app.get("/")
def index():
    return FileResponse(os.path.join(os.path.dirname(__file__), "static", "index.html"))
