from datetime import timedelta

from sqlalchemy.orm import Session

from .database import Transaction
from .categorizer import CATEGORY_TRANSFER, is_transfer_text

# Max calendar-day gap for matching a debit and a credit of the same amount
# across two of the user's own accounts.
PAIR_WINDOW_DAYS = 3
AMOUNT_TOLERANCE = 0.01


def mark_keyword_transfers(db: Session, user_id: int) -> int:
    """Flag transactions whose description looks like a self-transfer."""
    changed = 0
    rows = db.query(Transaction).filter(
        Transaction.user_id == user_id,
        Transaction.is_internal_transfer.is_(False),
    ).all()
    for t in rows:
        if is_transfer_text(t.description):
            t.is_internal_transfer = True
            if not t.category or t.category in ("Uncategorized", "Other"):
                t.category = CATEGORY_TRANSFER
            changed += 1
    return changed


def mark_paired_transfers(db: Session, user_id: int) -> int:
    """Flag matching debit/credit pairs (same amount, 1-3 days apart) between accounts."""
    rows = db.query(Transaction).filter(
        Transaction.user_id == user_id,
    ).order_by(Transaction.date.asc(), Transaction.id.asc()).all()

    debits = [t for t in rows if t.amount < 0]
    credits = [t for t in rows if t.amount > 0]
    used_credit_ids = set()
    changed = 0

    for debit in debits:
        if debit.is_internal_transfer:
            continue
        for credit in credits:
            if credit.id in used_credit_ids or credit.is_internal_transfer:
                continue
            if credit.account_id == debit.account_id:
                continue
            if abs(abs(debit.amount) - abs(credit.amount)) > AMOUNT_TOLERANCE:
                continue
            if abs((credit.date - debit.date)) > timedelta(days=PAIR_WINDOW_DAYS):
                continue
            debit.is_internal_transfer = True
            credit.is_internal_transfer = True
            used_credit_ids.add(credit.id)
            changed += 2
            break

    return changed


def detect_internal_transfers(db: Session, user_id: int) -> dict:
    """Run keyword then pair detection and commit the result."""
    keyword = mark_keyword_transfers(db, user_id)
    paired = mark_paired_transfers(db, user_id)
    db.commit()
    return {"keyword_flagged": keyword, "paired_flagged": paired}
