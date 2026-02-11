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
