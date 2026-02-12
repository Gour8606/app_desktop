"""Tests for import_logic module - validation functions."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from import_logic import (
    normalize_gst_rate, safe_float, parse_date,
    validate_meesho_tax_invoice_zip, validate_invoices_zip,
    validate_flipkart_sales_excel, validate_amazon_zip,
)


def test_normalize_gst_rate():
    assert normalize_gst_rate(5) == 5.0
    assert normalize_gst_rate(5.0) == 5.0
    assert normalize_gst_rate(12) == 12.0
    assert normalize_gst_rate(18) == 18.0
    assert normalize_gst_rate(0) == 0.0


def test_normalize_gst_rate_edge_cases():
    assert normalize_gst_rate(None) == 0.0
    assert normalize_gst_rate("") == 0.0
    assert normalize_gst_rate("18") == 18.0


def test_safe_float():
    assert safe_float(100) == 100.0
    assert safe_float("200.5") == 200.5
    assert safe_float(None) == 0.0
    assert safe_float("") == 0.0
    assert safe_float("invalid") == 0.0


def test_parse_date_none():
    assert parse_date(None) is None


def test_validate_meesho_tax_invoice_zip():
    # Non-zip file should fail
    is_valid, msg = validate_meesho_tax_invoice_zip("report.xlsx")
    assert not is_valid


def test_validate_invoices_zip():
    is_valid, msg = validate_invoices_zip("report.xlsx")
    assert not is_valid


def test_validate_flipkart_sales_excel():
    is_valid, msg = validate_flipkart_sales_excel("report.zip")
    assert not is_valid


def test_validate_amazon_zip():
    is_valid, msg = validate_amazon_zip("report.xlsx")
    assert not is_valid
