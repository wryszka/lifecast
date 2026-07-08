# Databricks notebook source
# MAGIC %md
# MAGIC # LifeCast — the model factory, part 3a: package the GPU variant
# MAGIC
# MAGIC The same projection as **tensors** (`torch` where v2 has `numpy` — that is the
# MAGIC entire structural diff), registered as another version of the *same* Unity
# MAGIC Catalog model, alias `@gpu`. One model, CPU and GPU shapes, one audit trail.
# MAGIC
# MAGIC Packaging doesn't need a GPU — the class picks CUDA at load time wherever it
# MAGIC runs, and falls back to CPU tensors. The GPU proof is the next notebook
# MAGIC (`03_run_gpu`), which loads this exact version from the registry on serverless
# MAGIC GPU compute. (The GPU pool has no egress to artifact storage — it can *load*
# MAGIC models, not publish them — so build here, run there: the factory pattern.)
# MAGIC
# MAGIC Run by job `lifecast_model_factory` (after the grid).

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

# COMMAND ----------

# MAGIC %md ## 1 · Start from the champion's own frozen basis

# COMMAND ----------

import glob
import json
import os

import mlflow
import numpy as np
import pandas as pd
from mlflow import MlflowClient

mlflow.set_registry_uri("databricks-uc")
mlflow.set_experiment(EXPERIMENT)
client = MlflowClient()
champ = client.get_model_version_by_alias(MODEL_NAME, "champion")

_root = mlflow.artifacts.download_artifacts(f"models:/{MODEL_NAME}/{champ.version}")
_hits = glob.glob(f"{_root}/**/mortality.csv", recursive=True)
assert _hits, f"Frozen basis not found inside model version {champ.version}"
ART = os.path.dirname(_hits[0])
meta = json.load(open(f"{ART}/meta.json"))
print(f"Packaging the torch variant of champion v{champ.version} — "
      f"basis {meta['basis_id']} · curve {meta['curve_date']}")

# COMMAND ----------

# MAGIC %md ## 2 · The tensor implementation — v2 with `torch` for `numpy`

# COMMAND ----------

class TermProjectionGPU(mlflow.pyfunc.PythonModel):
    """The torch implementation. Runs on CUDA when present, falls back to CPU
    tensors otherwise — same contract, same frozen artifacts as v1/v2."""

    def load_context(self, context):
        import torch as _t

        self.dev = _t.device("cuda" if _t.cuda.is_available() else "cpu")
        art = context.artifacts["basis"]
        mort = pd.read_csv(f"{art}/mortality.csv")
        self.max_age = int(mort.age.max())
        qx = np.zeros((self.max_age + 1, 2, 2))
        for r in mort.itertuples():
            qx[int(r.age), 1 if r.sex == "F" else 0, 1 if r.smoker_status == "S" else 0] = r.qx
        lp = np.zeros(41)
        for r in pd.read_csv(f"{art}/lapse.csv").itertuples():
            lp[int(r.policy_year)] = r.lapse_rate
        self.qx_t = _t.tensor(qx, device=self.dev)
        self.lapse_t = _t.tensor(lp, device=self.dev)
        self.expense = {r.expense_type: float(r.value)
                        for r in pd.read_csv(f"{art}/expense.csv").itertuples()}
        self.spot = {int(r.maturity_years): float(r.spot_rate)
                     for r in pd.read_csv(f"{art}/curve.csv").itertuples()}
        self.max_tenor = max(self.spot)

    def predict(self, context, model_input, params=None):
        import torch as _t

        m, dev = model_input, self.dev
        z = _t.zeros((), device=dev, dtype=_t.float64)
        age = _t.tensor(m["age_attained"].to_numpy(int), device=dev)
        term = _t.tensor(m["outstanding_term_years"].to_numpy(int), device=dev)
        dur = _t.tensor(np.rint(m["dur_if_y"].to_numpy(float)).astype(int), device=dev)
        prem = _t.tensor(m["annual_premium"].to_numpy(float), device=dev)
        sa = _t.tensor(m["sum_assured"].to_numpy(float), device=dev, dtype=_t.float64)
        in_force = _t.tensor(m["init_pols_if"].to_numpy(float), device=dev)
        sex_i = _t.tensor((m["sex"].to_numpy() == "F").astype(int), device=dev)
        smk_i = _t.tensor((m["smoker_status"].to_numpy() == "S").astype(int), device=dev)
        n = len(m)
        pv_p = _t.zeros(n, device=dev, dtype=_t.float64)
        pv_c = _t.zeros(n, device=dev, dtype=_t.float64)
        pv_e = _t.zeros(n, device=dev, dtype=_t.float64)
        for t in range(int(term.max().item())):
            active = term > t
            df_t = (1.0 + self.spot[min(t, self.max_tenor)]) ** (-t) if t else 1.0
            df_t1 = (1.0 + self.spot[min(t + 1, self.max_tenor)]) ** (-(t + 1))
            q = self.qx_t[_t.clamp(age + t, max=self.max_age), sex_i, smk_i]
            w = self.lapse_t[_t.clamp(dur + t + 1, max=40)]
            deaths = _t.where(active, in_force * q, z)
            infl = (1.0 + self.expense["expense_inflation_pa"]) ** t
            pv_p += _t.where(active, in_force * prem * df_t, z)
            pv_c += deaths * sa * df_t1
            pv_e += _t.where(active,
                             (in_force * self.expense["maintenance_per_policy_pa"] * infl
                              + deaths * self.expense["claim_handling_per_claim"]) * df_t1, z)
            in_force = _t.where(active, (in_force - deaths) * (1.0 - w), in_force)
        return pd.DataFrame({
            "mp_num": m["mp_num"].to_numpy(int),
            "pv_premiums": np.round(pv_p.cpu().numpy(), 2),
            "pv_claims": np.round(pv_c.cpu().numpy(), 2),
            "pv_expenses": np.round(pv_e.cpu().numpy(), 2),
            "bel": np.round((pv_c + pv_e - pv_p).cpu().numpy(), 2),
        })

