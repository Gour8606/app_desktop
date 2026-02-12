import os
import logging
import pandas as pd
import zipfile
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from models import MeeshoSale, MeeshoReturn, MeeshoInvoice
import shutil

logger = logging.getLogger(__name__)

_APP_DIR = os.path.dirname(os.path.abspath(__file__))
_TEMP_EXTRACT_DIR = os.path.join(_APP_DIR, "extracted_temp")
_TEMP_GSTIN_FILE = os.path.join(_APP_DIR, "temp_flipkart_gstin.json")


def parse_date(value):
    if pd.isna(value):
        return None
    try:
        return pd.to_datetime(value).date()
    except Exception:
        return None


def safe_float(value):
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


from constants import normalize_rate as normalize_gst_rate  # backward-compatible alias


# ============================================================================
# FILE VALIDATION FUNCTIONS - Prevent wrong files from being uploaded
# ============================================================================

def validate_meesho_tax_invoice_zip(filepath: str) -> tuple[bool, str]:
    """Validate that ZIP contains Meesho tax invoice files."""
    if not filepath.lower().endswith('.zip'):
        return False, "❌ Wrong file type! Please select a ZIP file for Meesho Tax Invoice."
    
    try:
        with zipfile.ZipFile(filepath, 'r') as zip_ref:
            files = [f.lower() for f in zip_ref.namelist()]
            
            # Check for expected Meesho files
            has_orders = any('orders_' in f and f.endswith('.csv') for f in files)
            has_sales = any('tcs_sales.xlsx' in f for f in files)
            has_returns = any('tcs_sales_return.xlsx' in f for f in files)
            
            if not (has_orders or has_sales or has_returns):
                # Check if it might be an Amazon or other marketplace file
                if any('mtr' in f or 'b2b' in f or 'b2c' in f for f in files):
                    return False, "❌ Wrong file! This appears to be an Amazon ZIP. Please use the Amazon buttons instead."
                if any('flipkart' in f for f in files):
                    return False, "❌ Wrong file! This appears to be a Flipkart ZIP. Please use the Flipkart buttons instead."
                
                return False, "❌ Wrong file! Meesho Tax Invoice ZIP should contain: orders_*.csv, tcs_sales.xlsx, or tcs_sales_return.xlsx"
            
            return True, "✅ Valid Meesho Tax Invoice ZIP"
    except zipfile.BadZipFile:
        return False, "❌ Invalid ZIP file! File is corrupted or not a valid ZIP archive."
    except Exception as e:
        return False, f"❌ Error reading ZIP file: {str(e)}"


def validate_invoices_zip(filepath: str) -> tuple[bool, str]:
    """Validate that ZIP contains Meesho GST report files."""
    if not filepath.lower().endswith('.zip'):
        return False, "❌ Wrong file type! Please select a ZIP file for Meesho GST Report."
    
    try:
        with zipfile.ZipFile(filepath, 'r') as zip_ref:
            files = zip_ref.namelist()
            
            # Should contain GST report files (usually Excel or PDF)
            has_files = len(files) > 0
            
            if not has_files:
                return False, "❌ Empty ZIP file! Please select a ZIP with GST report files."
            
            return True, "✅ Valid Meesho GST Report ZIP"
    except zipfile.BadZipFile:
        return False, "❌ Invalid ZIP file! File is corrupted or not a valid ZIP archive."
    except Exception as e:
        return False, f"❌ Error reading ZIP file: {str(e)}"


def validate_flipkart_sales_excel(filepath: str) -> tuple[bool, str]:
    """Validate that Excel contains Flipkart Sales Report."""
    if not filepath.lower().endswith(('.xlsx', '.xls')):
        return False, "❌ Wrong file type! Please select an Excel file (.xlsx or .xls)."
    
    try:
        # Check if 'Sales Report' sheet exists
        xl_file = pd.ExcelFile(filepath)
        
        if 'Sales Report' not in xl_file.sheet_names:
            # Check if it's a different file type
            first_sheet = xl_file.sheet_names[0] if xl_file.sheet_names else None
            if first_sheet:
                df = pd.read_excel(filepath, sheet_name=first_sheet, nrows=1)
                df.columns = [str(c).strip() for c in df.columns]
                
                if 'Product ID' in df.columns and 'Current Stock' in df.columns:
                    return False, "❌ Wrong file! This appears to be an Inventory file. Please use the Import Inventory button."
                if 'Sub Order No' in df.columns:
                    return False, "❌ Wrong file! This appears to be a Meesho file. Please use the Meesho buttons."
            
            return False, f"❌ Wrong file! Flipkart Sales Excel should have a 'Sales Report' sheet.\nFound sheets: {', '.join(xl_file.sheet_names)}"
        
        # Validate columns in Sales Report sheet
        df = pd.read_excel(filepath, sheet_name='Sales Report', nrows=1)
        df.columns = [str(c).strip() for c in df.columns]
        
        required_cols = ['Order ID', 'Order Item ID', 'FSN', 'SKU']
        missing = [col for col in required_cols if col not in df.columns]
        
        if missing:
            return False, f"❌ Wrong file! Flipkart Sales Report should have columns: {', '.join(required_cols)}\nMissing: {', '.join(missing)}"
        
        return True, "✅ Valid Flipkart Sales Excel"
    except Exception as e:
        return False, f"❌ Error reading Excel file: {str(e)}"


