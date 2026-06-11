# Databricks notebook source
# MAGIC %md
# MAGIC # LifeCast — Phase 3: AI/BI dashboard (create or update)
# MAGIC
# MAGIC Publishes the **`LifeCast — BEL Movement`** Lakeview dashboard into this use-case
# MAGIC folder, reading the governed results layer live. Idempotent: re-running updates
# MAGIC the same dashboard in place. The SQL warehouse is resolved at runtime (serverless
# MAGIC preferred) — nothing hardcoded, portable with the bundle.

# COMMAND ----------

dbutils.widgets.text("catalog", "")
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
           {"version": 1, "widgetType": "table",
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

serialized = json.dumps({
    "datasets": datasets,
    "pages": [{"name": "results", "displayName": "Results", "layout": layout}],
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
