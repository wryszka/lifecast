# Databricks notebook source
# MAGIC %md
# MAGIC # LifeCast — Phase 6 explainer: nested stochastic, honestly costed
# MAGIC
# MAGIC **An explainer, not a demo.** Nested stochastic is where naive ambition goes to
# MAGIC die — so we size it honestly instead of hand-waving.
# MAGIC
# MAGIC **The structure:** an *outer* set of real-world scenarios (where could the world
# MAGIC be in a year?) and, **at each outer node**, an *inner* market-consistent
# MAGIC valuation (what are the liabilities worth there?). The work is
# MAGIC `outer × inner × model points` — multiplicative, which is why a perfectly
# MAGIC reasonable-sounding request ("1,000 outer, 1,000 inner") is a million
# MAGIC valuations before anyone mentions model points.

# COMMAND ----------

# MAGIC %md ## The arithmetic — adjust the widgets, the conclusion adjusts itself

# COMMAND ----------

dbutils.widgets.text("outer_scenarios", "1000")
dbutils.widgets.text("inner_scenarios", "1000")
dbutils.widgets.text("model_points", "1623")
dbutils.widgets.text("ms_per_mp_valuation", "0.1")   # one MP through one inner path, vectorised
dbutils.widgets.text("worker_cores", "256")           # cores available to fan out across

outer = int(dbutils.widgets.get("outer_scenarios"))
inner = int(dbutils.widgets.get("inner_scenarios"))
mps = int(dbutils.widgets.get("model_points"))
ms = float(dbutils.widgets.get("ms_per_mp_valuation"))
cores = int(dbutils.widgets.get("worker_cores"))

valuations = outer * inner * mps
core_seconds = valuations * ms / 1000.0
core_hours = core_seconds / 3600.0
wall_hours = core_hours / cores

print(f"valuations           : {valuations:,.0f}  (outer {outer:,} x inner {inner:,} x {mps:,} MPs)")
print(f"compute              : {core_hours:,.0f} core-hours")
print(f"wall clock on {cores} cores : {wall_hours:,.1f} hours")
print()
print("The shape of the problem: double the outer set AND the inner set -> 4x the bill.")
print("Parallelism makes it FEASIBLE (outer nodes are independent — same fan-out as")
print("00_stochastic_fan_out); it does not make it CHEAP.")

# COMMAND ----------

# MAGIC %md ## What the industry actually does — and where we sit
# MAGIC
# MAGIC | Approach | Idea | Trade-off |
# MAGIC |---|---|---|
# MAGIC | **Brute force** | run the full grid | exact; the arithmetic above is the bill |
# MAGIC | **Fewer, smarter nodes** | inner valuations only where the outer state matters | judgement-heavy |
# MAGIC | **Proxy models / LSMC** | fit a fast surrogate to a sample of true valuations, evaluate the surrogate everywhere | the standard answer; fitting and validating the proxy is real actuarial work |
# MAGIC
# MAGIC **Where we sit, honestly:** the platform makes the brute-force layer parallel
# MAGIC and the proxy-fitting layer a standard ML workflow (training runs tracked in
# MAGIC MLflow, surrogate versioned in UC — the exact pattern of use case 05). The
# MAGIC *methodology* — proxy form, fitting strategy, validation standards — is
# MAGIC actuarial judgement: yours, or a partner's engine slotted in at the
# MAGIC projection-logic layer. We are the runtime and the governance underneath it.
# MAGIC
# MAGIC **Today → tomorrow:** today, nested runs are quietly descoped because the
# MAGIC overnight window can't fit them. Tomorrow, the outer grid fans out across a
# MAGIC cluster you size per run — and the honest conversation is about scenario
# MAGIC budgets and proxies, not server queues.

# COMMAND ----------

print("Explainer notebook — nothing persisted. The widget arithmetic is the talk track.")
