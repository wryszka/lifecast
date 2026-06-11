# Databricks notebook source
# MAGIC %md
# MAGIC # LifeCast — Phase 4: mock external ESG scenario file
# MAGIC
# MAGIC The **today-state** for scenarios: a licensed ESG vendor delivers a scenario file,
# MAGIC and it sits on a network share with no version control. This notebook fakes one
# MAGIC vendor-style delivery onto the volume (`esg/inbound/`) for use case 04 to ingest.
# MAGIC
# MAGIC No vendor is named or imitated. The numbers are **synthetic data generation, not
# MAGIC an ESG**: a simple mean-reverting rate path + lognormal equity index, arithmetically
# MAGIC consistent (discount factors compound the short rate), resembling no calibrated set.
# MAGIC
# MAGIC Run by `lifecast_synthetic_foundation`.

# COMMAND ----------

# Default catalog for interactive use (jobs always pass ${var.catalog}).
# Porting to another workspace: change once here or via sed across notebooks.
dbutils.widgets.text("catalog", "lr_dev_aws_us_catalog")
CATALOG = dbutils.widgets.get("catalog")
assert CATALOG, "Pass the target catalog via the `catalog` job parameter / widget."

SCHEMA = "lifecast"
VOLUME_ROOT = f"/Volumes/{CATALOG}/{SCHEMA}/lifecast_files"

# COMMAND ----------

from datetime import date

import numpy as np
import pandas as pd

SEED = 42
N_SCENARIOS = 1_000
HORIZON_YEARS = 40

rng = np.random.default_rng(SEED)
TODAY = date.today()

# Mean-reverting short rate (synthetic plausibility only) + GBM equity index.
r0, r_mean, kappa, r_vol = 0.038, 0.033, 0.12, 0.009
eq_vol = 0.17

dt = 1.0
rates = np.empty((N_SCENARIOS, HORIZON_YEARS + 1))
rates[:, 0] = r0
for t in range(1, HORIZON_YEARS + 1):
    z = rng.standard_normal(N_SCENARIOS)
    rates[:, t] = rates[:, t - 1] + kappa * (r_mean - rates[:, t - 1]) * dt + r_vol * np.sqrt(dt) * z

# Discount factors compound the path; equity grows risk-neutrally off the same path.
dfs = np.exp(-np.cumsum(rates[:, :-1] * dt, axis=1))
dfs = np.hstack([np.ones((N_SCENARIOS, 1)), dfs])
eq = np.empty_like(rates)
eq[:, 0] = 100.0
for t in range(1, HORIZON_YEARS + 1):
    z = rng.standard_normal(N_SCENARIOS)
    eq[:, t] = eq[:, t - 1] * np.exp((rates[:, t - 1] - 0.5 * eq_vol**2) * dt + eq_vol * np.sqrt(dt) * z)

rows = pd.DataFrame({
    "scenario_id": np.repeat(np.arange(1, N_SCENARIOS + 1), HORIZON_YEARS + 1),
    "time_years": np.tile(np.arange(0, HORIZON_YEARS + 1), N_SCENARIOS),
    "short_rate": np.round(rates.ravel(), 6),
    "discount_factor": np.round(dfs.ravel(), 8),
    "equity_index": np.round(eq.ravel(), 4),
})
rows.insert(0, "delivery_ref", f"EXT_{TODAY:%Y%m}")
rows.insert(1, "esg_basis", "RISK_NEUTRAL_GBP")

# COMMAND ----------

out_dir = f"{VOLUME_ROOT}/esg/inbound"
dbutils.fs.mkdirs(out_dir)
path = f"{out_dir}/EXTERNAL_ESG_{TODAY:%Y%m}_RN{N_SCENARIOS}.csv"
rows.to_csv(path, index=False)
print(f"Vendor-style scenario file written: {path}")
print(f"  {N_SCENARIOS:,} scenarios x {HORIZON_YEARS + 1} time points = {len(rows):,} rows")