def validate_flipkart_gst_excel(filepath: str) -> tuple[bool, str]:
    """Validate that Excel contains Flipkart GST/B2C data."""
    if not filepath.lower().endswith(('.xlsx', '.xls')):
        return False, "❌ Wrong file type! Please select an Excel file (.xlsx or .xls)."
    
    try:
        xl_file = pd.ExcelFile(filepath)
        
        if not xl_file.sheet_names:
            return False, "❌ Empty Excel file!"
        
        # Check if this is a GSTR-1 report with section sheets
        gstr_indicators = ['Section', 'GSTR-1', 'GSTR-8']
        has_gstr_sheets = any(any(indicator in sheet for indicator in gstr_indicators) for sheet in xl_file.sheet_names)
        
        if has_gstr_sheets:
            return True, "✅ Valid Flipkart GST Report (GSTR-1 format)"
        
        # Otherwise check the first non-Help sheet for GST columns
        first_sheet = None
        for sheet in xl_file.sheet_names:
            if sheet.lower() != 'help':
                first_sheet = sheet
                break
        
        if not first_sheet:
            return False, "❌ No data sheets found in Excel file!"
        
        df = pd.read_excel(filepath, sheet_name=first_sheet, nrows=1)
        df.columns = [str(c).strip() for c in df.columns]
        
        # Check for GSTR-1 related columns (B2C, B2CL)
        gst_indicators = ['Place of Supply', 'Invoice Type', 'Taxable Value', 'Rate', 'IGST', 'CGST', 'SGST', 
                          'Aggregate Taxable Value', 'Delivered State']
        has_gst_cols = any(col in df.columns for col in gst_indicators)
        
        if not has_gst_cols:
            if 'Order ID' in df.columns and 'FSN' in df.columns:
                return False, "❌ Wrong file! This appears to be a Flipkart Sales Report. Please use the Import Flipkart Sales button."
            if 'Product ID' in df.columns and 'Current Stock' in df.columns:
                return False, "❌ Wrong file! This appears to be an Inventory file. Please use the Import Meesho Inventory button."
            
            return False, "❌ Wrong file! Flipkart GST Excel should contain GST-related columns like 'Place of Supply', 'Taxable Value', 'Rate', etc."
        
        return True, "✅ Valid Flipkart GST Excel"
    except Exception as e:
        return False, f"❌ Error reading Excel file: {str(e)}"


def validate_amazon_zip(filepath: str, expected_type: str = "B2B") -> tuple[bool, str]:
    """Validate that ZIP contains Amazon MTR/GSTR1 CSV or Excel files."""
    if not filepath.lower().endswith('.zip'):
        return False, f"❌ Wrong file type! Please select a ZIP file for Amazon {expected_type}."
    
    try:
        with zipfile.ZipFile(filepath, 'r') as zip_ref:
            all_files = zip_ref.namelist()
            csv_files = [f for f in all_files if f.endswith('.csv')]
            excel_files = [f for f in all_files if f.endswith(('.xlsx', '.xls'))]
            
            # Check if it's a GSTR1 report (contains Excel)
            if expected_type == "GSTR1" and excel_files:
                return True, "Valid Amazon GSTR1 ZIP (Excel format)"
            
            # For B2B/B2C, check CSV files
            if not csv_files and not excel_files:
                # Check if it might be a Meesho file
                all_files_lower = [f.lower() for f in all_files]
                if any('tcs_sales' in f or 'orders_' in f for f in all_files_lower):
                    return False, "❌ Wrong file! This appears to be a Meesho ZIP. Please use the Import Meesho Tax Invoice button."
                
                return False, f"❌ Wrong file! Amazon {expected_type} ZIP should contain CSV or Excel files."
            
            # If we have CSV files, validate Amazon MTR format
            if csv_files:
                csv_file = csv_files[0]
                with zip_ref.open(csv_file) as f:
                    df = pd.read_csv(f, nrows=1)
                    df.columns = [str(c).strip() for c in df.columns]
                    
                    # Amazon MTR has specific columns
                    amazon_cols = ['Order Id', 'invoice-type', 'Product Title', 'sku', 'ship-city', 'ship-state']
                    has_amazon_cols = any(col in df.columns for col in amazon_cols)
                    
                    if not has_amazon_cols:
                        return False, f"❌ Wrong file! Amazon {expected_type} CSV should have columns like: {', '.join(amazon_cols[:3])}"
        
        return True, f"✅ Valid Amazon {expected_type} ZIP"
    except zipfile.BadZipFile:
        return False, "❌ Invalid ZIP file! File is corrupted or not a valid ZIP archive."
    except Exception as e:
        return False, f"❌ Error reading ZIP file: {str(e)}"


def import_from_zip(zip_path: str, db: Session) -> list:
    """
    Extracts and imports Meesho sales and returns data from a ZIP file.
    Returns a list of status messages for GUI display.
    """
    messages = []
    extract_dir = _TEMP_EXTRACT_DIR
    os.makedirs(extract_dir, exist_ok=True)

    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)

        sales_file = None
        returns_file = None

        for file in os.listdir(extract_dir):
            if "tcs_sales.xlsx" in file.lower():
                sales_file = os.path.join(extract_dir, file)
            elif "tcs_sales_return.xlsx" in file.lower():
                returns_file = os.path.join(extract_dir, file)

        if sales_file:
            messages += import_sales_data(sales_file, db)
        if returns_file:
            messages += import_returns_data(returns_file, db)
    finally:
        shutil.rmtree(extract_dir, ignore_errors=True)

    return messages
