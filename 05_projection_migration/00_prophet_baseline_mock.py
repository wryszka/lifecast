# Databricks notebook source
# MAGIC %md
# MAGIC # LifeCast — Phase 5: the engine baseline (fetched, not faked)
# MAGIC
# MAGIC The **before-state** for the side-by-side: the engine's own per-model-point
# MAGIC output for the term book. Since the estate's mock engine now runs end to end
# MAGIC (use case 03, `lifecast_engine_run`), this task simply **fetches the engine's
# MAGIC latest dump** and reshapes it into the baseline file the validation compares
# MAGIC against — exactly what you'd do with the real engine: take its output file,
# MAGIC don't re-derive it.
# MAGIC
# MAGIC Same model points, same governed basis, same curve — recorded in the file
# MAGIC itself. Run as task 1 of `lifecast_projection_run`.

# COMMAND ----------

# Default catalog for interactive use (jobs always pass ${var.catalog}).
# Porting to another workspace: change once here or via sed across notebooks.
dbutils.widgets.text("catalog", "lr_dev_aws_us_catalog")
CATALOG = dbutils.widgets.get("catalog")
assert CATALOG, "Pass the target catalog via the `catalog` job parameter / widget."

SCHEMA = "lifecast"
VOLUME_ROOT = f"/Volumes/{CATALOG}/{SCHEMA}/lifecast_files"

# COMMAND ----------

import glob
import os
from datetime import date

import pandas as pd

detail_files = sorted(glob.glob(f"{VOLUME_ROOT}/prophet/results_detail/ENGINE_MP_RESULTS_*.csv"),
                      key=os.path.getmtime)
assert detail_files, ("No engine output found — run lifecast_engine_run first (use case 03). "
                      "The baseline is the engine's own dump; we never re-derive it.")
src = detail_files[-1]
engine = pd.read_csv(src)

baseline = engine.rename(columns={"PV_PREM": "PV_PREM", "PV_CLAIM": "PV_CLAIM",
                                  "PV_EXP": "PV_EXP", "BEL": "BEL"})[
    ["MPNUM", "PV_PREM", "PV_CLAIM", "PV_EXP", "BEL"]].copy()
baseline["BASIS"] = engine["BASIS_ID"]
baseline["CURVE_DT"] = engine["CURVE_DT"]

out_dir = f"{VOLUME_ROOT}/prophet/term_bel"
dbutils.fs.mkdirs(out_dir)
path = f"{out_dir}/LEGACY_TERM_BEL_{date.today():%Y%m%d}.csv"
baseline.to_csv(path, index=False)

print(f"Engine baseline fetched from: {os.path.basename(src)}")
print(f"Baseline written: {path}")
print(f"  {len(baseline):,} model points · total BEL £{baseline.BEL.sum()/1e6:,.2f}m · "
      f"basis {baseline.BASIS.iloc[0]} · curve {baseline.CURVE_DT.iloc[0]}")
print("Next: 01_term_projection — your Python, on the same governed inputs, tied out against this file.")
