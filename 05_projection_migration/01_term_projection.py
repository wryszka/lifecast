# Databricks notebook source
# MAGIC %md
# MAGIC # LifeCast — Phase 5: the term projection in Python (the workshop notebook)
# MAGIC
# MAGIC The migration POC: the same deterministic term product, projected in Python on
# MAGIC the **same governed inputs** the legacy engine used — model points from the
# MAGIC pipeline, the approved assumption basis, the EIOPA curve. Every run is tracked
# MAGIC in MLflow and the projection is registered as a versioned model in UC
# MAGIC (`lifecast_term_projection`) with lineage.
# MAGIC
# MAGIC **Workshop format: we bring this scaffold; you write the product logic.** The
# MAGIC block marked `PRODUCT LOGIC` below is illustrative textbook mechanics for a
# MAGIC level term product — in the workshop it is deleted and rewritten by your
# MAGIC actuaries, so the result is **your** model, owned and trusted by the people who
# MAGIC sign it off. Everything around it (inputs, tracking, registration, validation,
# MAGIC orchestration) is the part Databricks brings.
# MAGIC
# MAGIC Run as task 2 of `lifecast_projection_run`.

# COMMAND ----------

# Default catalog for interactive use (jobs always pass ${var.catalog}).
# Porting to another workspace: change once here or via sed across notebooks.
dbutils.widgets.text("catalog", "lr_dev_aws_us_catalog")
CATALOG = dbutils.widgets.get("catalog")
assert CATALOG, "Pass the target catalog via the `catalog` job parameter / widget."

SCHEMA = "lifecast"
FQ = f"`{CATALOG}`.`{SCHEMA}`"
CURRENCY = "GBP"

# COMMAND ----------

# MAGIC %md ## INPUTS — all governed, all resolved at run time
# MAGIC Model points from use case 01's pipeline · approved basis via `asm_*_active()` ·
# MAGIC latest EIOPA curve from use case 04. Which basis fed which run is recorded, not
# MAGIC remembered.

# COMMAND ----------

import numpy as np
import pandas as pd

mps = spark.sql(f"SELECT * FROM {FQ}.gld_model_points ORDER BY mp_num").toPandas()
assert len(mps), "No model points — run lifecast_overnight_run first (use case 01)."
# DECIMAL/DATE columns arrive as python objects — cast for numpy + MLflow serialization.
mps["annual_premium"] = mps["annual_premium"].astype(float)
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
curve_date = spark.sql(f"SELECT MAX(effective_date) FROM {FQ}.esg_rfr_curve WHERE currency = '{CURRENCY}'").first()[0]
assert len(curve), "No RFR curve — run lifecast_esg_illustrative first (use case 04)."

print(f"{len(mps)} model points · basis {basis_id} · curve {curve_date}")

# COMMAND ----------

# MAGIC %md ## PRODUCT LOGIC — *you write this in the workshop*
# MAGIC Illustrative textbook mechanics for a level term product (annual steps,
# MAGIC premiums in advance, claims/expenses in arrears). **Not a methodology
# MAGIC recommendation — the slot your actuaries fill with their own formulae.**

# COMMAND ----------

def project_term_book(mps_df, mortality_df, lapse_df, expense_df, curve_df):
    """Deterministic BEL per model point. Returns DataFrame [mp_num, pv_premiums,
    pv_claims, pv_expenses, bel]. Pure function of governed inputs."""
    qx = {(int(r.age), r.sex, r.smoker_status): float(r.qx) for r in mortality_df.itertuples()}
    lapse = {int(r.policy_year): float(r.lapse_rate) for r in lapse_df.itertuples()}
    expense = {r.expense_type: float(r.value) for r in expense_df.itertuples()}
    spot = {int(r.maturity_years): float(r.spot_rate) for r in curve_df.itertuples()}
    max_tenor = max(spot)

    def df_at(t):
        return 1.0 if t == 0 else (1.0 + spot[min(t, max_tenor)]) ** (-t)

    rows = []
    for mp in mps_df.itertuples():
        in_force = float(mp.init_pols_if)
        dur = int(round(float(mp.dur_if_y)))  # completed years in force at valuation
        pv_prem = pv_claim = pv_exp = 0.0
        for t in range(int(mp.outstanding_term_years)):
            q = qx[(int(mp.age_attained) + t, mp.sex, mp.smoker_status)]
            w = lapse[min(dur + t + 1, 40)]  # lapse by policy year, not projection year
            deaths = in_force * q
            infl = (1.0 + expense["expense_inflation_pa"]) ** t
            pv_prem += in_force * float(mp.annual_premium) * df_at(t)
            pv_claim += deaths * float(mp.sum_assured) * df_at(t + 1)
            pv_exp += (in_force * expense["maintenance_per_policy_pa"] * infl
                       + deaths * expense["claim_handling_per_claim"]) * df_at(t + 1)
            in_force = (in_force - deaths) * (1.0 - w)
        rows.append((int(mp.mp_num), round(pv_prem, 2), round(pv_claim, 2),
                     round(pv_exp, 2), round(pv_claim + pv_exp - pv_prem, 2)))
    return pd.DataFrame(rows, columns=["mp_num", "pv_premiums", "pv_claims", "pv_expenses", "bel"])

