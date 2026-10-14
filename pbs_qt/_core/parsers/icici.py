from datetime import datetime
import re
from typing import Optional

import pdfplumber

from .base import BankParser, ParseResult, ParsedTransaction, register_parser

# Column classification by word left edge (x0), derived from the reference format.
S_NO = (0, 55)
DATE = (55, 110)
CHEQUE = (110, 190)
REMARKS = (190, 410)
WITHDRAWAL = (410, 465)
DEPOSIT = (465, 525)
BALANCE = (525, 1000)

_DATE_FULL = re.compile(r"\d{2}\.\d{2}\.\d{4}")
_ACCOUNT_NO = re.compile(r"Account no\.?\s+([\d]+)", re.IGNORECASE)
_ACCOUNT_TYPE = re.compile(r"\b(Saving|Current)\s+Account\b", re.IGNORECASE)
_PERIOD = re.compile(r"for the period\s+(.+?)\s*\-\s*(.+?)\s*\n", re.IGNORECASE)


def _column(x0: float) -> Optional[str]:
    if S_NO[0] <= x0 < S_NO[1]:
        return "s_no"
    if DATE[0] <= x0 < DATE[1]:
        return "date"
    if CHEQUE[0] <= x0 < CHEQUE[1]:
        return "cheque"
    if REMARKS[0] <= x0 < REMARKS[1]:
        return "remarks"
    if WITHDRAWAL[0] <= x0 < WITHDRAWAL[1]:
        return "withdrawal"
    if DEPOSIT[0] <= x0 < DEPOSIT[1]:
        return "deposit"
    if BALANCE[0] <= x0 < BALANCE[1]:
        return "balance"
    return None


@register_parser
class ICICIParser(BankParser):
    bank_name = "ICICI"

    @classmethod
    def supports(cls, path: str) -> bool:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages[:3]:
                txt = page.extract_text() or ""
                if "ICICI Bank" in txt and ("Statement of Transactions" in txt or "Account" in txt):
                    if "Transactions in" in txt:
                        return True
        return False

    @classmethod
    def parse(cls, path: str) -> ParseResult:
        account_number = account_type = None
        period_start = period_end = None
        anchors = []  # (top, row_start_index) for S No. tokens
        kinds = []    # per extracted token: (top, column, text)

        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                for word in page.extract_words():
                    col = _column(word["x0"])
                    if col is None:
                        continue
                    kinds.append((word["top"], col, word["text"]))
                    if col == "s_no":
                        anchors.append((word["top"], len(kinds) - 1))

                txt = page.extract_text() or ""
                if not account_number:
                    m = _ACCOUNT_NO.search(txt)
                    if m:
                        account_number = m.group(1)
                if not account_type:
                    mt = _ACCOUNT_TYPE.search(txt)
                    if mt:
                        account_type = mt.group(1)
                if not period_start:
                    mp = _PERIOD.search(txt)
                    if mp:
                        period_start = mp.group(1).strip()
                        period_end = mp.group(2).strip()

        rows = {}
        for anchor_idx, (anchor_top, anchor_pos) in enumerate(anchors):
            rows[anchor_idx] = {
                "s_no": kinds[anchor_pos][2],
                "date": [], "cheque": [], "remarks": [],
                "withdrawal": [], "deposit": [], "balance": [],
            }

        for top, col, text in kinds:
            if col == "s_no":
                continue
            chosen = -1
            run = None
            for idx, (anchor_top, _) in enumerate(anchors):
                if anchor_top <= top + 1:
                    chosen = idx
                elif run is None:
                    run = idx
                    break
            if chosen == -1:
                chosen = run if run is not None else 0
            if chosen >= 0 and col in rows[chosen]:
                rows[chosen][col].append(text)

        transactions = []
        for idx in sorted(rows.keys()):
            r = rows[idx]
            date = next((t for t in r["date"] if _DATE_FULL.fullmatch(t)), None)
            if not date:
                continue
            withdrawal = _float(_clean(r["withdrawal"])) if r["withdrawal"] else None
            deposit = _float(_clean(r["deposit"])) if r["deposit"] else None
            balance = _float(_clean(r["balance"])) if r["balance"] else None
            remarks = " ".join(r["remarks"])
            if withdrawal is not None and deposit is None:
                amount = -withdrawal
            elif deposit is not None:
                amount = deposit
            else:
                amount = balance or 0.0
            transactions.append(
                ParsedTransaction(
                    date=datetime.strptime(date, "%d.%m.%Y"),
                    remarks=remarks,
                    amount=amount,
                    cheque=r["cheque"][0] if r["cheque"] else None,
                    withdrawal=withdrawal,
                    deposit=deposit,
                    balance=balance,
                    s_no=r["s_no"],
                )
            )

        return ParseResult(
            bank_name=cls.bank_name,
            account_number=account_number,
            account_type=account_type,
            period_start=period_start,
            period_end=period_end,
            transactions=transactions,
        )


def _clean(tokens):
    return "".join(tokens).replace(",", "").replace("Cr", "").replace("Dr", "").strip()


def _float(raw: str) -> float:
    return float(raw) if raw else None