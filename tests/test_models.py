"""Tests for database models and schema."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from database import Base
from models import (
    SellerMapping, MeeshoSale, MeeshoReturn, MeeshoInvoice,
    FlipkartOrder, FlipkartReturn, AmazonOrder, AmazonReturn,
)


def get_test_db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session(), engine


def test_all_tables_created():
    """Verify all expected tables are created."""
    _, engine = get_test_db()
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    expected = [
        "seller_mapping", "meesho_sales", "meesho_returns",
        "meesho_invoices", "flipkart_orders", "flipkart_returns",
        "amazon_orders", "amazon_returns",
    ]
    for table in expected:
        assert table in tables, f"Missing table: {table}"


def test_seller_mapping_crud():
    """Test basic CRUD on SellerMapping."""
    db, _ = get_test_db()
    mapping = SellerMapping(supplier_id=12345, gstin="29ABCDE1234F1Z5", supplier_name="Test Seller")
    db.add(mapping)
    db.commit()

    result = db.query(SellerMapping).filter(SellerMapping.supplier_id == 12345).first()
    assert result is not None
    assert result.gstin == "29ABCDE1234F1Z5"
    assert result.supplier_name == "Test Seller"
    db.close()


def test_meesho_sale_insert():
    """Test inserting a Meesho sale record."""
    db, _ = get_test_db()
    sale = MeeshoSale(
        identifier="TEST",
        gstin="29ABCDE1234F1Z5",
        hsn_code=39199090,
        quantity=1,
        gst_rate=18.0,
        total_taxable_sale_value=100.0,
        tax_amount=18.0,
        financial_year=2026,
        month_number=1,
        supplier_id=12345,
    )
    db.add(sale)
    db.commit()

    result = db.query(MeeshoSale).first()
    assert result is not None
    assert result.gst_rate == 18.0
    assert result.financial_year == 2026
    db.close()


def test_flipkart_order_insert():
    """Test inserting a Flipkart order."""
    db, _ = get_test_db()
    order = FlipkartOrder(
        seller_gstin="29ABCDE1234F1Z5",
        order_id="OD12345",
        hsn_code="39199090",
        event_type="Sale",
        quantity=2,
        taxable_value=200.0,
        igst_rate=18.0,
        igst_amount=36.0,
    )
    db.add(order)
    db.commit()

    result = db.query(FlipkartOrder).filter(FlipkartOrder.order_id == "OD12345").first()
    assert result is not None
    assert result.seller_gstin == "29ABCDE1234F1Z5"
    db.close()


def test_amazon_order_insert():
    """Test inserting an Amazon order."""
    db, _ = get_test_db()
    order = AmazonOrder(
        seller_gstin="29ABCDE1234F1Z5",
        order_id="AMZ-001",
        transaction_type="Shipment",
        invoice_number="INV-001",
        hsn_sac="39199090",
        quantity=1,
        taxable_value=500.0,
        igst_rate=18.0,
        igst_amount=90.0,
    )
    db.add(order)
    db.commit()

    result = db.query(AmazonOrder).filter(AmazonOrder.order_id == "AMZ-001").first()
    assert result is not None
    assert result.transaction_type == "Shipment"
    db.close()


def test_gstin_based_filtering():
    """Test that GSTIN-based data isolation works."""
    db, _ = get_test_db()
    # Insert sales for two different GSTINs
    for gstin in ["29AAAA0000A1Z1", "27BBBB0000B2Z2"]:
        sale = MeeshoSale(
            gstin=gstin, hsn_code=12345, quantity=1,
            gst_rate=18.0, total_taxable_sale_value=100.0,
            financial_year=2026, month_number=1, supplier_id=1,
        )
        db.add(sale)
    db.commit()

    # Query for only one GSTIN
    results = db.query(MeeshoSale).filter(MeeshoSale.gstin == "29AAAA0000A1Z1").all()
    assert len(results) == 1
    assert results[0].gstin == "29AAAA0000A1Z1"
    db.close()
