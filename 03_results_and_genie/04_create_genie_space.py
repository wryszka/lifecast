# Databricks notebook source
# MAGIC %md
# MAGIC # LifeCast — Phase 3: Genie space (create if missing)
# MAGIC
# MAGIC Creates the **`LifeCast — Results`** Genie space over the governed results layer,
# MAGIC so the actuary asks *"show me BEL movement vs last quarter by product line"* and
# MAGIC gets an answer — instead of rebuilding a pivot table.
# MAGIC
# MAGIC Idempotent: skips creation if a space with this title already exists. Warehouse
# MAGIC resolved at runtime; the space lands in this use-case folder. Note: this API
# MAGIC version accepts only data sources on create — curated sample questions and
# MAGIC instructions are added in the Genie UI afterwards (suggestions in the README).

# COMMAND ----------

# Default catalog for interactive use (jobs always pass ${var.catalog}).
# Porting to another workspace: change once here or via sed across notebooks.
dbutils.widgets.text("catalog", "lr_dev_aws_us_catalog")
CATALOG = dbutils.widgets.get("catalog")
assert CATALOG, "Pass the target catalog via the `catalog` job parameter / widget."

SCHEMA = "lifecast"
FOLDER = "/Workspace/Shared/lifecast/03_results_and_genie"
TITLE = "LifeCast — Results"

# data_sources.tables MUST be sorted by identifier (API quirk).
TABLES = sorted([
    f"{CATALOG}.{SCHEMA}.gld_results_by_product",
    f"{CATALOG}.{SCHEMA}.gld_bel_movement",
    f"{CATALOG}.{SCHEMA}.gld_movement_by_cohort",
    f"{CATALOG}.{SCHEMA}.gld_bel_sensitivity",
    f"{CATALOG}.{SCHEMA}.gld_bel_concentration",
    f"{CATALOG}.{SCHEMA}.slv_projection_results",
    f"{CATALOG}.{SCHEMA}.asm_assumption_sets",
])

DESCRIPTION = (
    "Ask questions about Bricksurance Life liability results: best estimate liability (BEL) "
    "by product line and quarter, quarter-on-quarter BEL movement and what drove it, "
    "PV of premiums/claims/expenses, cohort-level drill-down, where rate risk and "
    "concentration sit (from the engine's ±100bp runs), and which governed assumption "
    "basis was approved when. Synthetic demo data — Bricksurance Life is fictional."
)

# COMMAND ----------

import json

from databricks.sdk import WorkspaceClient

w = WorkspaceClient()

existing = w.api_client.do("GET", "/api/2.0/genie/spaces").get("spaces", [])
match = [s for s in existing if s.get("title") == TITLE]
if match:
    space_id = match[0]["space_id"]
    print(f"Genie space already exists: {space_id} — skipping create.")
else:
    warehouses = list(w.warehouses.list())
    wh = next((x for x in warehouses if x.enable_serverless_compute), warehouses[0])
    body = {
        "title": TITLE,
        "description": DESCRIPTION,
        "warehouse_id": wh.id,
        "parent_path": FOLDER,
        "serialized_space": json.dumps(
            {"version": 2, "data_sources": {"tables": [{"identifier": t} for t in TABLES]}}
        ),
    }
    resp = w.api_client.do("POST", "/api/2.0/genie/spaces", body=body)
    space_id = resp["space_id"]
    print(f"Created Genie space: {space_id} (warehouse {wh.name})")

host = w.config.host.rstrip("/")
print(f"Open: {host}/genie/rooms/{space_id}")
print("\nQuestions worth asking live:")
for q in [
    "Show me BEL movement vs last quarter by product line",
    "Which product line drove the BEL increase in the latest quarter, and by how much?",
    "Plot total BEL by quarter",
    "Which cohort years contribute most to GROUP_PROTECTION BEL?",
    "Which assumption basis is currently approved and who approved it?",
]:
    print(f"  - {q}")
