# Databricks notebook source
# MAGIC %md
# MAGIC # LifeCast — Phase 3: AI/BI dashboard (create or update)
# MAGIC
# MAGIC Publishes the **`LifeCast — BEL Movement`** Lakeview dashboard into this use-case
# MAGIC folder, reading the governed results layer live. Idempotent: re-running updates
# MAGIC the same dashboard in place. The SQL warehouse is resolved at runtime (serverless
# MAGIC preferred) — nothing hardcoded, portable with the bundle.

# COMMAND ----------

# Default catalog for interactive use (jobs always pass ${var.catalog}).
# Porting to another workspace: change once here or via sed across notebooks.
dbutils.widgets.text("catalog", "lr_dev_aws_us_catalog")
CATALOG = dbutils.widgets.get("catalog")
assert CATALOG, "Pass the target catalog via the `catalog` job parameter / widget."

SCHEMA = "lifecast"
T = f"{CATALOG}.{SCHEMA}"
FOLDER = "/Workspace/Shared/lifecast/03_results_and_genie"
NAME = "LifeCast — BEL Movement"

# COMMAND ----------

import json

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

warehouses = list(w.warehouses.list())
assert warehouses, "No SQL warehouse available in this workspace."
wh = next((x for x in warehouses if x.enable_serverless_compute), warehouses[0])
print(f"Using warehouse: {wh.name} ({wh.id})")

# COMMAND ----------

LATEST = f"(SELECT MAX(reporting_period) FROM {T}.gld_results_by_product)"

datasets = [
    {"name": "trend", "displayName": "BEL trend",
     "queryLines": [f"SELECT reporting_period, product_line, CAST(bel/1e6 AS DOUBLE) AS bel_m "
                    f"FROM {T}.gld_results_by_product ORDER BY reporting_period"]},
    {"name": "latest_total", "displayName": "Latest BEL",
     "queryLines": [f"SELECT CAST(SUM(bel)/1e6 AS DOUBLE) AS bel_m FROM {T}.gld_results_by_product "
                    f"WHERE reporting_period = {LATEST}"]},
    {"name": "movement", "displayName": "Movement by product",
     "queryLines": [f"SELECT product_line, CAST(bel_movement/1e6 AS DOUBLE) AS movement_m, movement_pct "
                    f"FROM {T}.gld_bel_movement WHERE reporting_period = {LATEST}"]},
    {"name": "movement_total", "displayName": "Total movement",
     "queryLines": [f"SELECT CAST(SUM(bel_movement)/1e6 AS DOUBLE) AS movement_m "
                    f"FROM {T}.gld_bel_movement WHERE reporting_period = {LATEST}"]},
    {"name": "board", "displayName": "Board pack",
     "queryLines": [f"SELECT reporting_period, product_line, CAST(bel/1e6 AS DOUBLE) AS bel_m, "
                    f"CAST(bel_movement/1e6 AS DOUBLE) AS movement_m, movement_pct, policy_count "
                    f"FROM {T}.gld_bel_movement ORDER BY reporting_period DESC, product_line"]},
    {"name": "sensitivity", "displayName": "Rate risk",
     "queryLines": [f"SELECT age_band, term_band, CAST(dv100_up/1e6 AS DOUBLE) AS dv100_up_m "
                    f"FROM {T}.gld_bel_sensitivity ORDER BY age_band, term_band"]},
    {"name": "concentration", "displayName": "Concentration",
     "queryLines": [f"SELECT rank, cum_share_pct FROM {T}.gld_bel_concentration ORDER BY rank"]},
    {"name": "cohort_movers", "displayName": "Cohort movers",
     "queryLines": [f"SELECT product_line, cohort_year, CAST(bel/1e6 AS DOUBLE) AS bel_m, "
                    f"CAST(bel_movement/1e6 AS DOUBLE) AS movement_m, movement_pct "
                    f"FROM {T}.gld_movement_by_cohort "
                    f"WHERE reporting_period = (SELECT MAX(reporting_period) FROM {T}.gld_movement_by_cohort) "
                    f"AND bel_movement IS NOT NULL ORDER BY ABS(bel_movement) DESC LIMIT 12"]},
    {"name": "audit", "displayName": "Run audit",
     "queryLines": [f"SELECT reporting_period, run_id, engine_run_at, engine_run_by, model_point_file, "
                    f"input_gate_verdict, assumption_set_id, basis_version, basis_approved_by, "
                    f"curve_date, minutes_to_queryable "
                    f"FROM {T}.gld_run_audit ORDER BY engine_run_at DESC"]},
]


