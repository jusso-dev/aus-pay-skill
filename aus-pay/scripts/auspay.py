#!/usr/bin/env python3
"""Australian take-home pay calculator.

Computes annual tax liability (ATO assessment method, like paycalculator.com.au)
and per-period breakdowns. Figures verified against ato.gov.au July 2026.

This computes the ANNUAL LIABILITY divided into pay periods — not the ATO
Schedule 1 PAYG withholding formulas. Actual payslip withholding differs
slightly; the annual result is what matters after a tax return.

Usage examples:
  auspay.py --income 100000
  auspay.py --income 120000 --year 2025-26 --includes-super --help-debt
  auspay.py --income 90000 --residency whm --json
  auspay.py --selftest
"""

import argparse
import json
import sys

# ---------------------------------------------------------------------------
# Year-indexed parameters. All figures verified from ato.gov.au / legislation.
# ---------------------------------------------------------------------------

YEARS = {
    "2025-26": {
        "resident_brackets": [  # (threshold, marginal rate above threshold)
            (0, 0.0), (18200, 0.16), (45000, 0.30), (135000, 0.37), (190000, 0.45),
        ],
        "nonresident_brackets": [
            (0, 0.30), (135000, 0.37), (190000, 0.45),
        ],
        "whm_brackets": [
            (0, 0.15), (45000, 0.30), (135000, 0.37), (190000, 0.45),
        ],
        "medicare_rate": 0.02,
        # Medicare levy low-income reduction (2025-26 legislated values)
        "medicare_single_lower": 28011,
        "medicare_single_upper": 35013,
        "medicare_family_lower": 47238,
        "medicare_family_upper": 59047,
        "medicare_family_lower_per_child": 4338,
        "medicare_family_upper_per_child": 5423,
        "medicare_sapto_single_lower": 44268,
        "medicare_sapto_single_upper": 55335,
        # MLS tiers: (single threshold, family threshold, rate)
        "mls_tiers": [
            (101000, 202000, 0.0),
            (118000, 236000, 0.01),
            (158000, 316000, 0.0125),
            (float("inf"), float("inf"), 0.015),
        ],
        "mls_family_per_extra_child": 1500,
        # HELP/STSL marginal system (from 2025-26)
        "help_min": 67000,
        "help_mid": 125000,          # 15c band ends here
        "help_mid_base": 8700,       # repayment at help_mid
        "help_top": 179286,          # at/above: flat 10% of total repayment income
        "sg_rate": 0.12,
        "max_contribution_base_annual": 250000,  # $62,500/quarter x 4
        "concessional_cap": 30000,
        "div293_threshold": 250000,
    },
    "2026-27": {
        "resident_brackets": [
            (0, 0.0), (18200, 0.15), (45000, 0.30), (135000, 0.37), (190000, 0.45),
        ],
        "nonresident_brackets": [
            (0, 0.30), (135000, 0.37), (190000, 0.45),
        ],
        "whm_brackets": [
            (0, 0.15), (45000, 0.30), (135000, 0.37), (190000, 0.45),
        ],
        "medicare_rate": 0.02,
        # 2026-27 low-income thresholds not yet legislated; 2025-26 values used
        # as provisional (flagged in output).
        "medicare_single_lower": 28011,
        "medicare_single_upper": 35013,
        "medicare_family_lower": 47238,
        "medicare_family_upper": 59047,
        "medicare_family_lower_per_child": 4338,
        "medicare_family_upper_per_child": 5423,
        "medicare_sapto_single_lower": 44268,
        "medicare_sapto_single_upper": 55335,
        "medicare_thresholds_provisional": True,
        "mls_tiers": [
            (105000, 210000, 0.0),
            (123000, 246000, 0.01),
            (164000, 328000, 0.0125),
            (float("inf"), float("inf"), 0.015),
        ],
        "mls_family_per_extra_child": 1500,
        "help_min": 69528,
        "help_mid": 129717,
        "help_mid_base": 9028,
        "help_top": 186051,
        "sg_rate": 0.12,
        "max_contribution_base_annual": 270830,  # Payday Super annual base
        "concessional_cap": 32500,
        "div293_threshold": 250000,
    },
}

