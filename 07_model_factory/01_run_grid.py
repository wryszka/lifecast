# Databricks notebook source
# MAGIC %md
# MAGIC # LifeCast — the model factory, part 2: run it from Unity, across the grid
# MAGIC
# MAGIC The model lives in Unity Catalog now — so *running* it is a read, not a
# MAGIC deployment. This notebook loads **`@champion` straight from the registry** and
# MAGIC fans the governed model point book out across a compute grid.
# MAGIC
# MAGIC The point to land: **the grid is a parameter, not a procurement.** `grid_size`
# MAGIC is a job parameter — 10 for the demo, 100 when the book is real, and nothing
# MAGIC else about the run changes. Serverless allocates what the number implies and
# MAGIC releases it when the run ends.
# MAGIC
# MAGIC Run by job `lifecast_model_factory` (after part 1).

# COMMAND ----------

# Default catalog for interactive use (jobs always pass ${var.catalog}).
# Porting to another workspace: change once here or via sed across notebooks.
dbutils.widgets.text("catalog", "lr_dev_aws_us_catalog")
dbutils.widgets.text("grid_size", "10")        # partitions to fan out across
dbutils.widgets.text("replication", "100")     # book multiplier for the timing runs
CATALOG = dbutils.widgets.get("catalog")
assert CATALOG, "Pass the target catalog via the `catalog` job parameter / widget."
GRID = int(dbutils.widgets.get("grid_size"))
REPL = int(dbutils.widgets.get("replication"))

SCHEMA = "lifecast"
FQ = f"`{CATALOG}`.`{SCHEMA}`"
MODEL_NAME = f"{CATALOG}.{SCHEMA}.lifecast_engine_model"

# COMMAND ----------

# MAGIC %md ## 1 · Load the champion — from the registry, by alias
# MAGIC No wheel, no copy-paste, no "which version is Susan running". The alias is the
# MAGIC single answer to "what does production use", and the registry records who
# MAGIC promoted it and on what evidence (part 1's comparison gate).

# COMMAND ----------

import mlflow
from mlflow import MlflowClient

mlflow.set_registry_uri("databricks-uc")
client = MlflowClient()
champ = client.get_model_version_by_alias(MODEL_NAME, "champion")
MODEL_URI = f"models:/{MODEL_NAME}/{champ.version}"
creator = getattr(champ, "created_by", None) or getattr(champ, "user_id", None) or "on record"
print(f"Champion: {MODEL_NAME} v{champ.version} (created by {creator})")

INPUT_COLS = ["mp_num", "age_attained", "sex", "smoker_status", "dur_if_y",
              "outstanding_term_years", "init_pols_if", "annual_premium", "sum_assured"]
RESULT_TYPE = ("mp_num int, pv_premiums double, pv_claims double, "
               "pv_expenses double, bel double")

score = mlflow.pyfunc.spark_udf(spark, MODEL_URI, result_type=RESULT_TYPE,
                                env_manager="local")

# COMMAND ----------

# MAGIC %md ## 2 · Score the governed book from Unity — and prove it's the same number
# MAGIC The model reads `gld_model_points` (the same table everything else reads) and
# MAGIC the result reconciles to the engine's own output for the same valuation date —
# MAGIC one number, whichever path produced it.

# COMMAND ----------

from pyspark.sql import functions as F

book = (spark.table(f"{FQ}.gld_model_points")
        .where(f"valuation_date = (SELECT MAX(valuation_date) FROM {FQ}.gld_model_points)")
        .select(*[F.col(c).cast("double").alias(c) if c == "annual_premium" else F.col(c)
                  for c in INPUT_COLS]))
n_mps = book.count()

scored = (book.repartition(GRID)
          .withColumn("r", score(F.struct(*[F.col(c) for c in INPUT_COLS])))
          .select("mp_num", "r.pv_premiums", "r.pv_claims", "r.pv_expenses", "r.bel")
          .withColumn("model_name", F.lit(MODEL_NAME))
          .withColumn("model_version", F.lit(int(champ.version)))
          .withColumn("grid_size", F.lit(GRID))
          .withColumn("_scored_at", F.current_timestamp()))

scored.write.mode("overwrite").option("overwriteSchema", "true") \
    .saveAsTable(f"{FQ}.gld_factory_results")
spark.sql(f"COMMENT ON TABLE {FQ}.gld_factory_results IS "
          "'Valuation of the governed model point book by the UC-registered model "
          "(lifecast_engine_model @champion) — results stamped with the model version "
          "that produced them.'")

bel_model = spark.table(f"{FQ}.gld_factory_results").agg(F.sum("bel")).first()[0]
bel_engine = spark.sql(f"""
    SELECT SUM(bel) FROM {FQ}.slv_engine_mp_results
    WHERE valuation_date = (SELECT MAX(valuation_date) FROM {FQ}.slv_engine_mp_results)
""").first()[0]
print(f"{n_mps:,} model points scored on a grid of {GRID}.")
print(f"BEL — model from Unity: £{bel_model/1e6:,.2f}m · engine dump: £{bel_engine/1e6:,.2f}m "
      f"(Δ £{abs(bel_model-bel_engine):,.2f})")

# COMMAND ----------

# MAGIC %md ## 3 · The scale knob — the book ×100, grid 10 vs grid 100
# MAGIC The grouped book is small, so for the timing story we scale it up to
# MAGIC seriatim-like volume (the replicated rows are distinct model points as far as
# MAGIC the grid cares). The only thing that changes between the two runs is **one
# MAGIC number** — and the honest reading matters: at this scale each cell carries
# MAGIC milliseconds of work, so the small grid already wins and the big one just adds
# MAGIC scheduling overhead. The knob pays off when the per-cell work is heavy —
# MAGIC seriatim books, stochastic paths, nested loops. The point isn't that 100 beats
# MAGIC 10 here; it's that moving between them is a parameter, not a project.

# COMMAND ----------

import time

big = (book.crossJoin(spark.range(REPL).withColumnRenamed("id", "_rep"))
       .withColumn("mp_num", (F.col("mp_num") * REPL + F.col("_rep")).cast("int"))
       .drop("_rep"))
n_big = big.count()

timings = []
for g in [GRID, GRID * 10]:
    t0 = time.time()
    (big.repartition(g)
        .withColumn("r", score(F.struct(*[F.col(c) for c in INPUT_COLS])))
        .select(F.sum("r.bel"))
        .collect())
    secs = round(time.time() - t0, 1)
    timings.append((n_big, g, secs))
    print(f"grid {g:>4}: {n_big:,} model points valued in {secs}s")

import pandas as pd

spark.createDataFrame(pd.DataFrame(timings, columns=["model_points", "grid_size", "seconds"])) \
    .withColumn("model_version", F.lit(int(champ.version))) \
    .withColumn("_run_at", F.current_timestamp()) \
    .write.mode("append").saveAsTable(f"{FQ}.gld_grid_timings")

# COMMAND ----------

# MAGIC %md
# MAGIC **What just happened, in the old world's terms:** a bigger run didn't mean a
# MAGIC hardware request, a queue, or an overnight slot — it meant a bigger number in
# MAGIC `grid_size`. And every row of output is stamped with the model version that
# MAGIC produced it, so the results desk's audit trail extends into the model itself.
# MAGIC
# MAGIC Part 3 takes the same model to a GPU — for the day the book is seriatim and
# MAGIC the runs are stochastic.
