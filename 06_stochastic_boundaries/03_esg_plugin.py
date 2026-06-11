# Databricks notebook source
# MAGIC %md
# MAGIC # LifeCast — Phase 6 explainer: the ESG stays pluggable
# MAGIC
# MAGIC **An explainer, not a demo** — one page, reinforcing use case 04.
# MAGIC
# MAGIC ## The position
# MAGIC We do **not** ship an economic scenario generator, and we never will. The ESG —
# MAGIC which models, which calibration standards, whose sign-off — is the client's
# MAGIC choice and often a licensed relationship that works well. **We are the runtime
# MAGIC and the governance underneath it.**
# MAGIC
# MAGIC ## What "pluggable" means concretely (all built, all in use case 04)
# MAGIC
# MAGIC | Piece | What it is |
# MAGIC |---|---|
# MAGIC | The drop | a delivery lands on the volume (`esg/inbound/`) — file today; SFTP, API or share tomorrow, same landing |
# MAGIC | The gate | grid completeness + sanity checks; a broken delivery is **never activated** |
# MAGIC | The registry | `esg_scenario_sets` — every set versioned, ACTIVE / AVAILABLE / SUPERSEDED, full provenance |
# MAGIC | The feed point | `esg_scenarios_active()` — the **single function every consumer resolves**; swap the active set, every downstream run follows |
# MAGIC | The consumer | `00_stochastic_fan_out` values the book off that feed point — it does not know or care who generated the paths |
# MAGIC
# MAGIC ## The proof in this demo
# MAGIC Run `lifecast_stochastic_run` with `scenario_source = active` (the vendor-style
# MAGIC delivery) and again with `latest_illustrative` (the QuantLib set calibrated to
# MAGIC the EIOPA curve). Same code path, different governed set — and the MLflow
# MAGIC reconciliation metric shows exactly what changed: the market-consistent set
# MAGIC reproduces the curve valuation within Monte Carlo error; the vendor set prices
# MAGIC on its own basis. **The platform made the difference visible, not the choice.**
# MAGIC
# MAGIC ## The line to say out loud
# MAGIC *"Keep your ESG. Keep your licence. We'll give every scenario set a version, a
# MAGIC gate, an audit trail and a single feed point — and any engine that consumes it
# MAGIC inherits all four."*

# COMMAND ----------

print("Explainer notebook — nothing persisted.")
