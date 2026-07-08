# Databricks notebook source
# MAGIC %md
# MAGIC # LifeCast — the model factory, part 1: build → Unity → version → control
# MAGIC
# MAGIC The simplest possible version of the whole idea: **an actuarial model is code +
# MAGIC assumptions + curve — and on Databricks it becomes a governed, versioned object
# MAGIC in Unity Catalog**, with the same controls as everything else in this demo.
# MAGIC
# MAGIC What happens below, in order:
# MAGIC
# MAGIC 1. **Build** — the term projection (the same illustrative textbook mechanics the
# MAGIC    rest of LifeCast uses) is wrapped as an MLflow model. The active assumption
# MAGIC    basis and the latest curve are **frozen inside the version** — reproducibility
# MAGIC    by construction, not by convention.
# MAGIC 2. **Save to Unity** — registered as `lifecast_engine_model`. Who, when, from
# MAGIC    which run: recorded automatically.
# MAGIC 3. **Version** — a second implementation (vectorised) is registered as v2 of the
# MAGIC    *same* model. Two versions, one registry, aliases mark which one production
# MAGIC    trusts.
# MAGIC 4. **Control** — the challenger is compared against the champion on the governed
# MAGIC    model point book, per model point, before any promotion. The comparison is the
# MAGIC    gate; the alias flip is the sign-off.
# MAGIC
# MAGIC Illustrative mechanics only — the *pattern* is the demo, not the formulae.
# MAGIC Run by job `lifecast_model_factory` (parts 1 and 2 together).

# COMMAND ----------

# Default catalog for interactive use (jobs always pass ${var.catalog}).
# Porting to another workspace: change once here or via sed across notebooks.
dbutils.widgets.text("catalog", "lr_dev_aws_us_catalog")
CATALOG = dbutils.widgets.get("catalog")
assert CATALOG, "Pass the target catalog via the `catalog` job parameter / widget."

SCHEMA = "lifecast"
FQ = f"`{CATALOG}`.`{SCHEMA}`"
MODEL_NAME = f"{CATALOG}.{SCHEMA}.lifecast_engine_model"
EXPERIMENT = "/Shared/lifecast/07_model_factory/engine_model"
CURRENCY = "GBP"

# COMMAND ----------

# MAGIC %md ## 1 · Freeze the governed inputs into model artifacts
# MAGIC The basis and curve a model was built with should never be a matter of memory.
# MAGIC Here they are snapshotted from the governed tables **into the model version
# MAGIC itself** — load any version, ever, and it carries exactly what it was approved with.

# COMMAND ----------

import json
import os

import pandas as pd

ART_DIR = "/tmp/lifecast_engine_model_artifacts"
os.makedirs(ART_DIR, exist_ok=True)

basis_id = spark.sql(f"SELECT {FQ}.asm_active_set_id()").first()[0]
assert basis_id, "No approved basis — run the foundation job first (use case 02)."

spark.sql(f"SELECT age, sex, smoker_status, qx FROM {FQ}.asm_mortality_active()") \
    .toPandas().to_csv(f"{ART_DIR}/mortality.csv", index=False)
spark.sql(f"SELECT policy_year, lapse_rate FROM {FQ}.asm_lapse_active()") \
    .toPandas().to_csv(f"{ART_DIR}/lapse.csv", index=False)
spark.sql(f"SELECT expense_type, value FROM {FQ}.asm_expense_active()") \
    .toPandas().to_csv(f"{ART_DIR}/expense.csv", index=False)

curve_date = spark.sql(f"""SELECT MAX(effective_date) FROM {FQ}.esg_rfr_curve
                           WHERE currency = '{CURRENCY}'""").first()[0]
assert curve_date, "No RFR curve — run lifecast_esg_illustrative first (use case 04)."
spark.sql(f"""SELECT maturity_years, spot_rate FROM {FQ}.esg_rfr_curve
              WHERE currency = '{CURRENCY}' AND effective_date = '{curve_date}'
              ORDER BY maturity_years""") \
    .toPandas().to_csv(f"{ART_DIR}/curve.csv", index=False)

with open(f"{ART_DIR}/meta.json", "w") as f:
    json.dump({"basis_id": basis_id, "curve_date": str(curve_date),
               "currency": CURRENCY}, f)

