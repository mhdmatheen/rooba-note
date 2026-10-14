from collections import defaultdict
from datetime import timedelta

from .core import Context, confidence_bucket, inr, merchant_key, month_key, result


def _monthly_spend(ctx: Context):
    out = defaultdict(float)
    for t in ctx.txns:
        if t.amount < 0:
            out[month_key(t.date)] += abs(t.amount)
    return out


def _rolling3(values):
    out = []
    for i in range(len(values)):
        out.append(sum(values[max(0, i - 2):i + 1]) / len(values[max(0, i - 2):i + 1]))
    return out


def runway(ctx: Context):
    monthly = _monthly_spend(ctx)
    months = sorted(monthly)
    last3 = months[-3:]
    if last3:
        avg_spend = sum(monthly[m] for m in last3) / len(last3)
    else:
        avg_spend = 0.0

    if not ctx.has_balance or avg_spend <= 0:
        return result(
            "runway", "Runway", None, "months", "unknown",
            confidence_bucket(ctx.months), ctx.months,
            "Not enough data: need a current balance and 3 months of spending.",
        )
    months_left = ctx.current_balance / avg_spend
    good, warning = ctx.config["runway"]["good"], ctx.config["runway"]["warning"]
    status = "good" if months_left >= good else ("warning" if months_left >= warning else "bad")

    return result(
        "runway", "Runway", round(months_left, 1), "months", status,
        confidence_bucket(ctx.months), ctx.months,
        "Current balance {} lasts {:.1f} months at your avg {} monthly spend (3-mo).".format(
            inr(ctx.current_balance), months_left, inr(avg_spend)),
        extras={"months_left": round(months_left, 1), "avg_monthly_spend": round(avg_spend, 2),
                "current_balance": round(ctx.current_balance, 2)},
    )


def emergency_fund(ctx: Context):
    essential = defaultdict(float)
    for t in ctx.txns:
        if t.amount < 0 and ctx.essentiality_of(t) == "essential":
            essential[month_key(t.date)] += abs(t.amount)
    months = sorted(essential)
    last3 = months[-3:]
    if last3:
        avg_essential = sum(essential[m] for m in last3) / len(last3)
    else:
        avg_essential = 0.0

    if not ctx.has_balance or avg_essential <= 0:
        return result(
            "emergency_fund", "Emergency Fund Coverage", None, "months", "unknown",
            confidence_bucket(ctx.months), ctx.months,
            "Not enough data: need a current balance and essential spending history.",
        )
    coverage = ctx.current_balance / avg_essential
    good, warning = ctx.config["emergency_fund"]["good"], ctx.config["emergency_fund"]["warning"]
    status = "good" if coverage >= good else ("warning" if coverage >= warning else "bad")

    return result(
        "emergency_fund", "Emergency Fund Coverage", round(coverage, 1), "months", status,
        confidence_bucket(ctx.months), ctx.months,
        "Liquid balance {} covers {:.1f} months of essential spending (avg {}).".format(
            inr(ctx.current_balance), coverage, inr(avg_essential)),
        extras={"coverage": round(coverage, 1),
                "avg_essential": round(avg_essential, 2),
                "current_balance": round(ctx.current_balance, 2)},
    )


