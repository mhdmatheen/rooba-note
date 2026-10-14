import re
from collections import defaultdict
from datetime import timedelta

import numpy as np
from sqlalchemy.orm import Session

from .database import Account, Transaction
from .kpis.core import (
    confidence_bucket as _confidence,
    month_add as _month_add,
    month_key as _month_key,
    normalize_merchant as _merchant,
    weighted_average as _weighted_average,
)

MIN_FORECAST_MONTHS = 3
HIGH_CONFIDENCE_MONTHS = 6
DEFAULT_CATEGORY = "Uncategorized"

NOT_ENOUGH_DATA = "Not enough data to forecast (need at least {need} months, have {have})"
NOT_ENOUGH_HISTORY = "Not enough history for anomaly detection"


def _next_months(start_key: str, n: int):
    return [_month_add(start_key, i) for i in range(1, n + 1)]


def _real_rows(db: Session, user_id: int):
    """Transactions that count towards income/spending (internal transfers excluded)."""
    return db.query(Transaction).filter(
        Transaction.user_id == user_id,
        Transaction.is_internal_transfer.is_(False),
    ).all()


def _history_months(rows) -> list:
    return sorted({_month_key(t.date) for t in rows})


def _account_balance_state(db: Session, user_id: int):
    """Return (current_balance, opening_balance, has_balance, accounts_missing)."""
    accounts = db.query(Account).filter_by(user_id=user_id).all()
    current = 0.0
    opening = 0.0
    has_current = False
    has_opening = False
    missing = []

    for account in accounts:
        first = (
            db.query(Transaction)
            .filter(Transaction.account_id == account.id)
            .order_by(Transaction.date.asc(), Transaction.id.asc())
            .first()
        )
        latest = (
            db.query(Transaction)
            .filter(
                Transaction.account_id == account.id,
                Transaction.balance_after.isnot(None),
            )
            .order_by(Transaction.date.desc(), Transaction.id.desc())
            .first()
        )

        if latest is not None and latest.balance_after is not None:
            current += latest.balance_after
            has_current = True
        elif account.opening_balance is not None:
            current += account.opening_balance
            has_current = True

        if account.opening_balance is not None:
            opening += account.opening_balance
            has_opening = True
        elif first is not None and first.balance_after is not None:
            opening += first.balance_after - first.amount
            has_opening = True

        if latest is None and account.opening_balance is None:
            missing.append(
                {
                    "id": account.id,
                    "bank_name": account.bank_name,
                    "account_number": account.account_number,
                }
            )

    has_balance = has_current or has_opening
    return (
        current if has_current else (opening if has_opening else 0.0),
        opening if has_opening else None,
        has_balance,
        missing,
    )


def spending_forecast(db: Session, user_id: int, horizon: int = 3):
    rows = [t for t in _real_rows(db, user_id) if t.amount < 0]
    all_months = _history_months(_real_rows(db, user_id))
    n_months = len(all_months)
    last_month = all_months[-1] if all_months else None
    forecast_start = _month_add(last_month, 1) if last_month else None

    monthly = defaultdict(dict)  # category -> month -> spend
    for t in rows:
        category = t.category or DEFAULT_CATEGORY
        mk = _month_key(t.date)
        monthly[category][mk] = monthly[category].get(mk, 0.0) + abs(t.amount)

    message = None
    if n_months < MIN_FORECAST_MONTHS:
        message = NOT_ENOUGH_DATA.format(need=MIN_FORECAST_MONTHS, have=n_months)

    categories = []
    for category in sorted(monthly):
        per_month = monthly[category]
        months = sorted(per_month)
        amounts = [per_month[m] for m in months]

        item = {
            "category": category,
            "history": [{"month": m, "amount": round(per_month[m], 2)} for m in months],
            "forecast": [],
            "confidence": None,
            "months_of_history": n_months,
        }

        if n_months >= MIN_FORECAST_MONTHS:
            level = _weighted_average(amounts)
            item["confidence"] = _confidence(n_months)
            item["forecast"] = [
                {"month": mk, "amount": round(max(0.0, level), 2)}
                for mk in _next_months(last_month, horizon)
            ]
            if n_months >= HIGH_CONFIDENCE_MONTHS and amounts:
                for entry in item["forecast"]:
                    entry["low"] = round(max(0.0, min(amounts)), 2)
                    entry["high"] = round(max(amounts), 2)

        categories.append(item)

    return {
        "message": message,
        "months_of_history": n_months,
        "confidence": _confidence(n_months) if n_months >= MIN_FORECAST_MONTHS else None,
        "forecast_start": forecast_start,
        "categories": categories,
    }


