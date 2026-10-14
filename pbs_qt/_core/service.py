import hashlib

from sqlalchemy.orm import Session

from .database import Account, Transaction, Upload
from .parsers.base import ParseResult
from .categorizer import categorize, is_transfer_text
from .transfers import detect_internal_transfers


def _fp(account_id, date_iso, amount, remarks):
    raw = f"{account_id}|{date_iso}|{amount}|{remarks}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


_PLACEHOLDER_REFS = {"", "0", "000000000000000"}


def _tx_key(account_id, t, ref_counter):
    ref = getattr(t, "cheque", None) or ""
    date_iso = t.date.date().isoformat()
    if ref not in _PLACEHOLDER_REFS:
        return hashlib.sha256(f"{account_id}|{date_iso}|ref|{ref}".encode()).hexdigest()
    remarks = _normalize(t.remarks)
    ref_counter[ref] = ref_counter.get(ref, 0) + 1
    occ = ref_counter[ref]
    return _fp(account_id, date_iso, t.amount, remarks if occ == 1 else f"{remarks}#{occ}")


def _normalize(text):
    return " ".join(str(text or "").split()).lower()


def _resolve_account(db, user_id, result):
    if result.account_number:
        return (
            db.query(Account)
            .filter_by(user_id=user_id, account_number=result.account_number)
            .first()
        )
    banks = db.query(Account).filter_by(user_id=user_id, bank_name=result.bank_name).all()
    if len(banks) == 1:
        return banks[0]
    if not banks:
        return None
    return None


def ingest(db: Session, result: ParseResult, filename: str, user_id: int) -> dict:
    account = _resolve_account(db, user_id, result)
    if account is None:
        account = Account(
            user_id=user_id,
            bank_name=result.bank_name,
            account_number=result.account_number,
            account_type=result.account_type,
            currency="INR",
        )
        db.add(account)
        db.flush()

    upload = Upload(
        user_id=user_id,
        filename=filename,
        bank_name=result.bank_name,
        status="parsing",
    )
    db.add(upload)
    db.flush()

    seen = {}
    ref_counter = {}
    inserted = 0
    duplicate = 0

    for t in result.transactions:
        remarks = _normalize(t.remarks)
        if getattr(t, "cheque", None) not in _PLACEHOLDER_REFS:
            base = _tx_key(account.id, t, ref_counter)
        else:
            base = _fp(account.id, t.date.date().isoformat(), t.amount, remarks)
            seen[base] = seen.get(base, 0) + 1
            if seen[base] > 1:
                base = _fp(
                    account.id,
                    t.date.date().isoformat(),
                    t.amount,
                    f"{remarks}#{seen[base]}",
                )

        exists = (
            db.query(Transaction)
            .filter_by(user_id=user_id, fingerprint=base)
            .first()
        )
        if exists:
            duplicate += 1
            continue
        db.add(
            Transaction(
                account_id=account.id,
                user_id=user_id,
                date=t.date,
                description=remarks,
                amount=t.amount,
                category=categorize(remarks),
                balance_after=getattr(t, "balance", None),
                is_internal_transfer=is_transfer_text(remarks),
                source_file=filename,
                fingerprint=base,
            )
        )
        inserted += 1

    upload.status = "done"
    db.flush()
    detect_internal_transfers(db, user_id)
    db.commit()

    return {
        "account_number": result.account_number,
        "account_type": result.account_type,
        "period": {
            "start": result.period_start,
            "end": result.period_end,
        },
        "rows_in_statement": len(result.transactions),
        "inserted": inserted,
        "duplicates_skipped": duplicate,
        "status": upload.status,
    }