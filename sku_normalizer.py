"""
SKU Normalizer - Intelligently groups similar SKUs into unified product identifiers

Purpose: Merge profit from products listed under multiple SKU variations
Example: BLACK-100/., BLACK_100, BLACK-100-1 → All become "BLACK 100"
"""

import re
from typing import Optional

def normalize_sku(sku: Optional[str], product_name: Optional[str] = None) -> str:
    """
    Normalize SKU to group similar products together.
    
    SKU-ONLY STRATEGY: Only look at the SKU, ignore product names.
    Product names have marketing text that can confuse the pattern.
    "BLACK-100" in SKU is BLACK 100, regardless of product description.
    
    Args:
        sku: Raw supplier SKU (e.g., "BLACK-100/.", "blue-50-19")
        product_name: IGNORED - kept for backward compatibility
        
    Returns:
        Normalized product identifier (e.g., "BLACK 100", "BLUE 50")
    """
    if not sku:
        return "UNKNOWN"
    
    # Use ONLY the SKU, ignore product name
    text = sku.strip()
    
    # Handle combo SKUs (multiple products in one)
    # Combos can use comma (,) or plus (+) as separator
    # e.g., "BLACK-100,BLUE-100" or "BLACK-25+BLUE-25"
    # Order doesn't matter: BLACK,BLUE = BLUE,BLACK (same combo)
    
    # Check for combo separators: comma OR plus
    if ',' in text or '+' in text:
        # Split by either comma or plus (normalize the separator)
        # Replace + with , first, then split by comma
        text_normalized = text.replace('+', ',')
        parts = [part.strip() for part in text_normalized.split(',')]
        
        # Recursively normalize each part
        normalized_parts = []
        for part in parts:
            if part:
                # Recursively call normalize_sku on each part (avoid infinite loop)
                normalized_part = normalize_sku(part, None)
                normalized_parts.append(normalized_part)
        
        # SORT the parts so order doesn't matter!
        # BLACK 100, BLUE 50 = BLUE 50, BLACK 100 (same combo)
        normalized_parts.sort()
        
        # Return combo format: "BLACK 100 + BLUE 50" (always sorted alphabetically)
        if normalized_parts:
            return " + ".join(normalized_parts)
        # Fallback if no parts
        return text.upper().strip()[:50]
    
    # Convert to uppercase for consistency
    text = text.upper()
    
    # SPECIAL CASE: N95 masks with pack sizes
    # White-N95-Pack-of-15 → WHITE N95 PACK OF 15
    # White-N95-Pack-of-25 → WHITE N95 PACK OF 25
    n95_pack_match = re.search(
        r'\b(BLACK|BLUE|WHITE|PINK|GREEN|GREY|GRAY|YELLOW|ORANGE|RED|PURPLE|BROWN)[-_\s]*N95[-_\s]*PACK[-_\s]*OF[-_\s]*(\d+)\b',
        text,
        re.IGNORECASE
    )
    
    if n95_pack_match:
        color = n95_pack_match.group(1).upper()
        pack_size = n95_pack_match.group(2)
        return f"{color} N95 PACK OF {pack_size}"
    
    # SKU-ONLY: Extract ALL color-quantity patterns from SKU ONLY
    # Pick the LARGEST number to handle cases like "BLACK-100-10"
    # We want BLACK 100, not BLACK 10!
    all_color_qty_matches = re.findall(
        r'\b(BLACK|BLUE|WHITE|PINK|GREEN|GREY|GRAY|YELLOW|ORANGE|RED|PURPLE|BROWN)\D*(\d+)\b',
        text
    )
    
    if all_color_qty_matches:
        # Pick the match with the LARGEST quantity number
        # e.g., "BLACK-10 BLACK 100" → Pick BLACK 100 (100 > 10)
        best_match = max(all_color_qty_matches, key=lambda x: int(x[1]))
        color = best_match[0]
        quantity = best_match[1]
        return f"{color} {quantity}"
    
    # Special case: Extract quantity-color pattern (e.g., "100PCS-BLACK")
    qty_color_match = re.search(
        r'\b(\d+)\D*(BLACK|BLUE|WHITE|PINK|GREEN|GREY|GRAY|YELLOW|ORANGE|RED|PURPLE|BROWN)\b',
        text
    )
    
    if qty_color_match:
        quantity = qty_color_match.group(1)
        color = qty_color_match.group(2)
        return f"{color} {quantity}"
    
    # If no color-quantity pattern, try to extract meaningful parts
    # Remove common filler words
    text = re.sub(r'\b(PLY|LAYER|PCS|PACK|UNIT|UNITS|DISPOSABLE|SURGICAL|MASK|MASKS|FACE|POLLUTION)\b', '', text)
    
    # Remove special characters (convert to spaces)
    text = re.sub(r'[_\-/:.,!\'\"]+', ' ', text)
    
    # Clean up extra spaces
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Normalize singular/plural variations (PAIR vs PAIRS)
    text = re.sub(r'\bPAIRS?\b', 'PAIR', text)
    
    # Remove meaningless trailing suffixes that create duplicate SKUs
    # Strategy: Identify product patterns and handle appropriately
    
    # Pattern 1: "PRODUCT NAME + OF + NUMBER" - KEEP the number
    # Examples: "NYLON GLOVES PAIR OF 5", "NYLON GLOVES PAIR OF 10"
    has_of_pattern = re.search(r'OF\s+\d+', text)
    
    # Pattern 2: "EARPLUG/EAR PLUG + NUMBER" - KEEP the number (it's quantity)
    is_earplug = re.search(r'(EARPLUG|EAR\s+PLUG)\s+\d+', text)
    
    # Pattern 3: Products where trailing numbers are SUFFIXESto remove
    # "HEAT PAD ELECTRIC 10", "MAGIC BOOK 010", "ICE BAG 02"
    suffix_patterns = ['HEAT PAD', 'HOT WATER BAG', 'ICE BAG', 'MAGIC BOOK', 'KITCHEN', 'WIRE BRUSH']
    has_suffix_pattern = any(pattern in text for pattern in suffix_patterns)
    
    # Step 1: Remove trailing special characters (;, \, `, =, —)
    text = re.sub(r'\s*[;\\`=—]+\s*$', '', text)
    
    # Step 2: Remove trailing 0-padded numbers (00, 01, 010, 02, 04)
    text = re.sub(r'\s+0+\d*$', '', text)
    
    # Step 3: Remove single trailing digit after long words (BRUSH1 → BRUSH)
    text = re.sub(r'([A-Z]{4,})\d{1}$', r'\1', text)
    
    # Step 4: Handle duplicate trailing numbers
    # "NYLON GLOVES PAIR OF 5 3" → "NYLON GLOVES PAIR OF 5"
    # "EAR PLUG 10 1" → "EAR PLUG 10"
    if has_of_pattern or is_earplug:
        # Has meaningful number - remove only DUPLICATE trailing number
        text = re.sub(r'(\d+)\s+\d{1,2}$', r'\1', text)
    elif has_suffix_pattern:
        # These products should NOT have trailing numbers - they're all suffixes
        text = re.sub(r'\s+\d+$', '', text)
    
    # Step 5: Normalize compound words with spaces
    # "EAR PLUG" → "EARPLUG" (both should be treated as same product)
    # This ensures "ear-plug-10" and "earplug-10" normalize to the same result
    text = re.sub(r'\bEAR\s+PLUG\b', 'EARPLUG', text)
    
    # If we extracted something meaningful, return it (limit length)
    if text and len(text) > 2:
        return text[:30].strip()
    
    # Fallback to original (cleaned)
    return (sku or product_name or "UNKNOWN").upper().strip()[:30]


