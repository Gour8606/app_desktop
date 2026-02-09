"""
Application-wide constants and enumerations.

This module centralizes all magic numbers, hardcoded strings, and configuration
values used throughout the application. Using constants improves maintainability
and reduces the risk of typo-related bugs.
"""

from enum import Enum

# =============================================================================
# GSTR-1 THRESHOLDS & LIMITS
# =============================================================================

B2CL_INVOICE_THRESHOLD = 250000  # Rs 2.5 Lakhs - B2C Large invoice threshold
LOW_STOCK_THRESHOLD = 5  # Units - Alert when stock falls below this
OUT_OF_STOCK_THRESHOLD = 0  # Units - Product completely out of stock

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


class OrderStatus:
    """Standard order status values."""
    DELIVERED = 'Delivered'
    SHIPPED = 'Shipped'
    CANCELLED = 'Cancelled'
    RETURNED = 'Returned'
    PENDING = 'Pending'
    PROCESSING = 'Processing'


class InvoiceType:
    """GSTR-1 invoice type classifications."""
    REGULAR = 'Regular'
    REGULAR_B2B = 'Regular B2B'
    SEZ_WITH_PAYMENT = 'SEZ supplies with payment'
    SEZ_WITHOUT_PAYMENT = 'SEZ supplies without payment'
    DEEMED_EXPORT = 'Deemed Export'


class NoteType:
    """Credit/Debit note types for GSTR-1."""
    CREDIT = 'C'  # Credit Note
    DEBIT = 'D'   # Debit Note


class SupplyType:
    """Supply type for GSTR-1."""
    INTRA_STATE = 'Intra State'
    INTER_STATE = 'Inter State'


# =============================================================================
# DATABASE FIELD NAMES
# =============================================================================

class DBFields:
    """Standard database field names to avoid typos."""
    
    # Common Fields
    ID = 'id'
    ORDER_ID = 'order_id'
    ORDER_DATE = 'order_date'
    INVOICE_NUMBER = 'invoice_number'
    INVOICE_DATE = 'invoice_date'
    TRANSACTION_TYPE = 'transaction_type'
    
    # Customer/Business Fields
    CUSTOMER_GSTIN = 'customer_bill_to_gstid'
    CUSTOMER_SHIP_GSTIN = 'customer_ship_to_gstid'
    BUYER_NAME = 'buyer_name'
    SELLER_GSTIN = 'seller_gstin'
    
    # Address Fields
    BILL_TO_STATE = 'bill_to_state'
    BILL_TO_CITY = 'bill_to_city'
    BILL_TO_POSTAL = 'bill_to_postal_code'
    SHIP_TO_STATE = 'ship_to_state'
    SHIP_TO_CITY = 'ship_to_city'
    
    # Product Fields
    SKU = 'sku'
    PRODUCT_NAME = 'product_name'
    HSN_CODE = 'hsn_code'
    QUANTITY = 'quantity'
    
    # Financial Fields
    INVOICE_AMOUNT = 'invoice_amount'
    TAXABLE_VALUE = 'taxable_value'
    IGST_RATE = 'igst_rate'
    IGST_AMOUNT = 'igst_amount'
    CGST_RATE = 'cgst_rate'
    CGST_AMOUNT = 'cgst_amount'
    SGST_RATE = 'sgst_rate'
    SGST_AMOUNT = 'sgst_amount'
    
    # Supplier Fields
    SUPPLIER_ID = 'supplier_id'
    FINANCIAL_YEAR = 'financial_year'
    MONTH_NUMBER = 'month_number'


# =============================================================================
# GST & TAX RATES
# =============================================================================

class GSTRate:
    """Standard GST rates in India."""
    ZERO = 0.0
    FIVE = 5.0
    TWELVE = 12.0
    EIGHTEEN = 18.0
    TWENTY_EIGHT = 28.0


# =============================================================================
# FILE PATTERNS & EXTENSIONS
# =============================================================================

