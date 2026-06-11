# Databricks notebook source
# MAGIC %md
# MAGIC # LifeCast — demo lever: bad feed day
# MAGIC
# MAGIC - **`action=inject`** — copies the bad feed file (created in Phase 0, parked in
# MAGIC   `demo/bad_feed_day/`) into the landing path. Next `lifecast_overnight_run`:
# MAGIC   quarantine fills, the gate goes **RED**, the run stops, the model point file
# MAGIC   is protected.
# MAGIC - **`action=restore`** — removes the bad file from the landing path and
# MAGIC   full-refreshes the pipeline (the bad rows are already in bronze; a full
# MAGIC   refresh re-lists the landing path without them). Next overnight run: **GREEN**.

# COMMAND ----------

dbutils.widgets.text("catalog", "")
dbutils.widgets.dropdown("action", "inject", ["inject", "restore"])
CATALOG = dbutils.widgets.get("catalog")
ACTION = dbutils.widgets.get("action")
assert CATALOG, "Pass the target catalog via the `catalog` job parameter / widget."

SCHEMA = "lifecast"
VOLUME_ROOT = f"/Volumes/{CATALOG}/{SCHEMA}/lifecast_files"
RAW_DIR = f"{VOLUME_ROOT}/raw/policy_admin"
BAD_DIR = f"{VOLUME_ROOT}/demo/bad_feed_day"
BAD_MARKER = "BAD_FEED_DAY"
PIPELINE_NAME = "lifecast_model_point_pipeline"

# COMMAND ----------

if ACTION == "inject":
    bad_files = dbutils.fs.ls(BAD_DIR)
    assert bad_files, f"No bad feed file found in {BAD_DIR} — run lifecast_synthetic_foundation first."
    for f in bad_files:
        dbutils.fs.cp(f.path, f"{RAW_DIR}/{f.name}")
        print(f"Injected: {f.name} -> {RAW_DIR}")
    print("\nNext: run lifecast_overnight_run — the quality gate will go RED and stop the run.")

# COMMAND ----------

if ACTION == "restore":
    import time

    removed = 0
    for f in dbutils.fs.ls(RAW_DIR):
        if BAD_MARKER in f.name:
            dbutils.fs.rm(f.path)
            removed += 1
            print(f"Removed from landing path: {f.name}")
    print(f"{removed} bad feed file(s) removed.")

    # Full refresh so bronze re-lists the landing path without the bad file.
    from databricks.sdk import WorkspaceClient

    w = WorkspaceClient()
    matches = [
        p for p in w.pipelines.list_pipelines(filter=f"name LIKE '%{PIPELINE_NAME}%'")
        if PIPELINE_NAME in (p.name or "")
    ]
    assert len(matches) == 1, f"Expected exactly one pipeline matching '{PIPELINE_NAME}', found {len(matches)}"
    pipeline_id = matches[0].pipeline_id

    update_id = w.pipelines.start_update(pipeline_id=pipeline_id, full_refresh=True).update_id
    print(f"Full refresh started: pipeline {pipeline_id}, update {update_id}")

    deadline = time.time() + 30 * 60
    while time.time() < deadline:
        state = w.pipelines.get_update(pipeline_id, update_id).update.state.value
        if state in ("COMPLETED", "FAILED", "CANCELED"):
            break
        time.sleep(15)
    assert state == "COMPLETED", f"Full refresh ended in state {state}"
    print("Full refresh COMPLETED.\nNext: run lifecast_overnight_run — the gate will be GREEN again.")
