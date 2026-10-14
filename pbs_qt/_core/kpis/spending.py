from collections import defaultdict

from .core import (
    Context, confidence_bucket, group_by_month, history_months, inr, month_key, result,
)


def _income_spend(ctx: Context):
    income = sum(t.amount for t in ctx.txns if t.amount > 0)
    spend = sum(abs(t.amount) for t in ctx.txns if t.amount < 0)
    return income, spend


def _monthly_income_spend(ctx: Context):
    income = defaultdict(float)
    spend = defaultdict(float)
    for t in ctx.txns:
        mk = month_key(t.date)
        if t.amount > 0:
            income[mk] += t.amount
        else:
            spend[mk] += abs(t.amount)
    return income, spend


def _rolling3(values):
    out = []
    for i in range(len(values)):
        window = values[max(0, i - 2):i + 1]
        out.append(sum(window) / len(window))
    return out


def savings_rate(ctx: Context):
    income, spend = _income_spend(ctx)
    if income <= 0:
        return result(
            "savings_rate", "Savings Rate", None, "percent", "unknown",
            confidence_bucket(ctx.months), ctx.months,
            "Not enough data: no income recorded in this period.",
        )
    rate = (income - spend) / income

    monthly_income, monthly_spend = _monthly_income_spend(ctx)
    months = sorted(monthly_income.keys() | monthly_spend.keys())
    rates = [
        (income_m - spend_m) / income_m
        for income_m, spend_m in (
            (monthly_income.get(m, 0.0), monthly_spend.get(m, 0.0)) for m in months
        )
        if income_m > 0
    ]
    rolling = _rolling3(rates) if rates else []

    good = ctx.config["savings_rate"]["good"]
    warning = ctx.config["savings_rate"]["warning"]
    if rate >= good:
        status = "good"
    elif rate >= warning:
        status = "warning"
    else:
        status = "bad"

    explanation = (
        f"You saved {rate * 100:.1f}% of income over the selected period "
        f"({len(rates)} month(s) used). "
        f"{'3-mo rolling avg: ' + ', '.join(f'{r * 100:.1f}%' for r in rolling) + '.' if rolling else ''}"
    )
    return result(
        "savings_rate", "Savings Rate", round(rate, 4), "percent", status,
        confidence_bucket(ctx.months), ctx.months, explanation,
        extras={
            "trend": [
                {"month": m, "rate": round(r, 4)} for m, r in zip(months, rates)
            ],
            "rolling3": rolling,
        },
    )


def net_cash_flow(ctx: Context):
    income, spend = _income_spend(ctx)
    monthly_income, monthly_spend = _monthly_income_spend(ctx)
    months = sorted(monthly_income.keys() | monthly_spend.keys())
    series = []
    for m in months:
        series.append(round(monthly_income.get(m, 0.0) - monthly_spend.get(m, 0.0), 2))
    rolling = _rolling3(series)
    net = sum(series)
    neg_months = [m for m, v in zip(months, series) if v < 0]
    status = "bad" if neg_months and len(neg_months) == len(series) and net < 0 else (
        "warning" if neg_months else "good")
    if not series:
        status = "unknown"

    explanation = (f"Net cash flow was {inr(net)} over the period ({len(months)} month(s)). "
                   f"Negative months: {', '.join(neg_months) if neg_months else 'none'}.")
    return result(
        "net_cash_flow", "Net Cash Flow", round(net, 2), "inr", status,
        confidence_bucket(ctx.months), ctx.months, explanation,
        extras={"monthly": series, "months": months, "rolling3": rolling,
                "negative_months": neg_months, "income": round(income, 2),
                "spending": round(spend, 2)},
    )


def fixed_vs_variable(ctx: Context):
    fixed = sum(abs(t.amount) for t in ctx.txns if t.amount < 0 and ctx.spend_type_of(t) == "fixed")
    variable = sum(abs(t.amount) for t in ctx.txns if t.amount < 0 and ctx.spend_type_of(t) == "variable")
    total = fixed + variable
    income = sum(t.amount for t in ctx.txns if t.amount > 0)

    fixed_share = (fixed / total) if total else 0.0
    fixed_of_income = (fixed / income) if income else 0.0

    warning = ctx.config["fixed_share"]["warning"]
    bad = ctx.config["fixed_share"]["bad"]
    if not total:
        status = "unknown"
    elif fixed_share > bad:
        status = "bad"
    elif fixed_share > warning:
        status = "warning"
    else:
        status = "good"

    explanation = (
        f"Fixed spending is {inr(fixed)} ({fixed_share * 100:.0f}% of spending, "
        f"{fixed_of_income * 100:.0f}% of income). Variable is {inr(variable)}."
    )
    return result(
        "fixed_vs_variable", "Fixed vs Variable", round(fixed_of_income, 4), "percent", status,
        confidence_bucket(ctx.months), ctx.months, explanation,
        extras={"fixed": round(fixed, 2), "variable": round(variable, 2),
                "total": round(total, 2), "fixed_share": round(fixed_share, 4),
                "fixed_of_income": round(fixed_of_income, 4)},
    )


