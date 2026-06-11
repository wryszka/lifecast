# Databricks notebook source
# MAGIC %md
# MAGIC # LifeCast — Phase 6: stochastic valuation fan-out
# MAGIC
# MAGIC The one **real demo** of this use case: the term book valued across every path
# MAGIC of a governed scenario set, fanned out with `mapInPandas`. Stochastic-on-
# MAGIC deterministic is **embarrassingly parallel** — each scenario is independent, so
# MAGIC more scenarios means more workers, not more hours. This is exactly where a
# MAGIC single-machine overnight batch becomes compute-bound.
# MAGIC
# MAGIC The chain is end-to-end governed: cashflows from the same illustrative product
# MAGIC mechanics as use case 05, scenario paths resolved from the use case 04 registry
# MAGIC (`scenario_source` widget: the ACTIVE set, or the latest illustrative
# MAGIC QuantLib set), every run tracked in MLflow with the set id on the record.
# MAGIC
# MAGIC **Reconciliation check:** on a market-consistent (martingale) set, the mean
# MAGIC stochastic BEL must reproduce the deterministic curve valuation within Monte
# MAGIC Carlo error — logged as a metric, every run.
# MAGIC
# MAGIC Run by job `lifecast_stochastic_run`.

# COMMAND ----------

# Default catalog for interactive use (jobs always pass ${var.catalog}).
# Porting to another workspace: change once here or via sed across notebooks.
dbutils.widgets.text("catalog", "lr_dev_aws_us_catalog")
dbutils.widgets.dropdown("scenario_source", "active", ["active", "latest_illustrative"])
CATALOG = dbutils.widgets.get("catalog")
assert CATALOG, "Pass the target catalog via the `catalog` job parameter / widget."
SCENARIO_SOURCE = dbutils.widgets.get("scenario_source")

SCHEMA = "lifecast"
FQ = f"`{CATALOG}`.`{SCHEMA}`"
CURRENCY = "GBP"
MAX_T = 41

# COMMAND ----------

# MAGIC %md ## Governed inputs — model points, basis, curve, scenario set

# COMMAND ----------

import numpy as np
import pandas as pd

mps = spark.sql(f"SELECT * FROM {FQ}.gld_model_points ORDER BY mp_num").toPandas()
assert len(mps), "No model points — run lifecast_overnight_run first (use case 01)."
mps["annual_premium"] = mps["annual_premium"].astype(float)  # DECIMAL -> float
mps["valuation_date"] = mps["valuation_date"].astype(str)

basis_id = spark.sql(f"SELECT {FQ}.asm_active_set_id()").first()[0]
mortality = spark.sql(f"SELECT * FROM {FQ}.asm_mortality_active()").toPandas()
lapse_tbl = spark.sql(f"SELECT * FROM {FQ}.asm_lapse_active()").toPandas()
expense_tbl = spark.sql(f"SELECT * FROM {FQ}.asm_expense_active()").toPandas()

curve = spark.sql(f"""
    SELECT maturity_years, spot_rate FROM {FQ}.esg_rfr_curve
    WHERE currency = '{CURRENCY}'
      AND effective_date = (SELECT MAX(effective_date) FROM {FQ}.esg_rfr_curve WHERE currency = '{CURRENCY}')
    ORDER BY maturity_years
""").toPandas()
assert len(curve), "No RFR curve — run lifecast_esg_illustrative first (use case 04)."

if SCENARIO_SOURCE == "active":
    scenario_set_id = spark.sql(f"SELECT {FQ}.esg_active_set_id()").first()[0]
    assert scenario_set_id, "No ACTIVE scenario set — run lifecast_scenario_ingest first (use case 04)."
    scen_df = spark.sql(f"""
        SELECT scenario_id, time_years, discount_factor
        FROM {FQ}.esg_scenarios WHERE scenario_set_id = '{scenario_set_id}'
    """)
else:
    scenario_set_id = spark.sql(f"""
        SELECT scenario_set_id FROM {FQ}.esg_scenario_sets
        WHERE source = 'ILLUSTRATIVE' ORDER BY created_at DESC LIMIT 1
    """).first()[0]
    assert scenario_set_id, "No illustrative set — run lifecast_esg_illustrative first (use case 04)."
    scen_df = spark.sql(f"""
        SELECT scenario_id, time_years, discount_factor
        FROM {FQ}.esg_hull_white_paths WHERE scenario_set_id = '{scenario_set_id}'
    """)

n_scenarios = scen_df.select("scenario_id").distinct().count()
print(f"{len(mps)} model points · basis {basis_id} · scenario set {scenario_set_id} ({n_scenarios:,} paths)")

# COMMAND ----------

# MAGIC %md ## Aggregate cashflow vectors
# MAGIC Decrements are scenario-independent for this deterministic product — the same
# MAGIC illustrative mechanics as use case 05, aggregated to per-year premium and outgo
# MAGIC vectors. Market risk enters through each scenario's discounting.

# COMMAND ----------

