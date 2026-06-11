# Databricks notebook source
# MAGIC %md
# MAGIC # LifeCast — Phase 3: mock liability model results (the CSV dump)
# MAGIC
# MAGIC The **today-state** of reporting: the downstream liability model dumps quarterly
# MAGIC results as CSVs, and the board pack gets rebuilt in Excel from them. This notebook
# MAGIC fakes six quarters of those dumps onto the volume (`prophet/results/`) so use case
# MAGIC 03 has something real to ingest.
# MAGIC
# MAGIC The numbers are **synthetic data generation, not actuarial output**: smooth trends
# MAGIC plus noise, arithmetically consistent (`bel = pv_claims + pv_expenses − pv_premiums`),
# MAGIC resembling no real book. The estate is wider than use case 01's term book on purpose —
# MAGIC the liability model runs the whole estate; we migrated the term feed first.
# MAGIC
# MAGIC Run by `lifecast_synthetic_foundation`.

# COMMAND ----------

dbutils.widgets.text("catalog", "")
CATALOG = dbutils.widgets.get("catalog")
assert CATALOG, "Pass the target catalog via the `catalog` job parameter / widget."

SCHEMA = "lifecast"
VOLUME_ROOT = f"/Volumes/{CATALOG}/{SCHEMA}/lifecast_files"

# COMMAND ----------

from datetime import date, timedelta

import numpy as np
import pandas as pd

SEED = 42
rng = np.random.default_rng(SEED)
TODAY = date.today()


def last_quarter_ends(n: int, today: date):
    """The n most recent completed calendar quarter-ends, oldest first."""
    ends = []
    y, m = today.year, today.month
    while len(ends) < n:
        m = ((m - 1) // 3) * 3  # back to previous quarter boundary
        if m == 0:
            y, m = y - 1, 12
        qend = {3: date(y, 3, 31), 6: date(y, 6, 30), 9: date(y, 9, 30), 12: date(y, 12, 31)}[m]
        ends.append(qend)
    return list(reversed(ends))


QUARTERS = last_quarter_ends(6, TODAY)
PRODUCTS = {
    # product_line: (policy_count_base, avg_pv_premium_per_policy, claims_ratio, expense_ratio)
    # Ratios keep BEL comfortably away from zero so QoQ movement % stays readable
    # (a near-zero BEL base makes percentages explode on noise).
    "TERM_LEVEL":       (46_000, 4_800.0, 0.96, 0.10),
    "CREDIT_LIFE":      (118_000, 900.0, 0.97, 0.12),
    "GROUP_PROTECTION": (31_000, 2_600.0, 1.01, 0.09),
}
COHORTS = list(range(2018, 2026))

# Cohort mix is a property of the book — draw it once per product, NOT per
# quarter, so quarter-on-quarter movement reflects growth + the planted shock
# rather than resampling noise.
COHORT_W = {p: rng.uniform(0.06, 0.20, len(COHORTS)) for p in PRODUCTS}

rows = []
for qi, qend in enumerate(QUARTERS):
    label = f"{qend.year}Q{(qend.month - 1) // 3 + 1}"
    is_latest = qi == len(QUARTERS) - 1
    for product, (n_base, prem_pp, claims_r, exp_r) in PRODUCTS.items():
        # Book grows ~1%/quarter; the latest quarter carries a visible jump in
        # GROUP_PROTECTION claims PV — the "ask Genie why BEL moved" beat.
        growth = (1.011) ** qi
        shock = 1.085 if (is_latest and product == "GROUP_PROTECTION") else 1.0
        for ci, cohort in enumerate(COHORTS):
            cohort_w = float(COHORT_W[product][ci])
            n_pols = int(n_base * growth * cohort_w)
            pv_premiums = round(n_pols * prem_pp * float(rng.normal(1.0, 0.004)), 0)
            pv_claims = round(pv_premiums * claims_r * shock * float(rng.normal(1.0, 0.004)), 0)
            pv_expenses = round(pv_premiums * exp_r * float(rng.normal(1.0, 0.004)), 0)
            rows.append({
                "run_id": f"PR_{label}_001",
                "run_date": (qend + timedelta(days=10)).isoformat(),
                "reporting_period": label,
                "basis_label": f"BE_{label}",
                "product_line": product,
                "cohort_year": cohort,
                "policy_count": n_pols,
                "pv_premiums": pv_premiums,
                "pv_claims": pv_claims,
                "pv_expenses": pv_expenses,
                "bel": pv_claims + pv_expenses - pv_premiums,
                "currency": "GBP",
            })

results = pd.DataFrame(rows)

# COMMAND ----------

out_dir = f"{VOLUME_ROOT}/prophet/results"
dbutils.fs.mkdirs(out_dir)
for label, df_q in results.groupby("reporting_period"):
    path = f"{out_dir}/PROPHET_RESULTS_{label}.csv"
    df_q.to_csv(path, index=False)
    print(f"{path}  ({len(df_q)} rows, BEL £{df_q.bel.sum() / 1e6:,.1f}m)")

print(f"\n{len(results):,} result rows across {len(QUARTERS)} quarters x "
      f"{len(PRODUCTS)} product lines x {len(COHORTS)} cohorts")
