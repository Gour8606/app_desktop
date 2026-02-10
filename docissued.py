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

def append_meesho_docs_from_db(db: Session, csv_rows, gstin: str):
    """Read Meesho invoice data from database -> group by type+prefix -> append rows.

    Args:
        db: Database session
        csv_rows: List to append rows to
        gstin: GSTIN to filter by (required for data isolation).
    """
    from models import MeeshoInvoice, MeeshoSale

    if not gstin or not gstin.strip():
        raise ValueError("gstin parameter is required for data isolation")

    # Join with MeeshoSale to filter by GSTIN
    query = db.query(MeeshoInvoice).join(
        MeeshoSale, MeeshoInvoice.suborder_no == MeeshoSale.sub_order_num
    ).filter(MeeshoSale.gstin == gstin)
    
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

def append_flipkart_docs_from_db(db: Session, csv_rows, gstin: str):
    """Read Flipkart SALES invoice data from database -> group by invoice prefix -> append rows.

    Args:
        db: Database session
        csv_rows: List to append rows to
        gstin: GSTIN to filter by (required for data isolation).
    """
    from models import FlipkartOrder

    if not gstin or not gstin.strip():
        raise ValueError("gstin parameter is required for data isolation")

    # Filter for SALES ONLY (event_type='Sale'), exclude returns which are tracked separately
    query = db.query(FlipkartOrder).filter(
        FlipkartOrder.buyer_invoice_id.isnot(None),
        FlipkartOrder.seller_gstin == gstin,
        FlipkartOrder.event_type == 'Sale'  # Only sales invoices, not returns
    )
    
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

def append_flipkart_return_docs_from_db(db: Session, csv_rows, gstin: str):
    """Read Flipkart RETURN invoice data from database -> group by invoice prefix -> append rows.
    
    Returns are tracked as Credit Notes in GSTR-1 Table 13.

    Args:
        db: Database session
        csv_rows: List to append rows to
        gstin: GSTIN to filter by (required for data isolation).
    """
    from models import FlipkartReturn

    if not gstin or not gstin.strip():
        raise ValueError("gstin parameter is required for data isolation")

    # Query return invoices (credit notes)
    query = db.query(FlipkartReturn).filter(
        FlipkartReturn.buyer_invoice_id.isnot(None),
        FlipkartReturn.seller_gstin == gstin
    )
    
    returns = query.all()
    if not returns:
        return
    
    # Group return invoice numbers by prefix
    invoice_numbers = []
    for ret in returns:
        invoice_no = ret.buyer_invoice_id or ""
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
        grouped[prefix]["invoices"].append(full_invoice)
        grouped[prefix]["total"] += 1
    
    # Output return/credit note series
    doc_type = normalize_document_type("Credit Note")  # Returns are credit notes
    for prefix, data in sorted(grouped.items()):
        if data["numbers"]:
            sorted_pairs = sorted(zip(data["numbers"], data["invoices"]))
            sr_no_from = sorted_pairs[0][1]
            sr_no_to = sorted_pairs[-1][1]
            csv_rows.append([doc_type, sr_no_from, sr_no_to, data["total"], data["cancelled"]])

def append_amazon_docs_from_db(db: Session, csv_rows, gstin: str):
    """Read Amazon invoice data from database -> group by order ID -> append rows.

    Args:
        db: Database session
        csv_rows: List to append rows to
        gstin: GSTIN to filter by (required for data isolation).
    """
    from models import AmazonOrder

    if not gstin or not gstin.strip():
        raise ValueError("gstin parameter is required for data isolation")

    query = db.query(AmazonOrder).filter(
        AmazonOrder.transaction_type == 'Shipment',
        AmazonOrder.invoice_number.isnot(None),
        AmazonOrder.seller_gstin == gstin
    )
    
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
    
    # 2. Append Flipkart sales docs from DB
    append_flipkart_docs_from_db(db, csv_rows, gstin)
    
    # 3. Append Flipkart return docs (credit notes) from DB
    append_flipkart_return_docs_from_db(db, csv_rows, gstin)
    
    # 4. Append Amazon docs from DB
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
