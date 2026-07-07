# Databricks notebook source
# MAGIC %md
# MAGIC # LifeCast — BEL analytics: the questions the overnight batch never had time for
# MAGIC
# MAGIC The engine's own output, interrogated. Everything here comes from the per-model-
# MAGIC point detail the engine run dumped (base + ±100bp) — no new modelling, just the
# MAGIC governed results layer put to work:
# MAGIC
# MAGIC 1. **Where does my interest-rate risk live?** — BEL sensitivity by attained age ×
# MAGIC    outstanding term, from the engine's own ±100bp runs. The rate-risk map of the
# MAGIC    book, by cell.
# MAGIC 2. **Where is the book concentrated?** — which model points carry the liability;
# MAGIC    how much of BEL sits in the top 1% of cells.
# MAGIC 3. **What moved, exactly?** — quarter-on-quarter movement to cohort level, not
# MAGIC    just product level.
# MAGIC
# MAGIC Each lands as a governed `gld_` table — so the dashboard can chart it, Genie can
# MAGIC answer questions on it, and the export can carry it. *The point to land in the
# MAGIC room: this notebook ran in seconds, on results you already had. What else would
# MAGIC you ask if asking were this cheap?*

# COMMAND ----------

# Default catalog for interactive use (jobs always pass ${var.catalog}).
# Porting to another workspace: change once here or via sed across notebooks.
dbutils.widgets.text("catalog", "lr_dev_aws_us_catalog")
CATALOG = dbutils.widgets.get("catalog")
assert CATALOG, "Pass the target catalog via the `catalog` job parameter / widget."

SCHEMA = "lifecast"
FQ = f"`{CATALOG}`.`{SCHEMA}`"

# COMMAND ----------

# MAGIC %md ## 1 · The rate-risk map — sensitivity by age × outstanding term
# MAGIC Straight from the engine's ±100bp runs. `dv100` is the BEL change for a +100bp
# MAGIC parallel shift — where it's largest is where the ALM conversation starts.

# COMMAND ----------

from pyspark.sql import functions as F

detail = spark.sql(f"""
    SELECT * FROM {FQ}.slv_engine_mp_results
    WHERE valuation_date = (SELECT MAX(valuation_date) FROM {FQ}.slv_engine_mp_results)
""")
assert detail.count() > 0, "No engine detail — run lifecast_engine_run first."

banded = (detail
    .withColumn("age_band", F.concat((F.floor(F.col("age_attained") / 10) * 10).cast("int"), F.lit("s")))
    .withColumn("term_band", F.when(F.col("outstanding_term_years") <= 5, "0–5y")
                              .when(F.col("outstanding_term_years") <= 10, "6–10y")
                              .when(F.col("outstanding_term_years") <= 20, "11–20y")
                              .otherwise("21y+")))

sensitivity = (banded.groupBy("valuation_date", "age_band", "term_band")
    .agg(F.count("*").alias("model_points"),
         F.sum("policy_count").alias("policies"),
         F.round(F.sum("bel"), 0).alias("bel"),
         F.round(F.sum("bel_down100"), 0).alias("bel_down100"),
         F.round(F.sum("bel_up100"), 0).alias("bel_up100"))
    .withColumn("dv100_up", F.round(F.col("bel_up100") - F.col("bel"), 0))
    .withColumn("dv100_down", F.round(F.col("bel_down100") - F.col("bel"), 0))
    .orderBy("age_band", "term_band"))

sensitivity.write.mode("overwrite").saveAsTable(f"{FQ}.gld_bel_sensitivity")
spark.sql(f"COMMENT ON TABLE {FQ}.gld_bel_sensitivity IS "
          "'BEL rate sensitivity by attained-age band x outstanding-term band, from the engine''s own ±100bp runs — the rate-risk map of the book.'")

print("The rate-risk map (dv100_up = BEL change for +100bp):")
display(sensitivity.groupBy("age_band").pivot("term_band").agg(F.first("dv100_up")).orderBy("age_band"))

# COMMAND ----------

