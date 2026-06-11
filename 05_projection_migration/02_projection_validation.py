# Databricks notebook source
# MAGIC %md
# MAGIC # LifeCast — Phase 5: side-by-side validation
# MAGIC
# MAGIC The credibility beat: the Python projection joined to the legacy engine's
# MAGIC baseline **per model point** — same model points, same governed basis, same
# MAGIC curve. The tie-out is a gate: if any model point drifts beyond tolerance, this
# MAGIC task fails loudly and the run record says so.
# MAGIC
# MAGIC *Actuary's line: "the numbers tie out — and I wrote the product logic, so I own it."*
# MAGIC
# MAGIC Run as task 3 of `lifecast_projection_run`.

# COMMAND ----------

# Default catalog for interactive use (jobs always pass ${var.catalog}).
# Porting to another workspace: change once here or via sed across notebooks.
dbutils.widgets.text("catalog", "lr_dev_aws_us_catalog")
CATALOG = dbutils.widgets.get("catalog")
assert CATALOG, "Pass the target catalog via the `catalog` job parameter / widget."

SCHEMA = "lifecast"
FQ = f"`{CATALOG}`.`{SCHEMA}`"
VOLUME_ROOT = f"/Volumes/{CATALOG}/{SCHEMA}/lifecast_files"
TOLERANCE_GBP = 0.01  # per model point — ties out to the penny

# COMMAND ----------

import glob

import pandas as pd

baseline_files = sorted(glob.glob(f"{VOLUME_ROOT}/prophet/term_bel/LEGACY_TERM_BEL_*.csv"))
assert baseline_files, "No legacy baseline — run task 00_prophet_baseline_mock first."
baseline = pd.read_csv(baseline_files[-1])

python_run = spark.sql(f"""
    SELECT * FROM {FQ}.gld_term_projection
    WHERE run_ts = (SELECT MAX(run_ts) FROM {FQ}.gld_term_projection)
""").toPandas()
assert len(python_run), "No Python projection — run task 01_term_projection first."

joined = python_run.merge(
    baseline.rename(columns={"MPNUM": "mp_num"}), on="mp_num", how="outer", indicator=True
)
unmatched = int((joined["_merge"] != "both").sum())
joined = joined[joined["_merge"] == "both"].copy()
joined["abs_diff"] = (joined["bel"] - joined["BEL"]).abs()

max_diff = float(joined["abs_diff"].max())
within = int((joined["abs_diff"] <= TOLERANCE_GBP).sum())
within_pct = 100.0 * within / len(joined)
bel_python = float(python_run["bel"].sum())
bel_baseline = float(baseline["BEL"].sum())
verdict = "TIES_OUT" if (unmatched == 0 and within == len(joined)) else "DRIFT"

print(f"{len(joined):,} model points compared · unmatched {unmatched}")
print(f"max |diff| £{max_diff:.4f} · {within_pct:.1f}% within £{TOLERANCE_GBP} tolerance")
print(f"total BEL — python £{bel_python/1e6:,.2f}m vs legacy £{bel_baseline/1e6:,.2f}m")
print(f"VERDICT: {verdict}")

# COMMAND ----------

import datetime

import mlflow

run_ts = datetime.datetime.now()
spark.createDataFrame(
    [(run_ts, len(joined), unmatched, max_diff, within_pct, bel_python, bel_baseline,
      str(python_run["assumption_set_id"].iloc[0]), TOLERANCE_GBP, verdict)],
    "run_ts TIMESTAMP, mp_compared INT, mp_unmatched INT, max_abs_diff DOUBLE, "
    "within_tolerance_pct DOUBLE, bel_python DOUBLE, bel_baseline DOUBLE, "
    "assumption_set_id STRING, tolerance_gbp DOUBLE, verdict STRING",
).write.mode("append").saveAsTable(f"{FQ}.gld_projection_validation")

mlflow.set_experiment("/Shared/lifecast/05_projection_migration/projection")
with mlflow.start_run(run_name=f"validation_{run_ts:%Y%m%d_%H%M}"):
    mlflow.log_params({"engine_compared": "python_vs_legacy", "tolerance_gbp": TOLERANCE_GBP,
                       "assumption_set_id": str(python_run["assumption_set_id"].iloc[0])})
    mlflow.log_metrics({"max_abs_diff": max_diff, "within_tolerance_pct": within_pct,
                        "bel_python": bel_python, "bel_baseline": bel_baseline,
                        "mp_unmatched": unmatched})

if verdict != "TIES_OUT":
    worst = joined.nlargest(5, "abs_diff")[["mp_num", "bel", "BEL", "abs_diff"]]
    raise Exception(
        f"VALIDATION DRIFT — {len(joined) - within} of {len(joined)} model points beyond "
        f"£{TOLERANCE_GBP} (max £{max_diff:.4f}), {unmatched} unmatched. Worst:\n{worst.to_string(index=False)}")

print("Validation recorded in gld_projection_validation and MLflow — side by side, on the record.")
