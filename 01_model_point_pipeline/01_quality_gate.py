# Databricks notebook source
# MAGIC %md
# MAGIC # LifeCast — Phase 1: data-quality gate & sign-off
# MAGIC
# MAGIC The lightweight, real destination the Cockpit will later link to. Runs after
# MAGIC the pipeline refresh and **before** the model point file is exported:
# MAGIC
# MAGIC 1. Reads the gate metrics (bronze vs silver vs quarantine, per-rule breakdown).
# MAGIC 2. Records the run in `gld_run_quality` and exposes `gld_quality_dashboard`.
# MAGIC 3. **GREEN** → appends a sign-off row to `gld_run_signoff`; the run continues.
# MAGIC 4. **RED** → fails this task loudly, so a bad extract stops the run before
# MAGIC    the downstream model burns it.
# MAGIC
# MAGIC Sign-off is automated in Phase 1; the human approval workflow arrives with
# MAGIC Phase 2 (assumption governance).

# COMMAND ----------

# Default catalog for interactive use (jobs always pass ${var.catalog}).
# Porting to another workspace: change once here or via sed across notebooks.
dbutils.widgets.text("catalog", "lr_dev_aws_us_catalog")
CATALOG = dbutils.widgets.get("catalog")
assert CATALOG, "Pass the target catalog via the `catalog` job parameter / widget."

SCHEMA = "lifecast"
FQ = f"`{CATALOG}`.`{SCHEMA}`"

# Gate threshold: more than this share of landed rows in quarantine = RED.
QUARANTINE_RATE_RED = 0.02

# COMMAND ----------

import datetime
import json

from pyspark.sql import functions as F

MOVEMENT_TOL_PCT = 5.0   # |Δ| in policies or sum assured vs the last GREEN run

rows_bronze = spark.table(f"{FQ}.brz_policy_admin").count()
rows_silver = spark.table(f"{FQ}.slv_policies").count()
quarantine_df = spark.table(f"{FQ}.slv_policies_quarantine")
rows_quarantined = quarantine_df.count()
model_points = spark.table(f"{FQ}.gld_model_points").count()

quarantine_rate = rows_quarantined / max(rows_bronze, 1)
rule_breakdown = {
    r["rule"]: r["count"]
    for r in quarantine_df.select(F.explode("failed_rules").alias("rule"))
    .groupBy("rule")
    .count()
    .collect()
}

# Control totals over the valuation scope (in force, >= 1 year outstanding) —
# the practitioner's first daily check, now part of the gate.
scope = spark.table(f"{FQ}.slv_policies").filter(
    "policy_status = 'INFORCE' AND outstanding_term_years >= 1")
row = scope.agg(F.count("*"), F.sum("sum_assured")).first()
policies_in_scope, sum_assured_total = int(row[0]), float(row[1] or 0)

# Movement check vs the last GREEN run with totals on record. Guarded: the
# history table may predate these columns (schema evolves on next write).
try:
    prev = spark.sql(f"""
        SELECT policies_in_scope, sum_assured_total FROM {FQ}.gld_run_quality
        WHERE verdict = 'GREEN' AND policies_in_scope IS NOT NULL
        ORDER BY run_ts DESC LIMIT 1
    """).first()
except Exception:
    prev = None
if prev and prev[0]:
    movement_policies_pct = round(100.0 * (policies_in_scope - prev[0]) / prev[0], 2)
    movement_sa_pct = round(100.0 * (sum_assured_total - float(prev[1])) / float(prev[1]), 2)
    movement_check = ("PASS" if (abs(movement_policies_pct) <= MOVEMENT_TOL_PCT
                                 and abs(movement_sa_pct) <= MOVEMENT_TOL_PCT) else "BREACH")
else:
    movement_policies_pct = movement_sa_pct = None
    movement_check = "N_A"   # first run on record — nothing to reconcile against

# Grouping check: control totals must survive grouping exactly (counts) and
# within rounding (sum assured — model points carry rounded averages).
g = spark.table(f"{FQ}.gld_model_points").agg(
    F.sum("init_pols_if"), F.sum(F.col("sum_assured") * F.col("init_pols_if"))).first()
mp_policies, mp_sa_total = int(g[0] or 0), float(g[1] or 0)
sa_rel_err = abs(mp_sa_total - sum_assured_total) / max(sum_assured_total, 1)
grouping_check = "PASS" if (mp_policies == policies_in_scope and sa_rel_err < 1e-4) else "FAIL"

