from pbs_qt.format import (
    format_inr,
    format_inr_compact,
    format_month,
    format_signed_inr,
)


def test_thousands_indian_grouping():
    assert format_inr(25000) == "₹25,000"


def test_lakh_grouping():
    assert format_inr(125000) == "₹1,25,000"
    assert format_inr(12500000) == "₹1,25,00,000"


def test_negative_format():
    assert format_inr(-8500) == "-₹8,500"
    assert format_signed_inr(-8500) == "-₹8,500"


def test_signed_positive():
    assert format_signed_inr(30000) == "+₹30,000"


def test_rounding_and_defaults():
    assert format_inr(24999.6) == "₹25,000"
    assert format_inr(None) == "₹0"
    assert format_inr(float("nan")) == "₹0"


def test_compact():
    assert format_inr_compact(25000) == "₹25k"
    assert format_inr_compact(125000) == "₹1.25L"
    assert format_inr_compact(-8500) == "-₹8.5k"


def test_month():
    assert format_month("2026-08") == "Aug 2026"
    assert format_month("garbage") == "garbage"
