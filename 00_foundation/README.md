# 00 — Foundation (run once, not part of the demo)

Builds the synthetic world everything else runs on. Run job
**`lifecast_synthetic_foundation`** once after deploy; nothing here is shown
to a client directly.

| # | Asset | What it does |
|---|---|---|
| 00 | `00_synthetic_policy_book` | 50,000-policy Bricksurance Life term book, written as the file-shaped overnight policy-admin feed. Also parks the bad-feed-day file (used by use case 01). |
| 01 | `01_prophet_extract_mock` | The **before-state anchor**: a mock model point extract in the classic fixed-column MPF layout the downstream liability model consumes today. Use case 01 must reproduce it exactly. |

The foundation job also runs `02_assumption_governance/00_assumption_master`
(seeds the baseline basis + Excel template).

> Everything generated is synthetic. Bricksurance Life is fictional; no client
> data, no pricing logic, no actuarial formulae.