DEFAULT_YEAR = "2026-27"

# LITO and SAPTO parameters (static across both years)
LITO_MAX = 700
LITO_TAPER1_START, LITO_TAPER1_RATE = 37500, 0.05
LITO_TAPER2_START, LITO_TAPER2_RATE = 45000, 0.015
LITO_TAPER2_BASE = 325

SAPTO = {  # status: (max offset, shade-out threshold); taper 12.5c/$1
    "single": (2230, 34919),
    "couple": (1602, 30994),
    "illness-separated": (2040, 33732),
}

PERIODS = {"annual": 1, "monthly": 12, "fortnightly": 26, "weekly": 52}
STANDARD_WEEK_HOURS = 38.0


def tax_from_brackets(taxable, brackets):
    tax = 0.0
    for i, (threshold, rate) in enumerate(brackets):
        upper = brackets[i + 1][0] if i + 1 < len(brackets) else float("inf")
        if taxable > threshold:
            tax += (min(taxable, upper) - threshold) * rate
        else:
            break
    return tax


def lito(taxable):
    if taxable <= LITO_TAPER1_START:
        return LITO_MAX
    if taxable <= LITO_TAPER2_START:
        return LITO_MAX - (taxable - LITO_TAPER1_START) * LITO_TAPER1_RATE
    return max(0.0, LITO_TAPER2_BASE - (taxable - LITO_TAPER2_START) * LITO_TAPER2_RATE)


def sapto(rebate_income, status):
    max_offset, shade_out = SAPTO[status]
    return max(0.0, max_offset - max(0.0, rebate_income - shade_out) * 0.125)


def medicare_levy(taxable, y, *, exemption=None, family=False, dependants=0,
                  family_income=None, sapto_eligible=False):
    """Medicare levy with low-income reduction. Family reduction is an
    approximation (10c per $1 of family income over the family lower
    threshold, capped at the individual's full levy)."""
    if exemption == "full":
        return 0.0
    rate = y["medicare_rate"] / (2 if exemption == "half" else 1)
    full = taxable * rate
    if family or dependants:
        inc = family_income if family_income is not None else taxable
        lower = y["medicare_family_lower"] + dependants * y["medicare_family_lower_per_child"]
        upper = y["medicare_family_upper"] + dependants * y["medicare_family_upper_per_child"]
        if inc <= lower:
            return 0.0
        if inc <= upper:
            return min(full, (inc - lower) * 0.10)
        return full
    lower = y["medicare_sapto_single_lower"] if sapto_eligible else y["medicare_single_lower"]
    if taxable <= lower:
        return 0.0
    return min(full, (taxable - lower) * 0.10)


def mls(mls_income, charge_base, y, *, family=False, dependants=0, has_cover=False):
    if has_cover:
        return 0.0, "base (has cover)"
    extra_kids = max(0, dependants - 1)
    names = ["base", "tier 1", "tier 2", "tier 3"]
    for (single_t, family_t, rate), name in zip(y["mls_tiers"], names):
        threshold = family_t + extra_kids * y["mls_family_per_extra_child"] if (family or dependants) else single_t
        if mls_income <= threshold:
            return charge_base * rate, name
    return charge_base * y["mls_tiers"][-1][2], "tier 3"


def help_repayment(repayment_income, y, balance=None):
    ri = repayment_income
    if ri >= y["help_top"]:
        amount = ri * 0.10
    elif ri > y["help_mid"]:
        amount = y["help_mid_base"] + (ri - y["help_mid"]) * 0.17
    elif ri > y["help_min"]:
        amount = (ri - y["help_min"]) * 0.15
    else:
        amount = 0.0
    if balance is not None:
        amount = min(amount, balance)
    return amount


