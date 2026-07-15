# Edge cases and calculation conventions

How paycalculator.com.au, paycalculators.com.au and the ATO tools structure the calculation. Verified 15 July 2026.

## Annual liability vs PAYG withholding — the core distinction

Two different numbers, both correct:

1. **Annual liability** (what this skill's calculator computes): full-year tax including offsets (LITO, SAPTO), Medicare reduction, MLS, HELP — divided by pay periods. This is what the person actually owes after their tax return.
2. **PAYG withholding** (what a payslip shows): ATO Schedule 1 formulas per pay period. Slightly different — offsets and deductions apply only at year end, and withholding rounds per period. Differences are "always in favour of the ATO" and come back as a tax refund.

paycalculator.com.au shows both: periodic columns use Schedule 1 withholding, the annual column uses annual liability, and the delta is shown as "Estimated Tax Return". paycalculators.com.au computes annual liability only, divided by periods.

When a user asks "what will my payslip show", note the withholding caveat. When they ask "what do I take home", the annual liability method is the honest answer.

## Pay-frequency conversions (industry convention)

- Weekly = annual ÷ 52
- Fortnightly = annual ÷ 26
- Monthly = annual ÷ 12
- Daily = annual ÷ 260 (5 days × 52)
- Hourly = annual ÷ 52 ÷ 38 (38-hour week per Fair Work Act; paycalculator.com.au default: 38 h, 5 days)

ATO Schedule 1 official conversions (withholding context): fortnightly ÷ 2 → weekly; monthly × 3 ÷ 13 → weekly (add 1c if monthly ends in 33c); back-convert: fortnightly = rounded weekly × 2, monthly = rounded weekly × 13 ÷ 3.

### 53-week / 27-fortnight years

Some years contain 53 weekly or 27 fortnightly pays. Standard withholding under-collects; ATO publishes fixed extra-withholding tiers (e.g. 27 fortnights: +$12/$27/$48 per fortnight by earnings band). Annual liability method is unaffected — only withholding.

## "Salary includes super"

If package $X includes super at rate r: base salary = X ÷ (1 + r). Super = base × r. With 12%: $112,000 package → $100,000 base + $12,000 super. Otherwise super is paid on top of the stated salary.

SG is payable on ordinary time earnings ("qualifying earnings" from 1 July 2026) up to the maximum contribution base — cap employer SG for very high earners (see medicare-help-super.md).

## ATO Schedule 1 withholding rounding (when replicating payslips)

- Formulas: y = a·x − b, where x = weekly earnings ignoring cents + $0.99.
- Result rounded to nearest dollar, 50c rounds up, no intermediate cent rounding.
- Scale 4 (no TFN): flat 47% resident / 45% foreign, ignore cents, no +99c.
- Claimed tax offsets reduce withholding by 1.9% (weekly) / 3.8% (fortnightly) / 8.3% (monthly) / 25% (quarterly) of the annual offset amount, rounded to nearest dollar.
- STSL (HELP) withholding is a separate Schedule 8 component added on top.

## Inputs a full-featured calculator supports (paycalculator.com.au feature map)

- Pay cycle: annual/monthly/fortnightly/weekly/daily/hourly; casual loading (default 1.5×) on daily/hourly; overtime entries; bonus (fixed or % of salary, optional "bonus includes super", bonus fully sacrificed to super)
- Pro-rata part-time (hours/days per week), purchased leave (48/52, 50/52 …)
- Super: custom employer rate, no-super, additional pre-tax (salary sacrifice, with "maximise to cap" option), carry-forward unused concessional cap, spouse contributions, co-contribution/LISTO, concessional + non-concessional caps and excess-contributions tax, max contribution base
- Student loans: HELP/VSL/SSL/ABSTUDY SSL/SFSS/AASL — all use the same STSL thresholds
- Tax category: non-resident, working holiday maker (with/without TFN — no TFN → 45% flat WHM), no tax-free threshold (second job), not-for-profit salary packaging
- Medicare: full/half exemption, spouse + dependants (family reduction), private hospital cover (MLS), SAPTO (single/couple/illness-separated)
- Novated lease: EV FBT exemption, employee contribution method, RFBA effects
- Fringe benefits: reportable (grossed-up) amounts feed MLS income, HELP repayment income, Div 293 — but not taxable income
- Other: deductions, other income, capital gains, business income, franking credits, tax credits, child support
- Division 293 for high earners (taxable + concessional super > $250k)

## Cross-check values (verified against live paycalculator.com.au, FY 2026-27)

- Resident table: $18,201–$45,000 at 15%, tax at $45,000 = $4,020. SG 12%.
- $65,000 gross 2025-26 annual method: income tax $10,288 (= $4,288 + 30% × $20,000), LITO $25.

## Known traps

1. **paycalculators.com.au is stale** (as at July 2026): still shows 2025-26 16% bracket, 11% super, $90k/$180k MLS thresholds, LMITO, and the pre-2025-26 flat-rate HELP tables. Do not use it as a rates source.
2. **LMITO is dead** (ended 2021-22). Any calculator still showing it is wrong.
3. **HELP flat top tier**: from 2025-26 the system is marginal (15c/17c bands) BUT above the top threshold it reverts to a flat 10% of TOTAL repayment income — a cliff, not a marginal band.
4. **Salary sacrifice doesn't reduce HELP/MLS/Div 293 income** — reportable super contributions are added back.
5. **Offsets can't reduce Medicare levy or MLS** — LITO/SAPTO offset income tax only.
6. **MLS tier uses full income-for-MLS-purposes, but the surcharge is charged on taxable income + reportable fringe benefits only.**
7. **Non-residents**: no tax-free threshold, no LITO, no Medicare levy. WHM at unregistered employer → foreign-resident withholding rates.
8. **Bonus in a pay period** spikes withholding in that period (ATO Method A/B for additional payments) but annual liability just treats it as income.
9. ATO's own estimators lag: they assess completed years (Income tax estimator covered up to 2025-26 as at July 2026); they are not forward-year pay calculators.
