
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

class MeeshoInvoicePDF(Base):
    __tablename__ = "meesho_invoice_pdfs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_no = Column(String, index=True)
    suborder_no = Column(String, index=True)
    pdf_filename = Column(String)
    pdf_path = Column(String)
    pdf_size = Column(Integer)  # in bytes
    imported_at = Column(DateTime, default=datetime.now)

class MeeshoInventory(Base):
    __tablename__ = "meesho_inventory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    catalog_name = Column(String)
    catalog_id = Column(String, index=True)
    product_name = Column(String)
    product_id = Column(String, index=True)
    style_id = Column(String)
    variation_id = Column(String)
    variation = Column(String)
    current_stock = Column(Integer)
    system_stock_count = Column(Integer)
    your_stock_count = Column(Integer)
    seller_gstin = Column(String, index=True)  # For multi-seller support
    last_updated = Column(DateTime)

class MeeshoPayment(Base):
    __tablename__ = "meesho_payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Order Related Details (9 columns)
    sub_order_no = Column(String, index=True)
    order_date = Column(Date, index=True)
    dispatch_date = Column(Date)
    product_name = Column(String, index=True)
    supplier_sku = Column(String, index=True)  # Links to MeeshoInventory.product_id
    live_order_status = Column(String, index=True)
    product_gst_percent = Column(Float)
    listing_price_incl_taxes = Column(Float)
    quantity = Column(Integer)
    
    # Payment Details (3 columns)
    transaction_id = Column(String, index=True)
    payment_date = Column(Date, index=True)
    final_settlement_amount = Column(Float)
    
    # Revenue Details (7 columns)
    price_type = Column(String)
    total_sale_amount_incl_shipping_gst = Column(Float)
    total_sale_return_amount_incl_shipping_gst = Column(Float)
    fixed_fee_incl_gst = Column(Float)
    warehousing_fee_inc_gst = Column(Float)
    return_premium_incl_gst = Column(Float)
    return_premium_incl_gst_of_return = Column(Float)
    
    # Deductions (9 columns)
    meesho_commission_percentage = Column(Float)
    meesho_commission_incl_gst = Column(Float)
    meesho_gold_platform_fee_incl_gst = Column(Float)
    meesho_mall_platform_fee_incl_gst = Column(Float)
    fixed_fee_deduction_incl_gst = Column(Float)
    warehousing_fee_deduction_incl_gst = Column(Float)
    return_shipping_charge_incl_gst = Column(Float)
    gst_compensation_prp_shipping = Column(Float)
    shipping_charge_incl_gst = Column(Float)
    
    # Other Charges (4 columns)
    other_support_service_charges_excl_gst = Column(Float)
    waivers_excl_gst = Column(Float)
    net_other_support_service_charges_excl_gst = Column(Float)
    gst_on_net_other_support_service_charges = Column(Float)
    
    # TCS & TDS (3 columns)
    tcs = Column(Float)
    tds_rate_percent = Column(Float)
    tds = Column(Float)
    
    # Recovery, Claims and Compensation Details (6 columns)
    compensation = Column(Float)
    claims = Column(Float)
    recovery = Column(Float)
    compensation_reason = Column(String)
    claims_reason = Column(String)
    recovery_reason = Column(String)
    
    # Multi-seller support
    seller_gstin = Column(String, index=True)
    
    imported_at = Column(DateTime, default=datetime.now)

class MeeshoAdsCost(Base):
    __tablename__ = "meesho_ads_cost"

    id = Column(Integer, primary_key=True, autoincrement=True)
    deduction_duration = Column(String)
    deduction_date = Column(Date, index=True)
    campaign_id = Column(String, index=True)
    ad_cost = Column(Float)
    credits_waivers_discounts = Column(Float)
    ad_cost_incl_credits_waivers = Column(Float)
    gst = Column(Float)
    total_ads_cost = Column(Float)
    seller_gstin = Column(String, index=True)  # For multi-seller support
    imported_at = Column(DateTime, default=datetime.now)

class MeeshoReferralPayment(Base):
    __tablename__ = "meesho_referral_payments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reward_id = Column(String, index=True, unique=True)
    payment_date = Column(Date)
    store_name = Column(String)
    reason = Column(String)
    net_referral_amount = Column(Float)
    taxes_gst_tds = Column(Float)
    seller_gstin = Column(String, index=True)  # For multi-seller support
    imported_at = Column(DateTime, default=datetime.now)

class MeeshoCompensationRecovery(Base):
    __tablename__ = "meesho_compensation_recovery"

    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, index=True)
    program_name = Column(String)
    reason = Column(String)
    amount_inc_gst = Column(Float)
    seller_gstin = Column(String, index=True)  # For multi-seller support
    imported_at = Column(DateTime, default=datetime.now)

class MeeshoOrder(Base):
    __tablename__ = "meesho_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reason_for_credit_entry = Column(String)
    sub_order_no = Column(String, index=True)
    order_date = Column(Date)
    customer_state = Column(String)
    product_name = Column(String)
    product_id = Column(String, index=True)  # From MeeshoInventory mapping
    sku = Column(String)
    size = Column(String)
    quantity = Column(Integer)
    supplier_listed_price = Column(Float)
    supplier_discounted_price = Column(Float)
    packet_id = Column(String)

class MeeshoSale(Base):
    __tablename__ = "meesho_sales"

    id = Column(Integer, primary_key=True, autoincrement=True)  # New PK

    # Remove or comment out old PK constraint line
    # __table_args__ = (PrimaryKeyConstraint("sub_order_num", "order_date", name="meesho_sales_pk"),)

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

    id = Column(Integer, primary_key=True, autoincrement=True)  # New PK

    # __table_args__ = (PrimaryKeyConstraint("sub_order_num", "order_date", name="meesho_returns_pk"),)

    identifier = Column(String, index=True)
    sup_name = Column(String)
    gstin = Column(String)
    sub_order_num = Column(String)
    order_date = Column(Date)
    product_name = Column(String)  # Added for product tracking
    product_id = Column(String, index=True)  # From MeeshoInventory mapping
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
        # Composite unique constraint: same order_item can have multiple invoices
        # UniqueConstraint('order_item_id', 'buyer_invoice_id', name='uq_flipkart_order_invoice'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    marketplace = Column(String, default="Flipkart")  # Flipkart or Shopsy
    seller_gstin = Column(String, index=True)  # Seller GSTIN for multi-seller support
    order_id = Column(String, index=True)
    order_item_id = Column(String, index=True)  # Removed unique constraint
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
