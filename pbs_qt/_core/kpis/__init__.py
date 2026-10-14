"""KPI module: deterministic per-KPI pure functions over a transaction context."""

from sqlalchemy.orm import Session

from .core import Context, confidence_bucket, filter_by_period, history_months, load_config
from .insights import generate as generate_insights
from . import spending, cashflow, structure, income

_PERIOD_KEYS = {None: "all", 1: "last_month", 3: "last_3_months", 6: "last_6_months"}


def build_context(db: Session, user_id: int, months: int | None, config=None):
    from ..database import Account, Category, Transaction

    cfg = config or load_config()
    txns = db.query(Transaction).filter(
        Transaction.user_id == user_id,
        Transaction.is_internal_transfer.is_(False),
    ).all()

    spend_type = {"Uncategorized": "variable", "Transfer": "variable"}
    essentiality = {"Uncategorized": "discretionary", "Transfer": "discretionary"}
    budgets = {}
    for row in db.query(Category).filter(Category.user_id == user_id).all():
        if row.default_monthly_budget:
            budgets[row.name] = row.default_monthly_budget
        if row.name in spend_type:
            continue
        if row.spend_type:
            spend_type[row.name] = row.spend_type
        else:
            spend_type[row.name] = "variable"
        if row.essentiality:
            essentiality[row.name] = row.essentiality
        else:
            essentiality[row.name] = "discretionary"

    cfg = dict(cfg)
    if budgets:
        cfg["budget_defaults"] = budgets

    payment_mode = {}
    for t in txns:
        if t.payment_mode:
            payment_mode[t.id] = t.payment_mode

    current_balance = 0.0
    has_balance = False
    for account in db.query(Account).filter(Account.user_id == user_id).all():
        latest = (
            db.query(Transaction)
            .filter(Transaction.account_id == account.id,
                    Transaction.balance_after.isnot(None))
            .order_by(Transaction.date.desc(), Transaction.id.desc())
            .first()
        )
        if latest is not None:
            current_balance += latest.balance_after
            has_balance = True

    return Context(
        txns=txns,
        months=len(history_months(txns)),
        current_balance=current_balance,
        has_balance=has_balance,
        config=cfg,
        spend_type=spend_type,
        essentiality=essentiality,
        payment_mode=payment_mode,
    )


_PRIORITY = {
    "savings_rate": 1, "net_cash_flow": 1, "fixed_vs_variable": 1,
    "essential_discretionary": 1, "recurring": 1, "runway": 1,
    "category_share": 2, "top_merchants": 2, "budget": 2,
    "safe_to_spend": 3, "spend_day": 3, "weekday_weekend": 3,
    "payment_mode": 3, "small_tx_leakage": 3,
    "income_stability": 4, "debt_to_income": 4, "emergency_fund": 4, "fees_interest": 4,
}

_ALL = [
    spending.savings_rate, spending.net_cash_flow, spending.fixed_vs_variable,
    spending.essential_discretionary, structure.recurring, cashflow.runway,
    spending.category_share, structure.top_merchants, spending.budget,
    income.safe_to_spend, cashflow.spend_day, cashflow.weekday_weekend,
    structure.payment_mode, cashflow.leakage,
    income.income_stability, income.debt_to_income, cashflow.emergency_fund, income.fees_interest,
]


def run_all(db: Session, user_id: int, months: int | None = None, config=None):
    ctx = build_context(db, user_id, months, config)
    # Build a period-filtered context for KPIs that should respect the period filter.
    if months:
        ctx.txns = filter_by_period(ctx.txns, months)
        ctx.months = len(history_months(ctx.txns))

    results = []
    for fn in _ALL:
        try:
            r = fn(ctx)
        except Exception:
            r = {"id": fn.__name__, "name": fn.__name__,
                 "value": None, "unit": "unitless", "status": "unknown",
                 "confidence": confidence_bucket(ctx.months), "months": ctx.months,
                 "explanation": "Could not compute this KPI.", "extras": {}}
        r["priority"] = _PRIORITY.get(r["id"], 9)
        results.append(r)

    return {
        "period": _PERIOD_KEYS.get(months, "all"),
        "kpis": results,
        "insights": generate_insights(results),
    }