print(f"Frozen into artifacts: basis {basis_id} · curve {curve_date} ({CURRENCY})")

# COMMAND ----------

# MAGIC %md ## 2 · The model contract — governed table in, valuations out
# MAGIC Input: rows shaped like `gld_model_points`. Output: PVs + BEL per model point.
# MAGIC The contract is recorded as the model **signature** — callers can't drift.

# COMMAND ----------

INPUT_COLS = ["mp_num", "age_attained", "sex", "smoker_status", "dur_if_y",
              "outstanding_term_years", "init_pols_if", "annual_premium", "sum_assured"]

mps = (spark.table(f"{FQ}.gld_model_points")
       .where(f"valuation_date = (SELECT MAX(valuation_date) FROM {FQ}.gld_model_points)")
       .select(*INPUT_COLS)
       .toPandas())
mps["annual_premium"] = mps["annual_premium"].astype(float)  # DECIMAL breaks input_example
print(f"Governed book: {len(mps):,} model points at the latest valuation date")


def load_basis(art_dir):
    """Read the frozen artifacts back into lookup structures."""
    mort = pd.read_csv(f"{art_dir}/mortality.csv")
    qx = {(int(r.age), r.sex, r.smoker_status): float(r.qx) for r in mort.itertuples()}
    lapse = {int(r.policy_year): float(r.lapse_rate)
             for r in pd.read_csv(f"{art_dir}/lapse.csv").itertuples()}
    expense = {r.expense_type: float(r.value)
               for r in pd.read_csv(f"{art_dir}/expense.csv").itertuples()}
    curve = pd.read_csv(f"{art_dir}/curve.csv")
    spot = {int(r.maturity_years): float(r.spot_rate) for r in curve.itertuples()}
    meta = json.load(open(f"{art_dir}/meta.json"))
    return qx, lapse, expense, spot, meta

# COMMAND ----------

# MAGIC %md ## 3 · v1 — the straightforward implementation
# MAGIC A loop per model point: readable, checkable, the shape an actuary writes first.
# MAGIC The same mechanics as the side-by-side in use case 05 — nothing clever.

# COMMAND ----------

import mlflow
import mlflow.pyfunc
from mlflow.models import infer_signature

mlflow.set_registry_uri("databricks-uc")
mlflow.set_experiment(EXPERIMENT)


class TermProjectionV1(mlflow.pyfunc.PythonModel):
    """Deterministic term projection, one model point at a time."""

    def load_context(self, context):
        self.qx, self.lapse, self.expense, self.spot, self.meta = \
            load_basis(context.artifacts["basis"])
        self.max_tenor = max(self.spot)

    def predict(self, context, model_input, params=None):
        out = []
        for row in model_input.itertuples():
            in_force = float(row.init_pols_if)
            dur = int(round(float(row.dur_if_y)))
            pv_prem = pv_claim = pv_exp = 0.0
            for t in range(int(row.outstanding_term_years)):
                df_t = (1.0 + self.spot[min(t, self.max_tenor)]) ** (-t) if t else 1.0
                df_t1 = (1.0 + self.spot[min(t + 1, self.max_tenor)]) ** (-(t + 1))
                q = self.qx[(int(row.age_attained) + t, row.sex, row.smoker_status)]
                w = self.lapse[min(dur + t + 1, 40)]
                deaths = in_force * q
                infl = (1.0 + self.expense["expense_inflation_pa"]) ** t
                pv_prem += in_force * float(row.annual_premium) * df_t
                pv_claim += deaths * float(row.sum_assured) * df_t1
                pv_exp += (in_force * self.expense["maintenance_per_policy_pa"] * infl
                           + deaths * self.expense["claim_handling_per_claim"]) * df_t1
                in_force = (in_force - deaths) * (1.0 - w)
            out.append((int(row.mp_num), round(pv_prem, 2), round(pv_claim, 2),
                        round(pv_exp, 2), round(pv_claim + pv_exp - pv_prem, 2)))
        return pd.DataFrame(out, columns=["mp_num", "pv_premiums", "pv_claims",
                                          "pv_expenses", "bel"])


