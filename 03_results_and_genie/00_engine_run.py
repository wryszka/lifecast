# Databricks notebook source
# MAGIC %md
# MAGIC # LifeCast — the engine run (mock, orchestrated)
# MAGIC
# MAGIC **This notebook stands in for the existing actuarial engine** — the box in the
# MAGIC middle of the process map that we never touch. It behaves exactly like the real
# MAGIC thing behaves from the outside:
# MAGIC
# MAGIC - it **picks up the exported model point file** from the landing volume (the file
# MAGIC   use case 01 produced — the migrated feed),
# MAGIC - it reads the **approved assumption basis** and the **EIOPA curve**,
# MAGIC - it projects the term book per model point — base valuation **plus the ±100bp
# MAGIC   sensitivity runs** a real engine batch produces,
# MAGIC - and it **dumps results as CSV files**, because that is what engines do.
# MAGIC
# MAGIC The estate is wider than the migrated feed, deliberately: CREDIT_LIFE and
# MAGIC GROUP_PROTECTION are still "legacy-fed" — their results are synthesised here
# MAGIC (seeded, trend + noise), exactly how a partially-migrated estate looks in real
# MAGIC life. TERM_LEVEL is the real chain: policy → model point → engine → result —
# MAGIC so the number on the dashboard reconciles to the tie-out, to the model points,
# MAGIC to the policies.
# MAGIC
# MAGIC Illustrative textbook mechanics only — not a client methodology.
# MAGIC Run by job `lifecast_engine_run` (or the `lifecast_quarter_close` chain).

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
SENS_BP = 100  # the engine's standard parallel-shift sensitivity runs

# COMMAND ----------

# MAGIC %md ## 1 · The engine picks up its inputs
# MAGIC The model point file from the volume (as the real engine would), the approved
# MAGIC basis, the latest curve. Everything it consumes is governed and on the record.

# COMMAND ----------

import glob
from datetime import date

import numpy as np
import pandas as pd

mpf_files = sorted(glob.glob(f"{VOLUME_ROOT}/export/model_point_file/MPF_TERM_*.csv"))
assert mpf_files, "No model point file on the volume — run lifecast_overnight_run first (use case 01)."
mpf = pd.read_csv(mpf_files[-1])
val_date = pd.to_datetime(mpf["VAL_DATE"].iloc[0]).date()
quarter = f"{val_date.year}Q{(val_date.month - 1) // 3 + 1}"

basis_id = spark.sql(f"SELECT {FQ}.asm_active_set_id()").first()[0]
assert basis_id, "No approved basis — run the foundation job first (use case 02)."
qx = {(int(r.age), r.sex, r.smoker_status): float(r.qx)
      for r in spark.sql(f"SELECT * FROM {FQ}.asm_mortality_active()").collect()}
lapse = {int(r.policy_year): float(r.lapse_rate)
         for r in spark.sql(f"SELECT * FROM {FQ}.asm_lapse_active()").collect()}
expense = {r.expense_type: float(r.value)
           for r in spark.sql(f"SELECT * FROM {FQ}.asm_expense_active()").collect()}

curve_rows = spark.sql(f"""
    SELECT maturity_years, spot_rate FROM {FQ}.esg_rfr_curve
    WHERE currency = '{CURRENCY}'
      AND effective_date = (SELECT MAX(effective_date) FROM {FQ}.esg_rfr_curve WHERE currency = '{CURRENCY}')
    ORDER BY maturity_years
""").collect()
assert curve_rows, "No RFR curve — run lifecast_esg_illustrative first (use case 04)."
curve_date = spark.sql(f"SELECT MAX(effective_date) FROM {FQ}.esg_rfr_curve WHERE currency = '{CURRENCY}'").first()[0]
spot = {int(r.maturity_years): float(r.spot_rate) for r in curve_rows}
max_tenor = max(spot)

print(f"Engine inputs: {mpf_files[-1].split('/')[-1]} ({len(mpf):,} model points, valuation {val_date}) · "
      f"basis {basis_id} · curve {curve_date}")

# COMMAND ----------

# MAGIC %md ## 2 · The valuation — base and ±100bp, per model point
# MAGIC Same illustrative mechanics as the use case 05 side-by-side (this mock IS that
# MAGIC engine); the sensitivity runs come free because the projection is cheap.

# COMMAND ----------

import time