qx = {(int(r.age), r.sex, r.smoker_status): float(r.qx) for r in mortality.itertuples()}
lapse = {int(r.policy_year): float(r.lapse_rate) for r in lapse_tbl.itertuples()}
expense = {r.expense_type: float(r.value) for r in expense_tbl.itertuples()}

prem_v = np.zeros(MAX_T)   # premiums received at time t (start of year t)
outgo_v = np.zeros(MAX_T)  # claims + expenses paid at time t (end of year t-1)
for mp in mps.itertuples():
    in_force = float(mp.init_pols_if)
    dur = int(round(float(mp.dur_if_y)))
    for t in range(int(mp.outstanding_term_years)):
        q = qx[(int(mp.age_attained) + t, mp.sex, mp.smoker_status)]
        deaths = in_force * q
        infl = (1.0 + expense["expense_inflation_pa"]) ** t
        prem_v[t] += in_force * float(mp.annual_premium)
        outgo_v[t + 1] += (deaths * float(mp.sum_assured)
                           + in_force * expense["maintenance_per_policy_pa"] * infl
                           + deaths * expense["claim_handling_per_claim"])
        in_force = (in_force - deaths) * (1.0 - lapse[min(dur + t + 1, 40)])

# Deterministic anchor: the same cashflows on the EIOPA curve.
spot = {int(r.maturity_years): float(r.spot_rate) for r in curve.itertuples()}
max_tenor = max(spot)
curve_df = np.array([1.0] + [(1.0 + spot[min(t, max_tenor)]) ** (-t) for t in range(1, MAX_T)])
deterministic_bel = float((outgo_v * curve_df).sum() - (prem_v * curve_df).sum())
print(f"Deterministic BEL on the curve: £{deterministic_bel/1e6:,.2f}m")

# COMMAND ----------

# MAGIC %md ## The fan-out — `mapInPandas`, one independent valuation per path

# COMMAND ----------

import time

SCHEMA_OUT = "scenario_id INT, bel DOUBLE"


def value_scenarios(iterator):
    for pdf in iterator:
        rows = []
        for sid, g in pdf.groupby("scenario_id"):
            dfv = np.zeros(MAX_T)
            tt = g["time_years"].to_numpy()
            mask = tt < MAX_T
            dfv[tt[mask]] = g["discount_factor"].to_numpy()[mask]
            rows.append((int(sid), float((outgo_v * dfv).sum() - (prem_v * dfv).sum())))
        yield pd.DataFrame(rows, columns=["scenario_id", "bel"])


t0 = time.time()
bels = (
    scen_df.repartition(32, "scenario_id")
    .mapInPandas(value_scenarios, schema=SCHEMA_OUT)
    .toPandas()
)
wall_s = time.time() - t0

mean_bel = float(bels.bel.mean())
recon_pct = 100.0 * (mean_bel - deterministic_bel) / abs(deterministic_bel)
pcts = np.percentile(bels.bel, [0.5, 5, 50, 95, 99.5])
print(f"{len(bels):,} scenario valuations in {wall_s:.1f}s wall — independent paths, "
      f"so scale comes from workers, not hours")
print(f"mean £{mean_bel/1e6:,.2f}m vs deterministic £{deterministic_bel/1e6:,.2f}m "
      f"(reconciliation {recon_pct:+.2f}%)")
print(f"BEL distribution (£m): p0.5 {pcts[0]/1e6:,.1f} · p50 {pcts[2]/1e6:,.1f} · p99.5 {pcts[4]/1e6:,.1f}")

# COMMAND ----------

# MAGIC %md ## On the record — Delta + MLflow

# COMMAND ----------

import datetime

import mlflow

run_ts = datetime.datetime.now()
out = bels.copy()
out["scenario_set_id"] = scenario_set_id
out["assumption_set_id"] = basis_id
out["run_ts"] = run_ts
spark.createDataFrame(
    out, "scenario_id INT, bel DOUBLE, scenario_set_id STRING, assumption_set_id STRING, run_ts TIMESTAMP"
).write.mode("append").saveAsTable(f"{FQ}.gld_stochastic_bel")

mlflow.set_experiment("/Shared/lifecast/06_stochastic_boundaries/stochastic")
with mlflow.start_run(run_name=f"stochastic_{scenario_set_id}"):
    mlflow.log_params({
        "scenario_set_id": scenario_set_id, "scenario_source": SCENARIO_SOURCE,
        "assumption_set_id": basis_id, "n_scenarios": len(bels), "product": "TERM_LEVEL",
    })
    mlflow.log_metrics({
        "wall_seconds": wall_s, "mean_bel": mean_bel, "deterministic_bel": deterministic_bel,
        "reconciliation_pct": recon_pct,
        "bel_p0_5": float(pcts[0]), "bel_p50": float(pcts[2]), "bel_p99_5": float(pcts[4]),
    })

print(f"Per-scenario BELs in gld_stochastic_bel · run tracked with scenario set {scenario_set_id}")
print("Honest note: a market-consistent set reconciles to the curve within MC error; "
      "a vendor set on its own basis will not — and the metric makes that visible.")
