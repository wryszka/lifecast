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
    f"{CATALOG}.{SCHEMA}.gld_run_audit",
])

DESCRIPTION = (
    "Ask questions about Bricksurance Life liability results: best estimate liability (BEL) "
    "by product line and quarter, quarter-on-quarter BEL movement and what drove it, "
    "PV of premiums/claims/expenses, cohort-level drill-down, where rate risk and "
    "concentration sit (from the engine's ±100bp runs), which governed assumption "
    "basis was approved when, and the full audit trail per engine run (gld_run_audit: "
    "input file, gate verdict, basis version and approver, curve date, operator). "
    "Synthetic demo data — Bricksurance Life is fictional."
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
print("\nQuestions worth asking live:")
for q in [
    "Show me BEL movement vs last quarter by product line",
    "Which product line drove the BEL increase in the latest quarter, and by how much?",
    "Plot total BEL by quarter",
    "Which cohort years contribute most to GROUP_PROTECTION BEL?",
    "Which assumption basis is currently approved and who approved it?",
    "Where is my rate risk concentrated?",
    "Who ran the latest engine run and which basis did it use?",
]:
    print(f"  - {q}")