def essential_discretionary(ctx: Context):
    essential = sum(abs(t.amount) for t in ctx.txns if t.amount < 0 and ctx.essentiality_of(t) == "essential")
    discretionary = sum(abs(t.amount) for t in ctx.txns if t.amount < 0 and ctx.essentiality_of(t) == "discretionary")
    total = essential + discretionary
    income = sum(t.amount for t in ctx.txns if t.amount > 0)

    e_share = (essential / income) if income else None
    d_share = (discretionary / income) if income else None
    s_share = (max(0.0, income - total) / income) if income else None

    benchmark = {"needs": 0.5, "wants": 0.3, "savings": 0.2}
    actual = {"needs": e_share, "wants": d_share, "savings": s_share}
    status = "unknown" if not total else "good"

    explanation = (
        f"Essential spend is {inr(essential)} ({e_share * 100:.0f}% of income), "
        f"discretionary {inr(discretionary)} ({d_share * 100:.0f}% of income), "
        f"against a 50/30/20 benchmark."
    )
    return result(
        "essential_discretionary", "Essential vs Discretionary", round(e_share, 4) if e_share else None,
        "percent", status, confidence_bucket(ctx.months), ctx.months, explanation,
        extras={"essential": round(essential, 2), "discretionary": round(discretionary, 2),
                "benchmark": benchmark, "actual": {
                    k: (round(v, 4) if v is not None else None) for k, v in actual.items()}},
    )


def category_share(ctx: Context):
    by_cat = defaultdict(float)
    by_cat_month = defaultdict(lambda: defaultdict(float))
    for t in ctx.txns:
        if t.amount >= 0:
            continue
        cat = t.category or "Uncategorized"
        by_cat[cat] += abs(t.amount)
        by_cat_month[cat][month_key(t.date)] += abs(t.amount)

    total = sum(by_cat.values())
    months = history_months(ctx.txns)
    current = months[-1] if months else None
    prev = months[-2] if len(months) > 1 else None

    movers = []
    if current and prev:
        for cat in by_cat:
            cur = by_cat_month[cat].get(current, 0.0)
            past = by_cat_month[cat].get(prev, 0.0)
            delta = round(cur - past, 2)
            pct = (delta / past * 100) if past else None
            movers.append({"category": cat, "delta": delta, "pct": pct,
                           "current": round(cur, 2), "previous": round(past, 2)})
    movers.sort(key=lambda m: abs(m["delta"]), reverse=True)
    top_up = [m for m in movers if m["delta"] > 0][:3]
    top_down = sorted([m for m in movers if m["delta"] < 0],
                      key=lambda m: m["delta"])[:3]

    shares = {cat: round(amt / total, 4) for cat, amt in by_cat.items()} if total else {}
    # plain-English mover insight
    if movers and top_up:
        first = top_up[0]
        insight = "Spending is up {} vs last month, driven by {}.".format(
            "{:,}".format(int(abs(first["delta"]))), first["category"])
    elif movers and top_down:
        first = top_down[0]
        insight = "Spending dropped {} vs last month, led by {}.".format(
            "{:,}".format(int(abs(first["delta"]))), first["category"])
    else:
        insight = "No notable month-over-month category changes."

    if total:
        explanation = "Total spending {} across {} categories.".format(inr(total), len(by_cat))
    else:
        explanation = "No spending in this period."
    return result(
        "category_share", "Category Share & Movers", round(total, 2), "inr",
        "good" if total else "unknown", confidence_bucket(ctx.months), ctx.months, explanation,
        extras={"shares": shares, "total": round(total, 2),
                "top_up": top_up, "top_down": top_down, "insight": insight,
                "current_month": current, "previous_month": prev},
    )


def budget(ctx: Context):
    budgets = ctx.config.get("budget_defaults", {})
    by_cat = defaultdict(float)
    total_spend = 0.0
    for t in ctx.txns:
        if t.amount >= 0:
            continue
        cat = t.category or "Uncategorized"
        by_cat[cat] += abs(t.amount)
        total_spend += abs(t.amount)

    if not budgets:
        explanation = "Set monthly budgets per category to see budget vs actual."
        return result("budget", "Budget vs Actual", None, "inr", "unknown",
                      confidence_bucket(ctx.months), ctx.months, explanation,
                      extras={"rows": [], "total_spend": round(total_spend, 2),
                              "projected_month_end": None})

    rows = []
    overall = "good"
    over = False
    for cat, budget_amt in budgets.items():
        if not budget_amt:
            continue
        spent = by_cat.get(cat, 0.0)
        pct = spent / budget_amt if budget_amt else 0.0
        status = "bad" if pct >= 1.0 else ("warning" if pct >= ctx.config["budget_progress"]["warning"] else "good")
        if status != "good":
            overall = status
            over = over or status == "bad"
        rows.append({"category": cat, "budget": round(budget_amt, 2),
                     "actual": round(spent, 2), "pct": round(pct, 4), "status": status})

    # projected month-end based on the pace so far this month (days elapsed).
    projected = None
    from datetime import date
    today = date.today()
    if today.day > 0 and rows:
        days_elapsed = today.day
        days_in_month = 30
        pace = (total_spend / days_elapsed) if days_elapsed else 0.0
        projected = round(pace * days_in_month, 2)

    status = "bad" if over else ("warning" if overall == "warning" else ("good" if rows else "unknown"))
    return result("budget", "Budget vs Actual", round(total_spend, 2), "inr", status,
                  confidence_bucket(ctx.months), ctx.months,
                  f"Spent {inr(total_spend)} against configured budgets over the period.",
                  extras={"rows": rows, "total_spend": round(total_spend, 2),
                          "projected_month_end": projected})