# Databricks notebook source
# MAGIC %md
# MAGIC # LifeCast — the model factory, part 3b: run it from Unity, on a GPU
# MAGIC
# MAGIC The purest form of the whole flow: **nothing is built here.** This notebook
# MAGIC runs on serverless GPU compute (one A10, allocated for the run, gone when it
# MAGIC ends), loads the `@gpu` version of `lifecast_engine_model` **from the
# MAGIC registry**, and runs it — the class finds the CUDA device by itself.
# MAGIC
# MAGIC Three honest points, in order:
# MAGIC
# MAGIC 1. **Same numbers.** The registry version carries its frozen basis and curve;
# MAGIC    it must reproduce the champion to the penny before anything else counts.
# MAGIC 2. **Same registry.** CPU grid yesterday, GPU today — the *model* didn't
# MAGIC    change, only the compute under it.
# MAGIC 3. **When it earns its place.** At grouped-book scale a GPU is a rounding
# MAGIC    error; the timing below scales the book to seriatim-like volume, where the
# MAGIC    answer starts to change — per hot loop, never an upfront platform bet.
# MAGIC
# MAGIC **Compute:** job `lifecast_model_factory_gpu` (serverless GPU, `GPU_1xA10`), or
# MAGIC interactively with the notebook environment's **Accelerator set to A10**.

# COMMAND ----------

# Default catalog for interactive use (jobs always pass ${var.catalog}).
# Porting to another workspace: change once here or via sed across notebooks.
dbutils.widgets.text("catalog", "lr_dev_aws_us_catalog")
dbutils.widgets.text("replication", "100")   # book multiplier for the timing section
CATALOG = dbutils.widgets.get("catalog")
assert CATALOG, "Pass the target catalog via the `catalog` job parameter / widget."
REPL = int(dbutils.widgets.get("replication"))

SCHEMA = "lifecast"
FQ = f"`{CATALOG}`.`{SCHEMA}`"
MODEL_NAME = f"{CATALOG}.{SCHEMA}.lifecast_engine_model"

# COMMAND ----------

import torch

assert torch.cuda.is_available(), (
    "No GPU visible. Run via job lifecast_model_factory_gpu (serverless GPU "
    "compute), or set the notebook environment's Accelerator to A10."
)
print(f"GPU: {torch.cuda.get_device_name(0)} · torch {torch.__version__}")

# COMMAND ----------

# MAGIC %md ## 1 · Load both shapes from the registry — nothing local

# COMMAND ----------

import mlflow
import numpy as np
from mlflow import MlflowClient

mlflow.set_registry_uri("databricks-uc")
client = MlflowClient()
v_gpu = client.get_model_version_by_alias(MODEL_NAME, "gpu")
v_champ = client.get_model_version_by_alias(MODEL_NAME, "champion")

gpu_model = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}/{v_gpu.version}")
champ_model = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}/{v_champ.version}")
print(f"@gpu = v{v_gpu.version} (torch) · @champion = v{v_champ.version} (vectorised numpy) — "
      "both straight from Unity Catalog")

# COMMAND ----------

# MAGIC %md ## 2 · Gate first: penny-parity on the governed book

# COMMAND ----------

INPUT_COLS = ["mp_num", "age_attained", "sex", "smoker_status", "dur_if_y",
              "outstanding_term_years", "init_pols_if", "annual_premium", "sum_assured"]
mps = (spark.table(f"{FQ}.gld_model_points")
       .where(f"valuation_date = (SELECT MAX(valuation_date) FROM {FQ}.gld_model_points)")
       .select(*INPUT_COLS).toPandas())
mps["annual_premium"] = mps["annual_premium"].astype(float)

r_gpu = gpu_model.predict(mps)
r_cpu = champ_model.predict(mps)
cmp_df = r_cpu.merge(r_gpu, on="mp_num", suffixes=("_cpu", "_gpu"))
max_diff = float((cmp_df.bel_cpu - cmp_df.bel_gpu).abs().max())
n_breach = int(((cmp_df.bel_cpu - cmp_df.bel_gpu).abs() > 0.01).sum())
print(f"GPU vs champion on {len(mps):,} model points: max |ΔBEL| £{max_diff:.2f}, "
      f"breaches over £0.01: {n_breach}")
assert n_breach == 0, "GPU run does not reproduce the champion — stop."
print(f"Total BEL £{r_gpu.bel.sum()/1e6:,.2f}m — the same number, computed on a GPU this time.")

# COMMAND ----------

# MAGIC %md ## 3 · Where the GPU earns its place — seriatim-scale timing
# MAGIC The grouped book (~8k rows) is far too small to feed a GPU. Scaled ×100 to
# MAGIC seriatim-like volume the comparison becomes meaningful — and this is *one*
# MAGIC deterministic run; stochastic multiplies it by the path count.

# COMMAND ----------

import time

import pandas as pd

big = pd.concat([mps] * REPL, ignore_index=True)
big["mp_num"] = np.arange(len(big), dtype=np.int32)  # keep the signature's int32
print(f"Timing book: {len(big):,} model points (the grouped book ×{REPL})")

# CPU: the champion (vectorised numpy) on this same machine.
t0 = time.time(); _ = champ_model.predict(big); cpu_s = time.time() - t0

# GPU: warm-up then timed (the first CUDA call pays one-off init).
_ = gpu_model.predict(big.head(1000))
torch.cuda.synchronize()
t0 = time.time(); _ = gpu_model.predict(big); torch.cuda.synchronize()
gpu_s = time.time() - t0

print(f"CPU (champion, vectorised): {cpu_s:6.1f}s")
print(f"GPU (@gpu, A10):            {gpu_s:6.1f}s   ×{cpu_s/max(gpu_s,1e-9):,.1f}")

from pyspark.sql import functions as F

spark.createDataFrame(pd.DataFrame(
    [(len(big), "cpu_vectorised", round(cpu_s, 2), int(v_champ.version)),
     (len(big), "gpu_a10", round(gpu_s, 2), int(v_gpu.version))],
    columns=["model_points", "engine", "seconds", "model_version"])) \
    .withColumn("_run_at", F.current_timestamp()) \
    .write.mode("append").option("mergeSchema", "true").saveAsTable(f"{FQ}.gld_gpu_timings")
print("Timings recorded: gld_gpu_timings")

# COMMAND ----------

# MAGIC %md
# MAGIC **The honest close:** at grouped-book scale the CPU was already fine — the GPU
# MAGIC is for seriatim books, stochastic fan-outs and nested loops, per hot loop, on
# MAGIC compute that exists only while the run does. Nothing was deployed to get here:
# MAGIC the model came out of Unity Catalog, found a GPU under itself, and produced
# MAGIC the same number it produces everywhere else.
# MAGIC
# MAGIC *(One platform quirk, stated openly: this GPU pool can load from the registry
# MAGIC but not publish to it — so the factory packages on CPU, and the GPU runs. Build
# MAGIC anywhere, run anywhere is the point of the registry anyway.)*
