# 04 — Scenario management (use case 4, the bridge)

**The story:** *"My production scenarios are governed for the first time. And I can
generate a quick market-consistent set for testing — without it pretending to be my
licensed ESG."* Two patterns, deliberately separate:

- **(a) Consume** — the client's licensed ESG delivery lands in Delta, is validated,
  **versioned in UC** and activated. Zero friction; we are runtime and governance,
  the ESG stays the client's choice.
- **(b) Illustrate** — Hull-White 1F + Black-Scholes in **QuantLib**, calibrated to
  the **EIOPA RFR curve**, calibration tracked in **MLflow**. Registered AVAILABLE,
  never auto-activated.

**Drive it with two jobs:** `lifecast_scenario_ingest` (consume) and
`lifecast_esg_illustrative` (RFR curve → QuantLib generator).

| # | Asset | What it does |
|---|---|---|
| 00 | `00_external_scenarios_mock` | The today-state: one vendor-style scenario delivery (1,000 scenarios × 41 time points) faked onto `esg/inbound/` — the file that today sits on a network share. No vendor named. Run by the foundation job. |
| 01 | `01_scenario_ingest` | Consume: validation gate (grid completeness, sane DFs — a broken delivery is never activated) → `esg_scenarios` + `esg_scenario_sets` registry → ACTIVE, previous set SUPERSEDED. UC functions `esg_active_set_id()` / `esg_scenarios_active()` are the feed point Phases 5–6 resolve. |
| 02 | `02_eiopa_rfr` | EIOPA monthly RFR publication (`RFR_spot_no_VA`) → `esg_rfr_curve`. **Reused from the actuarial Excel accelerator**; a sample EIOPA-format workbook ships in `sample_data/`. |
| 03 | `03_quantlib_hull_white` | Illustrate: HW1F + BS paths off the EIOPA curve → `esg_hull_white_paths`, registered AVAILABLE; params + martingale diagnostics (curve reproduction in bp) logged to MLflow at `/Shared/lifecast/04_scenario_management/esg_calibration`. |

**Where to look while presenting:** `esg_governance_dashboard` (every set, source,
status, provenance — the network-share problem solved), the MLflow experiment
(set → calibration → diagnostics traceability), and lineage from the delivery CSV
into `esg_scenarios`.

**Today → tomorrow:** today, scenario files on a network share, no version control.
Tomorrow, every set versioned in UC alongside assumptions and runs, calibration
tracked in MLflow — or a quick illustrative set generated on demand.
