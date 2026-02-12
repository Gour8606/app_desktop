"""
Application-wide constants and enumerations.
"""

# =============================================================================
# GSTR-1 THRESHOLDS & LIMITS
# =============================================================================

B2CL_INVOICE_THRESHOLD = 250000  # Rs 2.5 Lakhs - B2C Large invoice threshold

# =============================================================================
# TRANSACTION TYPES
# =============================================================================

class TransactionType:
    """Standard transaction type values across all marketplaces."""
    SHIPMENT = 'Shipment'
    REFUND = 'Refund'
    CANCEL = 'Cancel'
    ORDER = 'Order'
    RETURN = 'Return'


class NoteType:
    """Credit/Debit note types for GSTR-1."""
    CREDIT = 'C'  # Credit Note
    DEBIT = 'D'   # Debit Note


# =============================================================================
# STATE CODE MAPPING (Complete List)
# =============================================================================

STATE_CODE_MAPPING = {
    # Official GST State/UT Codes - Latest from GST returns
    "JAMMU AND KASHMIR": "01-Jammu and Kashmir",
    "HIMACHAL PRADESH": "02-Himachal Pradesh",
    "PUNJAB": "03-Punjab",
    "CHANDIGARH": "04-Chandigarh",
    "UTTARAKHAND": "05-Uttarakhand",
    "HARYANA": "06-Haryana",
    "DELHI": "07-Delhi",
    "RAJASTHAN": "08-Rajasthan",
    "UTTAR PRADESH": "09-Uttar Pradesh",
    "BIHAR": "10-Bihar",
    "SIKKIM": "11-Sikkim",
    "ARUNACHAL PRADESH": "12-Arunachal Pradesh",
    "NAGALAND": "13-Nagaland",
    "MANIPUR": "14-Manipur",
    "MIZORAM": "15-Mizoram",
    "TRIPURA": "16-Tripura",
    "MEGHALAYA": "17-Meghalaya",
    "ASSAM": "18-Assam",
    "WEST BENGAL": "19-West Bengal",
    "JHARKHAND": "20-Jharkhand",
    "ODISHA": "21-Odisha",
    "CHHATTISGARH": "22-Chhattisgarh",
    "MADHYA PRADESH": "23-Madhya Pradesh",
    "GUJARAT": "24-Gujarat",
    "DADRA AND NAGAR HAVELI AND DAMAN AND DIU": "26-Dadra and Nagar Haveli and Daman and Diu",
    "MAHARASHTRA": "27-Maharashtra",
    "ANDHRA PRADESH": "37-Andhra Pradesh",
    "KARNATAKA": "29-Karnataka",
    "GOA": "30-Goa",
    "LAKSHADWEEP": "31-Lakshadweep",
    "KERALA": "32-Kerala",
    "TAMIL NADU": "33-Tamil Nadu",
    "PUDUCHERRY": "34-Puducherry",
    "ANDAMAN AND NICOBAR ISLANDS": "35-Andaman and Nicobar Islands",
    "TELANGANA": "36-Telangana",
    "LADAKH": "38-Ladakh",
    "OTHER TERRITORY": "97-Other Territory",

    # Alternative spellings
    "ORISSA": "21-Odisha",
    "PONDICHERRY": "34-Puducherry",
    "LEH LADAKH": "38-Ladakh",
    "ANDAMAN & NICOBAR": "35-Andaman and Nicobar Islands",
    "DAMAN": "26-Dadra and Nagar Haveli and Daman and Diu",
    "DAMAN AND DIU": "26-Dadra and Nagar Haveli and Daman and Diu",
    "JAMMU & KASHMIR": "01-Jammu and Kashmir",
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def normalize_rate(rate_value):
    """
    Normalize GST rate to percentage format.
    Converts 0.05 -> 5.0, 0.12 -> 12.0, 0.18 -> 18.0, 5 -> 5.0, etc.
    """
    if rate_value is None or rate_value == 0:
        return 0.0
    try:
        rate = float(rate_value)
    except (ValueError, TypeError):
        return 0.0
    if 0 < rate < 1:
        rate = rate * 100
    return round(rate, 2)


def get_state_code(state_name: str) -> str:
    """
    Get the GSTR-1 formatted state code for a given state name.

    Args:
        state_name: State name (case-insensitive)

    Returns:
        Formatted state code like "29-Karnataka" or original state if not found
    """
    if not state_name:
        return ""

    state_upper = state_name.strip().upper()
    return STATE_CODE_MAPPING.get(state_upper, state_name)


def generate_note_number(invoice_number: str, note_type: str = NoteType.CREDIT) -> str:
    """
    Generate a note number from invoice number.

    Args:
        invoice_number: Original invoice number
        note_type: Type of note (CREDIT or DEBIT)

    Returns:
        Generated note number
    """
    prefix = "CN" if note_type == NoteType.CREDIT else "DN"
    return f"{prefix}-{invoice_number}"


def fy_month_to_date_range(financial_year: int, month_number: int):
    """
    Convert financial year + month number to a (month_start, month_end) date range.

    Uses end-year convention: FY 2026 = Apr 2025 to Mar 2026.
    - Months 1-3 (Jan-Mar): calendar year = financial_year
    - Months 4-12 (Apr-Dec): calendar year = financial_year - 1

    Args:
        financial_year: End-year FY (e.g. 2026 for Apr 2025 - Mar 2026)
        month_number: Month number (1-12)

    Returns:
        (month_start, month_end) as datetime objects
    """
    from datetime import datetime

    if month_number <= 3:
        year = financial_year
    else:
        year = financial_year - 1

    month_start = datetime(year, month_number, 1)
    if month_number == 12:
        month_end = datetime(year + 1, 1, 1)
    else:
        month_end = datetime(year, month_number + 1, 1)

    return month_start, month_end


def resolve_gstin(gstin_or_supplier_id, db):
    """
    Resolve a GSTIN string or legacy supplier ID to a GSTIN.

    Args:
        gstin_or_supplier_id: Either a 15-char GSTIN string or a supplier ID
        db: SQLAlchemy session

    Returns:
        GSTIN string

    Raises:
        ValueError: If GSTIN cannot be resolved
    """
    if isinstance(gstin_or_supplier_id, str) and len(gstin_or_supplier_id) == 15:
        return gstin_or_supplier_id

    # Import here to avoid circular imports
    from models import SellerMapping
    mapping = db.query(SellerMapping).filter(
        SellerMapping.supplier_id == int(gstin_or_supplier_id)
    ).first()
    if mapping:
        return mapping.gstin
    raise ValueError(f"No GSTIN found for supplier ID {gstin_or_supplier_id}")
