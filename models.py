
from sqlalchemy import Column, Integer, String, Date, Float, DateTime
from datetime import datetime
from database import Base

class SellerMapping(Base):
    """Maps Meesho supplier_id to GSTIN for multi-seller support"""
    __tablename__ = "seller_mapping"

    id = Column(Integer, primary_key=True, autoincrement=True)
    supplier_id = Column(Integer, unique=True, index=True, nullable=False)
    gstin = Column(String, nullable=False)
    supplier_name = Column(String)
    last_updated = Column(DateTime, default=datetime.now)

class MeeshoInvoice(Base):
    __tablename__ = "meesho_invoices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_type = Column(String)  # INVOICE, CREDIT NOTE
    order_date = Column(DateTime)
    suborder_no = Column(String, index=True)
    product_description = Column(String)
    hsn_code = Column(String)
    invoice_no = Column(String, unique=True, index=True)
    imported_at = Column(DateTime, default=datetime.now)

class MeeshoSale(Base):
    __tablename__ = "meesho_sales"

    id = Column(Integer, primary_key=True, autoincrement=True)

    identifier = Column(String, index=True)
    sup_name = Column(String)
    gstin = Column(String)
    sub_order_num = Column(String)
    order_date = Column(Date)
    hsn_code = Column(Integer)
    quantity = Column(Integer)
    gst_rate = Column(Float)
    total_taxable_sale_value = Column(Float)
    tax_amount = Column(Float)
    total_invoice_value = Column(Float)
    taxable_shipping = Column(Float)
    end_customer_state_new = Column(String)
    enrollment_no = Column(String)
    financial_year = Column(Integer, index=True)
    month_number = Column(Integer, index=True)
    supplier_id = Column(Integer, index=True)

class MeeshoReturn(Base):
    __tablename__ = "meesho_returns"

    id = Column(Integer, primary_key=True, autoincrement=True)

    identifier = Column(String, index=True)
    sup_name = Column(String)
    gstin = Column(String)
    sub_order_num = Column(String)
    order_date = Column(Date)
    product_name = Column(String)
    product_id = Column(String, index=True)
    hsn_code = Column(Integer)
    quantity = Column(Integer)
    gst_rate = Column(Float)
    total_taxable_sale_value = Column(Float)
    tax_amount = Column(Float)
    total_invoice_value = Column(Float)
    taxable_shipping = Column(Float)
    end_customer_state_new = Column(String)
    enrollment_no = Column(String)
    financial_year = Column(Integer, index=True)
    month_number = Column(Integer, index=True)
    supplier_id = Column(Integer, index=True)


# Flipkart Marketplace Models

