import os
import re
from datetime import datetime

import xlrd

from .base import BankParser, ParseResult, ParsedTransaction, register_parser

_HEADER_MARKERS = {"date", "narration", "chq./ref.no.", "value dt", "withdrawal amt.", "deposit amt.", "closing balance"}
_FILENAME_ACCOUNT = re.compile(r"_(\d{4})_")


def _is_header_row(row):
    cols = {str(c).strip().lower() for c in row if isinstance(c, str)}
    return cols.issuperset({"date", "narration"})


@register_parser
class HDFCExcelParser(BankParser):
    bank_name = "HDFC"

    @classmethod
    def supports(cls, path: str) -> bool:
        if not path.lower().endswith((".xls", ".xlsx")):
            return False
        try:
            wb = xlrd.open_workbook(path)
            sh = wb.sheet_by_index(0)
            header_row = None
            for r in range(min(sh.nrows, 20)):
                row = [sh.cell_value(r, c) for c in range(sh.ncols)]
                if any("hdfc" in str(v).lower() for v in row):
                    return True
                if header_row is None and _is_header_row(row):
                    header_row = r
            return header_row is not None
        except Exception:
            return False

    @classmethod
    def parse(cls, path: str) -> ParseResult:
        account_number = None
        m = _FILENAME_ACCOUNT.search(os.path.basename(path))
        if m:
            account_number = m.group(1)

        wb = xlrd.open_workbook(path)
        sh = wb.sheet_by_index(0)

        header_idx = None
        for r in range(min(sh.nrows, 20)):
            row = [sh.cell_value(r, c) for c in range(sh.ncols)]
            if _is_header_row(row):
                header_idx = r
                break

        transactions = []
        for r in range(header_idx + 1, sh.nrows):
            row = [sh.cell_value(r, c) for c in range(sh.ncols)]
            narration = str(row[1] or "").strip()
            date_raw = str(row[0] or "").strip()
            if not narration or narration.startswith("*"):
                continue
            if not date_raw:
                continue

            withdrawal = _num(row[4])
            deposit = _num(row[5])
            balance = _num(row[6])
            ref_no = str(row[2] or "").strip() or None

            if withdrawal is not None and deposit is None:
                amount = -withdrawal
            elif deposit is not None:
                amount = deposit
            else:
                amount = balance or 0.0

            transactions.append(
                ParsedTransaction(
                    date=_parse_date(date_raw),
                    remarks=narration,
                    amount=amount,
                    cheque=ref_no,
                    withdrawal=withdrawal,
                    deposit=deposit,
                    balance=balance,
                )
            )

        return ParseResult(
            bank_name=cls.bank_name,
            account_number=account_number,
            account_type=None,
            period_start=None,
            period_end=None,
            transactions=transactions,
        )


def _num(v):
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v or "").replace(",", "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _parse_date(raw: str) -> datetime:
    raw = raw.strip()
    for fmt in ("%d/%m/%y", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unparseable date: {raw!r}")