# COMMAND ----------

# MAGIC %md ## RUN + TRACK — every run logged, results in Delta, model versioned in UC

# COMMAND ----------

import datetime
import time

import mlflow

t0 = time.time()
results = project_term_book(mps, mortality, lapse_tbl, expense_tbl, curve)
runtime_s = time.time() - t0
total_bel = float(results.bel.sum())
print(f"Projected {len(results):,} model points in {runtime_s:.2f}s — "
      f"total BEL £{total_bel/1e6:,.2f}m (the legacy anchor for this product is a multi-hour batch)")

run_ts = datetime.datetime.now()
out = results.copy()
out["run_ts"] = run_ts
out["engine"] = "python"
out["assumption_set_id"] = basis_id
out["curve_date"] = curve_date
spark.createDataFrame(
    out,
    "mp_num INT, pv_premiums DOUBLE, pv_claims DOUBLE, pv_expenses DOUBLE, bel DOUBLE, "
    "run_ts TIMESTAMP, engine STRING, assumption_set_id STRING, curve_date DATE",
).write.mode("append").saveAsTable(f"{FQ}.gld_term_projection")

# COMMAND ----------

# MLflow: the run record — params, metrics, and the model registered in UC.
class TermProjectionModel(mlflow.pyfunc.PythonModel):
    """The projection as a versioned UC model: predict(model_points) -> BEL per MP,
    with the assumption basis and curve pinned as artifacts at registration time."""

    def load_context(self, context):
        self.mortality = pd.read_csv(context.artifacts["mortality"])
        self.lapse = pd.read_csv(context.artifacts["lapse"])
        self.expense = pd.read_csv(context.artifacts["expense"])
        self.curve = pd.read_csv(context.artifacts["curve"])

    def predict(self, context, model_input):
        return project_term_book(model_input, self.mortality, self.lapse, self.expense, self.curve)


import os
import tempfile

mlflow.set_experiment("/Shared/lifecast/05_projection_migration/projection")
mlflow.set_registry_uri("databricks-uc")
with mlflow.start_run(run_name=f"term_projection_{run_ts:%Y%m%d_%H%M}"):
    mlflow.log_params({
        "engine": "python", "product": "TERM_LEVEL", "model_points": len(results),
        "assumption_set_id": basis_id, "curve_date": str(curve_date), "currency": CURRENCY,
    })
    mlflow.log_metrics({"total_bel": total_bel, "runtime_seconds": runtime_s})

    with tempfile.TemporaryDirectory() as tmp:
        arts = {}
        for name, df in [("mortality", mortality), ("lapse", lapse_tbl),
                         ("expense", expense_tbl), ("curve", curve)]:
            p = os.path.join(tmp, f"{name}.csv")
            df.to_csv(p, index=False)
            arts[name] = p
        info = mlflow.pyfunc.log_model(
            name="term_projection",
            python_model=TermProjectionModel(),
            artifacts=arts,
            input_example=mps.head(5),
            registered_model_name=f"{CATALOG}.{SCHEMA}.lifecast_term_projection",
        )

from mlflow import MlflowClient

client = MlflowClient()
version = int(info.registered_model_version)  # UC registry: no stages, use aliases
client.set_registered_model_alias(f"{CATALOG}.{SCHEMA}.lifecast_term_projection", "champion", version)
print(f"Registered {CATALOG}.{SCHEMA}.lifecast_term_projection v{version} (@champion)")
print("Next: 02_projection_validation — side by side against the legacy baseline.")
