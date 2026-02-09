import pandas as pd
import csv
import re
import os
from sqlalchemy.orm import Session

def split_invoice_number(invoice_no):
    """Split invoice into prefix and trailing digits for series grouping."""
    digit_runs = re.findall(r'\d+', invoice_no)
    if not digit_runs:
        return invoice_no, 0
    last_digits = digit_runs[-1]
    pos = invoice_no.rfind(last_digits)
    prefix = invoice_no[:pos]
    number = int(last_digits)
    return prefix, number

def normalize_document_type(doc_type):
    """Normalize document type to GST-standard format for Table 13.
    
    Maps:
    - INVOICE -> Invoices for outward supply
    - CREDIT_* -> Credit Note
    - DEBIT_NOTE -> Debit Note
    """
    if not doc_type:
        return "Invoices for outward supply"
    
    doc_type_upper = str(doc_type).strip().upper()
    
    # Normalize all CREDIT types to "Credit Note"
    if doc_type_upper.startswith("CREDIT"):
        return "Credit Note"
    elif doc_type_upper == "INVOICE" or doc_type_upper == "INV":
        return "Invoices for outward supply"
    elif doc_type_upper == "DEBIT NOTE" or doc_type_upper == "DEBIT_NOTE":
        return "Debit Note"
    elif doc_type_upper == "DELIVERY CHALLAN" or doc_type_upper == "DELIVERY_CHALLAN":
        return "Delivery Challan for job work"
    
    # Return as-is if not a known type
    return doc_type

def append_meesho_docs(meesho_excel_path, csv_rows):
    """Read Meesho Tax_invoice_details.xlsx -> group by type+prefix -> append rows."""
    df = pd.read_excel(meesho_excel_path, sheet_name="Invoice_Info")
    df = df.dropna(subset=["Invoice No.", "Type"])
    df["Cancelled"] = 0  # adjust if real cancelled data available

    grouped = {}
    for _, row in df.iterrows():
        doc_type = row["Type"]
        invoice_no = str(row["Invoice No."])
        prefix, number = split_invoice_number(invoice_no)
        key = (doc_type, prefix)
        if key not in grouped:
            grouped[key] = {"prefix": prefix, "numbers": [], "cancelled": 0, "total": 0}
        grouped[key]["numbers"].append(number)
        grouped[key]["total"] += 1
        if row["Cancelled"] == 1:
            grouped[key]["cancelled"] += 1

    for (doc_type, prefix), data in sorted(grouped.items(), key=lambda x: (x[0][0], x[0][1])):
        min_num = min(data["numbers"])
        max_num = max(data["numbers"])
        sr_no_from = f"{prefix}{min_num}"
        sr_no_to = f"{prefix}{max_num}"
        csv_rows.append([doc_type, sr_no_from, sr_no_to, data["total"], data["cancelled"]])

def append_meesho_docs_from_db(db: Session, csv_rows, gstin=None):
    """Read Meesho invoice data from database -> group by type+prefix -> append rows.
    
    Args:
        db: Database session
        csv_rows: List to append rows to
        gstin: Optional GSTIN to filter by. If None, includes all invoices.
    """
    from models import MeeshoInvoice, MeeshoSale
    
    # Build query with optional GSTIN filter
    query = db.query(MeeshoInvoice)
    if gstin:
        # Join with MeeshoSale to filter by GSTIN
        query = query.join(MeeshoSale, MeeshoInvoice.suborder_no == MeeshoSale.sub_order_num).filter(MeeshoSale.gstin == gstin)
    
    invoices = query.all()
    if not invoices:
        return
    
    grouped = {}
    for invoice in invoices:
        doc_type_raw = invoice.invoice_type or ""
        doc_type = normalize_document_type(doc_type_raw)  # Normalize to GST standard
        invoice_no = invoice.invoice_no or ""
        if not doc_type or not invoice_no:
            continue
        
        prefix, number = split_invoice_number(invoice_no)
        key = (doc_type, prefix)
        if key not in grouped:
            grouped[key] = {"prefix": prefix, "numbers": [], "invoices": [], "cancelled": 0, "total": 0}
        grouped[key]["numbers"].append(number)
        grouped[key]["invoices"].append(invoice_no)  # Store actual invoice number
        grouped[key]["total"] += 1

    for (doc_type, prefix), data in sorted(grouped.items(), key=lambda x: (x[0][0], x[0][1])):
        if data["numbers"]:
            # Sort by numeric part to find first and last
            sorted_pairs = sorted(zip(data["numbers"], data["invoices"]))
            sr_no_from = sorted_pairs[0][1]   # First actual invoice number
            sr_no_to = sorted_pairs[-1][1]    # Last actual invoice number
            csv_rows.append([doc_type, sr_no_from, sr_no_to, data["total"], data["cancelled"]])