def widget(name, dataset, fields, spec, x, y, wd, h):
    return {
        "widget": {
            "name": name,
            "queries": [{"name": "main_query", "query": {
                "datasetName": dataset,
                "fields": [{"name": f, "expression": f"`{f}`"} for f in fields],
                "disaggregated": True,
            }}],
            "spec": spec,
        },
        "position": {"x": x, "y": y, "width": wd, "height": h},
    }


def counter(title, field):
    return {"version": 2, "widgetType": "counter",
            "frame": {"showTitle": True, "title": title},
            "encodings": {"value": {"fieldName": field, "displayName": title}}}


layout = [
    {"widget": {"name": "header", "textbox_spec":
        "## Bricksurance Life — results & BEL movement\n"
        "Governed results layer (`gld_results_by_product` / `gld_bel_movement`). "
        "*About this demo: Bricksurance Life is fictional; all figures are synthetic and illustrative.*"},
     "position": {"x": 0, "y": 0, "width": 6, "height": 2}},
    widget("c_bel", "latest_total", ["bel_m"], counter("Total BEL, latest quarter (£m)", "bel_m"), 0, 2, 3, 3),
    widget("c_mvmt", "movement_total", ["movement_m"], counter("BEL movement QoQ (£m)", "movement_m"), 3, 2, 3, 3),
    widget("ch_trend", "trend", ["reporting_period", "product_line", "bel_m"],
           {"version": 3, "widgetType": "line",
            "frame": {"showTitle": True, "title": "BEL by quarter and product line (£m)"},
            "encodings": {
                "x": {"fieldName": "reporting_period", "scale": {"type": "categorical"}, "displayName": "Quarter"},
                "y": {"fieldName": "bel_m", "scale": {"type": "quantitative"}, "displayName": "BEL (£m)"},
                "color": {"fieldName": "product_line", "scale": {"type": "categorical"}, "displayName": "Product"},
            }}, 0, 5, 3, 6),
    widget("ch_mvmt", "movement", ["product_line", "movement_m"],
           {"version": 3, "widgetType": "bar",
            "frame": {"showTitle": True, "title": "BEL movement, latest quarter (£m)"},
            "encodings": {
                "x": {"fieldName": "product_line", "scale": {"type": "categorical"}, "displayName": "Product"},
                "y": {"fieldName": "movement_m", "scale": {"type": "quantitative"}, "displayName": "Movement (£m)"},
            }}, 3, 5, 3, 6),
    widget("tbl_board", "board",
           ["reporting_period", "product_line", "bel_m", "movement_m", "movement_pct", "policy_count"],
           # Table widgets: version 2, columns carry ONLY fieldName + displayName
           # (anything else -> "Visualization has no fields selected").
           {"version": 2, "widgetType": "table",
            "frame": {"showTitle": True, "title": "Board pack — all quarters"},
            "encodings": {"columns": [
                {"fieldName": "reporting_period", "displayName": "Quarter"},
                {"fieldName": "product_line", "displayName": "Product line"},
                {"fieldName": "bel_m", "displayName": "BEL (£m)"},
                {"fieldName": "movement_m", "displayName": "Movement (£m)"},
                {"fieldName": "movement_pct", "displayName": "Movement %"},
                {"fieldName": "policy_count", "displayName": "Policies"},
            ]}}, 0, 11, 6, 6),
]