# MAGIC %md ## 2 · Concentration — who carries the liability
# MAGIC Ranked cells with cumulative share. If a handful of cells dominate, that's where
# MAGIC data quality, reinsurance and experience monitoring earn their keep first.

# COMMAND ----------

from pyspark.sql.window import Window

w_rank = Window.orderBy(F.abs(F.col("bel")).desc())
w_cum = Window.orderBy(F.abs(F.col("bel")).desc()).rowsBetween(Window.unboundedPreceding, 0)
total_abs = detail.agg(F.sum(F.abs("bel"))).first()[0]

concentration = (detail
    .select("valuation_date", "mp_num", "age_attained", "sex", "smoker_status",
            "outstanding_term_years", "policy_count", "sum_assured", "bel")
    .withColumn("rank", F.row_number().over(w_rank))
    .withColumn("cum_share_pct", F.round(100 * F.sum(F.abs("bel")).over(w_cum) / total_abs, 2))
    .filter("rank <= 500"))

concentration.write.mode("overwrite").saveAsTable(f"{FQ}.gld_bel_concentration")
spark.sql(f"COMMENT ON TABLE {FQ}.gld_bel_concentration IS "
          "'Top-500 model points by |BEL| with cumulative share — where the liability actually lives.'")

top1pct = concentration.filter(f"rank <= {max(1, detail.count() // 100)}").agg(F.max("cum_share_pct")).first()[0]
print(f"The top 1% of model points carry {top1pct}% of absolute BEL.")
display(concentration.limit(15))

# COMMAND ----------

# MAGIC %md ## 3 · Movement, to cohort level
# MAGIC The product-level movement said GROUP_PROTECTION jumped. This says which
# MAGIC cohorts did the jumping — the difference between a number and an explanation.

# COMMAND ----------

w_lag = Window.partitionBy("product_line", "cohort_year").orderBy("reporting_period")
movement = (spark.table(f"{FQ}.slv_projection_results")
    .groupBy("reporting_period", "product_line", "cohort_year")
    .agg(F.sum("bel").alias("bel"), F.sum("policy_count").alias("policy_count"))
    .withColumn("bel_prev", F.lag("bel").over(w_lag))
    .withColumn("bel_movement", F.round(F.col("bel") - F.col("bel_prev"), 0))
    .withColumn("movement_pct", F.round(100 * (F.col("bel") - F.col("bel_prev")) / F.abs(F.col("bel_prev")), 2)))

movement.write.mode("overwrite").saveAsTable(f"{FQ}.gld_movement_by_cohort")
spark.sql(f"COMMENT ON TABLE {FQ}.gld_movement_by_cohort IS "
          "'Quarter-on-quarter BEL movement by product line and inception cohort — the drill behind the movement dashboard.'")

print("Largest cohort-level movers, latest quarter:")
display(spark.sql(f"""
    SELECT product_line, cohort_year, bel, bel_movement, movement_pct
    FROM {FQ}.gld_movement_by_cohort
    WHERE reporting_period = (SELECT MAX(reporting_period) FROM {FQ}.gld_movement_by_cohort)
      AND bel_movement IS NOT NULL
    ORDER BY ABS(bel_movement) DESC LIMIT 10
"""))

# COMMAND ----------

# MAGIC %md ## What else becomes cheap once results live here
# MAGIC *Not built — listed because every one of these is the same pattern you just saw:*
# MAGIC - **Mass-lapse what-if** — rerun the projection with a shocked lapse table; minutes, not a change request.
# MAGIC - **Experience monitoring** — actual deaths vs the basis, monthly instead of annually, feeding the assumption cycle (the loop on the roadmap).
# MAGIC - **New business strain by cell** — same grid, different question.
# MAGIC - **Per-policy seriatim** — drop the grouping entirely; the destination tab of the map.
# MAGIC
# MAGIC The tables written here are already visible to Genie and the dashboard — ask
# MAGIC *"where is my rate risk concentrated?"* in plain English and watch it answer.

# COMMAND ----------

print("Analytics tables written: gld_bel_sensitivity, gld_bel_concentration, gld_movement_by_cohort")