def append_flipkart_section13(flipkart_excel_path, csv_rows):
    try:
        df_fk = pd.read_excel(flipkart_excel_path, sheet_name="Section 13 in GSTR-1")
        # Normalise column names
        df_fk.columns = [" ".join(str(c).replace("\n", " ").replace("\r", " ").split()) for c in df_fk.columns]
        required_cols = ["Invoice Series From", "Invoice Series To", "Total Number of Invoices", "Cancelled if any"]
        for col in required_cols:
            if col not in df_fk.columns:
                raise ValueError(f"Missing expected column: {col} — actual columns: {df_fk.columns.tolist()}")

        for _, row in df_fk.iterrows():
            sr_from = str(row["Invoice Series From"]) if pd.notna(row["Invoice Series From"]) else ""
            sr_to = str(row["Invoice Series To"]) if pd.notna(row["Invoice Series To"]) else ""
            total = int(row["Total Number of Invoices"] or 0)
            cancelled = int(row["Cancelled if any"] or 0)
            csv_rows.append(["Invoice", sr_from, sr_to, total, cancelled])
    except Exception as e:
        print(f"⚠️ Could not append Flipkart Section 13: {e}")

def append_flipkart_docs_from_db(db: Session, csv_rows, gstin=None):
    """Read Flipkart invoice data from database -> group by invoice prefix -> append rows.
    
    Args:
        db: Database session
        csv_rows: List to append rows to
        gstin: Optional GSTIN to filter by. If None, includes all invoices.
    """
    from models import FlipkartOrder
    
    # Build query with optional GSTIN filter
    query = db.query(FlipkartOrder).filter(FlipkartOrder.buyer_invoice_id.isnot(None))
    if gstin:
        query = query.filter(FlipkartOrder.seller_gstin == gstin)
    
    orders = query.all()
    if not orders:
        return
    
    # Group invoices by prefix
    invoice_numbers = []
    for order in orders:
        invoice_no = order.buyer_invoice_id or ""
        if invoice_no and invoice_no.strip():
            prefix, number = split_invoice_number(invoice_no)
            invoice_numbers.append((prefix, number, invoice_no))
    
    if not invoice_numbers:
        return
    
    # Group by prefix
    grouped = {}
    for prefix, number, full_invoice in invoice_numbers:
        if prefix not in grouped:
            grouped[prefix] = {"numbers": [], "invoices": [], "total": 0, "cancelled": 0}
        grouped[prefix]["numbers"].append(number)
        grouped[prefix]["invoices"].append(full_invoice)  # Store actual invoice number
        grouped[prefix]["total"] += 1
    
    # Output invoice series for each prefix - use normalized doc type
    doc_type = normalize_document_type("Invoice")
    for prefix, data in sorted(grouped.items()):
        if data["numbers"]:
            # Sort by numeric part to find first and last
            sorted_pairs = sorted(zip(data["numbers"], data["invoices"]))
            sr_no_from = sorted_pairs[0][1]   # First actual invoice number
            sr_no_to = sorted_pairs[-1][1]    # Last actual invoice number
            csv_rows.append([doc_type, sr_no_from, sr_no_to, data["total"], data["cancelled"]])

