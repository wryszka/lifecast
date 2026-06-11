"""LifeCast — Phase 3: the governed results layer.

This file is the SOURCE of pipeline `lifecast_results_pipeline` — it runs
inside that pipeline (triggered by job `lifecast_results_run`), not as a
notebook.

The liability model's quarterly CSV dumps land in Delta, once, governed:

    brz_prophet_results       streaming table, Auto Loader over prophet/results/
    slv_projection_results    typed + quality expectations
    gld_results_by_product    product x quarter aggregate (Genie + dashboard)
    gld_bel_movement          adds quarter-on-quarter BEL movement

One results layer the whole team queries — no more reconciling five versions
of the board pack. UC lineage from CSV to dashboard is automatic.
"""

import dlt
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

spark = SparkSession.getActiveSession()

VOLUME_ROOT = spark.conf.get("volume_root")
RESULTS_PATH = f"{VOLUME_ROOT}/prophet/results"

RESULT_RULES = {
    "valid_period": "reporting_period RLIKE '^[0-9]{4}Q[1-4]$'",
    "valid_product": "product_line IS NOT NULL",
    "valid_bel": "bel IS NOT NULL",
    "consistent_bel": "ABS(bel - (pv_claims + pv_expenses - pv_premiums)) < 1.0",
}


@dlt.table(
    name="brz_prophet_results",
    comment="As-landed quarterly results dumps from the downstream liability model (Auto Loader over the lifecast_files volume).",
)
def brz_prophet_results():
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "csv")
        .option("header", "true")
        .load(RESULTS_PATH)
        .select(
            "*",
            F.col("_metadata.file_path").alias("_source_file"),
            F.current_timestamp().alias("_ingested_at"),
        )
    )


@dlt.table(
    name="slv_projection_results",
    comment="Typed, quality-checked projection results — one row per run x product x cohort.",
)
@dlt.expect_all_or_drop(RESULT_RULES)
def slv_projection_results():
    return spark.read.table("brz_prophet_results").select(
        "run_id",
        F.expr("try_cast(run_date AS DATE)").alias("run_date"),
        "reporting_period",
        "basis_label",
        "product_line",
        F.expr("try_cast(cohort_year AS INT)").alias("cohort_year"),
        F.expr("try_cast(policy_count AS BIGINT)").alias("policy_count"),
        F.expr("try_cast(pv_premiums AS DECIMAL(18,2))").alias("pv_premiums"),
        F.expr("try_cast(pv_claims AS DECIMAL(18,2))").alias("pv_claims"),
        F.expr("try_cast(pv_expenses AS DECIMAL(18,2))").alias("pv_expenses"),
        F.expr("try_cast(bel AS DECIMAL(18,2))").alias("bel"),
        "currency",
        "_source_file",
        "_ingested_at",
    )


@dlt.table(
    name="gld_results_by_product",
    comment="Best estimate liability and PV components by product line and reporting quarter — the governed results layer Genie and the dashboard query.",
)
def gld_results_by_product():
    return (
        spark.read.table("slv_projection_results")
        .groupBy("reporting_period", "product_line", "basis_label", "currency")
        .agg(
            F.sum("policy_count").alias("policy_count"),
            F.sum("pv_premiums").alias("pv_premiums"),
            F.sum("pv_claims").alias("pv_claims"),
            F.sum("pv_expenses").alias("pv_expenses"),
            F.sum("bel").alias("bel"),
        )
    )


@dlt.table(
    name="gld_bel_movement",
    comment="Quarter-on-quarter BEL movement by product line — the 'why did BEL move' table.",
)
def gld_bel_movement():
    w = Window.partitionBy("product_line").orderBy("reporting_period")
    return (
        spark.read.table("gld_results_by_product")
        .withColumn("bel_prev", F.lag("bel").over(w))
        .withColumn("bel_movement", F.col("bel") - F.col("bel_prev"))
        .withColumn(
            "movement_pct",
            F.round(100 * (F.col("bel") - F.col("bel_prev")) / F.abs(F.col("bel_prev")), 2),
        )
        .select(
            "reporting_period", "product_line", "bel", "bel_prev",
            "bel_movement", "movement_pct", "policy_count",
        )
    )
