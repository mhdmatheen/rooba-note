"""Currency and month formatting helpers (Indian numbering system)."""

from __future__ import annotations

import math
from datetime import datetime


def format_inr(value: float | int | None) -> str:
    """Format a number as Indian rupees, e.g. 125000 -> '₹1,25,000'.

    Negatives are rendered consistently as '-₹8,500'.
    """
    if value is None or not math.isfinite(float(value)):
        value = 0
    rounded = int(round(float(value)))
    sign = "-" if rounded < 0 else ""
    digits = str(abs(rounded))

    if len(digits) <= 3:
        grouped = digits
    else:
        last3 = digits[-3:]
        rest = digits[:-3]
        parts: list[str] = []
        while len(rest) > 2:
            parts.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            parts.insert(0, rest)
        grouped = ",".join(parts) + "," + last3

    return f"{sign}₹{grouped}"


def format_signed_inr(value: float | int | None) -> str:
    """Like :func:`format_inr` but prefixes an explicit + for credits."""
    if value is None:
        value = 0
    prefix = "+" if float(value) > 0 else ""
    return prefix + format_inr(value)


def format_inr_compact(value: float | int | None) -> str:
    """'₹25,000' -> '₹25k'; 125000 -> '₹1.25L'; 12500000 -> '₹1.25Cr'."""
    if value is None or not math.isfinite(float(value)):
        value = 0
    number = float(value)
    sign = "-" if number < 0 else ""
    magnitude = abs(number)
    if magnitude >= 1e7:
        scaled, unit = magnitude / 1e7, "Cr"
    elif magnitude >= 1e5:
        scaled, unit = magnitude / 1e5, "L"
    elif magnitude >= 1e3:
        scaled, unit = magnitude / 1e3, "k"
    else:
        return f"{sign}₹{int(round(magnitude))}"
    text = f"{scaled:.2f}".rstrip("0").rstrip(".")
    return f"{sign}₹{text}{unit}"


def format_month(value: str) -> str:
    """'2026-08' -> 'Aug 2026'."""
    try:
        dt = datetime.strptime(value, "%Y-%m")
        return dt.strftime("%b %Y")
    except (ValueError, TypeError):
        return value