def append_amazon_docs_from_db(db: Session, csv_rows, gstin=None):
    """Read Amazon invoice data from database -> group by order ID -> append rows.
    
    Args:
        db: Database session
        csv_rows: List to append rows to
        gstin: Optional GSTIN to filter by. If None, includes all invoices.
    """
    from models import AmazonOrder
    
    # Build query with optional GSTIN filter
    query = db.query(AmazonOrder).filter(
        AmazonOrder.transaction_type == 'Shipment',
        AmazonOrder.invoice_number.isnot(None)
    )
    if gstin:
        query = query.filter(AmazonOrder.seller_gstin == gstin)
    
    orders = query.all()
    
    if not orders:
        return
    
    # Collect all unique order IDs and their invoice numbers
    orderid_to_data = {}
    invoice_list = []  # Store (number, invoice) pairs for proper sorting
    
    for order in orders:
        oid = str(order.order_id or "").strip()
        inv = str(order.invoice_number or "").strip()
        
        if oid and oid.lower() != "nan":
            if oid not in orderid_to_data:
                orderid_to_data[oid] = {"shipped": True, "invoices": set()}
            
            if inv and inv.lower() != "nan" and inv.strip() != "":
                orderid_to_data[oid]["invoices"].add(inv)
                # Extract numeric part for sorting
                prefix, number = split_invoice_number(inv)
                invoice_list.append((number, inv))
    
    # Calculate document series
    unique_order_ids = sorted(orderid_to_data.keys())
    total_orders = len(unique_order_ids)
    cancelled_orders = 0  # All orders in database are shipped (transaction_type == 'Shipment')
    
    # Remove duplicates and sort by numeric part
    unique_invoices = {}
    for number, inv in invoice_list:
        unique_invoices[inv] = number
    sorted_invoices = sorted(unique_invoices.items(), key=lambda x: x[1])
    
    if sorted_invoices:
        sr_no_from = sorted_invoices[0][0]  # First invoice
        sr_no_to = sorted_invoices[-1][0]   # Last invoice
        doc_type = normalize_document_type("Invoice")
        csv_rows.append([doc_type, sr_no_from, sr_no_to, total_orders, cancelled_orders])

def append_amazon_document_series(amz_csv_path, csv_rows):
    df_amz = pd.read_csv(amz_csv_path)
    df_amz["Order_ID"] = df_amz["Order Id"].astype(str).str.strip()
    df_amz["Invoice_Number"] = df_amz["Invoice Number"].astype(str).str.strip()
    df_amz["Transaction_Type"] = df_amz["Transaction Type"].astype(str).str.strip().str.upper()

    # Remove blanks
    df_amz = df_amz[df_amz["Order_ID"].notna() & (df_amz["Order_ID"] != "")]

    orderid_to_data = {}
    for _, row in df_amz.iterrows():
        oid = row["Order_ID"]
        inv = row["Invoice_Number"]
        shipped = (row["Transaction_Type"] == "SHIPMENT")
        if oid not in orderid_to_data:
            orderid_to_data[oid] = {"shipped": shipped, "invoices": set()}
        else:
            if shipped:
                orderid_to_data[oid]["shipped"] = True
        if inv and inv.lower() != "nan" and inv.strip() != "":
            orderid_to_data[oid]["invoices"].add(inv)

    unique_order_ids = sorted(orderid_to_data.keys())
    total_orders = len(unique_order_ids)
    cancelled_orders = sum(1 for data in orderid_to_data.values() if not data["shipped"])
    all_invoices = sorted({inv for data in orderid_to_data.values() for inv in data["invoices"] if inv.strip() != ""})
    sr_no_from = all_invoices[0] if all_invoices else ""
    sr_no_to = all_invoices[-1] if all_invoices else ""

    csv_rows.append(["Invoice", sr_no_from, sr_no_to, total_orders, cancelled_orders])

