"""Data-access bridge to the shared, deterministic backend core.

Reuses ``source/fastapi/app`` (database, parsers, categorizer, analytics,
transfers, service) directly. Each function opens its own short-lived SQLAlchemy
session so nothing is shared across threads or widgets.
"""

from __future__ import annotations

import os
import sys
from datetime import date, datetime, time
from typing import Any, Optional

# Make the shared core importable: <repo>/source/fastapi
_QT_DIR = os.path.dirname(os.path.abspath(__file__))
_CORE_DIR = os.path.abspath(os.path.join(_QT_DIR, "..", "..", "fastapi"))
if _CORE_DIR not in sys.path:
    sys.path.insert(0, _CORE_DIR)

from app import config as core_config  # noqa: E402
from app import analytics as _analytics  # noqa: E402
from app import parsers as _parsers  # noqa: E402  (registers bank parsers)
from app.categorizer import CATEGORIES, DEFAULT_CATEGORY  # noqa: E402
from app.database import Account, Category, SessionLocal, Transaction, init_db  # noqa: E402
from app.parsers import base as _parser_base  # noqa: E402
from app.service import ingest as _ingest  # noqa: E402

USER_ID = core_config.DEFAULT_USER_ID


def initialize() -> None:
    """Create tables / default user if needed."""
    init_db()


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #
def _tx_dict(t: Transaction, account: Optional[Account]) -> dict[str, Any]:
    return {
        "id": t.id,
        "date": t.date,
        "description": t.description,
        "amount": t.amount,
        "category": t.category,
        "account_id": t.account_id,
        "account": f"{account.bank_name} {account.account_number}" if account else "",
        "balance_after": t.balance_after,
        "is_internal_transfer": bool(t.is_internal_transfer),
        "source_file": t.source_file,
    }


def list_transactions(filters: Optional[dict] = None) -> list[dict[str, Any]]:
    filters = filters or {}
    db = SessionLocal()
    try:
        query = db.query(Transaction)
        frm = filters.get("from")
        to = filters.get("to")
        if isinstance(frm, date):
            query = query.filter(Transaction.date >= datetime.combine(frm, time.min))
        if isinstance(to, date):
            query = query.filter(Transaction.date <= datetime.combine(to, time.max))
        if filters.get("account_id"):
            query = query.filter(Transaction.account_id == filters["account_id"])
        if filters.get("category"):
            query = query.filter(Transaction.category == filters["category"])
        if filters.get("type") == "credit":
            query = query.filter(Transaction.amount > 0)
        elif filters.get("type") == "debit":
            query = query.filter(Transaction.amount < 0)
        if filters.get("q"):
            query = query.filter(Transaction.description.ilike(f"%{filters['q']}%"))

        rows = query.order_by(Transaction.date.desc(), Transaction.id.desc()).all()
        accounts = {a.id: a for a in db.query(Account).all()}
        return [_tx_dict(t, accounts.get(t.account_id)) for t in rows]
    finally:
        db.close()


def list_accounts() -> list[dict[str, Any]]:
    db = SessionLocal()
    try:
        return [
            {
                "id": a.id,
                "bank_name": a.bank_name,
                "account_number": a.account_number,
                "account_type": a.account_type,
                "currency": a.currency,
                "opening_balance": a.opening_balance,
            }
            for a in db.query(Account).all()
        ]
    finally:
        db.close()


def transaction_months() -> list[str]:
    """Distinct transaction months (YYYY-MM), ascending."""
    db = SessionLocal()
    try:
        keys = {t.date.strftime("%Y-%m") for t in db.query(Transaction).all()}
    finally:
        db.close()
    return sorted(keys)


def list_categories() -> list[str]:
    db = SessionLocal()
    try:
        rows = (
            db.query(Transaction.category)
            .filter(Transaction.category.isnot(None))
            .distinct()
            .all()
        )
        used = sorted({r[0] for r in rows})
        return used or list(CATEGORIES)
    finally:
        db.close()


def all_categories() -> list[str]:
    return list(CATEGORIES)


def managed_categories() -> list[str]:
    """Categories the user can assign from (synced from the rule set + user additions)."""
    db = SessionLocal()
    try:
        rows = db.query(Category).filter_by(user_id=USER_ID).order_by(Category.sort_order).all()
        return [c.name for c in rows]
    finally:
        db.close()


def add_category(name: str) -> bool:
    name = (name or "").strip()
    if not name:
        return False
    db = SessionLocal()
    try:
        if db.query(Category).filter_by(user_id=USER_ID, name=name).first() is not None:
            return False
        db.add(Category(user_id=USER_ID, name=name, sort_order=db.query(Category).count()))
        db.commit()
        return True
    finally:
        db.close()


def rename_category(old: str, new: str) -> bool:
    new = (new or "").strip()
    if not new or old == new:
        return False
    db = SessionLocal()
    try:
        if db.query(Category).filter_by(user_id=USER_ID, name=new).first() is not None:
            return False
        category = db.query(Category).filter_by(user_id=USER_ID, name=old).first()
        if category is None:
            return False
        category.name = new
        (
            db.query(Transaction)
            .filter(Transaction.user_id == USER_ID, Transaction.category == old)
            .update({Transaction.category: new}, synchronize_session=False)
        )
        db.commit()
        return True
    finally:
        db.close()


def delete_category(name: str) -> None:
    db = SessionLocal()
    try:
        db.query(Category).filter_by(user_id=USER_ID, name=name).delete()
        (
            db.query(Transaction)
            .filter(Transaction.user_id == USER_ID, Transaction.category == name)
            .update({Transaction.category: DEFAULT_CATEGORY}, synchronize_session=False)
        )
        db.commit()
    finally:
        db.close()


def get_spending(horizon: int = 6) -> dict[str, Any]:
    db = SessionLocal()
    try:
        return _analytics.spending_forecast(db, USER_ID, horizon)
    finally:
        db.close()


def get_cashflow(horizon: int = 6) -> dict[str, Any]:
    db = SessionLocal()
    try:
        return _analytics.cashflow_forecast(db, USER_ID, horizon)
    finally:
        db.close()


def get_anomalies() -> dict[str, Any]:
    db = SessionLocal()
    try:
        return _analytics.anomalies(db, USER_ID)
    finally:
        db.close()


# --------------------------------------------------------------------------- #
# Writes
# --------------------------------------------------------------------------- #
def ingest_statement(path: str) -> dict[str, Any]:
    filename = os.path.basename(path)
    parser = _parser_base.detect_parser(path)
    if parser is None:
        return {"error": "Unsupported statement format (no matching bank parser)."}
    try:
        result = parser.parse(path)
    except Exception as exc:  # pragma: no cover - parser specific
        return {"error": str(exc)}

    db = SessionLocal()
    try:
        return _ingest(db, result, filename, USER_ID)
    finally:
        db.close()


def set_transfer_flag(transaction_id: int, value: bool) -> None:
    db = SessionLocal()
    try:
        txn = db.get(Transaction, transaction_id)
        if txn is not None:
            txn.is_internal_transfer = value
            db.commit()
    finally:
        db.close()


def set_category(transaction_id: int, category: str) -> None:
    db = SessionLocal()
    try:
        txn = db.get(Transaction, transaction_id)
        if txn is not None:
            txn.category = category
            db.commit()
    finally:
        db.close()


def set_opening_balance(account_id: int, opening_balance: float) -> None:
    db = SessionLocal()
    try:
        account = db.get(Account, account_id)
        if account is not None:
            account.opening_balance = opening_balance
            db.commit()
    finally:
        db.close()