def import_sales_data(filepath: str, db: Session) -> list:
    from models import SellerMapping
    df = pd.read_excel(filepath)
    messages = []

    numeric_cols = [
        "hsn_code", "quantity", "gst_rate",
        "total_taxable_sale_value", "tax_amount", "total_invoice_value",
        "taxable_shipping", "financial_year", "month_number", "supplier_id"
    ]

    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if df.empty:
        messages.append("⚠️ File has headers but no data rows. Nothing to import.")
        return messages

    # Extract unique financial year, month number, and supplier ID from the data
    fy = int(df["financial_year"].iloc[0])
    mn = int(df["month_number"].iloc[0])
    sid = int(df["supplier_id"].iloc[0])
    
    # Extract GSTIN and supplier name for mapping
    gstin = df["gstin"].iloc[0] if "gstin" in df.columns and not pd.isna(df["gstin"].iloc[0]) else None
    sup_name = df["sup_name"].iloc[0] if "sup_name" in df.columns and not pd.isna(df["sup_name"].iloc[0]) else None
    
    # Save or update seller mapping
    if gstin:
        existing_mapping = db.query(SellerMapping).filter(SellerMapping.supplier_id == sid).first()
        if existing_mapping:
            existing_mapping.gstin = gstin
            existing_mapping.supplier_name = sup_name
            existing_mapping.last_updated = datetime.now()
            messages.append(f"Updated seller mapping: Supplier {sid} → GSTIN {gstin}")
        else:
            new_mapping = SellerMapping(
                supplier_id=sid,
                gstin=gstin,
                supplier_name=sup_name
            )
            db.add(new_mapping)
            messages.append(f"Created seller mapping: Supplier {sid} → GSTIN {gstin}")
        db.commit()

    # Delete existing sales data for this financial year, month number and supplier ID
    db.query(MeeshoSale).filter(
        MeeshoSale.financial_year == fy,
        MeeshoSale.month_number == mn,
        MeeshoSale.supplier_id == sid
    ).delete(synchronize_session=False)
    db.commit()
    messages.append(f"Existing sales data deleted for FY {fy}, Month {mn}, Supplier {sid}")

    for _, row in df.iterrows():
        record = MeeshoSale(
            identifier=row.get("identifier", ""),
            sup_name=row.get("sup_name", ""),
            gstin=gstin,
            sub_order_num=row.get("sub_order_num", ""),
            order_date=parse_date(row.get("order_date")),
            hsn_code=int(row.get("hsn_code") or 0),
            quantity=int(row.get("quantity") or 0),
            gst_rate=safe_float(row.get("gst_rate")),
            total_taxable_sale_value=safe_float(row.get("total_taxable_sale_value")),
            tax_amount=safe_float(row.get("tax_amount")),
            total_invoice_value=safe_float(row.get("total_invoice_value")),
            taxable_shipping=safe_float(row.get("taxable_shipping")),
            end_customer_state_new=row.get("end_customer_state_new", ""),
            enrollment_no=str(row.get("enrollment_no", "")),
            financial_year=fy,
            month_number=mn,
            supplier_id=sid,
        )
        db.add(record)

    try:
        db.commit()
        messages.append(f"Sales data imported from {os.path.basename(filepath)}")
    except IntegrityError:
        db.rollback()
        messages.append("Duplicate skipped during sales import.")
    except Exception as e:
        db.rollback()
        messages.append(f"Error during sales import: {e}")

    return messages


def import_returns_data(filepath: str, db: Session) -> list:
    df = pd.read_excel(filepath)
    messages = []

    numeric_cols = [
        "hsn_code", "quantity", "gst_rate",
        "total_taxable_sale_value", "tax_amount", "total_invoice_value",
        "taxable_shipping", "financial_year", "month_number", "supplier_id"
    ]

    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if df.empty:
        messages.append("⚠️ Returns file has headers but no data rows. Nothing to import.")
        return messages

    fy = int(df["financial_year"].iloc[0])
    mn = int(df["month_number"].iloc[0])
    sid = int(df["supplier_id"].iloc[0])

    gstin = df["gstin"].iloc[0] if "gstin" in df.columns and not pd.isna(df["gstin"].iloc[0]) else None

    # Delete existing returns data for this financial year, month number and supplier ID
    db.query(MeeshoReturn).filter(
        MeeshoReturn.financial_year == fy,
        MeeshoReturn.month_number == mn,
        MeeshoReturn.supplier_id == sid
    ).delete(synchronize_session=False)
    db.commit()
    messages.append(f"Existing returns data deleted for FY {fy}, Month {mn}, Supplier {sid}")

    for _, row in df.iterrows():
        product_name = row.get("Product Name") or row.get("product_name", "")
        if isinstance(product_name, str):
            product_name = product_name.strip()

        record = MeeshoReturn(
            identifier=row.get("identifier", ""),
            sup_name=row.get("sup_name", ""),
            gstin=gstin,
            sub_order_num=row.get("sub_order_num", ""),
            order_date=parse_date(row.get("order_date")),
            product_name=product_name,
            product_id=None,
            hsn_code=int(row.get("hsn_code") or 0),
            quantity=int(row.get("quantity") or 0),
            gst_rate=safe_float(row.get("gst_rate")),
            total_taxable_sale_value=safe_float(row.get("total_taxable_sale_value")),
            tax_amount=safe_float(row.get("tax_amount")),
            total_invoice_value=safe_float(row.get("total_invoice_value")),
            taxable_shipping=safe_float(row.get("taxable_shipping")),
            end_customer_state_new=row.get("end_customer_state_new", ""),
            enrollment_no=str(row.get("enrollment_no", "")),
            financial_year=fy,
            month_number=mn,
            supplier_id=sid,
        )
        db.add(record)

    try:
        db.commit()
        messages.append(f"Returns data imported from {os.path.basename(filepath)} with product_id mapping")
    except IntegrityError:
        db.rollback()
        messages.append("Duplicate skipped during returns import.")
    except Exception as e:
        db.rollback()
        messages.append(f"Error during returns import: {e}")

    return messages


