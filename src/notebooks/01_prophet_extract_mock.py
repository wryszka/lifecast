# Databricks notebook source
# MAGIC %md
# MAGIC # LifeCast — Phase 0: mock downstream model point extract
# MAGIC
# MAGIC The **before-state anchor**: one mock model point extract in the classic
# MAGIC fixed-column MPF shape the downstream liability model consumes today.
# MAGIC This is the format the Phase 1 pipeline must reproduce *exactly* — the
# MAGIC downstream model runs unchanged.
# MAGIC
# MAGIC Grouping and column layout here are deliberately identical to
# MAGIC `gld_model_points` + the Phase 1 export, so the two tie out row for row.
# MAGIC
# MAGIC Run as part of `lifecast_synthetic_foundation`, **before** any bad-feed
# MAGIC injection (it reads the raw landing path directly).

# COMMAND ----------

dbutils.widgets.text("catalog", "")
CATALOG = dbutils.widgets.get("catalog")
assert CATALOG, "Pass the target catalog via the `catalog` job parameter / widget."

SCHEMA = "lifecast"
VOLUME_ROOT = f"/Volumes/{CATALOG}/{SCHEMA}/lifecast_files"

# COMMAND ----------

from datetime import date
from pyspark.sql import functions as F
from pyspark.sql.window import Window

raw = (
    spark.read.option("header", True)
    .csv(f"{VOLUME_ROOT}/raw/policy_admin/")
    .select(
        "policy_id",
        F.col("dob").cast("date").alias("dob"),
        "sex",
        "smoker_status",
        F.col("sum_assured").cast("bigint").alias("sum_assured"),
        F.col("policy_term_years").cast("int").alias("policy_term_years"),
        F.col("inception_date").cast("date").alias("inception_date"),
        # DECIMAL, not DOUBLE — exact aggregation, penny-reproducible averages
        # (kept identical to the pipeline's typed view).
        F.col("annual_premium").cast("decimal(12,2)").alias("annual_premium"),
        "premium_frequency",
        "policy_status",
    )
    .filter(F.col("policy_status") == "INFORCE")
    .withColumn(
        "age_at_entry",
        F.floor(F.datediff("inception_date", "dob") / F.lit(365.25)).cast("int"),
    )
)

# COMMAND ----------

# Same grouping as gld_model_points: one model point per
# (age at entry, sex, smoker, term, premium frequency) cell.
group_cols = ["age_at_entry", "sex", "smoker_status", "policy_term_years", "premium_frequency"]

mpf = (
    raw.groupBy(*group_cols)
    .agg(
        F.count("*").alias("init_pols_if"),
        F.round(F.avg("sum_assured"), 0).cast("bigint").alias("sum_assured"),
        F.round(F.avg("annual_premium"), 2).alias("annual_premium"),
    )
    .withColumn("mp_num", F.row_number().over(Window.orderBy(*group_cols)))
    .withColumn("prod_cd", F.lit("TERM_LEVEL"))
)

# Fixed MPF column layout — keep in sync with 03_export_model_point_file.py.
mpf_pdf = (
    mpf.select(
        F.col("mp_num").alias("MPNUM"),
        F.col("prod_cd").alias("PROD_CD"),
        F.col("age_at_entry").alias("AGE_AT_ENTRY"),
        F.col("sex").alias("SEX"),
        F.col("smoker_status").alias("SMOKER_STAT"),
        F.col("policy_term_years").alias("POL_TERM_Y"),
        F.col("premium_frequency").alias("PREM_FREQ"),
        F.col("sum_assured").alias("SUM_ASSURED"),
        F.col("annual_premium").alias("ANNUAL_PREM"),
        F.col("init_pols_if").alias("INIT_POLS_IF"),
    )
    .orderBy("MPNUM")
    .toPandas()
)

# COMMAND ----------

out_dir = f"{VOLUME_ROOT}/prophet/model_point_extract"
dbutils.fs.mkdirs(out_dir)
out_path = f"{out_dir}/MPF_TERM_{date.today().strftime('%Y%m')}.csv"
mpf_pdf.to_csv(out_path, index=False)

print(f"Mock model point extract written: {out_path}")
print(f"  {len(mpf_pdf):,} model points covering {int(mpf_pdf.INIT_POLS_IF.sum()):,} in-force policies")
