import json
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime


class KPIError(Exception):
    """Raised when a KPI cannot be computed (insufficient data)."""


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_DEFAULTS = {
    "currency": "INR",
    "savings_rate": {"good": 0.20, "warning": 0.10},
    "fixed_share": {"warning": 0.50, "bad": 0.65},
    "runway": {"good": 6, "warning": 3},
    "emergency_fund": {"good": 6, "warning": 3},
    "income_stability": {"good": 0.15, "warning": 0.35},
    "dti": {"good": 0.30, "warning": 0.40},
    "budget_progress": {"warning": 0.80},
    "cash_withdrawal": {"untracked_share": 0.15},
    "small_txn_threshold": 200,
    "recurring": {
        "min_occurrences": 3,
        "interval_tolerance_days": 3,
        "amount_tolerance_pct": 0.10,
        "new_item_days": 60,
        "price_increase_pct": 0.10,
        "monthly_window": [28, 32],
        "weekly_days": 7,
        "yearly_window": [360, 370],
    },
    "merchant_ref_pat": r"\b\d{3,}\b",
    "budget_defaults": {},
}


def _config_path():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "kpi_config.json")


def load_config(path=None):
    """Return merged config: defaults overridden by the editable kpi_config.json."""
    cfg = json.loads(json.dumps(_DEFAULTS))
    file_path = path or _config_path()
    try:
        with open(file_path) as fh:
            user = json.load(fh)
    except (OSError, ValueError):
        return cfg
    for key, value in user.items():
        if isinstance(value, dict) and isinstance(cfg.get(key), dict):
            cfg[key].update(value)
        else:
            cfg[key] = value
    return cfg


CONFIG = load_config()

# ---------------------------------------------------------------------------
# Month helpers
# ---------------------------------------------------------------------------


def month_key(dt):
    return dt.strftime("%Y-%m")


def month_add(key: str, delta: int) -> str:
    year, month = int(key[:4]), int(key[5:7])
    total = year * 12 + (month - 1) + delta
    return f"{total // 12:04d}-{total % 12 + 1:02d}"


def weighted_average(values):
    values = [float(v) for v in values]
    if not values:
        return 0.0
    weights = list(range(1, len(values) + 1))
    return sum(v * w for v, w in zip(values, weights)) / sum(weights)


def confidence_bucket(months: int):
    """Reuse the app-wide two-bucket confidence (Low / Medium/High, threshold 6)."""
    return "Medium/High" if months >= 6 else "Low"


def history_months(txns) -> list:
    return sorted({month_key(t.date) for t in txns})


# ---------------------------------------------------------------------------
# Merchant normalization & payment mode
# ---------------------------------------------------------------------------

_REF_PATTERN = re.compile(r"\b\d{3,}\b")


def normalize_merchant(description: str) -> str:
    """Lowercase, strip punctuation/digits/reference numbers and UPI handles."""
    text = re.sub(r"[^a-z0-9 ]+", " ", str(description or "").lower())
    text = _REF_PATTERN.sub(" ", text)
    tokens = [tok for tok in text.split() if tok]
    return " ".join(tokens[:2]) or str(description or "").lower().strip()


def merchant_key(description: str) -> str:
    return normalize_merchant(description)


# ---------------------------------------------------------------------------
# Currency formatting (Indian lakh grouping)
# ---------------------------------------------------------------------------


def _group_inr(digits: str) -> str:
    if len(digits) <= 3:
        return digits
    last3 = digits[-3:]
    rest = digits[:-3]
    two_groups = []
    while rest:
        two_groups.insert(0, rest[-2:])
        rest = rest[:-2]
    return ",".join(two_groups + [last3])


def inr(val, decimals=2) -> str:
    """Format an amount in Indian style, e.g. 125000 -> '₹1,25,000.00'."""
    negative = float(val) < 0
    v = round(abs(float(val)), decimals)
    fmt_digits = f"{v:.{decimals}f}"
    int_part, frac = fmt_digits.split(".")
    grouped = _group_inr(int_part)
    out = f"₹{grouped}.{frac}"
    return "-" + out if negative else out


# ---------------------------------------------------------------------------
# Period filtering
# ---------------------------------------------------------------------------


def filter_by_period(txns, months: int | None):
    """Keep transactions within the last `months` months (None = all)."""
    if not months:
        return list(txns)
    keys = history_months(txns)
    if not keys:
        return []
    end = keys[-1]
    start = month_add(end, -(months - 1))
    return [t for t in txns if month_key(t.date) >= start]


def group_by_month(txns):
    out = defaultdict(float)
    for t in txns:
        out[month_key(t.date)] += abs(t.amount)
    return out


def group_by(txns, field):
    out = defaultdict(float)
    for t in txns:
        key = getattr(t, field) or "Uncategorized"
        out[key] += abs(t.amount)
    return out


# ---------------------------------------------------------------------------
# KPI result + context
# ---------------------------------------------------------------------------


def result(kpi_id, name, value, unit, status, confidence, months, explanation, extras=None):
    return {
        "id": kpi_id,
        "name": name,
        "value": value,
        "unit": unit,
        "status": status,
        "confidence": confidence,
        "months": months,
        "explanation": explanation,
        "extras": extras or {},
    }


def status_from(flag: bool):
    """Map a KPI boolean/None to good/warning/bad."""
    return flag


@dataclass
class Context:
    """Pre-computed inputs shared by every KPI function. Built once in run_all."""

    txns: list = field(default_factory=list)          # non-transfer transactions
    months: int = 0                                   # distinct months of history
    current_balance: float = 0.0
    has_balance: bool = False
    config: dict = field(default_factory=dict)
    spend_type: dict = field(default_factory=dict)    # category -> fixed/variable
    essentiality: dict = field(default_factory=dict)  # category -> essential/discretionary
    payment_mode: dict = field(default_factory=dict)  # txn.id -> override mode

    def spend_type_of(self, t) -> str:
        cat = t.category or "Uncategorized"
        return self.spend_type.get(cat, "variable")

    def essentiality_of(self, t) -> str:
        cat = t.category or "Uncategorized"
        return self.essentiality.get(cat, "discretionary")