# COMMAND ----------

# MAGIC %md ## 3 · Gate on CPU, then into the registry as `@gpu`
# MAGIC Same rule as every promotion in this factory: reproduce the champion to the
# MAGIC penny on the governed book, or you don't get an alias.

# COMMAND ----------

from mlflow.models import infer_signature

INPUT_COLS = ["mp_num", "age_attained", "sex", "smoker_status", "dur_if_y",
              "outstanding_term_years", "init_pols_if", "annual_premium", "sum_assured"]
mps = (spark.table(f"{FQ}.gld_model_points")
       .where(f"valuation_date = (SELECT MAX(valuation_date) FROM {FQ}.gld_model_points)")
       .select(*INPUT_COLS).toPandas())
mps["annual_premium"] = mps["annual_premium"].astype(float)

gpu_local = TermProjectionGPU()


class _Ctx:
    artifacts = {"basis": ART}


gpu_local.load_context(_Ctx())
print(f"Packaging device for the gate run: {gpu_local.dev} (CUDA engages on the GPU job)")
r_torch = gpu_local.predict(_Ctx(), mps)

champ_model = mlflow.pyfunc.load_model(f"models:/{MODEL_NAME}/{champ.version}")
r_champ = champ_model.predict(mps)
cmp_df = r_champ.merge(r_torch, on="mp_num", suffixes=("_champ", "_torch"))
max_diff = float((cmp_df.bel_champ - cmp_df.bel_torch).abs().max())
n_breach = int(((cmp_df.bel_champ - cmp_df.bel_torch).abs() > 0.01).sum())
print(f"torch vs champion on {len(mps):,} MPs: max |ΔBEL| £{max_diff:.2f}, breaches: {n_breach}")
assert n_breach == 0, "Torch variant does not reproduce the champion — not registered."

signature = infer_signature(mps.head(5), r_torch.head(5))
with mlflow.start_run(run_name="v_torch_gpu_variant"):
    mlflow.log_params({"implementation": "torch", "basis_id": meta["basis_id"],
                       "curve_date": meta["curve_date"]})
    # artifact_path (not name) — works across mlflow generations.
    v_info = mlflow.pyfunc.log_model(
        artifact_path="model",
        python_model=TermProjectionGPU(),
        artifacts={"basis": ART},
        signature=signature,
        input_example=mps.head(5),
        registered_model_name=MODEL_NAME,
        pip_requirements=["torch", "numpy", "pandas"],
    )

v_gpu = getattr(v_info, "registered_model_version", None) or \
    max(int(m.version) for m in client.search_model_versions(f"name = '{MODEL_NAME}'"))
client.set_registered_model_alias(MODEL_NAME, "gpu", v_gpu)
client.set_model_version_tag(MODEL_NAME, v_gpu, "basis_id", meta["basis_id"])
print(f"Registered {MODEL_NAME} v{v_gpu} (torch) — alias @gpu. "
      "Job lifecast_model_factory_gpu now runs it from Unity on a real A10.")
