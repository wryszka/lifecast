# 07 — The model factory (use case 7 — inside the engine)

**The story:** the previous use cases moved everything *around* the engine. This
one shows what it looks like when a model itself lives on the platform: **build →
save to Unity → run from Unity.** An actuarial model becomes a governed,
versioned Unity Catalog object with the same controls as every table in this
demo — and the compute underneath it becomes a parameter.

Three parts, deliberately in this order:

| # | Asset | What it shows |
|---|---|---|
| 00 | `00_build_model.py` | **The simplest possible version of the idea.** The term projection wrapped as an MLflow model with the active basis + curve **frozen inside the version** (reproducibility by construction). Registered to UC as `lifecast_engine_model` v1 (loop). Then v2 (vectorised) as a *version of the same model* — compared per model point against v1 on the governed book (£0.01 gate) before the `@champion` alias flips. Who built what, from which basis: the registry answers. |
| 01 | `01_run_grid.py` | **Run it from Unity, across the grid.** `@champion` loaded by alias, fanned over the model point book via Spark. `grid_size` is a job parameter — 10 for the demo, 100 when the book is real; *the grid is a parameter, not a procurement*. Results land in `gld_factory_results` stamped with the model version; timings in `gld_grid_timings`. The total reconciles to the engine's own number. |
| 02 | `02_gpu_variant.py` | **Package the GPU shape.** The same projection as tensors (`torch` where v2 has `numpy` — the entire diff), gated to the penny against the champion, registered as the `@gpu` version of the same model. One model, CPU and GPU shapes, one audit trail. Packaging needs torch, not a GPU. |
| 03 | `03_run_gpu.py` | **Run it from Unity, on a GPU** (serverless GPU compute, A10). Nothing is built here: `@gpu` loads from the registry, finds the CUDA device by itself, reproduces the champion to the penny, then times the seriatim-scale book CPU vs GPU (`gld_gpu_timings`). Honest close: GPUs earn their place at seriatim/stochastic scale, per hot loop. |

**Drive it with:**
- `lifecast_model_factory` — parts 1+2 + GPU packaging (serverless; params `grid_size`, `replication`)
- `lifecast_model_factory_gpu` — the GPU run (serverless GPU compute, A10). Interactive
  alternative: open `03_run_gpu.py` and set the notebook environment's
  **Accelerator to A10**.

*Platform note, stated openly: the serverless GPU pool can **load** from the
registry but not publish to it (no egress to artifact storage) — so the factory
packages on CPU and the GPU runs. Build anywhere, run anywhere is the point of
the registry anyway.*

**The flow to say out loud:** *we build the model, we save it in Unity, we run it
from Unity* — notebook/batch here because valuations are batch-shaped; model
serving is the same registry one click further when something needs an endpoint
(per-policy, quote-time scoring).

**Today → tomorrow:** today a model change is a release cycle on licensed
software and a hardware question. Tomorrow it's a version in a registry —
compared before promotion, attributed, reproducible, and running on whatever
compute this quarter needs.

*About this demo: Bricksurance Life is fictional; the projection is illustrative
textbook mechanics, not a client methodology. The pattern is the point.*
