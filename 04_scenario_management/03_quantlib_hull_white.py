# Databricks notebook source
# MAGIC %md
# MAGIC # LifeCast — Phase 4: illustrative QuantLib scenario generator
# MAGIC
# MAGIC **Pattern (b) — illustrate.** Hull-White 1-factor short rates + Black-Scholes
# MAGIC equity in **QuantLib**, calibrated to the ingested EIOPA RFR curve, paths
# MAGIC versioned in UC (`esg_hull_white_paths`), calibration parameters and martingale
# MAGIC diagnostics tracked in **MLflow**.
# MAGIC
# MAGIC This is a quick market-consistent set for testing — it does **not** pretend to be
# MAGIC a licensed ESG (that's pattern (a), the consume path). Registered AVAILABLE in the
# MAGIC registry, never auto-activated.
# MAGIC
# MAGIC Run by job `lifecast_esg_illustrative` (after the RFR ingest task).

# COMMAND ----------

# MAGIC %pip install QuantLib --quiet

# COMMAND ----------

dbutils.widgets.text("catalog", "")
dbutils.widgets.text("n_scenarios", "1000")
dbutils.widgets.text("hw_a", "0.03")          # mean reversion
dbutils.widgets.text("hw_sigma", "0.009")     # short-rate vol
dbutils.widgets.text("equity_vol", "0.18")
CATALOG = dbutils.widgets.get("catalog")
assert CATALOG, "Pass the target catalog via the `catalog` job parameter / widget."
N_SCEN = int(dbutils.widgets.get("n_scenarios"))
HW_A = float(dbutils.widgets.get("hw_a"))
HW_SIGMA = float(dbutils.widgets.get("hw_sigma"))
EQ_VOL = float(dbutils.widgets.get("equity_vol"))
SEED, HORIZON, CURRENCY = 42, 40, "GBP"

SCHEMA = "lifecast"
FQ = f"`{CATALOG}`.`{SCHEMA}`"

# COMMAND ----------

# MAGIC %md ## Build the term structure from the latest EIOPA GBP curve

# COMMAND ----------

import numpy as np
import QuantLib as ql

curve_rows = spark.sql(f"""
    SELECT maturity_years, spot_rate FROM {FQ}.esg_rfr_curve
    WHERE currency = '{CURRENCY}'
      AND effective_date = (SELECT MAX(effective_date) FROM {FQ}.esg_rfr_curve WHERE currency = '{CURRENCY}')
    ORDER BY maturity_years
""").collect()
eff_date = spark.sql(f"SELECT MAX(effective_date) FROM {FQ}.esg_rfr_curve WHERE currency = '{CURRENCY}'").first()[0]
assert curve_rows, "No GBP RFR curve found — run the RFR ingest task first."

today = ql.Date(eff_date.day, eff_date.month, eff_date.year)
ql.Settings.instance().evaluationDate = today
dc = ql.Actual365Fixed()

# EIOPA spot rates are annually compounded -> continuous for the curve.
dates = [today] + [today + ql.Period(int(r.maturity_years), ql.Years) for r in curve_rows]
cont = [float(np.log(1.0 + r.spot_rate)) for r in curve_rows]
zero_rates = [cont[0]] + cont
curve = ql.YieldTermStructureHandle(ql.ZeroCurve(dates, zero_rates, dc))
curve.currentLink().enableExtrapolation()

print(f"Curve {eff_date} ({CURRENCY}): {len(curve_rows)} tenors, "
      f"1y {curve_rows[0].spot_rate:.4f}, 30y {curve_rows[-1].spot_rate:.4f}")

# COMMAND ----------

# MAGIC %md ## Hull-White 1F paths + Black-Scholes equity off the same rates

# COMMAND ----------

process = ql.HullWhiteProcess(curve, HW_A, HW_SIGMA)
rsg = ql.GaussianRandomSequenceGenerator(
    ql.UniformRandomSequenceGenerator(HORIZON, ql.UniformRandomGenerator(SEED)))
path_gen = ql.GaussianPathGenerator(process, float(HORIZON), HORIZON, rsg, False)

