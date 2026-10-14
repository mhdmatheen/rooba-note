from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class ParsedTransaction:
    date: datetime
    remarks: str
    amount: float  # signed; negative = spend (withdrawal), positive = income (deposit)
    cheque: Optional[str] = None
    withdrawal: Optional[float] = None
    deposit: Optional[float] = None
    balance: Optional[float] = None
    s_no: Optional[str] = None


@dataclass
class ParseResult:
    bank_name: str
    account_number: Optional[str]
    account_type: Optional[str]
    period_start: Optional[str]
    period_end: Optional[str]
    transactions: List[ParsedTransaction] = field(default_factory=list)


class BankParser:
    bank_name = "unknown"

    @classmethod
    def supports(cls, path: str) -> bool:
        raise NotImplementedError

    @classmethod
    def parse(cls, path: str) -> ParseResult:
        raise NotImplementedError


PARSERS: List[BankParser] = []
_REGISTERED = set()


def register_parser(parser):
    if parser.bank_name not in _REGISTERED:
        PARSERS.append(parser)
        _REGISTERED.add(parser.bank_name)
    return parser


def detect_parser(path: str) -> Optional[BankParser]:
    for parser in PARSERS:
        try:
            if parser.supports(path):
                return parser
        except Exception:
            continue
    return None