def cashflow_forecast(db: Session, user_id: int, horizon: int = 3):
    rows = _real_rows(db, user_id)
    income = defaultdict(float)
    spending = defaultdict(float)
    for t in rows:
        mk = _month_key(t.date)
        if t.amount > 0:
            income[mk] += t.amount
        else:
            spending[mk] += abs(t.amount)

    all_months = _history_months(rows)
    n_months = len(all_months)
    last_month = all_months[-1] if all_months else None
    forecast_start = _month_add(last_month, 1) if last_month else None

    current_balance, opening_balance, has_balance, missing = _account_balance_state(db, user_id)

    avg_income = _weighted_average([income.get(m, 0.0) for m in all_months]) if all_months else 0.0
    avg_spending = _weighted_average([spending.get(m, 0.0) for m in all_months]) if all_months else 0.0
    avg_net = avg_income - avg_spending
    current_net = round(sum(income.values()) - sum(spending.values()), 2)

    runway = None
    if has_balance and avg_spending > 0:
        runway = round(current_balance / avg_spending, 1)

    result = {
        "note": None,
        "has_balance": has_balance,
        "opening_balance": round(opening_balance, 2) if opening_balance is not None else None,
        "current_balance": round(current_balance, 2) if has_balance else None,
        "runway_months": runway,
        "months_of_history": n_months,
        "confidence": _confidence(n_months) if n_months >= MIN_FORECAST_MONTHS else None,
        "forecast_start": forecast_start,
        "message": None,
        "current_net": current_net,
        "accounts_missing_balance": missing,
        "historical": [
            {
                "month": m,
                "income": round(income.get(m, 0.0), 2),
                "spending": round(spending.get(m, 0.0), 2),
                "net": round(income.get(m, 0.0) - spending.get(m, 0.0), 2),
            }
            for m in all_months
        ],
        "forecast": [],
        "transfers": _transfer_rows(db, user_id),
    }

    if not has_balance:
        result["note"] = (
            "Opening balance is not captured from statements; cumulative is relative to net flows seen so far."
        )
    else:
        result["note"] = "Cumulative = starting balance + net of each forecast month."

    starting_balance = current_balance if has_balance else 0.0
    result["starting_balance"] = round(starting_balance, 2)

    if n_months < MIN_FORECAST_MONTHS:
        result["message"] = NOT_ENOUGH_DATA.format(need=MIN_FORECAST_MONTHS, have=n_months)
        return result

    cumulative = starting_balance
    forecast = []
    for mk in _next_months(last_month, horizon):
        cumulative += avg_net
        forecast.append(
            {
                "month": mk,
                "income": round(avg_income, 2),
                "spending": round(avg_spending, 2),
                "net": round(avg_net, 2),
                "cumulative": round(cumulative, 2),
            }
        )
    result["forecast"] = forecast
    return result


def _transfer_rows(db: Session, user_id: int):
    rows = (
        db.query(Transaction)
        .filter(
            Transaction.user_id == user_id,
            Transaction.is_internal_transfer.is_(True),
        )
        .order_by(Transaction.date.desc(), Transaction.id.desc())
        .all()
    )
    return [
        {
            "id": t.id,
            "date": t.date.date().isoformat(),
            "description": t.description,
            "amount": round(t.amount, 2),
            "category": t.category,
        }
        for t in rows
    ]





def anomalies(db: Session, user_id: int):
    rows = _real_rows(db, user_id)
    all_months = _history_months(rows)
    n_months = len(all_months)
    debits = [t for t in rows if t.amount < 0]

    result = {
        "insufficient_history": False,
        "message": None,
        "category_spikes": [],
        "duplicates": [],
        "first_time_large": [],
    }

    if n_months < MIN_FORECAST_MONTHS:
        result["insufficient_history"] = True
        result["message"] = NOT_ENOUGH_HISTORY
        return result

    # Category spikes: this month vs. the mean + 2 std of the other months.
    by_cat_month = defaultdict(dict)
    for t in debits:
        category = t.category or DEFAULT_CATEGORY
        mk = _month_key(t.date)
        by_cat_month[category][mk] = by_cat_month[category].get(mk, 0.0) + abs(t.amount)
    for category, months in by_cat_month.items():
        ordered = sorted(months)
        values = [months[m] for m in ordered]
        for i, m in enumerate(ordered):
            others = values[:i] + values[i + 1:]
            if len(others) < MIN_FORECAST_MONTHS:
                continue
            mean = float(np.mean(others))
            std = float(np.std(others))
            if std <= 0:
                continue
            if months[m] > mean + 2 * std:
                result["category_spikes"].append(
                    {
                        "category": category,
                        "month": m,
                        "amount": round(months[m], 2),
                        "mean_monthly": round(mean, 2),
                        "std": round(std, 2),
                    }
                )

    # Duplicate charges: same merchant + same amount within 24 hours.
    by_merchant_amount = defaultdict(list)
    for t in debits:
        key = (_merchant(t.description), round(abs(t.amount), 2))
        by_merchant_amount[key].append(t)
    for (merchant, amount), items in by_merchant_amount.items():
        items.sort(key=lambda t: t.date)
        cluster = []
        for t in items:
            if cluster and (t.date - cluster[-1].date) > timedelta(hours=24):
                if len(cluster) > 1:
                    result["duplicates"].append(_dup_entry(merchant, amount, cluster))
                cluster = []
            cluster.append(t)
        if len(cluster) > 1:
            result["duplicates"].append(_dup_entry(merchant, amount, cluster))

    # First-time merchants with an unusually large amount (> 95th percentile).
    if len(debits) >= 4:
        threshold = float(np.percentile([abs(t.amount) for t in debits], 95))
        counts = defaultdict(int)
        for t in debits:
            counts[_merchant(t.description)] += 1
        for t in debits:
            merchant = _merchant(t.description)
            if counts[merchant] == 1 and abs(t.amount) >= threshold:
                result["first_time_large"].append(
                    {
                        "id": t.id,
                        "date": t.date.date().isoformat(),
                        "description": t.description,
                        "merchant": merchant,
                        "amount": round(t.amount, 2),
                        "category": t.category,
                        "threshold": round(threshold, 2),
                    }
                )

    return result


def _dup_entry(merchant, amount, cluster):
    return {
        "date": cluster[0].date.date().isoformat(),
        "amount": round(amount, 2),
        "merchant": merchant,
        "category": cluster[0].category,
        "count": len(cluster),
        "ids": [t.id for t in cluster],
    }


def run_all(db: Session, user_id: int, horizon: int = 3):
    return {
        "spending_forecast": spending_forecast(db, user_id, horizon),
        "cashflow": cashflow_forecast(db, user_id, horizon),
        "anomalies": anomalies(db, user_id),
    }
