# 03 — Results, AI/BI & Genie (use case 3 — end of Track 1)

**The story:** *"I ask 'show me BEL movement vs last quarter by product line' and
get an answer — instead of rebuilding a pivot table."* The liability model's
quarterly CSV dumps land in Delta once, governed; AI/BI and Genie replace the
downstream Excel reporting stack. The CFO export is **always offered** — and the
QRT/XBRL templates stay in Excel. End of this use case = Track 1 complete,
**zero actuarial maths written**.

**Drive it with job `lifecast_results_run`:** results pipeline refresh → CFO
export → dashboard publish → Genie space.

| # | Asset | What it does |
|---|---|---|
| 00 | `00_prophet_results_mock` | The today-state: six quarters of synthetic liability-model results dumped as CSVs onto the volume (`prophet/results/`). Whole-estate scope (3 product lines × 8 cohorts) — wider than the term feed of use case 01, on purpose. Run by the foundation job. |
| 01 | `01_results_pipeline.py` | **Source of pipeline `lifecast_results_pipeline`** (don't run as a notebook): `brz_prophet_results` → `slv_projection_results` (typed + checked) → `gld_results_by_product` + `gld_bel_movement`. |
| 02 | `02_cfo_export` | The board pack as Excel + CSV to `export/board_pack/` on every run. Connect, don't replace. |
| 03 | `03_create_dashboard` | Creates/updates the **`LifeCast — BEL Movement`** Lakeview dashboard in this folder (warehouse resolved at runtime, idempotent). |
| 04 | `04_create_genie_space` | Creates the **`LifeCast — Results`** Genie space over the results layer + assumption registry (create-if-missing). |

**Where to look while presenting:** the dashboard (counters + trend + movement),
then Genie — ask *"Which product line drove the BEL increase in the latest
quarter?"* (the data carries a deliberate GROUP_PROTECTION jump), then
*"Which assumption basis is currently approved and who approved it?"* to tie
back to use case 02. Lineage on `gld_bel_movement` runs all the way from the CSV dump.

**Questions to seed in the Genie UI** (the create API doesn't take them):
BEL movement vs last quarter by product line · which product drove the latest
increase · total BEL trend · cohort contribution to GROUP_PROTECTION ·
currently approved basis and approver.

**Today → tomorrow:** today, the model dumps CSVs and the board pack is rebuilt
in Excel each quarter. Tomorrow, outputs land in Delta; AI/BI + Genie answer
instantly; the CFO export is one click and always current.
