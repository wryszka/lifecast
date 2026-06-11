"""LifeCast — Phase 1: the governed model point pipeline.

Lakeflow Declarative Pipeline (serverless), publishing into
${catalog}.lifecast. Medallion via table prefix in the single schema:

    brz_policy_admin          streaming table, Auto Loader over the volume feed
    slv_policies              typed, deduplicated, quality-gated (expectations)
    slv_policies_quarantine   every rejected row + which rules it failed
    gld_model_points          grouped model points in the downstream MPF layout

UC lineage volume -> bronze -> silver -> gold is captured automatically.
The downstream liability model consumes the exported gold layer unchanged.
"""

import dlt
from pyspark.sql import SparkSession
from pyspark.sql import functions as F
from pyspark.sql.window import Window

spark = SparkSession.getActiveSession()

VOLUME_ROOT = spark.conf.get("volume_root")
RAW_PATH = f"{VOLUME_ROOT}/raw/policy_admin"

# The quality gate. One rule per defect class; rules are also evaluated
# row-by-row to build the quarantine table, so rejects are visible, never silent.
QUALITY_RULES = {
    "valid_policy_id": "policy_id IS NOT NULL AND policy_id != ''",
    "not_duplicate": "_row_num = 1",
    "valid_dob": "dob IS NOT NULL AND dob > '1920-01-01' AND dob < inception_date",
    "valid_inception": "inception_date IS NOT NULL AND inception_date <= current_date()",
    "valid_sum_assured": "sum_assured IS NOT NULL AND sum_assured > 0",
    "valid_term": "policy_term_years IS NOT NULL AND policy_term_years BETWEEN 5 AND 40",
    "valid_premium": "annual_premium IS NOT NULL AND annual_premium > 0",
}


@dlt.table(
    name="brz_policy_admin",
    comment="As-landed policy admin feed (Auto Loader over the lifecast_files volume). All columns kept as strings — bronze is the untouched record of what arrived.",
)
def brz_policy_admin():
    return (
        spark.readStream.format("cloudFiles")
        .option("cloudFiles.format", "csv")
        .option("header", "true")
        .load(RAW_PATH)
        .select(
            "*",
            F.col("_metadata.file_path").alias("_source_file"),
            F.current_timestamp().alias("_ingested_at"),
        )
    )


@dlt.view(name="policy_admin_typed")
def policy_admin_typed():
    """Typed view over bronze: try_cast (bad values become NULL and are caught
    by the rules), entry-age derivation, duplicate flagging (first-landed wins)."""
    df = spark.read.table("brz_policy_admin").select(
        "policy_id",
        "product_code",
        F.expr("try_cast(dob AS DATE)").alias("dob"),
        "sex",
        "smoker_status",
        F.expr("try_cast(sum_assured AS BIGINT)").alias("sum_assured"),
        F.expr("try_cast(policy_term_years AS INT)").alias("policy_term_years"),
        F.expr("try_cast(inception_date AS DATE)").alias("inception_date"),
        # DECIMAL, not DOUBLE: exact aggregation, so the averaged model point
        # premium is reproducible to the penny and ties out with the extract.
        F.expr("try_cast(annual_premium AS DECIMAL(12,2))").alias("annual_premium"),
        "premium_frequency",
        "policy_status",
        "_source_file",
        "_ingested_at",
    )
    dedupe_window = Window.partitionBy("policy_id").orderBy(
        F.col("_ingested_at").asc(), F.col("_source_file").asc()
    )
    return df.withColumn("_row_num", F.row_number().over(dedupe_window)).withColumn(
        "age_at_entry",
        F.floor(F.datediff("inception_date", "dob") / F.lit(365.25)).cast("int"),
    )


@dlt.table(
    name="slv_policies",
    comment="Clean, typed, deduplicated policies. Every quality rule enforced as an expectation; failing rows are dropped here and surfaced in slv_policies_quarantine.",
)
@dlt.expect_all_or_drop(QUALITY_RULES)
def slv_policies():
    return spark.read.table("policy_admin_typed")


@dlt.table(
    name="slv_policies_quarantine",
    comment="Rows rejected by the quality gate, with the exact rules each row failed. The gate is auditable, not silent.",
)
def slv_policies_quarantine():
    df = spark.read.table("policy_admin_typed")
    # A rule whose predicate is NULL (e.g. comparison against a NULL cast) is a
    # failure, matching expectation semantics — hence coalesce(..., false).
    failed_rules = F.array_compact(
        F.array(
            *[
                F.when(~F.coalesce(F.expr(cond), F.lit(False)), F.lit(name))
                for name, cond in QUALITY_RULES.items()
            ]
        )
    )
    return df.withColumn("failed_rules", failed_rules).filter(F.size("failed_rules") > 0)


@dlt.table(
    name="gld_model_points",
    comment="Grouped model points in the downstream MPF layout — one row per (age at entry, sex, smoker, term, premium frequency) cell of the in-force book. Exported unchanged for the downstream liability model.",
)
def gld_model_points():
    group_cols = ["age_at_entry", "sex", "smoker_status", "policy_term_years", "premium_frequency"]
    grouped = (
        spark.read.table("slv_policies")
        .filter(F.col("policy_status") == "INFORCE")
        .groupBy(*group_cols)
        .agg(
            F.count("*").alias("init_pols_if"),
            F.round(F.avg("sum_assured"), 0).cast("bigint").alias("sum_assured"),
            F.round(F.avg("annual_premium"), 2).alias("annual_premium"),
        )
    )
    return (
        grouped.withColumn("mp_num", F.row_number().over(Window.orderBy(*group_cols)))
        .withColumn("prod_cd", F.lit("TERM_LEVEL"))
        .select(
            "mp_num",
            "prod_cd",
            "age_at_entry",
            "sex",
            "smoker_status",
            "policy_term_years",
            "premium_frequency",
            "sum_assured",
            "annual_premium",
            "init_pols_if",
        )
    )
