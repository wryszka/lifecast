# Databricks notebook source
# MAGIC %md
# MAGIC # LifeCast — the audit trail: every number carries its papers
# MAGIC
# MAGIC The question that stops a results meeting is never "what is BEL?" — it's
# MAGIC *"which basis fed that number, who approved it, and can you reproduce it?"*
# MAGIC Today answering it means an email chain. Here it is **one governed table**.
# MAGIC
# MAGIC `gld_run_audit` — one row per engine run — joins three records that already
# MAGIC exist, because everything flowed through the platform:
# MAGIC
# MAGIC | From | We get |
# MAGIC |---|---|
# MAGIC | the engine's own run log (`slv_engine_run_log`) | which model point file, which curve, who ran it, when, how long |
# MAGIC | the assumption registry (`asm_assumption_sets`) | the basis **version**, who approved it and when |
# MAGIC | the quality gate (`gld_run_quality`) | the gate verdict the input file passed before the engine ever saw it |
# MAGIC
# MAGIC Plus the consumption clock: minutes from the engine writing its files to the
# MAGIC results being queryable. And because everything is Delta, **time travel** means
# MAGIC "reproduce last quarter's number" is a `VERSION AS OF`, not an archaeology project.

# COMMAND ----------

# Default catalog for interactive use (jobs always pass ${var.catalog}).
# Porting to another workspace: change once here or via sed across notebooks.
dbutils.widgets.text("catalog", "lr_dev_aws_us_catalog")
CATALOG = dbutils.widgets.get("catalog")
assert CATALOG, "Pass the target catalog via the `catalog` job parameter / widget."

SCHEMA = "lifecast"
FQ = f"`{CATALOG}`.`{SCHEMA}`"

# COMMAND ----------

# MAGIC %md ## 1 · Build the audit record — one row per engine run

# COMMAND ----------

assert spark.table(f"{FQ}.slv_engine_run_log").count() > 0, \
    "No engine run log — run lifecast_engine_run first."

# The whole audit trail is ONE SQL statement — because every piece was already
# on the record. `gate` picks the quality-gate verdict that stood when the
# engine ran; `ingest` is the consumption clock (when detail became queryable).
spark.sql(f"""
CREATE OR REPLACE TABLE {FQ}.gld_run_audit AS
WITH gate AS (
    SELECT r.run_id,
           MAX(STRUCT(q.run_ts, q.verdict, q.movement_check, q.grouping_check)) AS g
    FROM {FQ}.slv_engine_run_log r
    LEFT JOIN {FQ}.gld_run_quality q ON q.run_ts <= r.run_ts
    GROUP BY r.run_id
),
ingest AS (
    SELECT valuation_date, MAX(_ingested_at) AS queryable_at
    FROM {FQ}.slv_engine_mp_results GROUP BY valuation_date
)
SELECT r.run_id,
       r.reporting_period,
       r.valuation_date,
       r.run_ts                AS engine_run_at,
       r.run_by                AS engine_run_by,
       r.job_run_id,
       r.mpf_file              AS model_point_file,
       r.mp_count              AS model_points,
       gate.g.verdict          AS input_gate_verdict,
       gate.g.run_ts           AS input_gate_at,
       gate.g.movement_check   AS input_movement_check,
       gate.g.grouping_check   AS input_grouping_check,
       r.assumption_set_id,
       b.version               AS basis_version,
       b.basis_name,
       b.approved_by           AS basis_approved_by,
       b.approved_at           AS basis_approved_at,
       r.curve_date,
       r.runtime_s             AS engine_runtime_s,
       r.results_file,
       r.detail_file,
       i.queryable_at,
       ROUND((UNIX_TIMESTAMP(i.queryable_at) - UNIX_TIMESTAMP(r.run_ts)) / 60.0, 1)
                               AS minutes_to_queryable
FROM {FQ}.slv_engine_run_log r
LEFT JOIN {FQ}.asm_assumption_sets b USING (assumption_set_id)
LEFT JOIN gate  ON gate.run_id = r.run_id
LEFT JOIN ingest i ON i.valuation_date = r.valuation_date
""")
spark.sql(f"COMMENT ON TABLE {FQ}.gld_run_audit IS "
          "'One row per engine run: input file, gate verdict, basis version + approver, curve, "
          "operator, timings — the reproducibility record behind every published number.'")

display(spark.sql(f"SELECT * FROM {FQ}.gld_run_audit ORDER BY engine_run_at DESC"))

# COMMAND ----------

# MAGIC %md ## 2 · The sentence that ends the meeting

# COMMAND ----------

r = spark.sql(f"SELECT * FROM {FQ}.gld_run_audit ORDER BY engine_run_at DESC LIMIT 1").first()

print(
    f"The {r.reporting_period} TERM number was produced by engine run {r.run_id} "
    f"on {r.engine_run_at:%d %b %Y at %H:%M}, run by {r.engine_run_by}.\n"
    f"It consumed {r.model_point_file} ({r.model_points:,} model points — "
    f"input gate {r.input_gate_verdict}, movement {r.input_movement_check}, "
    f"grouping {r.input_grouping_check}),\n"
    f"on basis {r.assumption_set_id} v{r.basis_version} ('{r.basis_name}'), "
    f"approved by {r.basis_approved_by} on {r.basis_approved_at:%d %b %Y}, "
    f"with the {r.curve_date} risk-free curve.\n"
    f"Results were queryable {r.minutes_to_queryable} minutes after the engine ran."
)

# COMMAND ----------

# MAGIC %md ## 3 · And if someone asks "reproduce it" — Delta time travel
# MAGIC Every table here is Delta: full change history, every write attributed, any
# MAGIC past state queryable. No restore-from-backup, no "which spreadsheet was it".

# COMMAND ----------

# MAGIC %md
# MAGIC The change history of the results layer — who/what wrote it, when:

# COMMAND ----------

history = (spark.sql(f"DESCRIBE HISTORY {FQ}.gld_run_quality")
           .selectExpr("version", "timestamp", "operation",
                       "COALESCE(userName, 'pipeline (service principal)') AS written_by")
           .limit(10))
display(history)

# COMMAND ----------

# Any past state, on demand — the table exactly as it stood N versions ago.
prev = max(0, history.agg({"version": "max"}).first()[0] - 1)
n_then = spark.sql(f"SELECT COUNT(*) FROM {FQ}.gld_run_quality VERSION AS OF {prev}").first()[0]
n_now = spark.sql(f"SELECT COUNT(*) FROM {FQ}.gld_run_quality").first()[0]
print(f"gld_run_quality VERSION AS OF {prev}: {n_then} rows · current: {n_now} rows — "
      "any published number can be re-derived from the exact state that produced it.")

# COMMAND ----------

# MAGIC %md
# MAGIC **The point to land:** none of this was *built* — it fell out of running the
# MAGIC process on a governed platform. The engine logged what it always logs; the
# MAGIC basis was approved where it's mastered; the gate recorded what it checked.
# MAGIC The audit trail is a join, not a project.
