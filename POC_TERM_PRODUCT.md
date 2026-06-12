# POC — one product, fully off the engine

*Brief §12.3, narrowed to the simplest credible case: one deterministic term product, valued end to end on the platform, with the existing actuarial engine reduced — for that product — to a comparison reference. 4–6 weeks. Client-safe: no competitor named, no cost framing; the decision language is "switch this product's engine run off", never "replace the engine".*

## Objective

At exit, the term product values end to end on the platform — feed → model points → approved basis → projection → results → audit — and the evidence pack is strong enough that **your validation function can defend switching this product's engine run off**. The engine itself is untouched and keeps running everything else.

## Scope

**In:** one deterministic product (level term). The full chain: policy extract ingestion, quality gate, model point grouping, assumption governance, projection in Python (your logic), per-model-point validation against real engine output, analysis of change between valuation dates, results layer, audit trail, scheduled operation.

**Out (mapped, not built):** complex products and guarantees · capital model integration · IFRS 17 engine feeds · any licence decision. Hybrid is a perfectly good end state.

## Reused vs swapped

| The scaffold (reused as-is) | Yours (swapped in) |
|---|---|
| Ingestion + quality gate + quarantine | Your policy extract (spec + 2 historical valuation dates) |
| Model point grouping with control-total proof | Your grouping bands and quality rules (~replace our 7) |
| Assumption registry, Excel round-trip, approval workflow | Your assumption workbooks |
| Projection scaffold + MLflow tracking + UC model registry | **Your product logic — written by your actuaries (the workshop)** |
| Per-MP validation harness with tolerance gate | Your engine's output files as the baseline |
| Results layer, dashboards, Genie, run-health overseer | Your reporting cuts |

## Week by week

**Week 1 — your data lands.** Extract connected, landed, gated; your quality rules in the gate; control totals (policy count, sum assured) reconcile extract → model points against your current MPF exactly.

**Week 2 — your basis, your logic.** Assumption workbooks imported through the Excel round-trip; basis approved on the record. Workshop: your actuaries delete our illustrative product logic and write yours in the scaffold.

**Week 3 — first side-by-side.** Python projection vs a real engine run on identical model points, basis and curve. Iterate the logic until the per-model-point tie-out passes tolerance. The gate fails loudly until it does — that's the point.

**Week 4 — the second date.** Repeat on the second valuation date. Analysis of change: the *movement* between dates ties out, not just the levels. Operational hardening: schedule, alerting, access controls, the bad-feed drill run deliberately.

**Weeks 5–6 (buffer) — evidence and exit.** Documentation pack assembled from the record (it already exists — runs, versions, sign-offs); independent reviewer walkthrough; downstream consumers of this product's BEL mapped; exit review.

## Exit criteria — measurable, agreed in week 1

| # | Criterion | Target |
|---|---|---|
| 1 | Per-model-point tie-out vs engine | 100% of MPs within agreed tolerance (default £0.01) on ≥ 2 valuation dates |
| 2 | Analysis of change | movement between the two dates within agreed tolerance |
| 3 | Control totals | policy count + sum assured reconcile exactly, extract → model points → projection scope |
| 4 | Run time | full valuation of the product in minutes, demonstrated live |
| 5 | Reproducibility | any past run re-executed from its recorded basis + curve + code version, same numbers |
| 6 | Operability | scheduled run with gate + alerting; a deliberately bad feed is stopped before the file (the RED drill) |
| 7 | Ownership | product logic written and documented by your actuaries; independent validation walkthrough completed |

## The evidence pack (produced automatically by running)

Tie-out records per run · MLflow run history with basis/curve/code version on every run · gate history with control totals and sign-offs · assumption approval audit trail · lineage policy → model point → BEL.

## The decision at exit

Move this product's engine run to "comparison only", then off — for this product. Nothing else changes: the engine, every other product, and all downstream consumers continue exactly as today. The next product starts from a proven scaffold and a faster week 1.

## What we need from you

- Extract spec + two historical valuation-date extracts
- The assumption workbooks for the product
- Two matching engine output files (same dates) as the baseline
- 2–3 actuaries for the workshop (the logic is theirs)
- A named contact in validation, involved from week 1
