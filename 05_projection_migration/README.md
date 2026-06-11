# 05 — Projection migration POC (use case 5, the expand)

**The story:** *"The numbers tie out — and the multi-hour run takes seconds. And I
wrote the product logic, so I own it and trust it."* One deterministic term
product, projected in Python on the **same governed inputs** the legacy engine
uses, tracked in MLflow beside it, validated side by side per model point, and
registered as a versioned model in UC.

**Delivered as a workshop.** We bring the scaffold — inputs, tracking,
registration, validation, orchestration. The client's actuaries delete the
illustrative `PRODUCT LOGIC` block and write their own. The result is *their*
model, on the platform, owned by the people who sign it off.

**Drive it with job `lifecast_projection_run`:** baseline → projection → validation.

| # | Asset | What it does |
|---|---|---|
| 00 | `00_prophet_baseline_mock` | The before-state: the "legacy engine" BEL run per model point (deliberately a separate implementation — plain loops), dumped as CSV to `prophet/term_bel/`. Same model points, same approved basis, same EIOPA curve. |
| 01 | `01_term_projection` | **The workshop notebook.** Governed inputs (`gld_model_points`, `asm_*_active()`, `esg_rfr_curve`) → `PRODUCT LOGIC` slot (illustrative textbook term mechanics — *the part the client rewrites*) → results to `gld_term_projection`, run tracked in MLflow, model registered as `lifecast_term_projection` in UC (@champion). |
| 02 | `02_projection_validation` | Per-model-point tie-out against the baseline, £0.01 tolerance. **A gate**: drift fails the run loudly. Summary to `gld_projection_validation` + MLflow. |

**Where to look while presenting:** the MLflow experiment
(`/Shared/lifecast/05_projection_migration/projection` — python run beside the
validation record, runtime in seconds), the UC model `lifecast_term_projection`
(versions, lineage back to the tables that fed it), and
`gld_projection_validation` (the tie-out on the record: which basis, which
curve, max diff, verdict).

**The chain to say out loud** (Developer/Quant card): logic in the notebook →
every run logged with basis + curve + results → versioned model in UC with
lineage → orchestrated by the job → promoted dev→prod via the bundle. *That
chain is the control plane.*

**Today → tomorrow:** today, a multi-hour run for a well-understood deterministic
product, opaque inside. Tomorrow, the same product in Python in seconds, tracked
beside the legacy engine until trust is earned — then it's your code, governed.

> Note for the actuary in the room: this projection produces a **negative BEL**
> (premiums exceed claims + expenses — typical for level term; the liability is
> an asset). It will not reconcile to the estate-level results of use case 03 —
> those are a separate, coarser synthetic fixture. Each use case's numbers are
> internally consistent; don't reconcile across them.