verdict = (
    "GREEN"
    if (quarantine_rate <= QUARANTINE_RATE_RED and rows_silver > 0 and model_points > 0
        and movement_check != "BREACH" and grouping_check == "PASS")
    else "RED"
)

print(f"bronze={rows_bronze:,}  silver={rows_silver:,}  quarantined={rows_quarantined:,} "
      f"({quarantine_rate:.2%})  model_points={model_points:,}")
print(f"scope: {policies_in_scope:,} policies, £{sum_assured_total/1e9:,.2f}bn sum assured")
print(f"movement vs last GREEN: policies {movement_policies_pct}%, SA {movement_sa_pct}% -> {movement_check}")
print(f"grouping: {policies_in_scope:,} policies -> {model_points:,} model points, "
      f"SA preserved within {sa_rel_err:.2e} -> {grouping_check}")
print(f"per-rule: {rule_breakdown}")
print(f"verdict: {verdict}")

# COMMAND ----------

# Record the gate result — every run, GREEN or RED.
try:
    ctx = json.loads(dbutils.notebook.entry_point.getDbutils().notebook().getContext().toJson())
    job_run_id = str(ctx.get("tags", {}).get("multitaskParentRunId")
                     or ctx.get("tags", {}).get("jobRunId") or "interactive")
except Exception:
    job_run_id = "interactive"

run_ts = datetime.datetime.now()

# Phase 2 tie-in: stamp the approved assumption basis onto the run record, so
# every run is reproducible — which extract AND which basis fed it.
try:
    assumption_set_id = spark.sql(f"SELECT {FQ}.asm_active_set_id()").first()[0]
except Exception:
    assumption_set_id = None  # Phase 2 assets not installed yet

quality_schema = (
    "run_ts TIMESTAMP, job_run_id STRING, rows_bronze BIGINT, rows_silver BIGINT, "
    "rows_quarantined BIGINT, model_points BIGINT, quarantine_rate DOUBLE, "
    "red_threshold DOUBLE, rule_breakdown STRING, verdict STRING, assumption_set_id STRING, "
    "valuation_date DATE, policies_in_scope BIGINT, sum_assured_total DOUBLE, "
    "movement_policies_pct DOUBLE, movement_sa_pct DOUBLE, movement_check STRING, "
    "grouping_check STRING"
)
spark.createDataFrame(
    [(run_ts, job_run_id, rows_bronze, rows_silver, rows_quarantined, model_points,
      float(quarantine_rate), QUARANTINE_RATE_RED, json.dumps(rule_breakdown), verdict,
      assumption_set_id, datetime.date.today(), policies_in_scope, sum_assured_total,
      movement_policies_pct, movement_sa_pct, movement_check, grouping_check)],
    quality_schema,
).write.mode("append").option("mergeSchema", "true").saveAsTable(f"{FQ}.gld_run_quality")

spark.sql(f"""
    CREATE OR REPLACE VIEW {FQ}.gld_quality_dashboard
    COMMENT 'Latest-first view of the quality gate history — the destination the Cockpit links to.'
    AS SELECT * FROM {FQ}.gld_run_quality ORDER BY run_ts DESC
""")

# COMMAND ----------

# GREEN -> sign off and continue. RED -> stop the run, loudly.
if verdict == "GREEN":
    signoff_schema = (
        "run_ts TIMESTAMP, job_run_id STRING, gate STRING, verdict STRING, "
        "signed_off_by STRING, note STRING"
    )
    signed_off_by = spark.sql("SELECT current_user()").first()[0]
    spark.createDataFrame(
        [(run_ts, job_run_id, "model_point_quality", verdict, signed_off_by,
          "Automated gate sign-off (Phase 1). Human approval workflow arrives with Phase 2.")],
        signoff_schema,
    ).write.mode("append").saveAsTable(f"{FQ}.gld_run_signoff")
    print(f"GREEN — signed off by {signed_off_by}. Export proceeds.")
else:
    raise Exception(
        f"QUALITY GATE RED — run stopped before export. "
        f"{rows_quarantined:,} of {rows_bronze:,} landed rows quarantined "
        f"({quarantine_rate:.2%}, threshold {QUARANTINE_RATE_RED:.2%}); "
        f"movement check {movement_check} (policies {movement_policies_pct}%, SA {movement_sa_pct}%); "
        f"grouping check {grouping_check}. "
        f"Per-rule: {json.dumps(rule_breakdown)}. "
        f"Inspect {CATALOG}.{SCHEMA}.slv_policies_quarantine; the downstream "
        f"model point file was NOT updated. Rejects are parked for repair and "
        f"resubmission — never discarded."
    )
