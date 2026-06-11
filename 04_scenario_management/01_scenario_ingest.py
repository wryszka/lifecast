# Databricks notebook source
# MAGIC %md
# MAGIC # LifeCast — Phase 4: scenario ingest (the consume pattern)
# MAGIC
# MAGIC **Pattern (a) — consume your scenario provider.** A delivered scenario file is
# MAGIC landed into Delta, validated, **versioned in UC** and activated — zero friction
# MAGIC for firms with a licensed ESG. Mirrors the assumption-governance pattern:
# MAGIC
# MAGIC - `esg_scenario_sets` — registry: one row per set, versioned, ACTIVE/AVAILABLE/SUPERSEDED
# MAGIC - `esg_scenarios` — the paths, keyed by `scenario_set_id`
# MAGIC - UC functions `esg_active_set_id()` / `esg_scenarios_active()` — the single feed
# MAGIC   point a projection run resolves (consumed by Phases 5–6)
# MAGIC - View `esg_governance_dashboard`
# MAGIC
# MAGIC Validation gate before activation: scenario count, horizon completeness, sane
# MAGIC discount factors. A broken delivery fails loudly and is **not** activated.
# MAGIC
# MAGIC Run by job `lifecast_scenario_ingest`.

# COMMAND ----------

dbutils.widgets.text("catalog", "")
CATALOG = dbutils.widgets.get("catalog")
assert CATALOG, "Pass the target catalog via the `catalog` job parameter / widget."

SCHEMA = "lifecast"
FQ = f"`{CATALOG}`.`{SCHEMA}`"
VOLUME_ROOT = f"/Volumes/{CATALOG}/{SCHEMA}/lifecast_files"
INBOUND = f"{VOLUME_ROOT}/esg/inbound"

# COMMAND ----------

# MAGIC %md ## Tables, functions, view (idempotent)

# COMMAND ----------

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {FQ}.esg_scenario_sets (
    scenario_set_id STRING NOT NULL,
    version INT NOT NULL,
    source STRING NOT NULL,          -- EXTERNAL | ILLUSTRATIVE
    provider_label STRING NOT NULL,  -- generic label; no vendor named
    source_ref STRING,               -- delivery file / generator run
    n_scenarios INT,
    horizon_years INT,
    status STRING NOT NULL,          -- ACTIVE | AVAILABLE | SUPERSEDED
    created_by STRING NOT NULL,
    created_at TIMESTAMP NOT NULL,
    note STRING
) COMMENT 'Scenario set registry — every set versioned in UC; one ACTIVE set feeds runs. Today this lives on a network share with no version control.'
""")

spark.sql(f"""
CREATE TABLE IF NOT EXISTS {FQ}.esg_scenarios (
    scenario_set_id STRING NOT NULL,
    scenario_id INT NOT NULL,
    time_years INT NOT NULL,
    short_rate DOUBLE,
    discount_factor DOUBLE,
    equity_index DOUBLE
) COMMENT 'Scenario paths by set — external deliveries land here, versioned, lineage back to the delivery file.'
""")

spark.sql(f"""
CREATE OR REPLACE FUNCTION {FQ}.esg_active_set_id()
RETURNS STRING
COMMENT 'The currently ACTIVE scenario set id — the single feed point a projection run resolves.'
RETURN (SELECT scenario_set_id FROM {FQ}.esg_scenario_sets
        WHERE status = 'ACTIVE' ORDER BY created_at DESC LIMIT 1)
""")

spark.sql(f"""
CREATE OR REPLACE FUNCTION {FQ}.esg_scenarios_active()
RETURNS TABLE (scenario_id INT, time_years INT, short_rate DOUBLE,
               discount_factor DOUBLE, equity_index DOUBLE)
