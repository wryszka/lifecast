# Databricks notebook source
# MAGIC %md
# MAGIC # LifeCast — Phase 1: model point file export
# MAGIC
# MAGIC Final task of the overnight run — only reached when the quality gate is GREEN.
# MAGIC
# MAGIC - **Model point file** → `export/model_point_file/` in the exact MPF layout of the
# MAGIC   Phase 0 mock extract. This is the file the downstream liability model picks up —
# MAGIC   **unchanged** by everything upstream.
# MAGIC - **Validation extract** → `export/validation/` — the read-only policy-level CSV for
# MAGIC   actuaries who want to eyeball the feed in Excel before a run.

# COMMAND ----------

# Default catalog for interactive use (jobs always pass ${var.catalog}).
# Porting to another workspace: change once here or via sed across notebooks.
dbutils.widgets.text("catalog", "lr_dev_aws_us_catalog")
CATALOG = dbutils.widgets.get("catalog")
assert CATALOG, "Pass the target catalog via the `catalog` job parameter / widget."

SCHEMA = "lifecast"
FQ = f"`{CATALOG}`.`{SCHEMA}`"
VOLUME_ROOT = f"/Volumes/{CATALOG}/{SCHEMA}/lifecast_files"

# COMMAND ----------

from datetime import date
from pyspark.sql import functions as F

# Fixed MPF column layout — keep in sync with 01_prophet_extract_mock.py.
mpf_pdf = (
    spark.table(f"{FQ}.gld_model_points")
    .select(
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

mpf_dir = f"{VOLUME_ROOT}/export/model_point_file"
dbutils.fs.mkdirs(mpf_dir)
mpf_path = f"{mpf_dir}/MPF_TERM_{date.today().strftime('%Y%m')}.csv"
mpf_pdf.to_csv(mpf_path, index=False)
print(f"Model point file exported: {mpf_path}")
print(f"  {len(mpf_pdf):,} model points, {int(mpf_pdf.INIT_POLS_IF.sum()):,} in-force policies")

# COMMAND ----------

# Read-only validation extract for the actuary's Excel eyeball check.
validation_pdf = (
    spark.table(f"{FQ}.slv_policies")
    .drop("_source_file", "_ingested_at", "_row_num")
    .orderBy("policy_id")
    .toPandas()
)

val_dir = f"{VOLUME_ROOT}/export/validation"
dbutils.fs.mkdirs(val_dir)
val_path = f"{val_dir}/policy_validation_extract_{date.today().strftime('%Y%m%d')}.csv"
validation_pdf.to_csv(val_path, index=False)
print(f"Validation extract exported: {val_path} ({len(validation_pdf):,} policies)")