example_in = mps.head(5)
_v1_local = TermProjectionV1()


class _Ctx:  # minimal context for a local smoke call before logging
    artifacts = {"basis": ART_DIR}


_v1_local.load_context(_Ctx())
example_out = _v1_local.predict(_Ctx(), example_in)
signature = infer_signature(example_in, example_out)

with mlflow.start_run(run_name="v1_loop") as run:
    mlflow.log_params({"implementation": "loop", "basis_id": basis_id,
                       "curve_date": str(curve_date)})
    v1_info = mlflow.pyfunc.log_model(
        name="model",
        python_model=TermProjectionV1(),
        artifacts={"basis": ART_DIR},
        signature=signature,
        input_example=example_in,
        registered_model_name=MODEL_NAME,
    )

from mlflow import MlflowClient

client = MlflowClient()
v1 = v1_info.registered_model_version
client.set_registered_model_alias(MODEL_NAME, "champion", v1)
client.set_model_version_tag(MODEL_NAME, v1, "basis_id", basis_id)
print(f"Registered {MODEL_NAME} v{v1} (loop) — alias @champion")

# COMMAND ----------

# MAGIC %md ## 4 · v2 — the vectorised implementation, as a new version
# MAGIC Same contract, same frozen basis — the loop over model points becomes array
# MAGIC maths (loop over time only). This is the shape that scales to the grid (part 2)
# MAGIC and to the GPU (part 3). Registered as **v2 of the same model**: a refactor is
# MAGIC a version, not a new spreadsheet.

# COMMAND ----------

import numpy as np


class TermProjectionV2(mlflow.pyfunc.PythonModel):
    """Same projection, vectorised across model points (time stays a loop —
    the in-force recursion is sequential; the book is not). Assumptions become
    lookup ARRAYS so every step is pure array maths — the shape that scales to
    the grid and, unchanged in structure, to the GPU."""

    def load_context(self, context):
        qx, lapse, expense, spot, self.meta = load_basis(context.artifacts["basis"])
        self.expense, self.spot, self.max_tenor = expense, spot, max(spot)
        # qx -> dense array [age, sex, smoker]; sex M=0/F=1, smoker N=0/S=1.
        self.max_age = max(a for a, _, _ in qx)
        self.qx_arr = np.zeros((self.max_age + 1, 2, 2))
        for (a, s, sm), v in qx.items():
            self.qx_arr[a, 1 if s == "F" else 0, 1 if sm == "S" else 0] = v
        # lapse -> array indexed by policy year (capped at 40, like v1).
        self.lapse_arr = np.zeros(41)
        for y, v in lapse.items():
            self.lapse_arr[y] = v

    def predict(self, context, model_input, params=None):
        m = model_input
        n = len(m)
        age = m["age_attained"].to_numpy(int)
        term = m["outstanding_term_years"].to_numpy(int)
        dur = np.rint(m["dur_if_y"].to_numpy(float)).astype(int)
        prem = m["annual_premium"].to_numpy(float)
        sa = m["sum_assured"].to_numpy(float)
        in_force = m["init_pols_if"].to_numpy(float).copy()
        sex_i = (m["sex"].to_numpy() == "F").astype(int)
        smk_i = (m["smoker_status"].to_numpy() == "S").astype(int)
        exp = self.expense
        pv_prem = np.zeros(n); pv_claim = np.zeros(n); pv_exp = np.zeros(n)

        for t in range(int(term.max())):
            active = term > t
            df_t = (1.0 + self.spot[min(t, self.max_tenor)]) ** (-t) if t else 1.0
            df_t1 = (1.0 + self.spot[min(t + 1, self.max_tenor)]) ** (-(t + 1))
            q = self.qx_arr[np.minimum(age + t, self.max_age), sex_i, smk_i]
            w = self.lapse_arr[np.minimum(dur + t + 1, 40)]
            deaths = np.where(active, in_force * q, 0.0)
            infl = (1.0 + exp["expense_inflation_pa"]) ** t
            pv_prem += np.where(active, in_force * prem * df_t, 0.0)
            pv_claim += deaths * sa * df_t1
            pv_exp += np.where(active,
                               (in_force * exp["maintenance_per_policy_pa"] * infl
                                + deaths * exp["claim_handling_per_claim"]) * df_t1, 0.0)
            in_force = np.where(active, (in_force - deaths) * (1.0 - w), in_force)

        return pd.DataFrame({
            "mp_num": m["mp_num"].to_numpy(int),
            "pv_premiums": np.round(pv_prem, 2),
            "pv_claims": np.round(pv_claim, 2),
            "pv_expenses": np.round(pv_exp, 2),
            "bel": np.round(pv_claim + pv_exp - pv_prem, 2),
        })