def calculate(args):
    y = YEARS[args.year]
    warnings = []

    # Gross annualisation
    gross = args.income
    if args.frequency != "annual":
        gross *= PERIODS[args.frequency]
    if args.hourly:
        gross = args.income * args.hours_per_week * 52

    # Super
    sg = args.super_rate if args.super_rate is not None else y["sg_rate"]
    if args.includes_super:
        base_salary = gross / (1 + sg)
    else:
        base_salary = gross
    sg_earnings = min(base_salary, y["max_contribution_base_annual"])
    employer_super = sg_earnings * sg
    if base_salary > y["max_contribution_base_annual"]:
        warnings.append(
            f"Salary exceeds maximum contribution base (${y['max_contribution_base_annual']:,}); "
            "employer SG capped accordingly.")

    sacrifice = args.salary_sacrifice
    concessional = employer_super + sacrifice
    if concessional > y["concessional_cap"]:
        warnings.append(
            f"Concessional contributions ${concessional:,.0f} exceed the "
            f"${y['concessional_cap']:,} cap; excess is taxed at marginal rates.")

    taxable = max(0.0, base_salary - sacrifice - args.deductions + args.other_income)

    # Income tax by residency
    if args.residency == "resident":
        brackets = y["resident_brackets"]
    elif args.residency == "nonresident":
        brackets = y["nonresident_brackets"]
    else:
        brackets = y["whm_brackets"]
    income_tax = tax_from_brackets(taxable, brackets)

    # Offsets (non-refundable, income tax only)
    lito_amt = lito(taxable) if args.residency == "resident" else 0.0
    sapto_amt = sapto(taxable, args.sapto) if args.sapto else 0.0
    offsets = min(income_tax, lito_amt + sapto_amt)
    income_tax_after_offsets = income_tax - offsets

    # Medicare levy (residents only)
    if args.residency == "resident":
        levy = medicare_levy(
            taxable, y, exemption=args.medicare_exemption, family=args.family,
            dependants=args.dependants, family_income=args.family_income,
            sapto_eligible=bool(args.sapto))
        if y.get("medicare_thresholds_provisional"):
            warnings.append("2026-27 Medicare low-income thresholds not yet "
                            "legislated; using 2025-26 values.")
    else:
        levy = 0.0

    # Reportable amounts feed MLS and HELP income definitions
    reportable_super = sacrifice
    mls_income = taxable + args.fringe_benefits + reportable_super + args.investment_losses
    repayment_income = mls_income  # same definition for HELP repayment income

    surcharge, mls_tier = (0.0, "n/a")
    if args.residency == "resident":
        surcharge, mls_tier = mls(
            mls_income, taxable + args.fringe_benefits, y,
            family=args.family, dependants=args.dependants,
            has_cover=args.private_hospital_cover)

    help_amt = 0.0
    if args.help_debt or args.help_balance is not None:
        help_amt = help_repayment(repayment_income, y, balance=args.help_balance)

    # Division 293 (reported, not subtracted from take-home: usually paid from super)
    div293 = 0.0
    div293_income = taxable + concessional
    if div293_income > y["div293_threshold"]:
        div293 = 0.15 * min(div293_income - y["div293_threshold"], concessional)

    total_tax = income_tax_after_offsets + levy + surcharge + help_amt
    cash_gross = base_salary - sacrifice
    net = cash_gross - total_tax

    result = {
        "year": args.year,
        "residency": args.residency,
        "package_gross": round(gross, 2),
        "base_salary_ex_super": round(base_salary, 2),
        "employer_super": round(employer_super, 2),
        "salary_sacrifice_super": round(sacrifice, 2),
        "taxable_income": round(taxable, 2),
        "income_tax_gross": round(income_tax, 2),
        "lito": round(lito_amt, 2),
        "sapto": round(sapto_amt, 2),
        "income_tax_after_offsets": round(income_tax_after_offsets, 2),
        "medicare_levy": round(levy, 2),
        "medicare_levy_surcharge": round(surcharge, 2),
        "mls_tier": mls_tier,
        "help_repayment": round(help_amt, 2),
        "total_tax": round(total_tax, 2),
        "net_income_annual": round(net, 2),
        "division_293_tax": round(div293, 2),
        "effective_tax_rate_pct": round(100 * total_tax / taxable, 2) if taxable else 0.0,
        "per_period": {
            name: {"gross": round(cash_gross / n, 2),
                   "tax": round(total_tax / n, 2),
                   "net": round(net / n, 2),
                   "super": round(employer_super / n, 2)}
            for name, n in PERIODS.items()
        },
        "warnings": warnings,
    }
    return result


