# Databricks notebook source
# MAGIC %md
# MAGIC # LifeCast — Phase 5: legacy engine baseline (the before-state)
# MAGIC
# MAGIC The **today-state** for the projection: the legacy liability engine's
# MAGIC deterministic BEL run for the term book, dumped per model point as a CSV — the
# MAGIC artifact the Python rebuild must tie out against, on the **same model points,
# MAGIC same governed basis, same curve**.
# MAGIC
# MAGIC This mock "legacy engine" is implemented deliberately in a *different style*
# MAGIC (plain per-model-point loops) from the Python rebuild, so the side-by-side
# MAGIC validation is a real reconciliation, not a tautology.
# MAGIC
# MAGIC Illustrative textbook mechanics only — not a client methodology. Run as task 1
# MAGIC of `lifecast_projection_run`.

# COMMAND ----------

# Default catalog for interactive use (jobs always pass ${var.catalog}).
# Porting to another workspace: change once here or via sed across notebooks.
dbutils.widgets.text("catalog", "lr_dev_aws_us_catalog")
CATALOG = dbutils.widgets.get("catalog")
assert CATALOG, "Pass the target catalog via the `catalog` job parameter / widget."

SCHEMA = "lifecast"
FQ = f"`{CATALOG}`.`{SCHEMA}`"
VOLUME_ROOT = f"/Volumes/{CATALOG}/{SCHEMA}/lifecast_files"
CURRENCY = "GBP"

# COMMAND ----------

# MAGIC %md ## Governed inputs — model points, approved basis, EIOPA curve

# COMMAND ----------

import numpy as np

mps = spark.sql(f"SELECT * FROM {FQ}.gld_model_points ORDER BY mp_num").collect()
assert mps, "No model points — run lifecast_overnight_run first (use case 01)."

basis_id = spark.sql(f"SELECT {FQ}.asm_active_set_id()").first()[0]
assert basis_id, "No approved assumption basis — run the foundation job first (use case 02)."
qx = {(r.age, r.sex, r.smoker_status): r.qx
      for r in spark.sql(f"SELECT * FROM {FQ}.asm_mortality_active()").collect()}
lapse = {r.policy_year: r.lapse_rate
         for r in spark.sql(f"SELECT * FROM {FQ}.asm_lapse_active()").collect()}
expense = {r.expense_type: r.value
           for r in spark.sql(f"SELECT * FROM {FQ}.asm_expense_active()").collect()}

curve_rows = spark.sql(f"""
    SELECT maturity_years, spot_rate FROM {FQ}.esg_rfr_curve
    WHERE currency = '{CURRENCY}'
      AND effective_date = (SELECT MAX(effective_date) FROM {FQ}.esg_rfr_curve WHERE currency = '{CURRENCY}')
    ORDER BY maturity_years
""").collect()
assert curve_rows, "No RFR curve — run lifecast_esg_illustrative first (use case 04)."
curve_date = spark.sql(f"SELECT MAX(effective_date) FROM {FQ}.esg_rfr_curve WHERE currency = '{CURRENCY}'").first()[0]
spot = {r.maturity_years: r.spot_rate for r in curve_rows}
max_tenor = max(spot)


def discount_factor(t: int) -> float:
    """Annual-compounding spot curve, flat extrapolation beyond the last tenor."""
    if t == 0:
        return 1.0
    rate = spot.get(min(t, max_tenor))
    return (1.0 + rate) ** (-t)


print(f"{len(mps)} model points · basis {basis_id} · curve {curve_date}")

# COMMAND ----------

# MAGIC %md ## The "legacy engine": plain loops, one model point at a time

# COMMAND ----------

import time

t0 = time.time()
out = []
for mp in mps:
    in_force = float(mp.init_pols_if)
    dur = int(round(float(mp.dur_if_y)))  # completed years in force at valuation
    pv_prem, pv_claim, pv_exp = 0.0, 0.0, 0.0
    for t in range(int(mp.outstanding_term_years)):
        age = int(mp.age_attained) + t
        q = qx[(age, mp.sex, mp.smoker_status)]
        w = lapse[min(dur + t + 1, 40)]  # lapse by policy year, not projection year
        deaths = in_force * q
        infl = (1.0 + expense["expense_inflation_pa"]) ** t
        # premiums at start of year; claims and expenses at end of year
        pv_prem += in_force * float(mp.annual_premium) * discount_factor(t)
        pv_claim += deaths * float(mp.sum_assured) * discount_factor(t + 1)
        pv_exp += (in_force * expense["maintenance_per_policy_pa"] * infl
                   + deaths * expense["claim_handling_per_claim"]) * discount_factor(t + 1)
        in_force = (in_force - deaths) * (1.0 - w)
    out.append((int(mp.mp_num), round(pv_prem, 2), round(pv_claim, 2), round(pv_exp, 2),
                round(pv_claim + pv_exp - pv_prem, 2)))
runtime_s = time.time() - t0

# COMMAND ----------

import pandas as pd
from datetime import date

baseline = pd.DataFrame(out, columns=["MPNUM", "PV_PREM", "PV_CLAIM", "PV_EXP", "BEL"])
baseline["BASIS"] = basis_id
baseline["CURVE_DT"] = str(curve_date)

out_dir = f"{VOLUME_ROOT}/prophet/term_bel"
dbutils.fs.mkdirs(out_dir)
path = f"{out_dir}/LEGACY_TERM_BEL_{date.today():%Y%m%d}.csv"
baseline.to_csv(path, index=False)

print(f"Baseline written: {path}")
print(f"  {len(baseline):,} model points, total BEL £{baseline.BEL.sum()/1e6:,.2f}m, "
      f"engine time {runtime_s:.1f}s (the real thing takes hours — that's the anchor)")