eq_rng = np.random.default_rng(SEED)
dt = 1.0
short = np.empty((N_SCEN, HORIZON + 1))
for i in range(N_SCEN):
    p = path_gen.next().value()
    short[i, :] = [p[j] for j in range(HORIZON + 1)]

dfs = np.exp(-np.cumsum(short[:, :-1] * dt, axis=1))
dfs = np.hstack([np.ones((N_SCEN, 1)), dfs])
eq = np.empty_like(short)
eq[:, 0] = 100.0
for t in range(1, HORIZON + 1):
    z = eq_rng.standard_normal(N_SCEN)
    eq[:, t] = eq[:, t - 1] * np.exp((short[:, t - 1] - 0.5 * EQ_VOL**2) * dt + EQ_VOL * np.sqrt(dt) * z)

# Martingale diagnostics: simulated discounting must reproduce the input curve,
# and discounted equity must stay a martingale. Quality metrics, not a model.
tenors = np.arange(1, HORIZON + 1)
curve_dfs = np.array([curve.discount(float(t)) for t in tenors])
mart_dev_bp = float(np.max(np.abs(dfs[:, 1:].mean(axis=0) - curve_dfs)) * 1e4)
eq_mart_err = float(abs((eq[:, 1:] * dfs[:, 1:]).mean(axis=0)[-1] / 100.0 - 1.0))
print(f"Martingale max |model DF - curve DF|: {mart_dev_bp:.1f} bp; "
      f"equity martingale error at {HORIZON}y: {eq_mart_err:.3%}")

# COMMAND ----------

# MAGIC %md ## Version the set in UC + track the calibration in MLflow

# COMMAND ----------

import pandas as pd

version = (spark.sql(f"SELECT COALESCE(MAX(version),0) FROM {FQ}.esg_scenario_sets").first()[0]) + 1
set_id = f"ESG_HW_{eff_date:%Y%m}_V{version}"

paths_pdf = pd.DataFrame({
    "scenario_set_id": set_id,
    "scenario_id": np.repeat(np.arange(1, N_SCEN + 1), HORIZON + 1),
    "time_years": np.tile(np.arange(0, HORIZON + 1), N_SCEN),
    "short_rate": np.round(short.ravel(), 6),
    "discount_factor": np.round(dfs.ravel(), 8),
    "equity_index": np.round(eq.ravel(), 4),
})
spark.createDataFrame(
    paths_pdf,
    "scenario_set_id STRING, scenario_id INT, time_years INT, "
    "short_rate DOUBLE, discount_factor DOUBLE, equity_index DOUBLE",
).write.mode("append").saveAsTable(f"{FQ}.esg_hull_white_paths")

spark.sql(f"""
    INSERT INTO {FQ}.esg_scenario_sets VALUES (
        '{set_id}', {version}, 'ILLUSTRATIVE', 'QuantLib HW1F + Black-Scholes (illustrative)',
        'esg_hull_white_paths / curve {eff_date}', {N_SCEN}, {HORIZON}, 'AVAILABLE',
        current_user(), current_timestamp(),
        'Illustrative market-consistent set for testing — not a licensed ESG. Martingale {mart_dev_bp:.1f}bp.')
""")

import mlflow

mlflow.set_experiment("/Shared/lifecast/04_scenario_management/esg_calibration")
with mlflow.start_run(run_name=set_id):
    mlflow.log_params({
        "scenario_set_id": set_id, "model": "HullWhite1F+BS", "currency": CURRENCY,
        "curve_effective_date": str(eff_date), "hw_a": HW_A, "hw_sigma": HW_SIGMA,
        "equity_vol": EQ_VOL, "n_scenarios": N_SCEN, "horizon_years": HORIZON, "seed": SEED,
    })
    mlflow.log_metrics({
        "martingale_max_dev_bp": mart_dev_bp,
        "equity_martingale_err": eq_mart_err,
    })
    run_id = mlflow.active_run().info.run_id

print(f"Set {set_id} (v{version}, AVAILABLE): {len(paths_pdf):,} path rows in esg_hull_white_paths")
print(f"MLflow run {run_id} in /Shared/lifecast/04_scenario_management/esg_calibration")
print("Set is AVAILABLE, not ACTIVE — activation stays a governance decision (registry).")