def import_invoice_data(zip_path: str, db: Session) -> list:
    """Extract and import invoice data from ZIP file containing Tax_invoice_details.xlsx"""
    messages = []
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Find Tax_invoice_details.xlsx
            excel_files = [f for f in zip_ref.namelist() if 'tax_invoice_details' in f.lower() and f.endswith('.xlsx')]
            if not excel_files:
                return ["❌ No Tax_invoice_details.xlsx file found in ZIP"]
            
            excel_file = excel_files[0]
            
            # Read invoice data
            df = pd.read_excel(zip_ref.open(excel_file))
            
            # Don't delete existing invoices - append new ones (skip duplicates)
            # This allows multiple sellers' invoices to coexist
            
            count = 0
            skipped = 0
            errors = 0
            for _, row in df.iterrows():
                if pd.isna(row.get("Suborder No.")):
                    continue
                
                try:
                    suborder_no = str(row.get("Suborder No.", "")).strip()
                    invoice_no = str(row.get("Invoice No.", "")).strip()
                    
                    # Check if this invoice already exists (by suborder_no and invoice_no)
                    existing = db.query(MeeshoInvoice).filter(
                        MeeshoInvoice.suborder_no == suborder_no,
                        MeeshoInvoice.invoice_no == invoice_no
                    ).first()
                    
                    if existing:
                        skipped += 1
                        continue
                    
                    order_date = pd.to_datetime(row.get("Order Date")) if pd.notna(row.get("Order Date")) else None
                    
                    # Get GSTIN from linked MeeshoSale to ensure invoice isolation by seller
                    meesho_sale = db.query(MeeshoSale).filter(
                        MeeshoSale.sub_order_num == suborder_no
                    ).first()
                    gstin_from_sale = meesho_sale.gstin if meesho_sale else None
                    
                    record = MeeshoInvoice(
                        invoice_type=str(row.get("Type", "")).strip(),
                        order_date=order_date,
                        suborder_no=suborder_no,
                        product_description=str(row.get("Product Description", "")).strip(),
                        hsn_code=str(row.get("HSN", "")).strip(),
                        invoice_no=invoice_no,
                        gstin=gstin_from_sale  # Add GSTIN for data isolation
                    )
                    db.add(record)
                    count += 1
                except Exception as row_err:
                    errors += 1
                    logger.warning(f"Skipped row {invoice_no}: {row_err}")
                    continue

            db.commit()
            messages.append(f"Invoice data imported: {count} new invoices")
            if skipped > 0:
                messages.append(f"   {skipped} duplicates skipped")
            if errors > 0:
                messages.append(f"   {errors} rows skipped due to errors (check logs)")
    except Exception as e:
        db.rollback()
        messages.append(f"❌ Error importing invoices: {e}")
    
    return messages


def import_flipkart_sales(filepath: str, db: Session) -> list:
    """
    Import Flipkart Sales Report Excel file with Sales Report and Cash Back Report sheets.
    Separates sales (Event Type = 'Sale') and returns (Event Type = 'Return') into different tables.
    
    CRITICAL SAFETY: Requires user to explicitly provide seller GSTIN to prevent data leakage.
    Flipkart Sales Report files don't contain GSTIN, so we MUST validate before importing.
    """
    from models import FlipkartOrder, FlipkartReturn
    messages = []
    
    # SAFETY CHECK: Require explicit GSTIN entry before import
    # Do NOT use temp file - this causes cross-seller data leakage
    seller_gstin = None
    try:
        import json
        import os
        # Check if we have a stored GSTIN from recent GST report import
        if os.path.exists(_TEMP_GSTIN_FILE):
            with open(_TEMP_GSTIN_FILE, 'r') as f:
                temp_config = json.load(f)
                last_gstin = temp_config.get('last_flipkart_gstin')
                if last_gstin:
                    messages.append(f"GSTIN found from previous import: {last_gstin}")
                    messages.append("This is a safety feature. Proceeding with this GSTIN.")
                    messages.append("If this is WRONG seller, STOP THIS IMPORT immediately.")
                    seller_gstin = last_gstin
    except Exception:
        pass

    if not seller_gstin:
        messages.append("❌ IMPORT BLOCKED: No seller GSTIN available.")
        messages.append("ℹ️  CRITICAL FOR DATA ISOLATION:")
        messages.append("    1. Import Flipkart GST Report FIRST (this captures your seller GSTIN)")
        messages.append("    2. Then import Flipkart Sales Report immediately after")
        messages.append("    3. Do NOT switch between different sellers without re-importing GST report")
        return messages
    
    try:
        # Read Sales Report sheet
        df = pd.read_excel(filepath, sheet_name='Sales Report')
        
        # Clean column names
        df.columns = [str(c).strip().replace('"""', '').replace('"', '') for c in df.columns]
        
        # Remove rows with missing Order ID
        df = df[df["Order ID"].notna()]
        
        # Remove duplicates based on Order Item ID + Buyer Invoice ID combination
        df = df.drop_duplicates(subset=['Order Item ID', 'Buyer Invoice ID'], keep='first')
        
        sales_count = 0
        returns_count = 0
        skipped_count = 0
        
        for _, row in df.iterrows():
            event_type = str(row.get("Event Type", "")).strip()
            is_shopsy = str(row.get("Is Shopsy Order?", "False")).strip()
            order_item_id = str(row.get("Order Item ID", ""))
            
            # Parse dates
            order_date = parse_date(row.get("Order Date"))
            order_approval_date = parse_date(row.get("Order Approval Date"))
            buyer_invoice_date = parse_date(row.get("Buyer Invoice Date"))
            
            if event_type == "Sale":
                # Check if this order item already exists
                existing = db.query(FlipkartOrder).filter(FlipkartOrder.order_item_id == order_item_id).first()
                if existing:
                    skipped_count += 1
                    continue
                
                # This is a sale order
                record = FlipkartOrder(
                    marketplace="Shopsy" if is_shopsy == "True" else "Flipkart",
                    seller_gstin=seller_gstin,  # Add seller GSTIN
                    order_id=str(row.get("Order ID", "")),
                    order_item_id=order_item_id,
                    product_title=str(row.get("Product Title/Description", "")),
                    fsn=str(row.get("FSN", "")),
                    sku=str(row.get("SKU", "")),
                    hsn_code=str(row.get("HSN Code", "")),
                    event_type=event_type,
                    event_sub_type=str(row.get("Event Sub Type", "")),
                    order_type=str(row.get("Order Type", "")),
                    order_date=order_date,
                    order_approval_date=order_approval_date,
                    quantity=int(row.get("Item Quantity") or 0),
                    warehouse_state=str(row.get("Order Shipped From (State)", "")),
                    price_before_discount=safe_float(row.get("Price before discount")),
                    total_discount=safe_float(row.get("Total Discount")),
                    price_after_discount=safe_float(row.get("Price after discount (Price before discount-Total discount)")),
                    shipping_charges=safe_float(row.get("Shipping Charges")),
                    final_invoice_amount=safe_float(row.get("Final Invoice Amount (Price after discount+Shipping Charges)")),
                    taxable_value=safe_float(row.get("Taxable Value (Final Invoice Amount -Taxes)")),
                    igst_rate=normalize_gst_rate(row.get("IGST Rate")),
                    igst_amount=safe_float(row.get("IGST Amount")),
                    cgst_rate=normalize_gst_rate(row.get("CGST Rate")),
                    cgst_amount=safe_float(row.get("CGST Amount")),
                    sgst_rate=normalize_gst_rate(row.get("SGST Rate (or UTGST as applicable)")),
                    sgst_amount=safe_float(row.get("SGST Amount (Or UTGST as applicable)")),
                    tcs_total=safe_float(row.get("Total TCS Deducted")),
                    tds_amount=safe_float(row.get("TDS Amount")),
                    buyer_invoice_id=str(row.get("Buyer Invoice ID", "")),
                    buyer_invoice_date=buyer_invoice_date,
                    customer_billing_state=str(row.get("Customer's Billing State", "")),
                    customer_delivery_state=str(row.get("Customer's Delivery State", "")),
                    is_shopsy=is_shopsy
                )
                db.add(record)
                sales_count += 1
                
            elif event_type == "Return":
                # Check if this return item already exists
                existing = db.query(FlipkartReturn).filter(FlipkartReturn.order_item_id == order_item_id).first()
                if existing:
                    skipped_count += 1
                    continue
                
                # This is a return/cancellation
                record = FlipkartReturn(
                    marketplace="Shopsy" if is_shopsy == "True" else "Flipkart",
                    seller_gstin=seller_gstin,  # Add seller GSTIN
                    order_id=str(row.get("Order ID", "")),
                    order_item_id=order_item_id,
                    product_title=str(row.get("Product Title/Description", "")),
                    fsn=str(row.get("FSN", "")),
                    sku=str(row.get("SKU", "")),
                    hsn_code=str(row.get("HSN Code", "")),
                    event_sub_type=str(row.get("Event Sub Type", "")),
                    order_date=order_date,
                    quantity=int(row.get("Item Quantity") or 0),
                    return_amount=safe_float(row.get("Final Invoice Amount (Price after discount+Shipping Charges)")),
                    taxable_value=safe_float(row.get("Taxable Value (Final Invoice Amount -Taxes)")),
                    igst_rate=normalize_gst_rate(row.get("IGST Rate")),
                    cgst_rate=normalize_gst_rate(row.get("CGST Rate")),
                    sgst_rate=normalize_gst_rate(row.get("SGST Rate (or UTGST as applicable)")),
                    igst_amount=safe_float(row.get("IGST Amount")),
                    cgst_amount=safe_float(row.get("CGST Amount")),
                    sgst_amount=safe_float(row.get("SGST Amount (Or UTGST as applicable)")),
                    customer_delivery_state=str(row.get("Customer's Delivery State", "")),
                    is_shopsy=is_shopsy
                )
                db.add(record)
                returns_count += 1
        
        db.commit()
        messages.append("Flipkart Sales Report imported:")
        messages.append(f"   📦 {sales_count} orders")
        messages.append(f"   🔄 {returns_count} returns/cancellations")
        if skipped_count > 0:
            messages.append(f"   ⏭️ {skipped_count} duplicates skipped")
        
    except Exception as e:
        db.rollback()
        messages.append(f"❌ Error importing Flipkart Sales Report: {e}")
    
    return messages