class FlipkartOrder(Base):
    __tablename__ = "flipkart_orders"
    __table_args__ = (
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    marketplace = Column(String, default="Flipkart")  # Flipkart or Shopsy
    seller_gstin = Column(String, index=True)  # Seller GSTIN for multi-seller support
    order_id = Column(String, index=True)
    order_item_id = Column(String, index=True)
    product_title = Column(String)
    fsn = Column(String, index=True)  # Flipkart SKU Number
    sku = Column(String, index=True)
    hsn_code = Column(String)
    event_type = Column(String)  # Sale, Return
    event_sub_type = Column(String)  # Sale, Cancellation, Customer Return
    order_type = Column(String)  # Postpaid, Prepaid
    order_date = Column(DateTime)
    order_approval_date = Column(DateTime)
    quantity = Column(Integer)
    warehouse_state = Column(String)
    price_before_discount = Column(Float)
    total_discount = Column(Float)
    price_after_discount = Column(Float)
    shipping_charges = Column(Float)
    final_invoice_amount = Column(Float)
    taxable_value = Column(Float)
    igst_rate = Column(Float)
    igst_amount = Column(Float)
    cgst_rate = Column(Float)
    cgst_amount = Column(Float)
    sgst_rate = Column(Float)
    sgst_amount = Column(Float)
    tcs_total = Column(Float)
    tds_amount = Column(Float)
    buyer_invoice_id = Column(String)
    buyer_invoice_date = Column(DateTime)
    customer_billing_state = Column(String)
    customer_delivery_state = Column(String)
    is_shopsy = Column(String)  # True/False as string
    imported_at = Column(DateTime, default=datetime.now)


class FlipkartReturn(Base):
    __tablename__ = "flipkart_returns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    marketplace = Column(String, default="Flipkart")
    seller_gstin = Column(String, index=True)  # Seller GSTIN for multi-seller support
    order_id = Column(String, index=True)
    order_item_id = Column(String, index=True)
    product_title = Column(String)
    fsn = Column(String, index=True)
    sku = Column(String, index=True)
    hsn_code = Column(String)
    event_sub_type = Column(String)  # Cancellation, Customer Return
    order_date = Column(DateTime)
    quantity = Column(Integer)
    return_amount = Column(Float)  # Negative invoice amount
    taxable_value = Column(Float)

    # Tax rates - added for HSN calculations
    igst_rate = Column(Float)
    cgst_rate = Column(Float)
    sgst_rate = Column(Float)

    # Tax amounts
    igst_amount = Column(Float)
    cgst_amount = Column(Float)
    sgst_amount = Column(Float)
    customer_delivery_state = Column(String)
    is_shopsy = Column(String)
    imported_at = Column(DateTime, default=datetime.now)


# Amazon Marketplace Models

class AmazonOrder(Base):
    __tablename__ = "amazon_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    marketplace = Column(String, default="Amazon")  # Amazon
    transaction_type = Column(String)  # Shipment, Refund, Cancel
    order_id = Column(String, index=True)
    shipment_id = Column(String, index=True)
    shipment_item_id = Column(String, index=True)
    invoice_number = Column(String, index=True)
    invoice_date = Column(DateTime)
    invoice_amount = Column(Float)
    order_date = Column(DateTime)
    shipment_date = Column(DateTime)
    quantity = Column(Integer)
    item_description = Column(String)
    asin = Column(String, index=True)  # Amazon Standard Identification Number
    sku = Column(String, index=True)
    hsn_sac = Column(String)

    # Tax and pricing details
    tax_exclusive_gross = Column(Float)
    total_tax_amount = Column(Float)
    taxable_value = Column(Float)
    principal_amount = Column(Float)
    shipping_amount = Column(Float)
    gift_wrap_amount = Column(Float)

    # Tax breakdown
    igst_rate = Column(Float)
    igst_amount = Column(Float)
    cgst_rate = Column(Float)
    cgst_amount = Column(Float)
    sgst_rate = Column(Float)
    sgst_amount = Column(Float)
    utgst_rate = Column(Float)
    utgst_amount = Column(Float)
    compensatory_cess_rate = Column(Float)
    compensatory_cess_amount = Column(Float)

    # TCS (Tax Collected at Source)
    tcs_igst_rate = Column(Float)
    tcs_igst_amount = Column(Float)
    tcs_cgst_rate = Column(Float)
    tcs_cgst_amount = Column(Float)
    tcs_sgst_rate = Column(Float)
    tcs_sgst_amount = Column(Float)

    # Location details
    ship_from_state = Column(String)
    ship_to_state = Column(String)
    ship_to_city = Column(String)
    ship_to_postal_code = Column(String)
    bill_to_state = Column(String)
    bill_to_city = Column(String)
    bill_to_postal_code = Column(String)

    # B2B specific fields
    seller_gstin = Column(String)
    customer_bill_to_gstid = Column(String, index=True)  # Buyer GSTIN for B2B transactions
    customer_ship_to_gstid = Column(String)
    buyer_name = Column(String)

    # Warehouse and fulfillment
    warehouse_id = Column(String)
    fulfillment_channel = Column(String)  # MFN, FBA

    imported_at = Column(DateTime, default=datetime.now)


class AmazonReturn(Base):
    __tablename__ = "amazon_returns"

    id = Column(Integer, primary_key=True, autoincrement=True)
    marketplace = Column(String, default="Amazon")
    transaction_type = Column(String)  # Refund, Cancel
    order_id = Column(String, index=True)
    shipment_item_id = Column(String, index=True)
    invoice_number = Column(String, index=True)
    invoice_date = Column(DateTime)
    return_amount = Column(Float)  # Negative amount
    order_date = Column(DateTime)
    quantity = Column(Integer)
    item_description = Column(String)
    asin = Column(String, index=True)
    sku = Column(String, index=True)
    hsn_sac = Column(String)
    taxable_value = Column(Float)

    # Tax rates - added for HSN calculations
    igst_rate = Column(Float)
    cgst_rate = Column(Float)
    sgst_rate = Column(Float)
    utgst_rate = Column(Float)

    # Tax amounts
    igst_amount = Column(Float)
    cgst_amount = Column(Float)
    sgst_amount = Column(Float)
    ship_to_state = Column(String)

    # B2B specific fields
    seller_gstin = Column(String)
    customer_bill_to_gstid = Column(String, index=True)
    buyer_name = Column(String)

    imported_at = Column(DateTime, default=datetime.now)
