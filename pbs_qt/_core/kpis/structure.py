import re
from collections import defaultdict
from datetime import timedelta

from .core import Context, confidence_bucket, inr, merchant_key, result

WEEKLY_X_MONTHLY = 52 / 12
YEARLY_X_MONTHLY = 1 / 12


def _detect_cadence(intervals, cfg):
    """Return (cadence, base_days) preferring monthly (resolved decision B), else None."""
    if not intervals:
        return None, None
    median = sorted(intervals)[len(intervals) // 2]
    monthly = cfg["monthly_window"]  # [28, 32]
    yearly = cfg["yearly_window"]    # [360, 370]
    weekly = cfg["weekly_days"]      # 7 (+/- tol)
    tol = cfg["interval_tolerance_days"]
    if monthly[0] <= median <= monthly[1]:
        return "monthly", 30
    if weekly - tol <= median <= weekly + tol:
        return "weekly", 7
    if yearly[0] <= median <= yearly[1]:
        return "yearly", 365
    return None, None


def recurring(ctx: Context):
    cfg = ctx.config["recurring"]
    groups = defaultdict(list)
    for t in ctx.txns:
        if t.amount < 0:
            groups[merchant_key(t.description)].append(t)
    for key in groups:
        groups[key].sort(key=lambda t: t.date)

    recurring_rows = []
    for merchant, txns in groups.items():
        amounts = [abs(t.amount) for t in txns]
        if len(txns) < cfg["min_occurrences"]:
            continue
        intervals = [(txns[i + 1].date - txns[i].date).days
                     for i in range(len(txns) - 1)]
        cadence, base_days = _detect_cadence(intervals, cfg)
        if cadence is None:
            continue
        tol = cfg["interval_tolerance_days"]
        if not all(abs(iv - base_days) <= tol for iv in intervals):
            continue

        median_amt = sorted(amounts)[len(amounts) // 2]
        amt_tol = cfg["amount_tolerance_pct"]
        close = sum(1 for a in amounts if abs(a - median_amt) / median_amt <= amt_tol)
        if close < 2:
            continue

        last = txns[-1]
        typical = median_amt
        monthly_factor = {"monthly": 1.0, "weekly": WEEKLY_X_MONTHLY, "yearly": YEARLY_X_MONTHLY}[cadence]
        monthly_cost = typical * monthly_factor
        next_expected = last.date + timedelta(days=base_days)

        earlier = amounts[:-1]
        combined = amounts[:-1] if amounts[:-1] else amounts
        earlier_median = sorted(combined)[len(combined) // 2]
        price_inc = bool(amounts[:-1]) and amounts[-1] > (1 + cfg["price_increase_pct"]) * earlier_median
        # first seen within last 60 days
        from datetime import date
        days_since = (date.today() - last.date.date()).days
        is_new = days_since <= cfg["new_item_days"]

        recurring_rows.append({
            "merchant": merchant,
            "cadence": cadence,
            "typical_amount": round(typical, 2),
            "last_charged": last.date.date().isoformat(),
            "next_expected": next_expected.date().isoformat(),
            "monthly_cost": round(monthly_cost, 2),
            "count": len(txns),
            "new": is_new,
            "price_increase": price_inc,
        })

    recurring_rows.sort(key=lambda r: r["monthly_cost"], reverse=True)
    total_monthly = round(sum(r["monthly_cost"] for r in recurring_rows), 2)
    new_items = [r for r in recurring_rows if r["new"]]
    hikes = [r for r in recurring_rows if r["price_increase"]]

    if not recurring_rows:
        return result("recurring", "Recurring Payments", 0.0, "inr", "unknown",
                      confidence_bucket(ctx.months), ctx.months,
                      "No recurring payments detected (need 3+ consistent charges).",
                      extras={"rows": [], "total_monthly": 0.0, "new": [], "hikes": []})

    explanation = (
        "Detected {} recurring payments totaling {} per month.".format(
            len(recurring_rows), inr(total_monthly))
    )
    return result("recurring", "Recurring Payments", total_monthly, "inr", "good",
                  confidence_bucket(ctx.months), ctx.months, explanation,
                  extras={"rows": recurring_rows, "total_monthly": total_monthly,
                          "new": new_items, "hikes": hikes})


def top_merchants(ctx: Context):
    by_merchant = defaultdict(float)
    by_count = defaultdict(int)
    for t in ctx.txns:
        if t.amount < 0:
            mk = merchant_key(t.description)
            by_merchant[mk] += abs(t.amount)
            by_count[mk] += 1
    by_amount = sorted(by_merchant.items(), key=lambda kv: kv[1], reverse=True)[:10]
    by_count = sorted(by_count.items(), key=lambda kv: kv[1], reverse=True)[:10]
    explanation = "Top merchants by total spend and by transaction count."
    return result(
        "top_merchants", "Top Merchants", None, "unitless", "good" if by_amount else "unknown",
        confidence_bucket(ctx.months), ctx.months, explanation,
        extras={
            "by_amount": [{"merchant": m, "amount": round(a, 2)} for m, a in by_amount],
            "by_count": [{"merchant": m, "count": c} for m, c in by_count],
        },
    )


_MODE_PATTERNS = [
    ("UPI", r"upi"),
    ("ATM/Cash", r"\b(nwd|ccwd|atm|cash|cash withdrawal)\b"),
    ("NEFT/IMPS", r"\b(neft|imps|rtgs|inft|fund transfer)\b"),
    ("Card", r"\b(card|visa|mastercard|pos|swipe|ecs)\b"),
    ("Cheque", r"\b(cheque|chq|check)\b"),
]
_COMPILED_MODES = [(name, re.compile(pat)) for name, pat in _MODE_PATTERNS]


def payment_mode(ctx: Context):
    modes = defaultdict(float)
    for t in ctx.txns:
        if t.amount >= 0:
            continue
        mode = ctx.payment_mode.get(t.id)
        if not mode:
            text = str(t.description or "").lower()
            mode = "Other"
            for name, pat in _COMPILED_MODES:
                if pat.search(text):
                    mode = name
                    break
        modes[mode] += abs(t.amount)
    total = sum(modes.values())
    share = {m: (a / total if total else 0.0) for m, a in modes.items()}
    cash_share = share.get("ATM/Cash", 0.0)
    flag = cash_share > ctx.config["cash_withdrawal"]["untracked_share"]
    status = "warning" if flag else ("good" if total else "unknown")
    explanation = (
        "Cash withdrawals make up {:.1f}% of spending{}.".format(
            cash_share * 100,
            " and may be untracked" if flag else "")
    ) if total else "No spending to attribute a payment mode to."
    return result(
        "payment_mode", "Payment Mode Mix", round(cash_share, 4), "percent", status,
        confidence_bucket(ctx.months), ctx.months, explanation,
        extras={"share": {m: round(s, 4) for m, s in share.items()},
                "cash_share": round(cash_share, 4), "untracked_flag": flag, "total": round(total, 2)},
    )