# LifeCast — App Structure Spec
## The Cockpit: blocks → beats → tabs. All placeholders except the model-points beat.

| | |
|---|---|
| **App** | `lifecast-workbench` — the LifeCast Cockpit |
| **Pairs with** | `LIFECAST_BUILD_BRIEF.md` (§9 The App), `CLAUDE.md` |
| **Status** | Spec. Only the model-points beat + the Overview map are live; everything else is an openly-marked placeholder. |
| **Last updated** | 11 June 2026 |

---

## 1. What it is

A presenter's cockpit — a thin layer over the real Databricks assets, in the Bricksurance design system. Not a business-process simulation. The Databricks SA picks a block and a beat and is routed to the right place, with what it proves and how it's built underneath. Right now one beat is real (model points); everything else is a placeholder that states intent, not a fake feature.

---

## 2. The hierarchy

- **Block** — a left-nav item; a business-process area; the solution shape. (Same set as the Overview map nodes.)
- **Beat** — a demo step opened from *inside* a block; the guided walkthrough. **Never a left-nav item.**
- **Tabs** — the three tabs inside a beat: **1 What we're showing · 2 Old → new · 3 Management**.
- **Presenter drawer** — collapsible; holds the step running order for the SA. **Not in the client-facing left pane.**

**Rule:** the left pane shows blocks only. Beats and tabs live one level down. That's what keeps it looking like a solution, not a demo script.

---

## 3. Placeholder treatment

Every not-yet-built block, beat or feature is **openly stubbed**: muted styling, a "coming" / "roadmap" tag, and one line of *what this will show*. A placeholder never fake-works — it states intent, it does not simulate a result. Live vs placeholder is always visually distinct, so the demo stays credible.

---

## 4. Left-nav blocks

### Overview — LIVE (structure)
The landing map, with a **today ↔ destination** toggle.
- **Today** — the full picture: inputs → engine → outputs. The engine is marked as the *destination*, not excluded. The model-points node is live and clickable; other nodes show their state (next / planned).
- **Destination** — the simplified end-state: seriatim, no grouping, no legacy engine, end to end; "what drops out" + "what you gain".
- The map nodes are the visual form of the left nav — clicking a node = opening the block.

### Inputs
- **Model points — LIVE.** The one built beat. Tabs: *process* (plain, tool-free) / *old → new* (what becomes what; ends in the scope-handoff block → engine → next: assumptions) / *management* (data-quality gate, run-overseer agent).
- **Assumptions — PLACEHOLDER.** Tabs stubbed. *Process:* setting mortality, lapse, expense. *Old → new:* Excel workbooks one person owns → governed Delta tables + Excel round-trip. *Management:* versioning, sign-off, experience agent. Posture: "bring yours / show how to derive them".
- **Scenarios (ESG) — PLACEHOLDER.** *Process:* economic scenarios for market-consistent runs. *Old → new:* provider file on a share → governed in Delta (input from Moody's), **or** QuantLib generated in-platform (show the package). *Management:* calibration tracked, versioned.

### Modelling — PLACEHOLDER
The projection — the content move. *Process:* policies + assumptions → cashflows → reserve. *Old → new:* Prophet content → Python on the platform, validated side-by-side. *Management:* run-overseer + reconciliation agents, MLflow runs, validate-to-tolerance. Low-hanging fruit = deterministic term projection; stochastic = roadmap (the hard last mile).

### Results — PLACEHOLDER
FCF / IFRS 17 outputs. *Process:* fulfilment cash flows = PV of future cash flows + risk adjustment, by IFRS 17 group; feeds the CSM engine downstream. *Old → new:* CSV dump + Excel board pack → Delta + AI/BI + Genie. *Management:* movement & disclosure agent, actual-vs-expected, movement analysis.

### Governance — PLACEHOLDER (the cross-cutting showcase)
The aggregated view of the lead seller. Stubs:
- **Trace this number** — lineage policy → assumption → cashflow → FCF.
- **Sign-off gates** — assumption + run-release.
- **Version & reproduce** — reproduce a historical valuation exactly.
- **Model risk register** — validation status, owner, reconciliation-to-Prophet result.
- **Roles & segregation of duties** — preparer / reviewer / approver.

Governance also appears contextually in each beat's management tab; this block is the one-place view.

### Roadmap / Wider solution — PLACEHOLDER (all)
The "fits in a business process" plug-points, marked "connects here / roadmap":
- **Downstream:** → IFRS 17 CSM engine / sub-ledger · → capital (SCR) · → general ledger · → reporting & disclosures · → ALM / treasury.
- **Upstream:** ← policy admin · ← finance data.
- **Loop:** experience analysis → back into assumptions.
- **Suite:** sibling Bricksurance Life workbenches (pricing, claims).

---

## 5. Agents — contextual, in management tabs

| Agent | Lives in | Status |
|---|---|---|
| Run overseer — "did it complete, anything quarantined, safe to release?" | Model points / Modelling | specced |
| Reconciliation — explains where Databricks and Prophet differ, and why | Modelling | placeholder |
| Movement & disclosure — IFRS 17 movement attribution, drafts commentary | Results | placeholder |
| Experience — actual-vs-expected summary, proposes an assumption adjustment | Assumptions | placeholder |
| Audit & documentation — drafts model docs, sign-off note, "what fed this number" | Governance | placeholder |

Place agents where they help, not in a list. An optional light "Agents" index is fine only if showcasing them together.

---

## 6. Cross-cutting rules

- Thin layer; no business logic; placeholders openly stubbed, never fake-working.
- Bricksurance design system; sentence case; the `lifecast` naming convention.
- Each beat = three tabs, each opening with **one plain, speakable lead line** (no "Say this" chrome — the copy is the script).
- Each *old → new* tab ends with the **scope/handoff block**: this input → engine → next input.
- **No money or cost framing** in any flow.
- Presenter drawer holds the step order; the left pane shows **blocks only**.

---

## 7. What's real right now

- **Live:** the model-points beat (Phase 1) and the Overview map structure.
- **Everything else:** placeholder. Built out as phases land and the client asks the next question.