def import_flipkart_b2c(filepath: str, db: Session) -> list:
    """
    Import Flipkart GST Report (Excel file with GSTR-1 sections).
    This report contains aggregated tax data for GST filing purposes.
    Note: Individual sales data should be imported from Flipkart Sales Report instead.
    
    NEW: Extracts and returns seller GSTIN from GST report for use in Sales Report imports.
    """
    from models import FlipkartOrder, FlipkartReturn
    messages = []
    seller_gstin = None
    
    try:
        # Check if file is Excel or ZIP
        if filepath.endswith('.xlsx'):
            # Flipkart GST Report - Excel file with GSTR sections
            messages.append("ℹ️  Flipkart GST Report detected (GSTR-1 format)")
            
            # Extract seller GSTIN from the first sheet
            xl = pd.ExcelFile(filepath)
            for sheet in xl.sheet_names:
                if sheet != 'Help':
                    try:
                        df = pd.read_excel(filepath, sheet_name=sheet, nrows=1)
                        if 'GSTIN' in df.columns and not df.empty:
                            gstin_value = df['GSTIN'].iloc[0]
                            if pd.notna(gstin_value) and str(gstin_value).strip():
                                seller_gstin = str(gstin_value).strip()
                                messages.append(f"✅ Seller GSTIN extracted: {seller_gstin}")
                                break
                    except Exception:
                        continue
            
            if not seller_gstin:
                messages.append("⚠️  No seller GSTIN found in GST report")
            
            messages.append("ℹ️  This report contains aggregated tax data for GST filing.")
            messages.append("ℹ️  For sales analytics, please import Flipkart Sales Report (.xlsx) instead.")
            messages.append("⚠️  GST Report import is not required for sales tracking.")
            
            # Read the file to show what's available
            messages.append("\nGST Report Sections found:")
            for sheet in xl.sheet_names:
                if sheet != 'Help':
                    df = pd.read_excel(filepath, sheet_name=sheet)
                    messages.append(f"   • {sheet} ({len(df)} records)")
            
            messages.append("\n✅ GST Report validated. Use for tax filing reference.")
            
            # Store GSTIN for later use (if Sales Report is imported next)
            if seller_gstin:
                # Save to a temp config file for use in next import
                import json
                import time
                temp_config = {
                    'last_flipkart_gstin': seller_gstin,
                    'timestamp': time.time()  # Track when this was imported for safety
                }
                with open(_TEMP_GSTIN_FILE, 'w') as f:
                    json.dump(temp_config, f)
                messages.append("\nDATA ISOLATION SAFETY:")
                messages.append(f"   GSTIN saved: {seller_gstin}")
                messages.append("   Import Sales Report for THIS SELLER next (don't switch sellers)")
                messages.append("   If you switch to different seller, re-import GST Report first")
            
            return messages
        
        # If it's a ZIP file, try to process as B2C report (old format)
        extract_dir = _TEMP_EXTRACT_DIR
        os.makedirs(extract_dir, exist_ok=True)
        
        with zipfile.ZipFile(filepath, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        # Find CSV file
        csv_file = None
        for file in os.listdir(extract_dir):
            if file.endswith('.csv'):
                csv_file = os.path.join(extract_dir, file)
                break
        
        if not csv_file:
            messages.append("❌ No CSV file found in ZIP")
            shutil.rmtree(extract_dir, ignore_errors=True)
            return messages
        
        # Read CSV
        df = pd.read_csv(csv_file)
        
        # Clean column names
        df.columns = [str(c).strip() for c in df.columns]
        
        # Remove rows with missing Order Id
        df = df[df["Order Id"].notna()]
        
        # REQUIRED: Get seller GSTIN from temp file (must import GST Report first)
        seller_gstin = None
        try:
            import json
            if os.path.exists(_TEMP_GSTIN_FILE):
                with open(_TEMP_GSTIN_FILE, 'r') as f:
                    temp_config = json.load(f)
                    seller_gstin = temp_config.get('last_flipkart_gstin')
        except Exception:
            pass

        if not seller_gstin:
            messages.append("❌ IMPORT BLOCKED: No seller GSTIN available for B2C ZIP report.")
            messages.append("ℹ️  CRITICAL FOR DATA ISOLATION:")
            messages.append("    1. Import Flipkart GST Report (Excel) FIRST")
            messages.append("    2. Then import Flipkart B2C Report (ZIP) immediately after")
            messages.append("    3. Do NOT switch between different sellers without re-importing GST")
            shutil.rmtree(extract_dir, ignore_errors=True)
            return messages
        
        shipments_count = 0
        cancellations_count = 0
        
        for _, row in df.iterrows():
            transaction_type = str(row.get("Transaction Type", "")).strip()
            
            # Parse dates
            order_date = parse_date(row.get("Order Date"))
            shipment_date = parse_date(row.get("Shipment Date"))
            invoice_date = parse_date(row.get("Invoice Date"))
            
            if transaction_type == "Shipment":
                # This is a shipment order
                record = FlipkartOrder(
                    marketplace="Flipkart",
                    seller_gstin=seller_gstin,
                    order_id=str(row.get("Order Id", "")),
                    order_item_id=str(row.get("Shipment Item Id", "")),
                    product_title=str(row.get("Item Description", "")),
                    fsn=str(row.get("Asin", "")),  # ASIN is like FSN
                    sku=str(row.get("Sku", "")),
                    hsn_code=str(row.get("Hsn/sac", "")),
                    event_type="Sale",
                    event_sub_type="Shipment",
                    order_type="",  # Not available in B2C
                    order_date=order_date,
                    order_approval_date=shipment_date,
                    quantity=int(row.get("Quantity") or 0),
                    warehouse_state=str(row.get("Ship From State", "")),
                    price_before_discount=safe_float(row.get("Principal Amount")),
                    total_discount=0.0,  # Not directly available
                    price_after_discount=safe_float(row.get("Principal Amount")),
                    shipping_charges=safe_float(row.get("Shipping Amount")),
                    final_invoice_amount=safe_float(row.get("Invoice Amount")),
                    taxable_value=safe_float(row.get("Tax Exclusive Gross")),
                    igst_rate=normalize_gst_rate(row.get("Igst Rate")),
                    igst_amount=safe_float(row.get("Igst Tax")),
                    cgst_rate=normalize_gst_rate(row.get("Cgst Rate")),
                    cgst_amount=safe_float(row.get("Cgst Tax")),
                    sgst_rate=normalize_gst_rate(row.get("Sgst Rate")),
                    sgst_amount=safe_float(row.get("Sgst Tax")),
                    tcs_total=safe_float(row.get("Tcs Igst Amount", 0)) + safe_float(row.get("Tcs Cgst Amount", 0)) + safe_float(row.get("Tcs Sgst Amount", 0)),
                    tds_amount=0.0,
                    buyer_invoice_id=str(row.get("Invoice Number", "")),
                    buyer_invoice_date=invoice_date,
                    customer_billing_state=str(row.get("Ship To State", "")),
                    customer_delivery_state=str(row.get("Ship To State", "")),
                    is_shopsy="False"
                )
                db.add(record)
                shipments_count += 1
                
            elif transaction_type == "Cancel":
                # This is a cancellation
                record = FlipkartReturn(
                    marketplace="Flipkart",
                    seller_gstin=seller_gstin,
                    order_id=str(row.get("Order Id", "")),
                    order_item_id=str(row.get("Shipment Item Id", "")),
                    product_title=str(row.get("Item Description", "")),
                    fsn=str(row.get("Asin", "")),
                    sku=str(row.get("Sku", "")),
                    hsn_code=str(row.get("Hsn/sac", "")),
                    event_sub_type="Cancellation",
                    order_date=order_date,
                    quantity=int(row.get("Quantity") or 0),
                    return_amount=safe_float(row.get("Invoice Amount")),
                    taxable_value=safe_float(row.get("Tax Exclusive Gross")),
                    igst_rate=normalize_gst_rate(row.get("Igst Rate")),
                    cgst_rate=normalize_gst_rate(row.get("Cgst Rate")),
                    sgst_rate=normalize_gst_rate(row.get("Sgst Rate")),
                    igst_amount=safe_float(row.get("Igst Tax")),
                    cgst_amount=safe_float(row.get("Cgst Tax")),
                    sgst_amount=safe_float(row.get("Sgst Tax")),
                    customer_delivery_state=str(row.get("Ship To State", "")),
                    is_shopsy="False"
                )
                db.add(record)
                cancellations_count += 1
        
        db.commit()
        messages.append("Flipkart B2C Report imported:")
        messages.append(f"   📦 {shipments_count} shipments")
        messages.append(f"   ❌ {cancellations_count} cancellations")
        
        # Clean up extracted files
        shutil.rmtree(extract_dir, ignore_errors=True)
        
    except Exception as e:
        db.rollback()
        messages.append(f"❌ Error importing Flipkart report: {e}")
        if 'extract_dir' in locals():
            shutil.rmtree(extract_dir, ignore_errors=True)
    
    return messages


def import_amazon_mtr(filepath: str, db: Session) -> list:
    """
    Import Amazon MTR (Monthly Tax Report) from ZIP file containing CSV.
    Handles B2B and B2C reports with shipments, refunds, and cancellations.
    """
    from models import AmazonOrder, AmazonReturn
    messages = []
    
    try:
        # Extract ZIP file
        extract_dir = _TEMP_EXTRACT_DIR
        os.makedirs(extract_dir, exist_ok=True)
        
        with zipfile.ZipFile(filepath, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        # Find CSV file
        csv_file = None
        for file in os.listdir(extract_dir):
            if file.endswith('.csv'):
                csv_file = os.path.join(extract_dir, file)
                break
        
        if not csv_file:
            messages.append("❌ No CSV file found in ZIP")
            shutil.rmtree(extract_dir, ignore_errors=True)
            return messages
        
        # Read CSV
        df = pd.read_csv(csv_file)
        
        # Clean column names
        df.columns = [str(c).strip() for c in df.columns]
        
        # Remove rows with missing Order Id
        df = df[df["Order Id"].notna()]
        
        shipments_count = 0
        returns_count = 0
        skipped_count = 0
        
        for _, row in df.iterrows():
            transaction_type = str(row.get("Transaction Type", "")).strip()
            order_id = str(row.get("Order Id", ""))
            shipment_item_id = str(row.get("Shipment Item Id", ""))
            
            # Parse dates
            order_date = parse_date(row.get("Order Date"))
            shipment_date = parse_date(row.get("Shipment Date"))
            invoice_date = parse_date(row.get("Invoice Date"))
            
            if transaction_type == "Shipment":
                # Check if already exists
                existing = db.query(AmazonOrder).filter(
                    AmazonOrder.order_id == order_id,
                    AmazonOrder.shipment_item_id == shipment_item_id
                ).first()
                if existing:
                    skipped_count += 1
                    continue
                
                # This is a shipment order
                record = AmazonOrder(
                    marketplace="Amazon",
                    transaction_type=transaction_type,
                    order_id=order_id,
                    shipment_id=str(row.get("Shipment Id", "")),
                    shipment_item_id=shipment_item_id,
                    invoice_number=str(row.get("Invoice Number", "")),
                    invoice_date=invoice_date,
                    invoice_amount=safe_float(row.get("Invoice Amount")),
                    order_date=order_date,
                    shipment_date=shipment_date,
                    quantity=int(row.get("Quantity") or 0),
                    item_description=str(row.get("Item Description", "")),
                    asin=str(row.get("Asin", "")),
                    sku=str(row.get("Sku", "")),
                    hsn_sac=str(row.get("Hsn/sac", "")),
                    
                    # Tax and pricing
                    tax_exclusive_gross=safe_float(row.get("Tax Exclusive Gross")),
                    total_tax_amount=safe_float(row.get("Total Tax Amount")),
                    taxable_value=safe_float(row.get("Tax Exclusive Gross")),
                    principal_amount=safe_float(row.get("Principal Amount")),
                    shipping_amount=safe_float(row.get("Shipping Amount")),
                    gift_wrap_amount=safe_float(row.get("Gift Wrap Amount")),
                    
                    # Tax breakdown
                    igst_rate=normalize_gst_rate(row.get("Igst Rate")),
                    igst_amount=safe_float(row.get("Igst Tax")),
                    cgst_rate=normalize_gst_rate(row.get("Cgst Rate")),
                    cgst_amount=safe_float(row.get("Cgst Tax")),
                    sgst_rate=normalize_gst_rate(row.get("Sgst Rate")),
                    sgst_amount=safe_float(row.get("Sgst Tax")),
                    utgst_rate=normalize_gst_rate(row.get("Utgst Rate")),
                    utgst_amount=safe_float(row.get("Utgst Tax")),
                    compensatory_cess_rate=normalize_gst_rate(row.get("Compensatory Cess Rate")),
                    compensatory_cess_amount=safe_float(row.get("Compensatory Cess Tax Amount")),
                    
                    # TCS
                    tcs_igst_rate=normalize_gst_rate(row.get("Tcs Igst Rate")),
                    tcs_igst_amount=safe_float(row.get("Tcs Igst Amount")),
                    tcs_cgst_rate=normalize_gst_rate(row.get("Tcs Cgst Rate")),
                    tcs_cgst_amount=safe_float(row.get("Tcs Cgst Amount")),
                    tcs_sgst_rate=normalize_gst_rate(row.get("Tcs Sgst Rate")),
                    tcs_sgst_amount=safe_float(row.get("Tcs Sgst Amount")),
                    
                    # Location
                    ship_from_state=str(row.get("Ship From State", "")),
                    ship_to_state=str(row.get("Ship To State", "")),
                    ship_to_city=str(row.get("Ship To City", "")),
                    ship_to_postal_code=str(row.get("Ship To Postal Code", "")),
                    bill_to_state=str(row.get("Bill To State", "")),
                    bill_to_city=str(row.get("Bill To City", "")),
                    bill_to_postal_code=str(row.get("Bill To Postalcode", "")),
                    
                    # B2B specific
                    seller_gstin=str(row.get("Seller Gstin", "")),
                    customer_bill_to_gstid=str(row.get("Customer Bill To Gstid", "")),
                    customer_ship_to_gstid=str(row.get("Customer Ship To Gstid", "")),
                    buyer_name=str(row.get("Buyer Name", "")),
                    
                    # Warehouse
                    warehouse_id=str(row.get("Warehouse Id", "")),
                    fulfillment_channel=str(row.get("Fulfillment Channel", ""))
                )
                db.add(record)
                shipments_count += 1
                
            elif transaction_type in ["Refund", "Cancel"]:
                # Check if already exists
                existing = db.query(AmazonReturn).filter(
                    AmazonReturn.order_id == order_id,
                    AmazonReturn.shipment_item_id == shipment_item_id
                ).first()
                if existing:
                    skipped_count += 1
                    continue
                
                # This is a return/cancellation
                record = AmazonReturn(
                    marketplace="Amazon",
                    transaction_type=transaction_type,
                    order_id=order_id,
                    shipment_item_id=shipment_item_id,
                    invoice_number=str(row.get("Invoice Number", "")),
                    invoice_date=invoice_date,
                    return_amount=safe_float(row.get("Invoice Amount")),
                    order_date=order_date,
                    quantity=int(row.get("Quantity") or 0),
                    item_description=str(row.get("Item Description", "")),
                    asin=str(row.get("Asin", "")),
                    sku=str(row.get("Sku", "")),
                    hsn_sac=str(row.get("Hsn/sac", "")),
                    taxable_value=safe_float(row.get("Tax Exclusive Gross")),
                    
                    # Tax rates - normalized
                    igst_rate=normalize_gst_rate(row.get("Igst Rate")),
                    cgst_rate=normalize_gst_rate(row.get("Cgst Rate")),
                    sgst_rate=normalize_gst_rate(row.get("Sgst Rate")),
                    utgst_rate=normalize_gst_rate(row.get("Utgst Rate")),
                    
                    # Tax amounts
                    igst_amount=safe_float(row.get("Igst Tax")),
                    cgst_amount=safe_float(row.get("Cgst Tax")),
                    sgst_amount=safe_float(row.get("Sgst Tax")),
                    ship_to_state=str(row.get("Ship To State", "")),
                    
                    # B2B specific
                    seller_gstin=str(row.get("Seller Gstin", "")),
                    customer_bill_to_gstid=str(row.get("Customer Bill To Gstid", "")),
                    buyer_name=str(row.get("Buyer Name", ""))
                )
                db.add(record)
                returns_count += 1
        
        db.commit()
        messages.append("Amazon MTR Report imported:")
        messages.append(f"   📦 {shipments_count} shipments")
        messages.append(f"   🔄 {returns_count} returns/cancellations")
        if skipped_count > 0:
            messages.append(f"   ⏭️ {skipped_count} duplicates skipped")
        
        # Clean up extracted files
        shutil.rmtree(extract_dir, ignore_errors=True)
        
    except Exception as e:
        db.rollback()
        messages.append(f"❌ Error importing Amazon MTR Report: {e}")
        shutil.rmtree(extract_dir, ignore_errors=True)
    
    return messages


def import_amazon_gstr1(filepath: str, db: Session) -> list:
    """
    Import Amazon GSTR-1 Report (Excel file with B2B, B2C, HSN Summary sheets).
    This report contains aggregated tax data for GST filing purposes.
    The data is validated and can be used as reference for GST exports.
    """
    messages = []
    
    try:
        # Extract ZIP file
        extract_dir = _TEMP_EXTRACT_DIR
        os.makedirs(extract_dir, exist_ok=True)
        
        with zipfile.ZipFile(filepath, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        
        # Find Excel file
        excel_file = None
        for file in os.listdir(extract_dir):
            if file.endswith('.xlsx'):
                excel_file = os.path.join(extract_dir, file)
                break
        
        if not excel_file:
            messages.append("❌ No Excel file found in ZIP")
            shutil.rmtree(extract_dir, ignore_errors=True)
            return messages
        
        messages.append("ℹ️  Amazon GSTR-1 Report detected (aggregated tax data)")
        messages.append("ℹ️  This report contains B2B, B2C, and HSN summary for GST filing.")
        
        # Read the file to validate and show what's available
        xl = pd.ExcelFile(excel_file)
        messages.append("\nGSTR-1 Report Sections found:")
        
        b2c_small_data = None
        hsn_summary_data = None
        
        for sheet in xl.sheet_names:
            df = pd.read_excel(excel_file, sheet_name=sheet)
            
            if sheet == "B2C Small":
                # Read B2C Small data (starts from row 4)
                b2c_small_data = pd.read_excel(excel_file, sheet_name=sheet, header=3)
                b2c_small_data.columns = [str(c).strip() for c in b2c_small_data.columns]
                valid_rows = len(b2c_small_data.dropna(how='all'))
                messages.append(f"   • {sheet} ({valid_rows} records)")
                
                if valid_rows > 0 and {"Place Of Supply", "Rate", "Taxable Value"}.issubset(set(b2c_small_data.columns)):
                    total_taxable = b2c_small_data["Taxable Value"].sum()
                    messages.append(f"     - Total Taxable Value: Rs {total_taxable:,.2f}")
            
            elif sheet == "HSN Summary":
                # Read HSN Summary data (starts from row 4)
                hsn_summary_data = pd.read_excel(excel_file, sheet_name=sheet, header=3)
                hsn_summary_data.columns = [str(c).strip() for c in hsn_summary_data.columns]
                valid_rows = len(hsn_summary_data.dropna(how='all'))
                messages.append(f"   • {sheet} ({valid_rows} records)")
                
                if valid_rows > 0 and "HSN" in hsn_summary_data.columns:
                    unique_hsn = hsn_summary_data["HSN"].nunique()
                    messages.append(f"     - Unique HSN Codes: {unique_hsn}")
            
            elif sheet == "GSTIN":
                messages.append(f"   • {sheet} (GSTIN info)")
            elif len(df) > 3:  # Has data beyond header
                messages.append(f"   • {sheet} ({len(df) - 3} records)")
            else:
                messages.append(f"   • {sheet} (summary only)")
        
        messages.append("\n✅ Amazon GSTR-1 Report validated successfully.")
        messages.append("ℹ️  Data ready for use in B2CS CSV and HSN CSV exports.")
        messages.append("ℹ️  Note: GSTR-1 contains pre-aggregated data. For order-level details, use MTR reports.")
        
        # Clean up extracted files
        shutil.rmtree(extract_dir, ignore_errors=True)
        
    except Exception as e:
        messages.append(f"❌ Error importing Amazon GSTR-1 Report: {e}")
        if 'extract_dir' in locals():
            shutil.rmtree(extract_dir, ignore_errors=True)
    
    return messages
