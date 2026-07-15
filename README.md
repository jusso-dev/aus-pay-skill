# aus-pay — Australian Pay Calculator Agent Skill

A reusable agent skill for **Claude Code** and **OpenAI Codex** that calculates Australian take-home pay: income tax, Medicare levy, Medicare levy surcharge, HELP/HECS (STSL) repayments, LITO/SAPTO offsets, and superannuation.

Covers **FY 2025-26 and FY 2026-27** for residents, foreign residents, and working holiday makers. All rates verified against ato.gov.au and legislation (including the legislated 16% → 15% bracket cut from 1 July 2026, the marginal HELP repayment system, and Payday Super changes).

## What's inside

```
aus-pay/
├── SKILL.md                          # skill entry point — pipeline + rules
├── scripts/
│   └── auspay.py                     # deterministic calculator (stdlib only)
└── references/
    ├── tax-rates-offsets.md          # bracket tables, LITO, SAPTO, WHM, non-resident
    ├── medicare-help-super.md        # Medicare levy/MLS, HELP/STSL, super, Div 293
    └── edge-cases.md                 # withholding vs annual liability, conventions, traps
```

## Install

Both Claude Code and Codex use the same SKILL.md format — symlink (or copy) the `aus-pay` folder:

```bash
git clone https://github.com/jusso-dev/aus-pay-skill.git
ln -s "$(pwd)/aus-pay-skill/aus-pay" ~/.claude/skills/aus-pay   # Claude Code
ln -s "$(pwd)/aus-pay-skill/aus-pay" ~/.codex/skills/aus-pay    # Codex
```

Then ask your agent things like *"what's my take-home on $120k including super with a HECS debt?"*

## Use the calculator directly

```bash
python3 aus-pay/scripts/auspay.py --income 100000
python3 aus-pay/scripts/auspay.py --income 120000 --includes-super --help-debt
python3 aus-pay/scripts/auspay.py --income 90000 --year 2025-26 --residency whm --json
python3 aus-pay/scripts/auspay.py --selftest
```

Requires Python 3 (standard library only).

The calculator computes **annual liability divided into pay periods** (the paycalculator.com.au "annual" method) — not per-payslip ATO Schedule 1 withholding. Payslip withholding is slightly higher and refunded at tax time; the reference docs explain the difference and include Schedule 8 STSL withholding coefficients.

## Verified against

- [ATO tax rates — Australian residents](https://www.ato.gov.au/tax-rates-and-codes/tax-rates-australian-residents)
- [ATO study and training support loans](https://www.ato.gov.au/tax-rates-and-codes/study-and-training-loan-repayment-thresholds-and-rates)
- [ATO key superannuation rates](https://www.ato.gov.au/tax-rates-and-codes/key-superannuation-rates-and-thresholds/super-guarantee)
- [Treasury Laws Amendment (More Cost of Living Relief) Act 2025](https://www.ato.gov.au/law/view/pdf/acts/20250028.pdf)
- Cross-checked against live [paycalculator.com.au](https://paycalculator.com.au/) output

Self-test suite: `python3 aus-pay/scripts/auspay.py --selftest` (20 assertions including ATO worked examples).

## Updating for a new financial year

Add a year entry to the `YEARS` dict in `scripts/auspay.py`, update the reference tables, extend `--selftest` with a known value. See "Updating for a new financial year" in `SKILL.md`.

## Disclaimer

Estimates for general guidance only — not tax, financial, or legal advice. Verify significant decisions with a registered tax agent or the ATO.