def project_mp(row, shift_bp: int) -> tuple:
    """One model point through the deterministic projection at a shifted curve."""
    def df_at(t):
        if t == 0:
            return 1.0
        rate = spot[min(t, max_tenor)] + shift_bp / 10_000.0
        return (1.0 + rate) ** (-t)

    in_force = float(row.INIT_POLS_IF)
    dur = int(round(float(row.DUR_IF_Y)))
    pv_prem = pv_claim = pv_exp = 0.0
    for t in range(int(row.OS_TERM_Y)):
        q = qx[(int(row.AGE_ATT) + t, row.SEX, row.SMOKER_STAT)]
        w = lapse[min(dur + t + 1, 40)]
        deaths = in_force * q
        infl = (1.0 + expense["expense_inflation_pa"]) ** t
        pv_prem += in_force * float(row.ANNUAL_PREM) * df_at(t)
        pv_claim += deaths * float(row.SUM_ASSURED) * df_at(t + 1)
        pv_exp += (in_force * expense["maintenance_per_policy_pa"] * infl
                   + deaths * expense["claim_handling_per_claim"]) * df_at(t + 1)
        in_force = (in_force - deaths) * (1.0 - w)
    return round(pv_prem, 2), round(pv_claim, 2), round(pv_exp, 2), round(pv_claim + pv_exp - pv_prem, 2)


t0 = time.time()
detail_rows = []
for row in mpf.itertuples():
    _, _, _, bel_dn = project_mp(row, -SENS_BP)
    pv_p, pv_c, pv_e, bel = project_mp(row, 0)
    _, _, _, bel_up = project_mp(row, +SENS_BP)
    detail_rows.append((int(row.MPNUM), str(val_date), int(row.AGE_ATT), row.SEX, row.SMOKER_STAT,
                        float(row.DUR_IF_Y), int(row.OS_TERM_Y), row.PREM_FREQ,
                        int(row.INIT_POLS_IF), int(row.SUM_ASSURED),
                        pv_p, pv_c, pv_e, bel, bel_dn, bel_up, basis_id, str(curve_date)))
runtime_s = time.time() - t0

detail = pd.DataFrame(detail_rows, columns=[
    "MPNUM", "VAL_DATE", "AGE_ATT", "SEX", "SMOKER_STAT", "DUR_IF_Y", "OS_TERM_Y", "PREM_FREQ",
    "POLS_IF", "SUM_ASSURED", "PV_PREM", "PV_CLAIM", "PV_EXP",
    "BEL", "BEL_DOWN100", "BEL_UP100", "BASIS_ID", "CURVE_DT"])
term_bel = float(detail.BEL.sum())
print(f"TERM_LEVEL valued: {len(detail):,} model points × 3 curves in {runtime_s:.1f}s — "
      f"BEL £{term_bel/1e6:,.2f}m (−100bp: £{detail.BEL_DOWN100.sum()/1e6:,.2f}m · "
      f"+100bp: £{detail.BEL_UP100.sum()/1e6:,.2f}m)")

# COMMAND ----------

# MAGIC %md ## 3 · The estate summary — six quarters, three product lines
# MAGIC TERM_LEVEL's current quarter is the real number above, rolled to inception
# MAGIC cohorts; its history trends into it. The two legacy-fed lines are synthesised
# MAGIC (seeded), with the deliberate GROUP_PROTECTION claims jump in the latest
# MAGIC quarter — the "ask Genie why BEL moved" beat.

# COMMAND ----------

from datetime import timedelta

SEED = 42
rng = np.random.default_rng(SEED)
run_ts = pd.Timestamp.now()
run_id = f"ENG_{quarter}_{run_ts:%H%M%S}"


