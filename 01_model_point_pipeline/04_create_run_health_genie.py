# Databricks notebook source
# MAGIC %md
# MAGIC # LifeCast — run health overseer (Genie space, create if missing)
# MAGIC
# MAGIC The plain-English overseer for the model point runs — the agent behind the
# MAGIC Cockpit's Management tab. It answers "did last night's run complete, was
# MAGIC anything quarantined, is it safe to release?" straight from the governed
# MAGIC record: run verdicts, control totals, quarantine reasons, sign-offs.
# MAGIC
# MAGIC Idempotent: skips creation if a space with this title exists. Run by the
# MAGIC foundation job (setup, not demo path).

# COMMAND ----------

# Default catalog for interactive use (jobs always pass ${var.catalog}).
# Porting to another workspace: change once here or via sed across notebooks.
dbutils.widgets.text("catalog", "lr_dev_aws_us_catalog")
CATALOG = dbutils.widgets.get("catalog")
assert CATALOG, "Pass the target catalog via the `catalog` job parameter / widget."

SCHEMA = "lifecast"
FOLDER = "/Workspace/Shared/lifecast/01_model_point_pipeline"
TITLE = "LifeCast — Run health"

# data_sources.tables MUST be sorted by identifier (API quirk).
TABLES = sorted([
    f"{CATALOG}.{SCHEMA}.gld_run_quality",
    f"{CATALOG}.{SCHEMA}.gld_run_signoff",
    f"{CATALOG}.{SCHEMA}.slv_policies_quarantine",
    f"{CATALOG}.{SCHEMA}.gld_model_points",
    f"{CATALOG}.{SCHEMA}.gld_run_audit",
])

DESCRIPTION = (
    "The run-health overseer for the Bricksurance Life model point process. Answers: did the "
    "latest run complete and was it GREEN; how many rows were quarantined and which quality "
    "rules they failed; do control totals (policy count, sum assured) reconcile against the "
    "previous run; who signed off; is it safe to release the model point file. Verdicts live "
    "in gld_run_quality (one row per run: verdict, valuation_date, policies_in_scope, "
    "movement and grouping checks, rule_breakdown JSON). Sign-offs in gld_run_signoff. "
    "Rejected rows with their failed_rules in slv_policies_quarantine. When asked to draft a "
    "sign-off note, summarise the latest run's verdict, volumes, checks and basis in two or "
    "three sentences. Synthetic demo data — Bricksurance Life is fictional."
)

# COMMAND ----------

import json

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

serialized = json.dumps(
    {"version": 2, "data_sources": {"tables": [{"identifier": t} for t in TABLES]}})

existing = w.api_client.do("GET", "/api/2.0/genie/spaces").get("spaces", [])
match = [s for s in existing if s.get("title") == TITLE]
if match:
    # Update in place so the table list and description never drift from this
    # script (PATCH replaces the serialized space — table list is owned here).
    space_id = match[0]["space_id"]
    w.api_client.do("PATCH", f"/api/2.0/genie/spaces/{space_id}",
                    body={"description": DESCRIPTION, "serialized_space": serialized})
    print(f"Genie space already exists: {space_id} — updated tables + description.")
else:
    warehouses = list(w.warehouses.list())
    wh = next((x for x in warehouses if x.enable_serverless_compute), warehouses[0])
    body = {
        "title": TITLE,
        "description": DESCRIPTION,
        "warehouse_id": wh.id,
        "parent_path": FOLDER,
        "serialized_space": serialized,
    }
    resp = w.api_client.do("POST", "/api/2.0/genie/spaces", body=body)
    space_id = resp["space_id"]
    print(f"Created Genie space: {space_id} (warehouse {wh.name})")

host = w.config.host.rstrip("/")
print(f"Open: {host}/genie/rooms/{space_id}")