def render(r):
    lines = [
        f"FY {r['year']} — {r['residency']}",
        f"  Package (gross):        ${r['package_gross']:>12,.2f}",
        f"  Base salary (ex super): ${r['base_salary_ex_super']:>12,.2f}",
        f"  Employer super:         ${r['employer_super']:>12,.2f}",
    ]
    if r["salary_sacrifice_super"]:
        lines.append(f"  Salary sacrifice super: ${r['salary_sacrifice_super']:>12,.2f}")
    lines += [
        f"  Taxable income:         ${r['taxable_income']:>12,.2f}",
        f"  Income tax:             ${r['income_tax_gross']:>12,.2f}",
    ]
    if r["lito"]:
        lines.append(f"  LITO:                  -${r['lito']:>12,.2f}")
    if r["sapto"]:
        lines.append(f"  SAPTO:                 -${r['sapto']:>12,.2f}")
    lines += [
        f"  Medicare levy:          ${r['medicare_levy']:>12,.2f}",
    ]
    if r["medicare_levy_surcharge"]:
        lines.append(f"  Medicare levy surcharge ({r['mls_tier']}): ${r['medicare_levy_surcharge']:,.2f}")
    if r["help_repayment"]:
        lines.append(f"  HELP/STSL repayment:    ${r['help_repayment']:>12,.2f}")
    lines += [
        f"  Total tax:              ${r['total_tax']:>12,.2f}",
        f"  NET (take-home):        ${r['net_income_annual']:>12,.2f}"
        f"   ({r['effective_tax_rate_pct']}% effective)",
        "",
        f"  {'Period':<12}{'Gross':>14}{'Tax':>14}{'Net':>14}{'Super':>14}",
    ]
    for name, p in r["per_period"].items():
        lines.append(f"  {name:<12}{p['gross']:>14,.2f}{p['tax']:>14,.2f}"
                     f"{p['net']:>14,.2f}{p['super']:>14,.2f}")
    if r["division_293_tax"]:
        lines.append(f"\n  Division 293 tax (usually paid from super): ${r['division_293_tax']:,.2f}")
    for w in r["warnings"]:
        lines.append(f"  ! {w}")
    return "\n".join(lines)


def selftest():
    cases = [
        # (kwargs, field, expected)
        (dict(income=100000, year="2025-26"), "income_tax_gross", 20788.00),
        (dict(income=100000, year="2025-26"), "medicare_levy", 2000.00),
        (dict(income=100000, year="2025-26"), "net_income_annual", 77212.00),
        (dict(income=100000, year="2026-27"), "income_tax_gross", 20520.00),
        (dict(income=100000, year="2026-27"), "net_income_annual", 77480.00),
        # LITO: $30,000 income → full $700
        (dict(income=30000, year="2025-26"), "lito", 700.00),
        # LITO taper 2: $50,000 → 325 − 5000×0.015 = 250
        (dict(income=50000, year="2025-26"), "lito", 250.00),
        # Medicare shade-in (ATO worked example): $29,000 → $98.90
        (dict(income=29000, year="2025-26"), "medicare_levy", 98.90),
        # HELP 2025-26: $80,000 → (80000−67000)×0.15 = 1950
        (dict(income=80000, year="2025-26", help_debt=True), "help_repayment", 1950.00),
        # HELP 2025-26 mid band: $150,000 → 8700 + 25000×0.17 = 12950
        (dict(income=150000, year="2025-26", help_debt=True), "help_repayment", 12950.00),
        # HELP 2025-26 flat tier: $200,000 → 10% = 20000
        (dict(income=200000, year="2025-26", help_debt=True), "help_repayment", 20000.00),
        # HELP 2026-27: $100,000 → (100000−69528)×0.15 = 4570.80
        (dict(income=100000, year="2026-27", help_debt=True), "help_repayment", 4570.80),
        # MLS 2026-27 single no cover: $120,000 → tier 1 → 1% = 1200
        (dict(income=120000, year="2026-27"), "medicare_levy_surcharge", 1200.00),
        # MLS with cover: 0
        (dict(income=120000, year="2026-27", private_hospital_cover=True),
         "medicare_levy_surcharge", 0.00),
        # Non-resident $100k: 30% flat, no Medicare, no LITO
        (dict(income=100000, year="2026-27", residency="nonresident"),
         "income_tax_gross", 30000.00),
        (dict(income=100000, year="2026-27", residency="nonresident"),
         "medicare_levy", 0.00),
        # WHM $45,000 → 15% = 6750
        (dict(income=45000, year="2026-27", residency="whm"), "income_tax_gross", 6750.00),
        # Includes super 2026-27: $112,000 package → base 100,000
        (dict(income=112000, year="2026-27", includes_super=True),
         "base_salary_ex_super", 100000.00),
        # Salary sacrifice reduces taxable but feeds HELP repayment income:
        # $100k, sacrifice $10k → taxable 90k; repayment income 100k → HELP 4570.80
        (dict(income=100000, year="2026-27", salary_sacrifice=10000, help_debt=True),
         "help_repayment", 4570.80),
        (dict(income=100000, year="2026-27", salary_sacrifice=10000),
         "taxable_income", 90000.00),
    ]
    failures = 0
    for kwargs, field, expected in cases:
        args = build_parser().parse_args([])
        args.income = kwargs.pop("income")
        for k, v in kwargs.items():
            setattr(args, k, v)
        r = calculate(args)
        got = r[field]
        ok = abs(got - expected) < 0.01
        status = "PASS" if ok else "FAIL"
        if not ok:
            failures += 1
        print(f"{status} {field}={got} (expected {expected}) for {kwargs}")
    print(f"\n{len(cases) - failures}/{len(cases)} passed")
    return 1 if failures else 0