class FilePatterns:
    """File name patterns for data imports."""
    
    # Meesho Files
    MEESHO_ORDERS = 'Orders_*.csv'
    MEESHO_SALES = 'tcs_sales.xlsx'
    MEESHO_RETURNS = 'tcs_sales_return.xlsx'
    MEESHO_INVENTORY = 'Inventory-Update-File_*.xlsx'
    MEESHO_PAYMENTS = 'meesho_PREVIOUS_PAYMENT_*.zip'
    MEESHO_GST = 'gst_*_*.zip'
    MEESHO_INVOICE = 'TAX_INVOICE_*.zip'
    
    # Flipkart Files
    FLIPKART_SALES = 'sales_report.xlsx'
    FLIPKART_GST = 'gst_report.xlsx'
    
    # Amazon Files
    AMAZON_B2B = 'b2bReport_*.zip'
    AMAZON_B2C = 'b2cReport_*.zip'
    AMAZON_MTR = '*MTR*.csv'


class FileExtensions:
    """Supported file extensions."""
    CSV = '.csv'
    XLSX = '.xlsx'
    ZIP = '.zip'
    PDF = '.pdf'
    JSON = '.json'


# =============================================================================
# GSTR-1 OUTPUT FILE NAMES
# =============================================================================

class GSTR1Files:
    """Standard GSTR-1 CSV file names."""
    B2B = 'b2b,sez,de.csv'
    B2CL = 'b2cl.csv'
    B2CS = 'b2cs.csv'
    CDNR = 'cdnr.csv'
    CDNUR = 'cdnur.csv'
    HSN_B2B = 'hsn(b2b).csv'
    HSN_B2C = 'hsn(b2c).csv'
    HSN_COMBINED = 'hsn.csv'
    DOCS = 'docs.csv'
    EXEMP = 'exemp.csv'


# =============================================================================
# GSTR-1 CSV HEADERS
# =============================================================================

class B2BHeaders:
    """GSTR-1 Table 4A (B2B) CSV headers."""
    HEADERS = [
        'GSTIN of Supplier',
        'Receiver Name',
        'GSTIN/UIN of Recipient',
        'Invoice Number',
        'Invoice date',
        'Invoice Value',
        'Place Of Supply',
        'Reverse Charge',
        'Invoice Type',
        'E-Commerce GSTIN',
        'Rate',
        'Taxable Value',
        'Cess Amount'
    ]


class B2CLHeaders:
    """GSTR-1 Table 5 (B2CL) CSV headers."""
    HEADERS = [
        'Invoice Number',
        'Invoice date',
        'Invoice Value',
        'Place Of Supply',
        'Applicable % of Tax Rate',
        'Rate',
        'Taxable Value',
        'Cess Amount',
        'E-Commerce GSTIN'
    ]


class B2CSHeaders:
    """GSTR-1 Table 7 (B2CS) CSV headers."""
    HEADERS = [
        'Type',
        'Place Of Supply',
        'Applicable % of Tax Rate',
        'Rate',
        'Taxable Value',
        'Cess Amount',
        'E-Commerce GSTIN'
    ]


class CDNRHeaders:
    """GSTR-1 Table 9B (CDNR) CSV headers."""
    HEADERS = [
        'GSTIN/UIN of Recipient',
        'Receiver Name',
        'Note Number',
        'Note Date',
        'Note Type',
        'Place Of Supply',
        'Reverse Charge',
        'Note Supply Type',
        'Note Value',
        'Applicable % of Tax Rate',
        'Rate',
        'Taxable Value',
        'Cess Amount'
    ]


class HSNHeaders:
    """GSTR-1 Table 12 (HSN) CSV headers."""
    HEADERS = [
        'HSN',
        'Description',
        'UQC',
        'Total Quantity',
        'Total Value',
        'Taxable Value',
        'Integrated Tax Amount',
        'Central Tax Amount',
        'State/UT Tax Amount',
        'Cess Amount'
    ]


