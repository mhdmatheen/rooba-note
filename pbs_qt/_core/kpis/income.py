import re
import statistics
from collections import defaultdict

from .core import Context, confidence_bucket, inr, merchant_key, month_key, result, weighted_average
from .structure import recurring as recurring_kpi

_FEE_PATTERN = re.compile(r"(charges|charge|fee|fees|interest|gst|penalty|sms charge)")


def _monthly_income(ctx: Context):
    out = defaultdict(float)
    for t in ctx.txns:
        if t.amount > 0:
            out[month_key(t.date)] += t.amount
    return out


def _monthly_spend(ctx: Context):
    out = defaultdict(float)
    for t in ctx.txns:
        if t.amount < 0:
            out[month_key(t.date)] += abs(t.amount)
    return out


def safe_to_spend(ctx: Context):
    income_by_month = _monthly_income(ctx)
    months = sorted(income_by_month)
    last3 = months[-3:]
    expected_income = weighted_average([income_by_month[m] for m in last3]) if last3 else 0.0
    if expected_income <= 0:
        return result("safe_to_spend", "Safe-to-Spend Today", None, "inr", "unknown",
                      confidence_bucket(ctx.months), ctx.months,
                      "Not enough data: need at least one month of income.",
                      extras={"per_day": None})

    from datetime import date
    today = date.today()
    days_in_month = 30
    days_left = max(1, days_in_month - today.day + 1)

    fixed_monthly = sum(
        abs(t.amount) for t in ctx.txns
        if t.amount < 0 and ctx.spend_type_of(t) == "fixed"
    )
    # committed fixed still due this month: expected fixed - fixed already paid this month.
    spent_fixed_this_month = sum(
        abs(t.amount) for t in ctx.txns
        if t.amount < 0 and ctx.spend_type_of(t) == "fixed"
        and t.date.month == today.month and t.date.year == today.year
    )
    committed_fixed = max(0.0, fixed_monthly - spent_fixed_this_month)

    spent_this_month = sum(
        abs(t.amount) for t in ctx.txns
        if t.amount < 0 and t.date.month == today.month and t.date.year == today.year
    )

    committed = committed_fixed
    per_day = (expected_income - committed - spent_this_month) / days_left

    status = "good" if per_day >= 0 else "warning" if per_day >= -500 else "bad"
    explanation = (
        "Estimated monthly income {}. After committed fixed costs and spend so far, "
        "you can safely spend {} per day for the next {} day(s).".format(
            inr(expected_income), inr(max(0.0, per_day)), days_left)
    )
    return result("safe_to_spend", "Safe-to-Spend Today", round(max(0.0, per_day), 2), "inr", status,
                  confidence_bucket(ctx.months), ctx.months, explanation,
                  extras={"per_day": round(per_day, 2), "days_left": days_left,
                          "expected_income": round(expected_income, 2),
                          "committed_fixed": round(committed_fixed, 2),
                          "spent_this_month": round(spent_this_month, 2)})


def income_stability(ctx: Context):
    income_by_month = _monthly_income(ctx)
    months = sorted(income_by_month)
    values = [income_by_month[m] for m in months if income_by_month[m] > 0]
    if len(values) < 3:
        return result("income_stability", "Income Stability", None, "unitless", "unknown",
                      confidence_bucket(ctx.months), ctx.months,
                      "Not enough data: need 3+ months of income.",
                      extras={"cv": None, "sources": 0, "typical_salary_day": None})

    mean = statistics.mean(values)
    std = statistics.stdev(values)
    cv = std / mean if mean else 0.0

    sources = set()
    for t in ctx.txns:
        if t.amount > 0:
            sources.add(merchant_key(t.description))
    income_days = defaultdict(list)
    for t in ctx.txns:
        if t.amount > 0:
            income_days[t.date.day].append(t.amount)
    typical_day = max(income_days, key=lambda d: sum(income_days[d])) if income_days else None

    good, warning = ctx.config["income_stability"]["good"], ctx.config["income_stability"]["warning"]
    status = "good" if cv < good else ("warning" if cv < warning else "bad")
    explanation = (
        "Income varies {:.1f}% (coefficient of variation) across {} months; "
        "{} distinct income source(s).".format(cv * 100, len(values), len(sources))
    )
    return result("income_stability", "Income Stability", round(cv, 4), "unitless", status,
                  confidence_bucket(ctx.months), ctx.months, explanation,
                  extras={"cv": round(cv, 4), "sources": len(sources),
                          "sources_list": sorted(sources), "typical_salary_day": typical_day,
                          "values": [round(v, 2) for v in values]})


def debt_to_income(ctx: Context):
    # Identify EMIs via category (primary) plus recurring detection (deduped).
    income_by_month = _monthly_income(ctx)
    months = sorted(income_by_month)
    last3 = months[-3:]
    monthly_income = weighted_average([income_by_month[m] for m in last3]) if last3 else 0.0

    emi_by_month = defaultdict(float)
    loan_merchants = set()
    for t in ctx.txns:
        if t.amount < 0 and t.category == "EMI":
            emi_by_month[month_key(t.date)] += abs(t.amount)
            loan_merchants.add(merchant_key(t.description))
    emi_months = sorted(emi_by_month)
    emi_m_last3 = emi_months[-3:]
    emi_monthly = (
        sum(emi_by_month[m] for m in emi_m_last3) / len(emi_m_last3)
        if emi_m_last3 else 0.0
    )

    rec = recurring_kpi(ctx)
    for row in rec["extras"].get("rows", []):
        if row.get("cadence") == "monthly" and row.get("merchant") not in loan_merchants:
            emi_monthly += row["monthly_cost"]

    if monthly_income <= 0:
        return result("debt_to_income", "Debt-to-Income", None, "percent", "unknown",
                      confidence_bucket(ctx.months), ctx.months,
                      "Not enough data: need monthly income.",
                      extras={"dti": None, "emi_monthly": round(emi_monthly, 2)})

    dti = emi_monthly / monthly_income
    good, warning = ctx.config["dti"]["good"], ctx.config["dti"]["warning"]
    status = "good" if dti < good else ("warning" if dti < warning else "bad")
    explanation = (
        "Monthly EMI/loans of {} equal {:.1f}% of monthly income.".format(inr(emi_monthly), dti * 100)
    )
    return result("debt_to_income", "Debt-to-Income", round(dti, 4), "percent", status,
                  confidence_bucket(ctx.months), ctx.months, explanation,
                  extras={"dti": round(dti, 4), "emi_monthly": round(emi_monthly, 2),
                          "monthly_income": round(monthly_income, 2)})


def fees_interest(ctx: Context):
    fees = [t for t in ctx.txns if t.amount < 0 and _FEE_PATTERN.search(str(t.description or "").lower())]
    total = sum(abs(t.amount) for t in fees)
    yearly = defaultdict(float)
    for t in fees:
        yearly[month_key(t.date)[:4]] += abs(t.amount)

    status = "warning" if total > 0 else "good"
    explanation = (
        "{} in avoidable fees and interest across {} charge(s).".format(inr(total), len(fees))
        if fees else "No fees or interest detected."
    )
    return result("fees_interest", "Fees & Interest Paid", round(total, 2), "inr", status,
                  confidence_bucket(ctx.months), ctx.months, explanation,
                  extras={"count": len(fees), "total": round(total, 2),
                          "yearly": {y: round(a, 2) for y, a in yearly.items()},
                          "items": [{"date": t.date.date().isoformat(), "description": t.description,
                                     "amount": round(abs(t.amount), 2)} for t in sorted(fees, key=lambda t: t.date, reverse=True)]})