layout2 = [
    {"widget": {"name": "header2", "textbox_spec":
        "## Risk & audit — the questions behind the number\n"
        "Rate risk from the engine's own ±100bp runs; concentration and cohort drill from the "
        "per-model-point detail; and the audit trail — which file, which basis, who, when — for every run. "
        "*Synthetic and illustrative.*"},
     "position": {"x": 0, "y": 0, "width": 6, "height": 2}},
    widget("ch_sens", "sensitivity", ["age_band", "term_band", "dv100_up_m"],
           {"version": 3, "widgetType": "bar",
            "frame": {"showTitle": True, "title": "BEL change for +100bp, by age band and outstanding term (£m)"},
            "encodings": {
                "x": {"fieldName": "age_band", "scale": {"type": "categorical"}, "displayName": "Attained age"},
                "y": {"fieldName": "dv100_up_m", "scale": {"type": "quantitative"}, "displayName": "ΔBEL +100bp (£m)"},
                "color": {"fieldName": "term_band", "scale": {"type": "categorical"}, "displayName": "Outstanding term"},
            }}, 0, 2, 3, 6),
    widget("ch_conc", "concentration", ["rank", "cum_share_pct"],
           {"version": 3, "widgetType": "line",
            "frame": {"showTitle": True, "title": "Concentration — cumulative share of |BEL| by ranked model point"},
            "encodings": {
                "x": {"fieldName": "rank", "scale": {"type": "quantitative"}, "displayName": "Model point rank"},
                "y": {"fieldName": "cum_share_pct", "scale": {"type": "quantitative"}, "displayName": "Cumulative share (%)"},
            }}, 3, 2, 3, 6),
    widget("tbl_movers", "cohort_movers",
           ["product_line", "cohort_year", "bel_m", "movement_m", "movement_pct"],
           {"version": 2, "widgetType": "table",
            "frame": {"showTitle": True, "title": "Largest cohort-level movers, latest quarter"},
            "encodings": {"columns": [
                {"fieldName": "product_line", "displayName": "Product line"},
                {"fieldName": "cohort_year", "displayName": "Cohort"},
                {"fieldName": "bel_m", "displayName": "BEL (£m)"},
                {"fieldName": "movement_m", "displayName": "Movement (£m)"},
                {"fieldName": "movement_pct", "displayName": "Movement %"},
            ]}}, 0, 8, 6, 5),
    widget("tbl_audit", "audit",
           ["reporting_period", "run_id", "engine_run_at", "engine_run_by", "model_point_file",
            "input_gate_verdict", "assumption_set_id", "basis_version", "basis_approved_by",
            "curve_date", "minutes_to_queryable"],
           {"version": 2, "widgetType": "table",
            "frame": {"showTitle": True, "title": "Run audit — every number carries its papers"},
            "encodings": {"columns": [
                {"fieldName": "reporting_period", "displayName": "Quarter"},
                {"fieldName": "run_id", "displayName": "Engine run"},
                {"fieldName": "engine_run_at", "displayName": "Run at"},
                {"fieldName": "engine_run_by", "displayName": "Run by"},
                {"fieldName": "model_point_file", "displayName": "Input file"},
                {"fieldName": "input_gate_verdict", "displayName": "Input gate"},
                {"fieldName": "assumption_set_id", "displayName": "Basis"},
                {"fieldName": "basis_version", "displayName": "Basis v"},
                {"fieldName": "basis_approved_by", "displayName": "Basis approved by"},
                {"fieldName": "curve_date", "displayName": "Curve"},
                {"fieldName": "minutes_to_queryable", "displayName": "Mins to queryable"},
            ]}}, 0, 13, 6, 5),
]

serialized = json.dumps({
    "datasets": datasets,
    "pages": [
        {"name": "results", "displayName": "Results", "layout": layout},
        {"name": "risk_audit", "displayName": "Risk & audit", "layout": layout2},
    ],
})

# COMMAND ----------

from databricks.sdk.service.dashboards import Dashboard

existing_id = None
for obj in w.workspace.list(FOLDER):
    if obj.object_type and obj.object_type.value == "DASHBOARD" and NAME in (obj.path or ""):
        existing_id = obj.resource_id
        break

if existing_id:
    dash = w.lakeview.update(existing_id, Dashboard(
        display_name=NAME, warehouse_id=wh.id, serialized_dashboard=serialized))
    print(f"Updated dashboard {dash.dashboard_id}")
else:
    dash = w.lakeview.create(Dashboard(
        display_name=NAME, parent_path=FOLDER, warehouse_id=wh.id, serialized_dashboard=serialized))
    print(f"Created dashboard {dash.dashboard_id}")

w.lakeview.publish(dash.dashboard_id, embed_credentials=True, warehouse_id=wh.id)
host = w.config.host.rstrip("/")
print(f"Published: {host}/dashboardsv3/{dash.dashboard_id}/published")