class DocsHeaders:
    """GSTR-1 Table 13 (Documents) CSV headers."""
    HEADERS = [
        'Nature of Document',
        'Sr. No. From',
        'Sr. No. To',
        'Total Number',
        'Cancelled'
    ]


# =============================================================================
# STATE CODE MAPPING (Complete List)
# =============================================================================

STATE_CODE_MAPPING = {
    # Official GST State/UT Codes - Latest from GST returns
    # Format: "STATE_NAME": "CODE-State Name"
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
    "CHHATTISGARH": "22-Chhattisgarh",
    "LEH LADAKH": "38-Ladakh",
    "ANDAMAN & NICOBAR": "35-Andaman and Nicobar Islands",
    "DAMAN": "26-Dadra and Nagar Haveli and Daman and Diu",
    "DAMAN AND DIU": "26-Dadra and Nagar Haveli and Daman and Diu",
    "JAMMU & KASHMIR": "01-Jammu and Kashmir",
}


# =============================================================================
# UI CONSTANTS
# =============================================================================

class UIConstants:
    """UI-related constants."""
    
    # Window Properties
    WINDOW_TITLE = "Meesho Sales Dashboard v2.0"
    MIN_WINDOW_WIDTH = 1200
    MIN_WINDOW_HEIGHT = 800
    
    # Button Sizes
    BUTTON_HEIGHT = 32
    BUTTON_MIN_WIDTH = 140
    
    # Icon/Emoji
    ICON_SUCCESS = "✅"
    ICON_ERROR = "❌"
    ICON_WARNING = "⚠️"
    ICON_INFO = "ℹ️"
    ICON_LOADING = "⏳"


# =============================================================================
# DATE & TIME CONSTANTS
# =============================================================================

class DateFormats:
    """Standard date format strings."""
    GST_DATE = "%d-%b-%y"  # 15-Sep-25
    ISO_DATE = "%Y-%m-%d"   # 2025-09-15
    DISPLAY_DATE = "%d %B %Y"  # 15 September 2025
    FILENAME_DATE = "%Y%m%d"   # 20250915


# =============================================================================
# VALIDATION RULES
# =============================================================================

class ValidationRules:
    """Data validation rules."""
    
    # GSTIN Format: 2 digits + 10 alphanumeric + 1 digit + 1 alpha + 1 alphanumeric
    GSTIN_PATTERN = r'^\d{2}[A-Z0-9]{10}[A-Z]\d[A-Z0-9]$'
    GSTIN_LENGTH = 15
    
    # HSN Code: 4, 6, or 8 digits
    HSN_MIN_LENGTH = 4
    HSN_MAX_LENGTH = 8
    
    # Invoice Number
    INVOICE_MAX_LENGTH = 16
    
    # Financial Year Range
    MIN_FINANCIAL_YEAR = 2020
    MAX_FINANCIAL_YEAR = 2030
    
    # Month Range
    MIN_MONTH = 1
    MAX_MONTH = 12


# =============================================================================
# ERROR MESSAGES
# =============================================================================

class ErrorMessages:
    """Standard error messages."""
    
    NO_DATA = "No data available for the selected period"
    IMPORT_FAILED = "Failed to import data. Please check file format"
    EXPORT_FAILED = "Failed to export file. Please check permissions"
    INVALID_DATE = "Invalid date range selected"
    INVALID_GSTIN = "Invalid GSTIN format"
    FILE_NOT_FOUND = "File not found. Please select a valid file"
    DATABASE_ERROR = "Database error occurred"
    PERMISSION_DENIED = "Permission denied. Check file/folder permissions"


# =============================================================================
# SUCCESS MESSAGES
# =============================================================================

