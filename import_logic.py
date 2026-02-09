import os
import pandas as pd
import zipfile
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from models import MeeshoSale, MeeshoReturn, MeeshoOrder, MeeshoInventory, MeeshoPayment, MeeshoInvoice, MeeshoAdsCost, MeeshoReferralPayment, MeeshoCompensationRecovery
import shutil


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


def normalize_gst_rate(rate_value):
    """
    Normalize GST rate to percentage format (whole number).
    Converts 0.05 -> 5, 0.12 -> 12, 0.18 -> 18, 5 -> 5, etc.
    Also handles edge cases like 0.0 or None.
    """
    if rate_value is None or rate_value == 0:
        return 0.0
    
    rate = safe_float(rate_value)
    
    # If rate is between 0 and 1 (decimal format like 0.05, 0.12, 0.18), multiply by 100
    if 0 < rate < 1:
        rate = rate * 100
    
    # Return as 2-decimal float (e.g., 5.0, 12.0, 18.0)
    return round(rate, 2)


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


def validate_inventory_excel(filepath: str) -> tuple[bool, str]:
    """Validate that Excel contains Meesho inventory data."""
    if not filepath.lower().endswith(('.xlsx', '.xls')):
        return False, "❌ Wrong file type! Please select an Excel file (.xlsx or .xls)."
    
    try:
        df = pd.read_excel(filepath, nrows=1)
        required_cols = ['PRODUCT ID', 'CATALOG ID', 'CATALOG NAME', 'PRODUCT NAME', 'STOCK']
        
        df.columns = [str(c).strip().upper() for c in df.columns]
        missing = [col for col in required_cols if col not in df.columns]
        
        if missing:
            # Check if it's a different marketplace file
            if 'ORDER ID' in df.columns and 'FSN' in df.columns:
                return False, "❌ Wrong file! This appears to be a Flipkart Sales Report. Please use the Import Flipkart Sales button."
            if 'SUB ORDER NO' in df.columns:
                return False, "❌ Wrong file! This appears to be a Meesho Order file. Please use the Import Meesho Tax Invoice button."
            if 'INVOICE NO' in df.columns or 'INVOICE NUMBER' in df.columns:
                return False, "❌ Wrong file! This appears to be an Invoice file. Please use the Import Meesho GST Report button."
            
            return False, f"❌ Wrong file! Meesho Inventory Excel should have columns: {', '.join(required_cols)}\nMissing: {', '.join(missing)}"
        
        return True, "✅ Valid Meesho Inventory Excel"
    except Exception as e:
        return False, f"❌ Error reading Excel file: {str(e)}"


def validate_payments_zip(filepath: str) -> tuple[bool, str]:
    """Validate that ZIP contains Meesho payment files."""
    if not filepath.lower().endswith('.zip'):
        return False, "❌ Wrong file type! Please select a ZIP file for Meesho Payments."
    
    try:
        with zipfile.ZipFile(filepath, 'r') as zip_ref:
            files = [f.lower() for f in zip_ref.namelist()]
            
            # Check for payment-related Excel files
            has_payment_excel = any(f.endswith('.xlsx') or f.endswith('.xls') for f in files)
            
            if not has_payment_excel:
                return False, "❌ Wrong file! Meesho Payments ZIP should contain Excel files with payment data."
            
            # Check if it's not an Amazon or Flipkart file
            if any('mtr' in f or 'amazon' in f for f in files):
                return False, "❌ Wrong file! This appears to be an Amazon ZIP. Please use the Amazon buttons instead."
            
            return True, "✅ Valid Meesho Payments ZIP"
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
                return True, f"✅ Valid Amazon GSTR1 ZIP (Excel format)"
            
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
    extract_dir = "extracted_temp"
    os.makedirs(extract_dir, exist_ok=True)

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_dir)


    sales_file = None
    returns_file = None
    orders_file = None

    for file in os.listdir(extract_dir):
        if "tcs_sales.xlsx" in file.lower():
            sales_file = os.path.join(extract_dir, file)
        elif "tcs_sales_return.xlsx" in file.lower():
            returns_file = os.path.join(extract_dir, file)
        elif file.lower().startswith("orders_") and file.lower().endswith(".csv"):
            orders_file = os.path.join(extract_dir, file)

    if sales_file:
        messages += import_sales_data(sales_file, db)
    if returns_file:
        messages += import_returns_data(returns_file, db)
    if orders_file:
        messages += import_orders_data(orders_file, db)