def spend_day(ctx: Context):
    by_day = defaultdict(float)
    by_day_count = defaultdict(int)
    from datetime import date
    today = date.today()
    days = defaultdict(list)
    for t in ctx.txns:
        if t.amount < 0:
            days[t.date.day].append(abs(t.amount))
    for day, amounts in days.items():
        by_day[day] = sum(amounts) / len(amounts)

    # avg daily spend over last 30 calendar days, transfers excluded
    recent = [t for t in ctx.txns if t.amount < 0 and (today - t.date.date()).days < 30]
    avg_daily = sum(abs(t.amount) for t in recent) / 30 if recent else 0.0
    days_left = (ctx.current_balance / avg_daily) if (ctx.has_balance and avg_daily > 0) else None

    # highlight days around typical salary day (peak income day-of-month)
    income_days = defaultdict(list)
    for t in ctx.txns:
        if t.amount > 0:
            income_days[t.date.day].append(t.amount)
    typical_salary_day = max(income_days, key=lambda d: sum(income_days[d])) if income_days else None
    highlight_days = []
    if typical_salary_day:
        for d in range(max(1, typical_salary_day - 3), min(31, typical_salary_day + 3) + 1):
            highlight_days.append(d)

    status = "good" if (days_left is None or days_left >= 15) else (
        "warning" if days_left >= 7 else "bad")
    explanation = (
        "Average spend is {} near the start of the month; you have {:.0f} day(s) of runway "
        "at your current daily spend pace.".format(
            inr(max(by_day.values(), default=0.0)),
            days_left if days_left is not None else 0.0)
        if days_left is not None else
        "Average spend by day computed; need balance for days-until-empty."
    )
    return result(
        "spend_day", "Spending by Day of Month", None, "unitless", status,
        confidence_bucket(ctx.months), ctx.months, explanation,
        extras={"by_day": {d: round(by_day[d], 2) for d in sorted(by_day)},
                "avg_daily_30d": round(avg_daily, 2),
                "days_left": round(days_left, 1) if days_left is not None else None,
                "typical_salary_day": typical_salary_day, "highlight_days": highlight_days},
    )


def weekday_weekend(ctx: Context):
    weekday = defaultdict(float)
    weekend = defaultdict(float)
    from collections import Counter
    wk, wnd = [], []
    for t in ctx.txns:
        if t.amount >= 0:
            continue
        if t.date.weekday() < 5:
            wk.append(abs(t.amount))
        else:
            wnd.append(abs(t.amount))
    avg_wk = sum(wk) / len(wk) if wk else 0.0
    avg_wnd = sum(wnd) / len(wnd) if wnd else 0.0
    ratio = (avg_wk / avg_wnd) if (avg_wk and avg_wnd) else None
    status = "unknown" if not (wk or wnd) else "good"
    explanation = (
        "Average daily spend is {} on weekdays vs {} on weekends.".format(inr(avg_wk), inr(avg_wnd))
    )
    return result(
        "weekday_weekend", "Weekday vs Weekend", round(ratio, 4) if ratio else None, "ratio",
        status, confidence_bucket(ctx.months), ctx.months, explanation,
        extras={"weekday_avg": round(avg_wk, 2), "weekend_avg": round(avg_wnd, 2),
                "ratio": round(ratio, 4) if ratio else None,
                "weekday_days": len(wk), "weekend_days": len(wnd)},
    )


def leakage(ctx: Context):
    threshold = ctx.config["small_txn_threshold"]
    small = [t for t in ctx.txns if t.amount < 0 and abs(t.amount) <= threshold]
    total_spend = sum(abs(t.amount) for t in ctx.txns if t.amount < 0)
    small_total = sum(abs(t.amount) for t in small)
    share = (small_total / total_spend) if total_spend else 0.0
    by_merchant = defaultdict(float)
    for t in small:
        by_merchant[merchant_key(t.description)] += abs(t.amount)
    top = sorted(by_merchant.items(), key=lambda kv: kv[1], reverse=True)[:5]
    top = [{"merchant": m, "amount": round(a, 2)} for m, a in top]
    status = "warning" if total_spend and share >= 0.10 else ("good" if total_spend else "unknown")
    explanation = (
        "{} small transactions under {} total {} ({:.1f}% of spending).".format(
            len(small), inr(threshold), inr(small_total), share * 100)
    )
    return result(
        "small_tx_leakage", "Small-Transaction Leakage", round(small_total, 2), "inr", status,
        confidence_bucket(ctx.months), ctx.months, explanation,
        extras={"count": len(small), "small_total": round(small_total, 2),
                "share": round(share, 4), "threshold": threshold, "top_merchants": top},
    )