class SuccessMessages:
    """Standard success messages."""
    
    IMPORT_SUCCESS = "✅ Data imported successfully"
    EXPORT_SUCCESS = "✅ File exported successfully"
    SAVE_SUCCESS = "✅ Configuration saved"
    
    # GST Exports
    B2B_EXPORT = "✅ B2B CSV generated successfully"
    B2CL_EXPORT = "✅ B2CL CSV generated successfully"
    B2CS_EXPORT = "✅ B2CS CSV generated successfully"
    CDNR_EXPORT = "✅ CDNR CSV generated successfully"
    HSN_EXPORT = "✅ HSN CSV generated successfully"
    DOCS_EXPORT = "✅ Documents CSV generated successfully"


# =============================================================================
# CONFIGURATION
# =============================================================================

class Config:
    """Application configuration constants."""
    
    CONFIG_FILE = "config.json"
    DATABASE_FILE = "meesho_sales.db"
    
    # Default Folders
    DEFAULT_OUTPUT_FOLDER = "output"
    DEFAULT_DATA_FOLDER = "sample"
    
    # Import Batch Size
    BATCH_SIZE = 1000  # Records per batch insert
    
    # Performance
    MAX_RECORDS_DISPLAY = 10000  # Max records to display in table
    QUERY_TIMEOUT = 30  # seconds
    
    # GST Offline JSON
    OFFLINE_JSON_VERSION = "GST3.2.3"


# =============================================================================
# FIXED COSTS PER ORDER
# =============================================================================

class FixedCosts:
    """Fixed costs per order (hard-coded operational costs)."""
    
    # Packing charges per order
    PACKING_CHARGE_PER_ORDER = 5  # Rs. 5 per order
    
    # TODO: Add more fixed costs as needed
    # LABEL_COST = 2.0  # Rs. 2 per order
    # TAPE_COST = 1.0   # Rs. 1 per order
    # etc.
    
    @classmethod
    def get_total_fixed_cost_per_order(cls) -> float:
        """
        Get total fixed cost per order (sum of all fixed costs).
        
        Returns:
            Total fixed cost per order in Rs.
        """
        return cls.PACKING_CHARGE_PER_ORDER
        # Add more as needed:
        # return cls.PACKING_CHARGE_PER_ORDER + cls.LABEL_COST + cls.TAPE_COST


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
    
    Example:
        >>> get_state_code("karnataka")
        '29-Karnataka'
        >>> get_state_code("DELHI")
        '07-Delhi'
    """
    if not state_name:
        return ""
    
    state_upper = state_name.strip().upper()
    return STATE_CODE_MAPPING.get(state_upper, state_name)


def is_b2b_transaction(customer_gstin: str) -> bool:
    """
    Check if a transaction is B2B based on customer GSTIN.
    
    Args:
        customer_gstin: Customer GSTIN value
    
    Returns:
        True if B2B transaction, False otherwise
    
    Example:
        >>> is_b2b_transaction("29ABCDE1234F1Z5")
        True
        >>> is_b2b_transaction("")
        False
        >>> is_b2b_transaction(None)
        False
    """
    if not customer_gstin:
        return False
    
    gstin_str = str(customer_gstin).strip()
    return bool(gstin_str and gstin_str != '' and gstin_str.lower() != 'nan')


def format_amount(amount: float, decimals: int = 2) -> float:
    """
    Format amount to specified decimal places.
    
    Args:
        amount: Amount to format
        decimals: Number of decimal places (default: 2)
    
    Returns:
        Rounded amount
    
    Example:
        >>> format_amount(123.456)
        123.46
        >>> format_amount(100.001, 0)
        100.0
    """
    return round(amount if amount else 0, decimals)


def generate_note_number(invoice_number: str, note_type: str = NoteType.CREDIT) -> str:
    """
    Generate a note number from invoice number.
    
    Args:
        invoice_number: Original invoice number
        note_type: Type of note (CREDIT or DEBIT)
    
    Returns:
        Generated note number
    
    Example:
        >>> generate_note_number("INV-123", NoteType.CREDIT)
        'CN-INV-123'
        >>> generate_note_number("INV-456", NoteType.DEBIT)
        'DN-INV-456'
    """
    prefix = "CN" if note_type == NoteType.CREDIT else "DN"
    return f"{prefix}-{invoice_number}"