def import_orders_data(filepath: str, db: Session) -> list:
    import pandas as pd
    messages = []
    df = pd.read_csv(filepath)

    # Clean column names
    df.columns = [str(c).strip().replace("\ufeff", "") for c in df.columns]

    # Remove any rows with missing Sub Order No
    df = df[df["Sub Order No"].notna()]

    # Delete existing orders for this file's date range (optional: could use order_date min/max)
    db.query(MeeshoOrder).delete(synchronize_session=False)
    db.commit()
    messages.append(f"Existing orders data deleted before import from {os.path.basename(filepath)}")

    # Build product_name -> product_id mapping from MeeshoInventory
    product_mapping = {}
    inventories = db.query(MeeshoInventory).all()
    for inv in inventories:
        if inv.product_name:
            product_mapping[inv.product_name.lower().strip()] = inv.product_id

    for _, row in df.iterrows():
        product_name = row.get("Product Name", "").strip()
        # Lookup product_id from inventory mapping
        product_id = product_mapping.get(product_name.lower()) if product_name else None
        
        record = MeeshoOrder(
            reason_for_credit_entry=row.get("Reason for Credit Entry", ""),
            sub_order_no=row.get("Sub Order No", ""),
            order_date=parse_date(row.get("Order Date")),
            customer_state=row.get("Customer State", ""),
            product_name=product_name,
            product_id=product_id,  # Now populated from inventory
            sku=row.get("SKU", ""),
            size=row.get("Size", ""),
            quantity=int(row.get("Quantity") or 0),
            supplier_listed_price=safe_float(row.get("Supplier Listed Price (Incl. GST + Commission)")),
            supplier_discounted_price=safe_float(row.get("Supplier Discounted Price (Incl GST and Commision)")),
            packet_id=row.get("Packet Id", "")
        )
        db.add(record)

    try:
        db.commit()
        messages.append(f"Orders data imported from {os.path.basename(filepath)} with product_id mapping")
    except IntegrityError:
        db.rollback()
        messages.append(f"Duplicate skipped during orders import.")
    except Exception as e:
        db.rollback()
        messages.append(f"Error during orders import: {e}")

    return messages

    for file in os.listdir(extract_dir):
        os.remove(os.path.join(extract_dir, file))
    os.rmdir(extract_dir)

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
            gstin=row.get("gstin", ""),
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
        messages.append(f"Duplicate skipped during sales import.")
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

    fy = int(df["financial_year"].iloc[0])
    mn = int(df["month_number"].iloc[0])
    sid = int(df["supplier_id"].iloc[0])

    # Delete existing returns data for this financial year, month number and supplier ID
    db.query(MeeshoReturn).filter(
        MeeshoReturn.financial_year == fy,
        MeeshoReturn.month_number == mn,
        MeeshoReturn.supplier_id == sid
    ).delete(synchronize_session=False)
    db.commit()
    messages.append(f"Existing returns data deleted for FY {fy}, Month {mn}, Supplier {sid}")

    # Build product_name -> product_id mapping from MeeshoInventory
    product_mapping = {}
    inventories = db.query(MeeshoInventory).all()
    for inv in inventories:
        if inv.product_name:
            product_mapping[inv.product_name.lower().strip()] = inv.product_id

    for _, row in df.iterrows():
        # Try to get product_name from "Product Name" or "product_name" columns
        product_name = row.get("Product Name") or row.get("product_name", "")
        if isinstance(product_name, str):
            product_name = product_name.strip()
        # Lookup product_id from inventory mapping
        product_id = product_mapping.get(product_name.lower()) if product_name else None
        
        record = MeeshoReturn(
            identifier=row.get("identifier", ""),
            sup_name=row.get("sup_name", ""),
            gstin=row.get("gstin", ""),
            sub_order_num=row.get("sub_order_num", ""),
            order_date=parse_date(row.get("order_date")),
            product_name=product_name,  # Added
            product_id=product_id,  # Added with inventory mapping
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
        messages.append(f"Duplicate skipped during returns import.")
    except Exception as e:
        db.rollback()
        messages.append(f"Error during returns import: {e}")

    return messages


def import_inventory_data(filepath: str, db: Session, seller_gstin: str = None) -> list:
    """Import inventory data from Excel file with multi-seller support.
    
    Args:
        filepath: Path to inventory Excel file
        db: Database session
        seller_gstin: GSTIN of the seller (optional - if not provided, will try to detect)
    """
    from models import SellerMapping
    messages = []
    try:
        # Read Excel file - row 0 has headers, row 1 has descriptions, data starts at row 2
        df = pd.read_excel(filepath, skiprows=1)
        df.columns = [str(c).strip().upper().replace(" ", "_") for c in df.columns]
        
        # Try to determine seller GSTIN
        if not seller_gstin:
            # Try to extract supplier_id from filename
            # Supports multiple formats:
            # - {supplier_id}_inventory.xlsx
            # - Inventory-Update-File_2025-11-21T23-52-21_{supplier_id}
            # - Any filename ending with _{supplier_id} or containing supplier_id before extension
            import re
            filename = os.path.basename(filepath)
            
            # Try pattern 1: supplier_id at the end (before extension)
            # Example: Inventory-Update-File_2025-11-21T23-52-21_1258379.xlsx
            match = re.search(r'_(\d{6,})(?:\.\w+)?$', filename)
            
            # Try pattern 2: supplier_id followed by _inventory
            if not match:
                match = re.search(r'(\d{6,})_inventory', filename, re.IGNORECASE)
            
            if match:
                supplier_id = int(match.group(1))
                # Look up GSTIN from mapping
                mapping = db.query(SellerMapping).filter(SellerMapping.supplier_id == supplier_id).first()
                if mapping:
                    seller_gstin = mapping.gstin
                    messages.append(f"✅ Detected seller: Supplier {supplier_id} → GSTIN {seller_gstin}")
        
        if not seller_gstin:
            messages.append("⚠️ Warning: seller_gstin not specified. Import GST data first to create seller mapping, or provide GSTIN parameter.")
            messages.append("⚠️ Inventory will be imported without GSTIN tagging (may cause issues in multi-seller setup)")
        
        count_new = 0
        count_updated = 0
        count_skipped = 0
        
        for _, row in df.iterrows():
            # Skip empty rows or description rows
            if pd.isna(row.get("PRODUCT_NAME")) or str(row.get("SERIAL_NO")).lower() == "row identifier":
                continue
            
            product_id = str(row.get("PRODUCT_ID", ""))
            variation_id = str(row.get("VARIATION_ID", ""))
            
            # Check if this product already exists for this seller
            existing = db.query(MeeshoInventory).filter(
                MeeshoInventory.product_id == product_id,
                MeeshoInventory.variation_id == variation_id,
                MeeshoInventory.seller_gstin == seller_gstin
            ).first()
            
            if existing:
                # Update existing inventory
                existing.catalog_name = str(row.get("CATALOG_NAME", ""))
                existing.catalog_id = str(row.get("CATALOG_ID", ""))
                existing.product_name = str(row.get("PRODUCT_NAME", ""))
                existing.style_id = str(row.get("STYLE_ID", ""))
                existing.variation = str(row.get("VARIATION", ""))
                existing.current_stock = int(row.get("STOCK") or 0)
                existing.system_stock_count = int(row.get("SYSTEM_STOCK_COUNT") or 0)
                existing.your_stock_count = int(row.get("YOUR_STOCK_COUNT") or 0)
                existing.last_updated = datetime.now()
                count_updated += 1
            else:
                # Add new inventory record
                record = MeeshoInventory(
                    catalog_name=str(row.get("CATALOG_NAME", "")),
                    catalog_id=str(row.get("CATALOG_ID", "")),
                    product_name=str(row.get("PRODUCT_NAME", "")),
                    product_id=product_id,
                    style_id=str(row.get("STYLE_ID", "")),
                    variation_id=variation_id,
                    variation=str(row.get("VARIATION", "")),
                    current_stock=int(row.get("STOCK") or 0),
                    system_stock_count=int(row.get("SYSTEM_STOCK_COUNT") or 0),
                    your_stock_count=int(row.get("YOUR_STOCK_COUNT") or 0),
                    seller_gstin=seller_gstin,
                    last_updated=datetime.now()
                )
                db.add(record)
                count_new += 1
        
        db.commit()
        messages.append(f"✅ Inventory import complete: {count_new} new, {count_updated} updated")
    except Exception as e:
        db.rollback()
        messages.append(f"❌ Error importing inventory: {e}")
    
    return messages


def import_payments_data(zip_path: str, db: Session, seller_gstin: str = None) -> list:
    """Extract and import payment data from ZIP file (all sheets) with multi-seller support.
    
    Args:
        zip_path: Path to payment ZIP file
        db: Database session
        seller_gstin: GSTIN of the seller (optional - will try to detect from sub_order_no)
    """
    from models import SellerMapping
    messages = []
    
    # If seller_gstin not provided, try to detect from filename or sub_order data
    detected_gstin = seller_gstin
    
    # Try to extract supplier_id from filename if GSTIN not provided
    if not detected_gstin:
        import re
        filename = os.path.basename(zip_path)
        
        # Try pattern 1: supplier_id at the end (before extension)
        # Example: Payment-Report_2025-11-21T23-52-21_1258379.zip
        match = re.search(r'_(\d{6,})(?:\.\w+)?$', filename)
        
        # Try pattern 2: supplier_id followed by _payment
        if not match:
            match = re.search(r'(\d{6,})_payment', filename, re.IGNORECASE)
        
        if match:
            supplier_id = int(match.group(1))
            # Look up GSTIN from mapping
            mapping = db.query(SellerMapping).filter(SellerMapping.supplier_id == supplier_id).first()
            if mapping:
                detected_gstin = mapping.gstin
                messages.append(f"✅ Detected seller from filename: Supplier {supplier_id} → GSTIN {detected_gstin}")
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            # Find Excel file
            excel_files = [f for f in zip_ref.namelist() if f.endswith('.xlsx')]
            if not excel_files:
                return ["❌ No Excel file found in payment ZIP"]
            
            excel_file = excel_files[0]
            
            # Try to extract supplier_id from Excel filename inside ZIP if not detected yet
            if not detected_gstin:
                import re
                excel_filename = os.path.basename(excel_file)
                
                # Pattern: {supplier_id}_SP_ORDER_ADS_REFERRAL_PAYMENT_FILE...
                # Example: 1258379_SP_ORDER_ADS_REFERRAL_PAYMENT_FILE_PREVIOUS_PAYMENT_2025-10-01_2025-10-31.xlsx
                match = re.search(r'^(\d{6,})_', excel_filename)
                
                if match:
                    supplier_id = int(match.group(1))
                    # Look up GSTIN from mapping
                    mapping = db.query(SellerMapping).filter(SellerMapping.supplier_id == supplier_id).first()
                    if mapping:
                        detected_gstin = mapping.gstin
                        messages.append(f"✅ Detected seller from Excel filename: Supplier {supplier_id} → GSTIN {detected_gstin}")
            
            # ============ IMPORT ORDER PAYMENTS SHEET ============
            try:
                # Row 0: Category headers (Order Related Details, Payment Details, etc.) - SKIP
                # Row 1: Actual column names (Sub Order No, Order Date, etc.) - USE AS HEADER
                # Row 2: Placeholder/formula row (nan, 'A', 'B', etc.) - SKIP
                # Row 3+: Actual data rows - IMPORT
                df = pd.read_excel(zip_ref.open(excel_file), sheet_name="Order Payments", header=1, skiprows=[2])
                
                if df.shape[0] < 1:
                    messages.append("⚠️  No payment data found")
                else:
                    # Normalize column names
                    df.columns = [str(col).strip().lower().replace(" ", "_").replace("(", "").replace(")", "").replace(".", "").replace(",", "").replace("%", "percent").replace("&", "and") for col in df.columns]
                    
                    # Try to detect seller GSTIN from first sub_order_no if not provided
                    if not detected_gstin and not df.empty:
                        first_suborder = str(df["sub_order_no"].iloc[0])
                        # Look up GSTIN from MeeshoSale
                        sale = db.query(MeeshoSale).filter(MeeshoSale.sub_order_num == first_suborder).first()
                        if sale and sale.gstin:
                            detected_gstin = sale.gstin
                            messages.append(f"✅ Detected seller GSTIN from sub_order_no: {detected_gstin}")
                    
                    if not detected_gstin:
                        messages.append("⚠️ Warning: seller_gstin not detected. Import GST data first, or provide GSTIN parameter.")
                        messages.append("⚠️ Payment data will be imported without GSTIN tagging (may cause issues in multi-seller setup)")
                    
                    count_new = 0
                    count_updated = 0
                    
                    # Process actual data rows
                    for _, row in df.iterrows():
                        # Skip rows without sub order number
                        if pd.isna(row.get("sub_order_no")):
                            continue
                        
                        sub_order_no = str(row.get("sub_order_no", ""))
                        
                        # Check if this payment already exists
                        existing = db.query(MeeshoPayment).filter(
                            MeeshoPayment.sub_order_no == sub_order_no
                        ).first()
                        
                        payment_data = {
                            # Order Related Details (9 columns)
                            "sub_order_no": sub_order_no,
                            "order_date": parse_date(row.get("order_date")),
                            "dispatch_date": parse_date(row.get("dispatch_date")),
                            "product_name": str(row.get("product_name", "")) if not pd.isna(row.get("product_name")) else None,
                            "supplier_sku": str(row.get("supplier_sku", "")) if not pd.isna(row.get("supplier_sku")) else None,
                            "live_order_status": str(row.get("live_order_status", "")) if not pd.isna(row.get("live_order_status")) else None,
                            "product_gst_percent": safe_float(row.get("product_gst_percent")),
                            "listing_price_incl_taxes": safe_float(row.get("listing_price_incl_taxes")),
                            "quantity": int(row.get("quantity", 0)) if not pd.isna(row.get("quantity")) else 0,
                            
                            # Payment Details (3 columns)
                            "transaction_id": str(row.get("transaction_id", "")) if not pd.isna(row.get("transaction_id")) else None,
                            "payment_date": parse_date(row.get("payment_date")),
                            "final_settlement_amount": safe_float(row.get("final_settlement_amount")),
                            
                            # Revenue Details (7 columns)
                            "price_type": str(row.get("price_type", "")) if not pd.isna(row.get("price_type")) else None,
                            "total_sale_amount_incl_shipping_gst": safe_float(row.get("total_sale_amount_incl_shipping_and_gst")),
                            "total_sale_return_amount_incl_shipping_gst": safe_float(row.get("total_sale_return_amount_incl_shipping_and_gst")),
                            "fixed_fee_incl_gst": safe_float(row.get("fixed_fee_incl_gst")),
                            "warehousing_fee_inc_gst": safe_float(row.get("warehousing_fee_inc_gst")),
                            "return_premium_incl_gst": safe_float(row.get("return_premium_incl_gst")),
                            "return_premium_incl_gst_of_return": safe_float(row.get("return_premium_incl_gst_of_return")),
                            
                            # Deductions (9 columns)
                            "meesho_commission_percentage": safe_float(row.get("meesho_commission_percentage")),
                            "meesho_commission_incl_gst": safe_float(row.get("meesho_commission_incl_gst")),
                            "meesho_gold_platform_fee_incl_gst": safe_float(row.get("meesho_gold_platform_fee_incl_gst")),
                            "meesho_mall_platform_fee_incl_gst": safe_float(row.get("meesho_mall_platform_fee_incl_gst")),
                            "fixed_fee_deduction_incl_gst": safe_float(row.get("fixed_fee_incl_gst1")),  # Excel has duplicate "Fixed Fee" column
                            "warehousing_fee_deduction_incl_gst": safe_float(row.get("warehousing_fee_incl_gst")),
                            "return_shipping_charge_incl_gst": safe_float(row.get("return_shipping_charge_incl_gst")),
                            "gst_compensation_prp_shipping": safe_float(row.get("gst_compensation_prp_shipping")),
                            "shipping_charge_incl_gst": safe_float(row.get("shipping_charge_incl_gst")),
                            
                            # Other Charges (4 columns)
                            "other_support_service_charges_excl_gst": safe_float(row.get("other_support_service_charges_excl_gst")),
                            "waivers_excl_gst": safe_float(row.get("waivers_excl_gst")),
                            "net_other_support_service_charges_excl_gst": safe_float(row.get("net_other_support_service_charges_excl_gst")),
                            "gst_on_net_other_support_service_charges": safe_float(row.get("gst_on_net_other_support_service_charges")),
                            
                            # TCS & TDS (3 columns)
                            "tcs": safe_float(row.get("tcs")),
                            "tds_rate_percent": safe_float(row.get("tds_rate_percent")),
                            "tds": safe_float(row.get("tds")),
                            
                            # Recovery, Claims and Compensation Details (6 columns)
                            "compensation": safe_float(row.get("compensation")),
                            "claims": safe_float(row.get("claims")),
                            "recovery": safe_float(row.get("recovery")),
                            "compensation_reason": str(row.get("compensation_reason", "")) if not pd.isna(row.get("compensation_reason")) else None,
                            "claims_reason": str(row.get("claims_reason", "")) if not pd.isna(row.get("claims_reason")) else None,
                            "recovery_reason": str(row.get("recovery_reason", "")) if not pd.isna(row.get("recovery_reason")) else None,
                            
                            # Multi-seller support
                            "seller_gstin": detected_gstin
                        }
                        
                        if existing:
                            # Update existing payment
                            for key, value in payment_data.items():
                                setattr(existing, key, value)
                            count_updated += 1
                        else:
                            # Add new payment
                            record = MeeshoPayment(**payment_data)
                            db.add(record)
                            count_new += 1
                    
                    db.commit()
                    messages.append(f"✅ Order Payments imported: {count_new} new, {count_updated} updated")
            except Exception as e:
                db.rollback()
                messages.append(f"⚠️  Order Payments error: {str(e)[:50]}")
            
            # ============ IMPORT ADS COST SHEET ============
            try:
                # Ads Cost has single header row at row 1 (row 0 is "Ads Cost" title)
                df_ads = pd.read_excel(zip_ref.open(excel_file), sheet_name="Ads Cost", header=1)
                
                if df_ads.shape[0] >= 1:
                    # Normalize column names
                    df_ads.columns = [str(col).strip().lower().replace(" ", "_").replace("/", "_").replace(".", "") for col in df_ads.columns]
                    
                    count_ads_new = 0
                    count_ads_updated = 0
                    
                    # Process data rows (skip empty first row)
                    for _, row in df_ads.iterrows():
                        # Skip empty rows
                        if pd.isna(row.get("deduction_date")):
                            continue
                        
                        campaign_id = str(row.get("campaign_id", ""))
                        deduction_date = parse_date(row.get("deduction_date"))
                        
                        # Check if exists
                        existing = db.query(MeeshoAdsCost).filter(
                            MeeshoAdsCost.campaign_id == campaign_id,
                            MeeshoAdsCost.deduction_date == deduction_date,
                            MeeshoAdsCost.seller_gstin == detected_gstin
                        ).first()
                        
                        if existing:
                            existing.deduction_duration = str(row.get("deduction_duration", ""))
                            existing.ad_cost = safe_float(row.get("ad_cost"))
                            existing.credits_waivers_discounts = safe_float(row.get("credits___waivers___discounts"))
                            existing.ad_cost_incl_credits_waivers = safe_float(row.get("ad_cost_incl_credits_waivers_discounts"))
                            existing.gst = safe_float(row.get("gst"))
                            existing.total_ads_cost = safe_float(row.get("total_ads_cost"))
                            count_ads_updated += 1
                        else:
                            record = MeeshoAdsCost(
                                deduction_duration=str(row.get("deduction_duration", "")),
                                deduction_date=deduction_date,
                                campaign_id=campaign_id,
                                ad_cost=safe_float(row.get("ad_cost")),
                                credits_waivers_discounts=safe_float(row.get("credits___waivers___discounts")),
                                ad_cost_incl_credits_waivers=safe_float(row.get("ad_cost_incl_credits_waivers_discounts")),
                                gst=safe_float(row.get("gst")),
                                total_ads_cost=safe_float(row.get("total_ads_cost")),
                                seller_gstin=detected_gstin
                            )
                            db.add(record)
                            count_ads_new += 1
                    
                    db.commit()
                    messages.append(f"✅ Ads Cost imported: {count_ads_new} new, {count_ads_updated} updated")
                else:
                    messages.append("⚠️  Ads Cost sheet is empty")
            except Exception as e:
                db.rollback()
                messages.append(f"⚠️  Ads Cost error: {str(e)[:50]}")
            
            # ============ IMPORT REFERRAL PAYMENTS SHEET ============
            try:
                df_ref = pd.read_excel(zip_ref.open(excel_file), sheet_name="Referral Payments", header=None)
                
                if df_ref.shape[0] >= 1:
                    # Get headers from row 0
                    headers_ref = [str(df_ref.iloc[0, col_idx]).lower().replace(" ", "_") for col_idx in range(df_ref.shape[1])]
                    df_ref.columns = headers_ref
                    
                    count_ref_new = 0
                    count_ref_updated = 0
                    
                    # Skip header row (row 0)
                    for _, row in df_ref.iloc[1:].iterrows():
                        if pd.isna(row.get("reward_id")):
                            continue
                        
                        reward_id = str(row.get("reward_id", ""))
                        
                        # Check if exists
                        existing = db.query(MeeshoReferralPayment).filter(
                            MeeshoReferralPayment.reward_id == reward_id,
                            MeeshoReferralPayment.seller_gstin == detected_gstin
                        ).first()
                        
                        if existing:
                            existing.payment_date = parse_date(row.get("payment_date"))
                            existing.store_name = str(row.get("store_name", ""))
                            existing.reason = str(row.get("reason", ""))
                            existing.net_referral_amount = safe_float(row.get("net_referral_amount"))
                            existing.taxes_gst_tds = safe_float(row.get("taxes_(gst/tds)"))
                            count_ref_updated += 1
                        else:
                            record = MeeshoReferralPayment(
                                reward_id=reward_id,
                                payment_date=parse_date(row.get("payment_date")),
                                store_name=str(row.get("store_name", "")),
                                reason=str(row.get("reason", "")),
                                net_referral_amount=safe_float(row.get("net_referral_amount")),
                                taxes_gst_tds=safe_float(row.get("taxes_(gst/tds)")),
                                seller_gstin=detected_gstin
                            )
                            db.add(record)
                            count_ref_new += 1
                    
                    db.commit()
                    messages.append(f"✅ Referral Payments imported: {count_ref_new} new, {count_ref_updated} updated")
                else:
                    messages.append("⚠️  Referral Payments sheet is empty")
            except Exception as e:
                db.rollback()
                messages.append(f"⚠️  Referral Payments error: {str(e)[:50]}")
            
            # ============ IMPORT COMPENSATION AND RECOVERY SHEET ============
            try:
                df_comp = pd.read_excel(zip_ref.open(excel_file), sheet_name="Compensation and Recovery", header=None)
                
                if df_comp.shape[0] >= 1:
                    # Get headers from row 0
                    headers_comp = [str(df_comp.iloc[0, col_idx]).lower().replace(" ", "_") for col_idx in range(df_comp.shape[1])]
                    df_comp.columns = headers_comp
                    
                    count_comp_new = 0
                    count_comp_updated = 0
                    
                    # Skip header row (row 0)
                    for _, row in df_comp.iloc[1:].iterrows():
                        if pd.isna(row.get("date")):
                            continue
                        
                        comp_date = parse_date(row.get("date"))
                        program_name = str(row.get("program_name", ""))
                        reason = str(row.get("reason", ""))
                        
                        # Check if exists (using date + program_name + reason as unique key)
                        existing = db.query(MeeshoCompensationRecovery).filter(
                            MeeshoCompensationRecovery.date == comp_date,
                            MeeshoCompensationRecovery.program_name == program_name,
                            MeeshoCompensationRecovery.reason == reason,
                            MeeshoCompensationRecovery.seller_gstin == detected_gstin
                        ).first()
                        
                        if existing:
                            existing.amount_inc_gst = safe_float(row.get("amount_(inc_gst)_inr"))
                            count_comp_updated += 1
                        else:
                            record = MeeshoCompensationRecovery(
                                date=comp_date,
                                program_name=program_name,
                                reason=reason,
                                amount_inc_gst=safe_float(row.get("amount_(inc_gst)_inr")),
                                seller_gstin=detected_gstin
                            )
                            db.add(record)
                            count_comp_new += 1
                    
                    db.commit()
                    messages.append(f"✅ Compensation & Recovery imported: {count_comp_new} new, {count_comp_updated} updated")
                else:
                    messages.append("⚠️  Compensation & Recovery sheet is empty")
            except Exception as e:
                db.rollback()
                messages.append(f"⚠️  Compensation & Recovery error: {str(e)[:50]}")
    
    except Exception as e:
        db.rollback()
        messages.append(f"❌ Error processing payment ZIP: {e}")
    
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
                    
                    record = MeeshoInvoice(
                        invoice_type=str(row.get("Type", "")).strip(),
                        order_date=order_date,
                        suborder_no=suborder_no,
                        product_description=str(row.get("Product Description", "")).strip(),
                        hsn_code=str(row.get("HSN", "")).strip(),
                        invoice_no=invoice_no
                    )
                    db.add(record)
                    count += 1
                except Exception as row_err:
                    continue
            
            db.commit()
            messages.append(f"✅ Invoice data imported: {count} new invoices")
            if skipped > 0:
                messages.append(f"   ⏭️ {skipped} duplicates skipped")
    except Exception as e:
        db.rollback()
        messages.append(f"❌ Error importing invoices: {e}")
    
    return messages


# PDF import functionality removed - PDFs no longer needed
    
    return messages


def import_flipkart_sales(filepath: str, db: Session) -> list:
    """
    Import Flipkart Sales Report Excel file with Sales Report and Cash Back Report sheets.
    Separates sales (Event Type = 'Sale') and returns (Event Type = 'Return') into different tables.
    NEW: Populates seller_gstin field using saved GSTIN from GST report import.
    """
    from models import FlipkartOrder, FlipkartReturn
    messages = []
    
    # Try to load seller GSTIN from temp config (saved from GST report import)
    seller_gstin = None
    try:
        import json
        import os
        if os.path.exists('temp_flipkart_gstin.json'):
            with open('temp_flipkart_gstin.json', 'r') as f:
                temp_config = json.load(f)
                seller_gstin = temp_config.get('last_flipkart_gstin')
                if seller_gstin:
                    messages.append(f"✅ Using seller GSTIN from GST report: {seller_gstin}")
    except:
        pass
    
    if not seller_gstin:
        messages.append("⚠️  No seller GSTIN available. Import Flipkart GST Report first to capture GSTIN.")
        messages.append("ℹ️  Continuing import without GSTIN (can be updated later).")
    
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
        messages.append(f"✅ Flipkart Sales Report imported:")
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
                    except:
                        continue
            
            if not seller_gstin:
                messages.append("⚠️  No seller GSTIN found in GST report")
            
            messages.append("ℹ️  This report contains aggregated tax data for GST filing.")
            messages.append("ℹ️  For sales analytics, please import Flipkart Sales Report (.xlsx) instead.")
            messages.append("⚠️  GST Report import is not required for sales tracking.")
            
            # Read the file to show what's available
            messages.append(f"\n📋 GST Report Sections found:")
            for sheet in xl.sheet_names:
                if sheet != 'Help':
                    df = pd.read_excel(filepath, sheet_name=sheet)
                    messages.append(f"   • {sheet} ({len(df)} records)")
            
            messages.append("\n✅ GST Report validated. Use for tax filing reference.")
            
            # Store GSTIN for later use (if Sales Report is imported next)
            if seller_gstin:
                # Save to a temp config file for use in next import
                import json
                temp_config = {'last_flipkart_gstin': seller_gstin}
                with open('temp_flipkart_gstin.json', 'w') as f:
                    json.dump(temp_config, f)
                messages.append(f"📝 GSTIN saved for Sales Report import: {seller_gstin}")
            
            return messages
        
        # If it's a ZIP file, try to process as B2C report (old format)
        extract_dir = "extracted_temp"
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
                    marketplace="Flipkart",  # B2C reports are typically Flipkart
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
        messages.append(f"✅ Flipkart B2C Report imported:")
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
        extract_dir = "extracted_temp"
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
        messages.append(f"✅ Amazon MTR Report imported:")
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
        extract_dir = "extracted_temp"
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
        messages.append(f"\n📋 GSTR-1 Report Sections found:")
        
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