def build_parser():
    p = argparse.ArgumentParser(description="Australian take-home pay calculator")
    p.add_argument("--income", type=float, help="Income amount (per --frequency)")
    p.add_argument("--year", choices=sorted(YEARS), default=DEFAULT_YEAR)
    p.add_argument("--frequency", choices=sorted(PERIODS), default="annual",
                   help="Frequency of --income input")
    p.add_argument("--hourly", action="store_true",
                   help="Treat --income as hourly rate")
    p.add_argument("--hours-per-week", type=float, default=STANDARD_WEEK_HOURS)
    p.add_argument("--includes-super", action="store_true",
                   help="Income is a package including super")
    p.add_argument("--super-rate", type=float, default=None,
                   help="Override SG rate as decimal, e.g. 0.12")
    p.add_argument("--salary-sacrifice", type=float, default=0.0,
                   help="Annual salary-sacrificed super")
    p.add_argument("--residency", choices=["resident", "nonresident", "whm"],
                   default="resident")
    p.add_argument("--help-debt", action="store_true", help="Has HELP/STSL debt")
    p.add_argument("--help-balance", type=float, default=None,
                   help="Outstanding HELP balance (caps repayment)")
    p.add_argument("--medicare-exemption", choices=["full", "half"], default=None)
    p.add_argument("--family", action="store_true",
                   help="Use family Medicare/MLS thresholds")
    p.add_argument("--family-income", type=float, default=None,
                   help="Combined family income for Medicare reduction")
    p.add_argument("--dependants", type=int, default=0)
    p.add_argument("--private-hospital-cover", action="store_true")
    p.add_argument("--sapto", choices=sorted(SAPTO), default=None)
    p.add_argument("--fringe-benefits", type=float, default=0.0,
                   help="Reportable fringe benefits (grossed-up)")
    p.add_argument("--investment-losses", type=float, default=0.0,
                   help="Total net investment losses")
    p.add_argument("--other-income", type=float, default=0.0)
    p.add_argument("--deductions", type=float, default=0.0)
    p.add_argument("--json", action="store_true")
    p.add_argument("--selftest", action="store_true")
    return p


def main():
    args = build_parser().parse_args()
    if args.selftest:
        sys.exit(selftest())
    if args.income is None:
        build_parser().error("--income is required (or use --selftest)")
    r = calculate(args)
    print(json.dumps(r, indent=2) if args.json else render(r))


if __name__ == "__main__":
    main()