COMMENT 'Scenario paths of the currently ACTIVE set.'
RETURN SELECT scenario_id, time_years, short_rate, discount_factor, equity_index
       FROM {FQ}.esg_scenarios
       WHERE scenario_set_id = (SELECT scenario_set_id FROM {FQ}.esg_scenario_sets
                                WHERE status = 'ACTIVE' ORDER BY created_at DESC LIMIT 1)
""")

spark.sql(f"""
CREATE OR REPLACE VIEW {FQ}.esg_governance_dashboard
COMMENT 'Scenario sets latest-first with status and provenance — the governance destination the Cockpit links to.'
AS SELECT * FROM {FQ}.esg_scenario_sets ORDER BY version DESC
""")

print("Scenario governance objects in place.")

# COMMAND ----------

# MAGIC %md ## Ingest new deliveries (validate -> version -> activate)

# COMMAND ----------

import datetime
import os

from pyspark.sql import functions as F

registered = {
    r[0] for r in spark.sql(
        f"SELECT source_ref FROM {FQ}.esg_scenario_sets WHERE source = 'EXTERNAL'"
    ).collect()
}
deliveries = [f for f in dbutils.fs.ls(INBOUND) if f.name.endswith(".csv") and f.name not in registered]
if not deliveries:
    print("No new deliveries in esg/inbound — nothing to do.")

for f in deliveries:
    df = (
        spark.read.option("header", True).csv(f.path)
        .select(
            F.expr("try_cast(scenario_id AS INT)").alias("scenario_id"),
            F.expr("try_cast(time_years AS INT)").alias("time_years"),
            F.expr("try_cast(short_rate AS DOUBLE)").alias("short_rate"),
            F.expr("try_cast(discount_factor AS DOUBLE)").alias("discount_factor"),
            F.expr("try_cast(equity_index AS DOUBLE)").alias("equity_index"),
        )
    )
    n_scen = df.select("scenario_id").distinct().count()
    horizon = df.agg(F.max("time_years")).first()[0]
    n_rows = df.count()
    bad_df = df.filter(
        "discount_factor IS NULL OR discount_factor <= 0 OR discount_factor > 1.5 "
        "OR short_rate IS NULL OR equity_index IS NULL OR equity_index <= 0"
    ).count()

    # The gate: a broken delivery never becomes the active set.
    assert n_scen > 0 and horizon and n_rows == n_scen * (horizon + 1), (
        f"{f.name}: incomplete scenario grid ({n_rows} rows, {n_scen} scenarios, horizon {horizon})")
    assert bad_df == 0, f"{f.name}: {bad_df} rows with implausible values — delivery NOT activated."

    version = (spark.sql(f"SELECT COALESCE(MAX(version),0) FROM {FQ}.esg_scenario_sets").first()[0]) + 1
    set_id = f"ESG_EXT_{os.path.splitext(f.name)[0].split('_')[-2]}_V{version}"

    df.withColumn("scenario_set_id", F.lit(set_id)).select(
        "scenario_set_id", "scenario_id", "time_years",
        "short_rate", "discount_factor", "equity_index",
    ).write.mode("append").saveAsTable(f"{FQ}.esg_scenarios")

    # New external delivery becomes ACTIVE; the previous ACTIVE set is superseded.
    spark.sql(f"UPDATE {FQ}.esg_scenario_sets SET status = 'SUPERSEDED' WHERE status = 'ACTIVE'")
    spark.sql(f"""
        INSERT INTO {FQ}.esg_scenario_sets VALUES (
            '{set_id}', {version}, 'EXTERNAL', 'Licensed ESG provider (mock delivery)',
            '{f.name}', {n_scen}, {horizon}, 'ACTIVE',
            current_user(), current_timestamp(),
            'Validated delivery: {n_rows} rows, gate passed.')
    """)
    print(f"Ingested {f.name} -> {set_id} (v{version}, ACTIVE): "
          f"{n_scen:,} scenarios x {horizon + 1} time points")

display(spark.sql(f"SELECT scenario_set_id, version, source, status, n_scenarios, horizon_years FROM {FQ}.esg_governance_dashboard"))
