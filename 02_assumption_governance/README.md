# 02 — Assumption governance (use case 2)

**The story:** *"I still enter shocks and loadings in Excel where I peer-review
them — now there's version history and an approval step, not a filename and an
email chain."* Mortality / lapse / expense live as versioned Delta tables;
Databricks is master, Excel stays the entry surface; every action is audited.

**Drive it with two jobs** (maker and checker, deliberately separate):
`lifecast_assumption_entry` → drafts a shocked basis, submits it (PENDING_APPROVAL);
`lifecast_assumption_approval` → approve (old basis SUPERSEDED) or reject.

| # | Asset | What it does |
|---|---|---|
| 00 | `00_assumption_master` | One-time setup (run by the foundation job): `asm_mortality/lapse/expense` versioned by `assumption_set_id`, the `asm_assumption_sets` registry, append-only `asm_approval_log`, UC functions `asm_active_set_id()` / `asm_*_active()` (the single read path), and the Excel entry template → `lifecast_files/excel/`. |
| 01 | `01_excel_entry_roundtrip` | The **maker** step, headless: runs exactly the SQL the Excel template submits via `DATABRICKS.SQL` (+10% smoker loading by default). |
| 02 | `02_assumption_approval` | The **checker** step: approve or reject the pending basis, fully audited. Shows `asm_governance_dashboard` at the end. |

**Where to look while presenting:** `asm_governance_dashboard` (every basis,
status, who/when), `asm_approval_log` (the full trail — including the rejected
stress basis), and the latest `gld_quality_dashboard` row — each overnight run
records **which basis was in force** (the SII / IFRS 17 reproducibility line).

**Today → tomorrow:** today, standalone workbooks version-controlled by
filename. Tomorrow, versioned Delta tables with an approval workflow — Excel
entry preserved, Databricks as master.
