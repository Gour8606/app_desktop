"""Tests for constants module."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from datetime import datetime
from constants import (
    get_state_code, generate_note_number,
    NoteType, TransactionType, B2CL_INVOICE_THRESHOLD,
    STATE_CODE_MAPPING, normalize_rate, fy_month_to_date_range,
)


def test_b2cl_threshold():
    assert B2CL_INVOICE_THRESHOLD == 250000


def test_transaction_types():
    assert TransactionType.SHIPMENT == 'Shipment'
    assert TransactionType.REFUND == 'Refund'
    assert TransactionType.CANCEL == 'Cancel'


def test_note_types():
    assert NoteType.CREDIT == 'C'
    assert NoteType.DEBIT == 'D'


def test_get_state_code_known_state():
    assert get_state_code("MAHARASHTRA") == "27-Maharashtra"
    assert get_state_code("KARNATAKA") == "29-Karnataka"
    assert get_state_code("DELHI") == "07-Delhi"


def test_get_state_code_case_insensitive():
    assert get_state_code("maharashtra") == "27-Maharashtra"
    assert get_state_code("  Maharashtra  ") == "27-Maharashtra"


def test_get_state_code_alternative_spellings():
    assert get_state_code("ORISSA") == "21-Odisha"
    assert get_state_code("PONDICHERRY") == "34-Puducherry"


def test_get_state_code_unknown_returns_original():
    assert get_state_code("UNKNOWN_STATE") == "UNKNOWN_STATE"


def test_get_state_code_empty():
    assert get_state_code("") == ""
    assert get_state_code(None) == ""


def test_generate_note_number_credit():
    assert generate_note_number("INV001") == "CN-INV001"
    assert generate_note_number("INV001", NoteType.CREDIT) == "CN-INV001"


def test_generate_note_number_debit():
    assert generate_note_number("INV001", NoteType.DEBIT) == "DN-INV001"


def test_state_code_mapping_completeness():
    """Ensure all major Indian states are mapped."""
    major_states = [
        "MAHARASHTRA", "KARNATAKA", "TAMIL NADU", "DELHI",
        "UTTAR PRADESH", "GUJARAT", "WEST BENGAL", "RAJASTHAN",
        "KERALA", "TELANGANA", "ANDHRA PRADESH",
    ]
    for state in major_states:
        assert state in STATE_CODE_MAPPING, f"Missing state: {state}"


# --- normalize_rate tests ---

def test_normalize_rate_whole_numbers():
    assert normalize_rate(5) == 5.0
    assert normalize_rate(12) == 12.0
    assert normalize_rate(18) == 18.0


def test_normalize_rate_decimal_format():
    """Rates like 0.05, 0.12, 0.18 should become 5.0, 12.0, 18.0."""
    assert normalize_rate(0.05) == 5.0
    assert normalize_rate(0.12) == 12.0
    assert normalize_rate(0.18) == 18.0


def test_normalize_rate_edge_cases():
    assert normalize_rate(None) == 0.0
    assert normalize_rate(0) == 0.0
    assert normalize_rate("18") == 18.0
    assert normalize_rate("invalid") == 0.0


# --- fy_month_to_date_range tests ---

def test_fy_month_to_date_range_jan():
    """FY 2026, month 1 (Jan) -> Jan 2026."""
    start, end = fy_month_to_date_range(2026, 1)
    assert start == datetime(2026, 1, 1)
    assert end == datetime(2026, 2, 1)


def test_fy_month_to_date_range_mar():
    """FY 2026, month 3 (Mar) -> Mar 2026."""
    start, end = fy_month_to_date_range(2026, 3)
    assert start == datetime(2026, 3, 1)
    assert end == datetime(2026, 4, 1)


def test_fy_month_to_date_range_apr():
    """FY 2026, month 4 (Apr) -> Apr 2025."""
    start, end = fy_month_to_date_range(2026, 4)
    assert start == datetime(2025, 4, 1)
    assert end == datetime(2025, 5, 1)


def test_fy_month_to_date_range_dec():
    """FY 2026, month 12 (Dec) -> Dec 2025."""
    start, end = fy_month_to_date_range(2026, 12)
    assert start == datetime(2025, 12, 1)
    assert end == datetime(2026, 1, 1)
