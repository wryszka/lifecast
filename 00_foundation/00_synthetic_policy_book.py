# Databricks notebook source
# MAGIC %md
# MAGIC # LifeCast — Phase 0: synthetic policy book
# MAGIC
# MAGIC Generates the **Bricksurance Life** synthetic level term assurance book as a
# MAGIC file-shaped policy-admin feed (CSV on the `lifecast_files` volume) — it plays the
# MAGIC role of the overnight extract the Phase 1 pipeline ingests.
# MAGIC
# MAGIC Two outputs:
# MAGIC - **Clean feed** → `raw/policy_admin/` — passes every quality rule.
# MAGIC - **Bad feed day** → `demo/bad_feed_day/` — a separate file, *outside* the landing
# MAGIC   path, full of planted defects. Injected during the demo via the
# MAGIC   `lifecast_bad_feed_day` job to show the quality gate stopping a run.
# MAGIC
# MAGIC Synthetic plausibility only — the premium is a crude rate-times-sum-assured
# MAGIC number so the data *looks* like a book. It is **not** pricing or actuarial logic.

# COMMAND ----------

# Default catalog for interactive use (jobs always pass ${var.catalog}).
# Porting to another workspace: change once here or via sed across notebooks.
dbutils.widgets.text("catalog", "lr_dev_aws_us_catalog")
CATALOG = dbutils.widgets.get("catalog")
assert CATALOG, "Pass the target catalog via the `catalog` job parameter / widget."

SCHEMA = "lifecast"
VOLUME_ROOT = f"/Volumes/{CATALOG}/{SCHEMA}/lifecast_files"

# Schema + volume are bundle-managed (resources/lifecast_uc.yml); guards keep
# the notebook runnable standalone.
spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{CATALOG}`.`{SCHEMA}`")
spark.sql(f"CREATE VOLUME IF NOT EXISTS `{CATALOG}`.`{SCHEMA}`.lifecast_files")

# COMMAND ----------

import numpy as np
import pandas as pd
from datetime import date, timedelta

SEED = 42
N_POLICIES = 50_000
N_BAD_FEED = 4_000

rng = np.random.default_rng(SEED)
TODAY = date.today()


def make_policies(n: int, rng, id_start: int = 1) -> pd.DataFrame:
    """Synthetic level term assurance policies. Every row passes the Phase 1 quality rules."""
    age_at_entry = rng.integers(20, 61, n)
    term = rng.choice([10, 15, 20, 25, 30], n, p=[0.15, 0.20, 0.30, 0.20, 0.15])
    days_back = rng.integers(0, 15 * 365, n)  # inception within the last 15 years
    inception = [TODAY - timedelta(days=int(d)) for d in days_back]
    dob_jitter = rng.integers(0, 365, n)
    dob = [inc - timedelta(days=int(a) * 365 + int(j)) for inc, a, j in zip(inception, age_at_entry, dob_jitter)]
    sex = rng.choice(["M", "F"], n, p=[0.52, 0.48])
    smoker = rng.choice(["N", "S"], n, p=[0.88, 0.12])
    sum_assured = np.round(np.exp(rng.normal(11.8, 0.55, n)) / 1000) * 1000
    sum_assured = np.clip(sum_assured, 25_000, 2_000_000).astype(int)
    # Crude plausibility rate — NOT pricing logic.
    base_rate = 0.0009 + (age_at_entry - 20) * 0.00004
    smoker_load = np.where(smoker == "S", 1.9, 1.0)
    annual_premium = np.round(sum_assured * base_rate * smoker_load + 60.0, 2)
    freq = rng.choice(["M", "Y"], n, p=[0.80, 0.20])
    status = rng.choice(["INFORCE", "LAPSED", "CLAIMED"], n, p=[0.92, 0.06, 0.02])

    return pd.DataFrame(
        {
            "policy_id": [f"TL{i:07d}" for i in range(id_start, id_start + n)],
            "product_code": "TERM_LEVEL",
            "dob": [d.isoformat() for d in dob],
            "sex": sex,
            "smoker_status": smoker,
            "sum_assured": sum_assured,
            "policy_term_years": term,
            "inception_date": [d.isoformat() for d in inception],
            "annual_premium": annual_premium,
            "premium_frequency": freq,
            "policy_status": status,
        }
    )


book = make_policies(N_POLICIES, rng)
print(f"Clean book: {len(book):,} policies, "
      f"{(book.policy_status == 'INFORCE').sum():,} in force, "
      f"total sum assured £{book.sum_assured.sum() / 1e9:.1f}bn")

# COMMAND ----------

# MAGIC %md ## Write the clean overnight feed

# COMMAND ----------

raw_dir = f"{VOLUME_ROOT}/raw/policy_admin"
dbutils.fs.mkdirs(raw_dir)
feed_path = f"{raw_dir}/policy_admin_extract_{TODAY.strftime('%Y%m%d')}.csv"
book.to_csv(feed_path, index=False)
print(f"Clean feed written: {feed_path}")

# COMMAND ----------

# MAGIC %md ## Write the bad feed day file (kept OUTSIDE the landing path)
# MAGIC
# MAGIC Defect classes, each of which one Phase 1 quality rule catches:
# MAGIC duplicate policy IDs, future dates of birth, non-positive sums assured,
# MAGIC missing premiums, implausible terms, future inception dates.
# MAGIC The remainder of the file is clean — a bad feed still carries good rows.

# COMMAND ----------

bad = make_policies(N_BAD_FEED, rng, id_start=900_001)
idx = rng.permutation(N_BAD_FEED)

dup_idx = bad.index[idx[:600]]
bad.loc[dup_idx, "policy_id"] = (
    book["policy_id"].iloc[rng.choice(N_POLICIES, len(dup_idx), replace=False)].values
)
bad.loc[bad.index[idx[600:1300]], "dob"] = (TODAY + timedelta(days=2000)).isoformat()
bad.loc[bad.index[idx[1300:1600]], "sum_assured"] = -50_000
bad.loc[bad.index[idx[1600:1900]], "sum_assured"] = 0
bad.loc[bad.index[idx[1900:2700]], "annual_premium"] = np.nan
bad.loc[bad.index[idx[2700:3100]], "policy_term_years"] = rng.choice([0, 99], 400)
bad.loc[bad.index[idx[3100:3500]], "inception_date"] = (TODAY + timedelta(days=90)).isoformat()
# idx[3500:] left clean

bad_dir = f"{VOLUME_ROOT}/demo/bad_feed_day"
dbutils.fs.mkdirs(bad_dir)
bad_path = f"{bad_dir}/policy_admin_extract_BAD_FEED_DAY.csv"
bad.to_csv(bad_path, index=False)
print(f"Bad feed day file written (NOT yet in the landing path): {bad_path}")
print(f"  {N_BAD_FEED:,} rows, ~3,500 defective across 6 defect classes")