with mlflow.start_run(run_name="v2_vectorised") as run:
    mlflow.log_params({"implementation": "vectorised_numpy", "basis_id": basis_id,
                       "curve_date": str(curve_date)})
    v2_info = mlflow.pyfunc.log_model(
        name="model",
        python_model=TermProjectionV2(),
        artifacts={"basis": ART_DIR},
        signature=signature,
        input_example=example_in,
        registered_model_name=MODEL_NAME,
    )

v2 = v2_info.registered_model_version
client.set_registered_model_alias(MODEL_NAME, "challenger", v2)
client.set_model_version_tag(MODEL_NAME, v2, "basis_id", basis_id)
print(f"Registered {MODEL_NAME} v{v2} (vectorised) — alias @challenger")

# COMMAND ----------

# MAGIC %md ## 5 · The control — compare before you promote
# MAGIC Both versions loaded back **from Unity** (not from memory — the registry copy is
# MAGIC the only copy that counts) and run on the full governed book. The gate: every
# MAGIC model point within a penny. Then, and only then, the alias flips.

# COMMAND ----------

import time

champ = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}/{v1}")
chall = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}/{v2}")

t0 = time.time(); r1 = champ.predict(mps); t1 = time.time() - t0
t0 = time.time(); r2 = chall.predict(mps); t2 = time.time() - t0

cmp_df = r1.merge(r2, on="mp_num", suffixes=("_v1", "_v2"))
cmp_df["bel_diff"] = (cmp_df.bel_v1 - cmp_df.bel_v2).abs()
max_diff = float(cmp_df.bel_diff.max())
n_breach = int((cmp_df.bel_diff > 0.01).sum())

print(f"v1 (loop):       {t1:6.1f}s   BEL £{r1.bel.sum()/1e6:,.2f}m")
print(f"v2 (vectorised): {t2:6.1f}s   BEL £{r2.bel.sum()/1e6:,.2f}m")
print(f"per-MP max |ΔBEL| = £{max_diff:.2f} · breaches over £0.01: {n_breach} of {len(cmp_df):,}")
assert n_breach == 0, "Challenger does not reproduce the champion — promotion blocked."

client.set_registered_model_alias(MODEL_NAME, "champion", v2)
client.delete_registered_model_alias(MODEL_NAME, "challenger")
print(f"\nPROMOTED: v{v2} is now @champion (v{v1} stays in the registry, on the record).")

# COMMAND ----------

# MAGIC %md ## 6 · The audit answer, for models
# MAGIC The same question as the results desk — *which version, built by whom, from
# MAGIC what* — answered from the registry, not from a filing system.

# COMMAND ----------

from datetime import datetime

for sv in client.search_model_versions(f"name = '{MODEL_NAME}'"):
    mv = client.get_model_version(MODEL_NAME, sv.version)  # full entity (search results are partial)
    run = client.get_run(mv.run_id)
    creator = getattr(mv, "user_id", None) or run.info.user_id
    created = datetime.fromtimestamp(mv.creation_timestamp / 1000)
    aliases = [str(a) for a in (getattr(mv, "aliases", None) or [])]
    print(f"v{mv.version}  created by {creator} on {created:%d %b %Y %H:%M}  "
          f"impl={run.data.params.get('implementation')}  "
          f"basis={run.data.params.get('basis_id')}  curve={run.data.params.get('curve_date')}  "
          f"aliases={aliases}")

print("\nThe model is now a governed Unity Catalog object: versioned, attributed, "
      "frozen with its basis and curve, promoted only through a recorded comparison. "
      "Part 2 runs it from Unity across the grid; part 3 puts the same maths on a GPU.")