def normalize_product_name(product_name: Optional[str], sku: Optional[str] = None) -> str:
    """
    Normalize product name for grouping similar products.
    
    SKU-ONLY STRATEGY: Use ONLY the SKU, ignore product descriptions.
    "BLACK-100" in SKU is BLACK 100 - product name is ignored.
    
    Args:
        product_name: IGNORED - kept for backward compatibility
        sku: SKU for normalization (PRIMARY SOURCE)
        
    Returns:
        Normalized product name based on SKU (e.g., "BLACK 100", "BLUE 50")
    """
    # Use ONLY the SKU - ignore product_name completely
    normalized = normalize_sku(sku, None)
    
    # If we got a clear color-quantity pattern, use it directly
    if re.match(r'^[A-Z]+ \d+$', normalized):
        return normalized
    
    # Otherwise, keep the normalized result but limit length
    return normalized[:50].strip()


def get_sku_mapping_report(db_session) -> dict:
    """
    Generate a report showing which raw SKUs map to which normalized products.
    
    Args:
        db_session: SQLAlchemy database session
        
    Returns:
        Dictionary with normalized products and their raw SKU variations
    """
    from models import MeeshoPayment
    
    # Get all unique product-SKU combinations
    products = db_session.query(
        MeeshoPayment.product_name, 
        MeeshoPayment.supplier_sku
    ).distinct().all()
    
    # Build mapping
    mapping = {}
    
    for product_name, sku in products:
        normalized = normalize_product_name(product_name, sku)
        
        if normalized not in mapping:
            mapping[normalized] = {
                'raw_skus': set(),
                'raw_product_names': set()
            }
        
        if sku:
            mapping[normalized]['raw_skus'].add(sku)
        if product_name:
            mapping[normalized]['raw_product_names'].add(product_name)
    
    # Convert sets to sorted lists for display
    for normalized, data in mapping.items():
        data['raw_skus'] = sorted(list(data['raw_skus']))
        data['raw_product_names'] = sorted(list(data['raw_product_names']))
        data['sku_count'] = len(data['raw_skus'])
        data['name_count'] = len(data['raw_product_names'])
    
    # Sort by number of variations (most variations first)
    sorted_mapping = dict(sorted(
        mapping.items(), 
        key=lambda x: x[1]['sku_count'], 
        reverse=True
    ))
    
    return sorted_mapping


if __name__ == "__main__":
    # Test the normalizer
    test_cases = [
        ("BLACK-100/.", None, "BLACK 100"),
        ("BLACK_100", None, "BLACK 100"),
        ("BLACK-100-1", None, "BLACK 100"),
        ("blue-100-6", None, "BLUE 100"),
        ("blue_100!", None, "BLUE 100"),
        ("black-50,pink-50,white-50", None, "BLACK 50"),
        ("ear-plug-10-/", "Disposable Ear Plugs", "EAR 10"),
        (None, "3PLY BLACK 100", "BLACK 100"),
        (None, "Disposable Ear Plugs Reducing", "DISPOSABLE EAR PLUGS REDUCING"),
    ]
    
    print("=" * 80)
    print("SKU NORMALIZER TEST CASES")
    print("=" * 80)
    
    for sku, product_name, expected in test_cases:
        result = normalize_product_name(product_name, sku)
        status = "✓" if result == expected else "✗"
        print(f"\n{status} SKU: {sku}")
        print(f"  Product Name: {product_name}")
        print(f"  Expected: {expected}")
        print(f"  Got:      {result}")