def generate_docs_csv_from_all(meesho_excel_path, flipkart_excel_path, amazon_csv_path, output_csv="docs.csv"):
    """Generate the combined 'Documents Issued' CSV from 3 dynamic inputs."""
    if not (os.path.exists(meesho_excel_path) and os.path.exists(flipkart_excel_path) and os.path.exists(amazon_csv_path)):
        raise FileNotFoundError("One or more input files are missing.")

    csv_rows = []
    append_meesho_docs(meesho_excel_path, csv_rows)
    append_flipkart_section13(flipkart_excel_path, csv_rows)
    append_amazon_document_series(amazon_csv_path, csv_rows)

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Nature of Document", "Sr. No. From", "Sr. No. To", "Total Number", "Cancelled"])
        writer.writerows(csv_rows)

    print(f"✅ {output_csv} generated with {len(csv_rows)} rows (Meesho + Flipkart + Amazon).")
    return f"✅ Documents CSV written to {output_csv} with {len(csv_rows)} rows."

def generate_docs_issued_csv(financial_year, month_number, gstin_or_supplier_id, db: Session, output_csv="docs.csv"):
    """Generate Documents Issued CSV from database for GSTR-1 filing.
    
    Args:
        financial_year: Financial year
        month_number: Month number (1-12)
        gstin_or_supplier_id: GSTIN string or supplier ID integer
        db: Database session
        output_csv: Output file path
    
    Returns:
        Success message with file path
    """
    from models import MeeshoSale
    from logic import get_gstin_for_supplier
    
    # Get GSTIN
    if isinstance(gstin_or_supplier_id, str) and len(gstin_or_supplier_id) == 15:
        gstin = gstin_or_supplier_id
    else:
        gstin = get_gstin_for_supplier(gstin_or_supplier_id, db)
        if not gstin:
            raise ValueError(f"GSTIN not found for supplier ID {gstin_or_supplier_id}")
    
    csv_rows = []
    
    # 1. Append Meesho docs from DB
    append_meesho_docs_from_db(db, csv_rows, gstin)
    
    # 2. Append Flipkart docs from DB
    append_flipkart_docs_from_db(db, csv_rows, gstin)
    
    # 3. Append Amazon docs from DB
    append_amazon_docs_from_db(db, csv_rows, gstin)
    
    # 4. Aggregate rows by document type (combine multiple prefixes of same type)
    # This handles cases where CREDIT_NOTE, CREDIT_CONVERSION, CREDIT_DISCOUNT all become "Credit Note"
    aggregated_rows = {}
    for row in csv_rows:
        doc_type = row[0]
        sr_from = row[1]
        sr_to = row[2]
        total = row[3]
        cancelled = row[4]
        
        if doc_type not in aggregated_rows:
            aggregated_rows[doc_type] = {
                "series": [],
                "total": 0,
                "cancelled": 0
            }
        
        aggregated_rows[doc_type]["total"] += total
        aggregated_rows[doc_type]["cancelled"] += cancelled
        aggregated_rows[doc_type]["series"].append((sr_from, sr_to))
    
    # Write CSV with proper headers (GST Table 13 format)
    final_rows = []
    for doc_type in sorted(aggregated_rows.keys()):
        data = aggregated_rows[doc_type]
        # Use first series From and last series To
        sr_from = data["series"][0][0] if data["series"] else ""
        sr_to = data["series"][-1][1] if data["series"] else ""
        
        # Only include rows with valid Sr. No. From and Sr. No. To (not empty, not 0)
        if sr_from and sr_to and str(sr_from).strip() != "0" and str(sr_to).strip() != "0":
            final_rows.append([doc_type, sr_from, sr_to, data["total"], data["cancelled"]])
    
    if not final_rows:
        # No valid documents found
        return f"⚠️ Warning: No valid documents found to generate docs.csv. Created empty file with headers only."
    
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerow(["Nature of Document", "Sr. No. From", "Sr. No. To", "Total Number", "Cancelled"])
        writer.writerows(final_rows)
    
    return f"✅ Documents CSV written to {output_csv} with {len(final_rows)} aggregated document types (combined {len(csv_rows)} series) in GST standard format."
