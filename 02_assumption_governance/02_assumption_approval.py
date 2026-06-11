# Databricks notebook source
# MAGIC %md
# MAGIC # LifeCast — Phase 2: assumption approval (the checker step)
# MAGIC
# MAGIC The approval action on a PENDING_APPROVAL basis:
# MAGIC
# MAGIC - **approve** — the set becomes APPROVED, the previous APPROVED basis becomes
# MAGIC   SUPERSEDED, both actions land in the audit log. Every consumer of
# MAGIC   `asm_*_active()` switches to the new basis at that instant.
# MAGIC - **reject** — the set becomes REJECTED with the checker's note; the current
# MAGIC   basis stays in force.
# MAGIC
# MAGIC In a client setting the checker is a separate principal enforced with UC grants
# MAGIC (EXECUTE on this job / MODIFY on `asm_` tables for the approvers group only);
# MAGIC the demo runs single-user, so maker/checker separation is by action, not identity.

# COMMAND ----------

# Default catalog for interactive use (jobs always pass ${var.catalog}).
# Porting to another workspace: change once here or via sed across notebooks.
dbutils.widgets.text("catalog", "lr_dev_aws_us_catalog")
dbutils.widgets.text("assumption_set_id", "latest_pending")
dbutils.widgets.dropdown("decision", "approve", ["approve", "reject"])
dbutils.widgets.text("note", "Reviewed against experience analysis — pack attached in client setting.")
CATALOG = dbutils.widgets.get("catalog")
assert CATALOG, "Pass the target catalog via the `catalog` job parameter / widget."
SET_ID = dbutils.widgets.get("assumption_set_id")
DECISION = dbutils.widgets.get("decision")
NOTE = dbutils.widgets.get("note").replace("'", "’")

SCHEMA = "lifecast"
T = f"`{CATALOG}`.`{SCHEMA}`"

# COMMAND ----------

if SET_ID == "latest_pending":
    row = spark.sql(f"""
        SELECT assumption_set_id FROM {T}.asm_assumption_sets
        WHERE status = 'PENDING_APPROVAL' ORDER BY submitted_at DESC LIMIT 1
    """).first()
    assert row, "No PENDING_APPROVAL basis found — run lifecast_assumption_entry first."
    SET_ID = row[0]

status = spark.sql(
    f"SELECT status FROM {T}.asm_assumption_sets WHERE assumption_set_id = '{SET_ID}'"
).first()
assert status, f"Assumption set {SET_ID} not found."
assert status[0] == "PENDING_APPROVAL", f"Set {SET_ID} is {status[0]}, not PENDING_APPROVAL."

print(f"{DECISION.upper()} on {SET_ID}")

# COMMAND ----------

if DECISION == "approve":
    superseded = spark.sql(
        f"SELECT assumption_set_id FROM {T}.asm_assumption_sets WHERE status = 'APPROVED'"
    ).collect()
    spark.sql(f"UPDATE {T}.asm_assumption_sets SET status = 'SUPERSEDED' WHERE status = 'APPROVED'")
    spark.sql(f"""
        UPDATE {T}.asm_assumption_sets
        SET status = 'APPROVED', approved_by = current_user(), approved_at = current_timestamp()
        WHERE assumption_set_id = '{SET_ID}'
    """)
    for s in superseded:
        spark.sql(f"""
            INSERT INTO {T}.asm_approval_log VALUES
            (current_timestamp(), '{s[0]}', 'SUPERSEDE', current_user(),
             'Superseded by {SET_ID}.')
        """)
    spark.sql(f"""
        INSERT INTO {T}.asm_approval_log VALUES
        (current_timestamp(), '{SET_ID}', 'APPROVE', current_user(), '{NOTE}')
    """)
    print(f"{SET_ID} APPROVED; superseded: {[s[0] for s in superseded]}")
    print("asm_*_active() now resolves to the new basis for every consumer.")
else:
    spark.sql(f"""
        UPDATE {T}.asm_assumption_sets
        SET status = 'REJECTED', approved_by = current_user(), approved_at = current_timestamp()
        WHERE assumption_set_id = '{SET_ID}'
    """)
    spark.sql(f"""
        INSERT INTO {T}.asm_approval_log VALUES
        (current_timestamp(), '{SET_ID}', 'REJECT', current_user(), '{NOTE}')
    """)
    print(f"{SET_ID} REJECTED — the current approved basis stays in force.")

# COMMAND ----------

display(spark.sql(f"""
    SELECT assumption_set_id, version, basis_name, status, submitted_by, approved_by, note
    FROM {T}.asm_governance_dashboard
"""))