def quarter_ends(n: int, upto: date):
    ends, y, m = [], upto.year, upto.month
    while len(ends) < n:
        m = ((m - 1) // 3) * 3
        if m == 0:
            y, m = y - 1, 12
        ends.append({3: date(y, 3, 31), 6: date(y, 6, 30), 9: date(y, 9, 30), 12: date(y, 12, 31)}[m])
    return list(reversed(ends))


QUARTERS = quarter_ends(5, val_date) + [val_date]  # 5 history quarters + the valuation date
COHORTS_LEGACY = list(range(2018, 2026))
LEGACY = {"CREDIT_LIFE": (118_000, 900.0, 0.97, 0.12),
          "GROUP_PROTECTION": (31_000, 2_600.0, 1.01, 0.09)}
# Cohort mix is a property of the book — drawn once per product, not per quarter.
W_BY = {p: rng.uniform(0.06, 0.20, len(COHORTS_LEGACY)) for p in LEGACY}

# TERM_LEVEL current quarter, cohort view straight from the engine detail.
term_now = detail.copy()
term_now["cohort_year"] = (pd.to_datetime(term_now.VAL_DATE).dt.year - term_now.DUR_IF_Y.round()).astype(int)
term_cohorts = (term_now.groupby("cohort_year")
                .agg(policy_count=("POLS_IF", "sum"), pv_premiums=("PV_PREM", "sum"),
                     pv_claims=("PV_CLAIM", "sum"), pv_expenses=("PV_EXP", "sum"), bel=("BEL", "sum"))
                .reset_index())

rows = []
for qi, qend in enumerate(QUARTERS):
    label = f"{qend.year}Q{(qend.month - 1) // 3 + 1}"
    is_current = qi == len(QUARTERS) - 1
    back = len(QUARTERS) - 1 - qi
    rid = run_id if is_current else f"PR_{label}_001"
    rdate = (qend + timedelta(days=10)).isoformat()

    # TERM_LEVEL: real for the current quarter; history scaled back into it.
    # PVs are rounded first and BEL derived from them, so the accounting identity
    # bel = pv_claims + pv_expenses - pv_premiums holds exactly in the file —
    # the results pipeline enforces it as a quality rule.
    for c in term_cohorts.itertuples():
        sc = 1.0 if is_current else (1.011 ** -back) * float(rng.normal(1.0, 0.004))
        pv_p = round(c.pv_premiums * sc, 0)
        pv_c = round(c.pv_claims * sc, 0)
        pv_e = round(c.pv_expenses * sc, 0)
        rows.append((rid, rdate, label, f"BE_{label}", "TERM_LEVEL",
                     int(c.cohort_year), int(c.policy_count * sc), pv_p,
                     pv_c, pv_e, pv_c + pv_e - pv_p, "GBP"))

    # Legacy-fed lines: synthesised, stable cohort mix, GROUP shock in the current quarter.
    for product, (n_base, prem_pp, claims_r, exp_r) in LEGACY.items():
        growth = 1.011 ** qi
        shock = 1.085 if (is_current and product == "GROUP_PROTECTION") else 1.0
        for ci, cohort in enumerate(COHORTS_LEGACY):
            n_pols = int(n_base * growth * float(W_BY[product][ci]))
            pv_p = round(n_pols * prem_pp * float(rng.normal(1.0, 0.004)), 0)
            pv_c = round(pv_p * claims_r * shock * float(rng.normal(1.0, 0.004)), 0)
            pv_e = round(pv_p * exp_r * float(rng.normal(1.0, 0.004)), 0)
            rows.append((rid, rdate, label, f"BE_{label}", product,
                         cohort, n_pols, pv_p, pv_c, pv_e, pv_c + pv_e - pv_p, "GBP"))

summary = pd.DataFrame(rows, columns=[
    "run_id", "run_date", "reporting_period", "basis_label", "product_line", "cohort_year",
    "policy_count", "pv_premiums", "pv_claims", "pv_expenses", "bel", "currency"])

# COMMAND ----------

# MAGIC %md ## 4 · The engine dumps its output — CSVs on the volume, like always

# COMMAND ----------

out_dir = f"{VOLUME_ROOT}/prophet/results"
dbutils.fs.mkdirs(out_dir)
for label, df_q in summary.groupby("reporting_period"):
    is_current = label == quarter
    name = f"PROPHET_RESULTS_{label}{'_' + run_id if is_current else ''}.csv"
    df_q.to_csv(f"{out_dir}/{name}", index=False)
    print(f"{name}  ({len(df_q)} rows, BEL £{df_q.bel.sum()/1e6:,.1f}m)")

detail_dir = f"{VOLUME_ROOT}/prophet/results_detail"
dbutils.fs.mkdirs(detail_dir)
detail_name = f"ENGINE_MP_RESULTS_{quarter}_{run_id}.csv"
detail.to_csv(f"{detail_dir}/{detail_name}", index=False)
print(f"{detail_name}  ({len(detail):,} model points, base + ±{SENS_BP}bp)")

print(f"\nEngine run {run_id} complete — TERM fed by the governed model point file; "
      "CREDIT_LIFE and GROUP_PROTECTION still legacy-fed. The results run ingests these dumps next.")
