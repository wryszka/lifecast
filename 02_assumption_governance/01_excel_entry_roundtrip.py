# Databricks notebook source
# MAGIC %md
# MAGIC # LifeCast — Phase 2: assumption entry (the Excel round-trip, headless)
# MAGIC
# MAGIC Runs **exactly the SQL the Excel template submits** via `DATABRICKS.SQL`, so the
# MAGIC demo works end to end without Excel in the room. The actuary's story: *"I entered
# MAGIC a smoker loading in my workbook and pressed recalculate — the draft basis landed
# MAGIC in the governed master and went for approval."*
# MAGIC
# MAGIC Maker step only: the new basis ends **PENDING_APPROVAL**. Approval is a separate
# MAGIC action (job `lifecast_assumption_approval`) — maker and checker stay separated.
# MAGIC
# MAGIC Every statement is printed so the equivalence with the Excel formulas is visible.

# COMMAND ----------

dbutils.widgets.text("catalog", "")
dbutils.widgets.text("basis_name", "Best Estimate — smoker loading review")
dbutils.widgets.text("smoker_loading_pct", "10")
CATALOG = dbutils.widgets.get("catalog")
assert CATALOG, "Pass the target catalog via the `catalog` job parameter / widget."
BASIS_NAME = dbutils.widgets.get("basis_name")
LOADING_PCT = float(dbutils.widgets.get("smoker_loading_pct"))

SCHEMA = "lifecast"
T = f"`{CATALOG}`.`{SCHEMA}`"

# COMMAND ----------

import datetime
import uuid

active_set = spark.sql(f"SELECT {T}.asm_active_set_id()").first()[0]
assert active_set, "No APPROVED basis found — run lifecast_synthetic_foundation first."

version = spark.sql(f"SELECT MAX(version) FROM {T}.asm_assumption_sets").first()[0] + 1
set_id = f"AS_{datetime.date.today():%Y%m%d}_{uuid.uuid4().hex[:6].upper()}"
note = f"Smoker qx loading +{LOADING_PCT:g}% on basis {active_set}; lapse/expense carried unchanged."

print(f"Active basis: {active_set} -> drafting {set_id} (v{version}), smoker loading +{LOADING_PCT:g}%")

# COMMAND ----------

# The same statements the Excel 'Submit shock' sheet runs through DATABRICKS.SQL.
statements = [
    # Step 1 — draft mortality: copy the approved basis, load smoker rates.
    f"""INSERT INTO {T}.asm_mortality
        SELECT '{set_id}', age, sex, smoker_status,
               CASE WHEN smoker_status = 'S'
                    THEN LEAST(ROUND(qx * (1 + {LOADING_PCT} / 100), 6), 1.0)
                    ELSE qx END
        FROM {T}.asm_mortality_active()""",
    # Step 2 — lapse and expense carried over unchanged into the new set.
    f"""INSERT INTO {T}.asm_lapse
        SELECT '{set_id}', policy_year, lapse_rate FROM {T}.asm_lapse_active()""",
    f"""INSERT INTO {T}.asm_expense
        SELECT '{set_id}', expense_type, value, unit FROM {T}.asm_expense_active()""",
    # Step 3 — register the draft and submit it for approval.
    f"""INSERT INTO {T}.asm_assumption_sets VALUES
        ('{set_id}', {version}, '{BASIS_NAME}', 'PENDING_APPROVAL', 'EXCEL_ROUNDTRIP',
         current_user(), current_timestamp(), current_user(), current_timestamp(),
         NULL, NULL, '{note}')""",
    f"""INSERT INTO {T}.asm_approval_log VALUES
        (current_timestamp(), '{set_id}', 'CREATE', current_user(), 'Draft created from {active_set}.')""",
    f"""INSERT INTO {T}.asm_approval_log VALUES
        (current_timestamp(), '{set_id}', 'SUBMIT', current_user(), '{note}')""",
]

for stmt in statements:
    print(stmt.strip(), "\n")
    spark.sql(stmt)

print(f"Draft basis {set_id} (v{version}) is PENDING_APPROVAL.")
print("Next: run lifecast_assumption_approval (decision=approve|reject).")
