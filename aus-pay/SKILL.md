---
name: aus-pay
description: Calculate Australian take-home pay, income tax, Medicare levy, Medicare levy surcharge, HELP/HECS (STSL) repayments, and superannuation. Use when asked about Australian salary/pay calculations, take-home or net pay, PAYG tax, HECS/HELP repayments, salary packaging, salary sacrifice, super guarantee, tax brackets, LITO/SAPTO offsets, or comparing job offers in AUD. Covers FY 2025-26 and 2026-27, residents, non-residents, and working holiday makers.
---

# Australian Pay Calculator

Calculate take-home pay the way paycalculator.com.au and the ATO income tax estimator do: annual liability (income tax − offsets + Medicare levy + MLS + HELP repayment), divided into pay periods.

## Quick start

Run the bundled calculator — do NOT hand-compute tax; the script encodes verified ATO figures:

```bash
python3 scripts/auspay.py --income 100000                          # FY 2026-27 resident
python3 scripts/auspay.py --income 120000 --includes-super --help-debt
python3 scripts/auspay.py --income 90000 --year 2025-26 --residency whm --json
python3 scripts/auspay.py --selftest                               # verify integrity
```

Key flags: `--year 2025-26|2026-27`, `--frequency annual|monthly|fortnightly|weekly`, `--hourly --hours-per-week 38`, `--includes-super`, `--salary-sacrifice N`, `--residency resident|nonresident|whm`, `--help-debt` (or `--help-balance N` to cap repayment), `--private-hospital-cover`, `--family --dependants N --family-income N`, `--medicare-exemption full|half`, `--sapto single|couple|illness-separated`, `--fringe-benefits N`, `--deductions N`, `--other-income N`, `--json`.

## Calculation pipeline

1. **Annualise** income (weekly ×52, fortnightly ×26, monthly ×12, hourly ×38×52 by default).
2. **Split super**: if package includes super, base = package ÷ (1 + SG rate). SG is 12% both years. Cap SG at the maximum contribution base.
3. **Taxable income** = base − salary-sacrificed super − deductions + other income.
4. **Income tax** from bracket table for residency (resident / foreign resident / working holiday maker). NOTE: 2026-27 second bracket is 15% (legislated cut from 16%); 2027-28 will be 14%.
5. **Offsets**: LITO (residents, auto), SAPTO (if eligible). Non-refundable; reduce income tax only — never Medicare levy, MLS, or HELP.
6. **Medicare levy** 2% (residents only), with low-income shade-in (10c per $1 over lower threshold) and full/half exemptions.
7. **MLS** if no private hospital cover and income-for-MLS-purposes exceeds tier thresholds. Tier decided on full MLS income; surcharge charged on taxable + reportable fringe benefits.
8. **HELP/STSL** repayment on repayment income (taxable + reportable super + fringe benefits + investment losses). Marginal 15c/17c bands, then flat 10% of TOTAL income above top threshold. Cap at loan balance.
9. **Net** = base − sacrifice − all of the above. Report Division 293 separately (usually paid from super).

## Reference files — read before answering non-trivial questions

- `references/tax-rates-offsets.md` — bracket tables (2025-26, 2026-27, 2027-28), non-resident and WHM rates, LITO, SAPTO, tax-free threshold, no-TFN withholding rates.
- `references/medicare-help-super.md` — Medicare levy reduction thresholds, exemption categories, MLS tiers, HELP/STSL thresholds + income definition + Schedule 8 withholding coefficients, SG/caps/Div 293, salary-sacrifice interactions.
- `references/edge-cases.md` — withholding vs annual liability, pay-frequency and rounding conventions, 53-week years, includes-super math, feature map of paycalculator.com.au, known traps.

## Rules that prevent wrong answers

1. **Never compute Australian tax from memory.** Use the script or the reference tables. Rates change every year and mid-decade reforms (stage 3, 15%/14% cuts, HELP marginal system, Payday Super) invalidate trained knowledge.
2. **Ask which financial year** if ambiguous; default to the FY containing today (FY runs 1 July – 30 June).
3. **Distinguish payslip withholding from annual liability.** The script computes annual liability ÷ periods. Actual payslips use ATO Schedule 1/8 withholding formulas — slightly higher, refunded at tax time. Say so when relevant.
4. **Salary sacrifice reduces taxable income but NOT HELP repayment income, MLS income, or Div 293 income** (reportable super is added back), and NOT the employer's SG base.
5. **HELP top tier is a cliff**: flat 10% of total repayment income at/above the top threshold, not marginal.
6. **Non-residents**: no tax-free threshold, no LITO, no Medicare levy. WHM: 15% from first dollar; 45% flat if no TFN.
7. For years outside 2025-26/2026-27 or unpublished thresholds (e.g. 2026-27 Medicare low-income), state the assumption and flag it — the script emits warnings for these.
8. This is an estimate for general guidance, not tax advice. Say so for high-stakes decisions (Div 293, contribution caps, residency changes).

## Updating for a new financial year

Add a new entry to the `YEARS` dict in `scripts/auspay.py` and update reference tables. Verify against: ato.gov.au tax-rates pages (blocks default fetchers — use a browser user-agent), the study-and-training-loans thresholds page, and key-superannuation-rates. Then extend `--selftest` with a known value and run it.
