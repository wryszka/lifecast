# Databricks notebook source
# MAGIC %md
# MAGIC # LifeCast — Phase 6 explainer: where vectorisation breaks
# MAGIC
# MAGIC **An explainer, not a demo.** The honest map of the hard edge between
# MAGIC "Python is instant" and "this needs engineering."
# MAGIC
# MAGIC **The short version:**
# MAGIC - A simple projection (no path feedback) **vectorises beautifully** — whole
# MAGIC   scenario blocks as array maths, milliseconds per thousand paths.
# MAGIC - A **simple ratchet** (e.g. a GMAB locking in the highest fund value) still
# MAGIC   vectorises — a running maximum is `np.maximum.accumulate`.
# MAGIC - It genuinely breaks when **this year's decision depends on last year's
# MAGIC   result**: dynamic management actions, hedge rebalancing rules, bonus
# MAGIC   declarations conditioned on solvency. That's a loop-carried dependency —
# MAGIC   you must step through time.
# MAGIC - The fix for the hot loop is compilation (Numba/JAX) — **solvable, not free**:
# MAGIC   real engineering, worth it only where profiling says so.

# COMMAND ----------

# MAGIC %md ## 1 · Simple projection: array maths across all paths at once

# COMMAND ----------

import time

import numpy as np

rng = np.random.default_rng(42)
N_PATHS, N_STEPS = 10_000, 480  # 10k paths, 40y monthly
returns = rng.normal(0.004, 0.04, (N_PATHS, N_STEPS))

t0 = time.time()
fund_vec = 100.0 * np.cumprod(1.0 + returns, axis=1)   # every path, every step, one expression
t_vec = time.time() - t0

t0 = time.time()
fund_loop = np.empty((N_PATHS, N_STEPS))
for i in range(N_PATHS):                                # the same thing, stepped in Python
    f = 100.0
    for t in range(N_STEPS):
        f *= 1.0 + returns[i, t]
        fund_loop[i, t] = f
t_loop = time.time() - t0

print(f"vectorised: {t_vec*1000:,.0f} ms   python loop: {t_loop:,.1f} s   "
      f"-> {t_loop/t_vec:,.0f}x — and the answers match: {np.allclose(fund_vec, fund_loop)}")

# COMMAND ----------

# MAGIC %md ## 2 · A simple ratchet STILL vectorises (don't give up too early)

# COMMAND ----------

t0 = time.time()
gmab_lockin = np.maximum.accumulate(fund_vec, axis=1)  # highest fund value to date, per path
t_ratchet = time.time() - t0
print(f"running-max ratchet across {N_PATHS:,} paths: {t_ratchet*1000:,.0f} ms — "
      "a pure ratchet is just a cumulative maximum")

# COMMAND ----------

# MAGIC %md ## 3 · Where it actually breaks: decision feedback
# MAGIC The moment the projection takes an **action** that changes the path — derisking
# MAGIC when the ratchet bites, declaring bonuses off the solvency position, dynamic
# MAGIC lapses responding to rates — step *t* needs the **decided** state of step
# MAGIC *t−1*. No array expression removes that dependency; you step through time:

# COMMAND ----------

t0 = time.time()
fund = np.full(N_PATHS, 100.0)
locked = fund.copy()
equity_weight = np.full(N_PATHS, 0.8)
for t in range(N_STEPS):                       # loop over TIME is irreducible now
    fund = fund * (1.0 + equity_weight * returns[:, t])
    locked = np.maximum(locked, fund)
    # management action: derisk where the guarantee bites — feeds back into t+1
    equity_weight = np.where(fund < 0.85 * locked, 0.4, 0.8)
t_feedback = time.time() - t0
print(f"decision-feedback projection: {t_feedback:,.2f} s — note the loop is over TIME "
      f"({N_STEPS} steps), still vectorised across paths. That hybrid is usually the answer.")

# COMMAND ----------

# MAGIC %md ## 4 · The honest summary to say out loud
# MAGIC
# MAGIC | Pattern | Vectorises? | What it costs |
# MAGIC |---|---|---|
# MAGIC | Deterministic / no feedback | fully | milliseconds — free lunch |
# MAGIC | Pure ratchet / lookback | fully (`cummax`, `cumprod`) | still cheap |
# MAGIC | Decision feedback (management actions, dynamic hedging) | across **paths**, not time | a time loop — seconds to minutes |
# MAGIC | Heavy per-step logic inside that time loop | no | compile the hot loop: **Numba/JAX** — solvable, not free |
# MAGIC
# MAGIC And when one machine isn't enough, the time loop parallelises across
# MAGIC **scenarios** the same way as `00_stochastic_fan_out` — the platform's answer
# MAGIC is workers, not cleverness. Where the product logic is genuinely gnarly, a
# MAGIC partner's engine slots in at the projection-logic layer — the governance,
# MAGIC data and orchestration around it stay exactly as built here.

# COMMAND ----------

print("Explainer notebook — nothing persisted. Run cells live if the room wants proof.")
