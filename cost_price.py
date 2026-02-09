"""
Product Cost Price Management

Simple CSV-based cost price lookup for products.
Cost prices are stored per SKU and normalized for analysis.

IMPORTANT: The CSV can use EITHER format:
1. Raw SKUs (BLACK-100, BLACK_100, etc.) - System auto-normalizes
2. Normalized SKUs (BLACK 100) - Recommended, avoids confusion

Use generate_normalized_sku_list.py to get a list of normalized SKUs
from your actual data, so you only enter each product ONCE!
"""

import csv
import os
from typing import Dict, Optional
from sku_normalizer import normalize_product_name

# Global cache for cost prices
_cost_price_cache: Optional[Dict[str, float]] = None

def load_cost_prices(csv_path: str = "product_cost_prices.csv") -> Dict[str, float]:
    """
    Load cost prices from CSV file.
    
    CSV Format (use EITHER raw or normalized SKUs):
        sku,cost_price
        BLACK-100,50.0        <- Raw SKU (system auto-normalizes)
        BLUE 50,30.0          <- Normalized SKU (recommended)
    
    NOTE: System automatically normalizes all SKUs, so:
          BLACK-100, BLACK_100, BLACK-100/. all map to same cost
    
    TIP: Run generate_normalized_sku_list.py to get normalized SKUs
         from your actual order data!
    
    Args:
        csv_path: Path to CSV file with cost prices
        
    Returns:
        Dictionary mapping normalized SKU to cost price
        
    Example:
        >>> cost_prices = load_cost_prices()
        >>> cost_prices['BLACK 100']  # Normalized format
        50.0
        >>> get_cost_price('BLACK-100', cost_prices)  # Any variation works
        50.0
    """
    cost_prices = {}
    
    if not os.path.exists(csv_path):
        print(f"[WARNING] Cost price file not found: {csv_path}")
        print(f"          Creating default file...")
        create_default_cost_price_file(csv_path)
        return cost_prices
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            
            for row in reader:
                # Support both 'sku' and 'normalized_sku' column names
                raw_sku = row.get('sku', '') or row.get('normalized_sku', '')
                raw_sku = raw_sku.strip()
                
                cost_price_str = row.get('cost_price', '0').strip()
                
                if not raw_sku or not cost_price_str:
                    continue
                
                try:
                    cost_price = float(cost_price_str)
                    
                    # Normalize the SKU (same logic as analysis)
                    normalized_sku = normalize_product_name(None, raw_sku)
                    
                    # Store normalized SKU → cost price
                    cost_prices[normalized_sku] = cost_price
                    
                except ValueError:
                    print(f"[WARNING] Invalid cost price for SKU '{raw_sku}': {cost_price_str}")
                    continue
        
        print(f"[SUCCESS] Loaded {len(cost_prices)} cost prices from {csv_path}")
        
    except Exception as e:
        print(f"[ERROR] Error loading cost prices: {e}")
    
    return cost_prices


def get_cost_price(sku: str, cost_prices: Optional[Dict[str, float]] = None) -> float:
    """
    Get cost price for a SKU (normalized).
    
    Args:
        sku: Raw SKU (will be normalized)
        cost_prices: Cost price dictionary (if None, loads from cache)
        
    Returns:
        Cost price, or 0.0 if not found
        
    Example:
        >>> get_cost_price('BLACK-100')
        50.0
        >>> get_cost_price('BLACK_100')  # Same normalized SKU
        50.0
        >>> get_cost_price('UNKNOWN-SKU')
        0.0
    """
    global _cost_price_cache
    
    # Load cache if needed
    if cost_prices is None:
        if _cost_price_cache is None:
            _cost_price_cache = load_cost_prices()
        cost_prices = _cost_price_cache
    
    # Normalize the SKU
    normalized_sku = normalize_product_name(None, sku)
    
    # Lookup cost price
    return cost_prices.get(normalized_sku, 0.0)


def reload_cost_prices() -> Dict[str, float]:
    """
    Force reload of cost prices from CSV file.
    
    Returns:
        Updated cost price dictionary
        
    Example:
        >>> cost_prices = reload_cost_prices()
        ✅ Loaded 50 cost prices from product_cost_prices.csv
    """
    global _cost_price_cache
    _cost_price_cache = load_cost_prices()
    return _cost_price_cache


def create_default_cost_price_file(csv_path: str = "product_cost_prices.csv"):
    """
    Create a default cost price CSV file with example data.
    
    Args:
        csv_path: Path where to create the file
    """
    default_data = [
        {'sku': 'BLACK-100', 'cost_price': '50.0'},
        {'sku': 'BLUE-50', 'cost_price': '30.0'},
        {'sku': 'RED-25', 'cost_price': '15.0'},
        {'sku': 'WHITE-50', 'cost_price': '30.0'},
        {'sku': 'BLACK-25+BLUE-25', 'cost_price': '40.0'},
    ]
    
    try:
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['sku', 'cost_price'])
            writer.writeheader()
            writer.writerows(default_data)
        
        print(f"[SUCCESS] Created default cost price file: {csv_path}")
        print(f"          Please edit this file and add your actual cost prices!")
        
    except Exception as e:
        print(f"[ERROR] Error creating default cost price file: {e}")


def get_all_cost_prices() -> Dict[str, float]:
    """
    Get all cost prices (loads from cache or file).
    
    Returns:
        Dictionary of all cost prices
    """
    global _cost_price_cache
    
    if _cost_price_cache is None:
        _cost_price_cache = load_cost_prices()
    
    return _cost_price_cache.copy()


def add_cost_price(sku: str, cost_price: float, csv_path: str = "product_cost_prices.csv") -> bool:
    """
    Add or update a cost price for a SKU.
    
    Args:
        sku: Raw SKU
        cost_price: Cost price value
        csv_path: Path to CSV file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Load existing cost prices
        existing_prices = {}
        if os.path.exists(csv_path):
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    existing_prices[row['sku']] = row['cost_price']
        
        # Add/update the new one
        existing_prices[sku] = str(cost_price)
        
        # Write back to file
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['sku', 'cost_price'])
            writer.writeheader()
            for sku_key, price in existing_prices.items():
                writer.writerow({'sku': sku_key, 'cost_price': price})
        
        # Reload cache
        reload_cost_prices()
        
        print(f"[SUCCESS] Updated cost price for {sku}: Rs. {cost_price}")
        return True
        
    except Exception as e:
        print(f"[ERROR] Error updating cost price: {e}")
        return False


if __name__ == "__main__":
    # Test the module
    print("=" * 80)
    print("COST PRICE MODULE TEST")
    print("=" * 80)
    
    # Load cost prices
    cost_prices = load_cost_prices()
    
    # Test lookups
    test_skus = [
        'BLACK-100',
        'BLACK_100',  # Should get same price (normalized)
        'BLACK-100/.',  # Should get same price (normalized)
        'BLUE-50',
        'BLACK-25+BLUE-25',  # Combo
        'UNKNOWN-SKU',  # Should return 0.0
    ]
    
    print("\nCost Price Lookups:")
    print("-" * 80)
    for sku in test_skus:
        normalized = normalize_product_name(None, sku)
        cost = get_cost_price(sku, cost_prices)
        print(f"SKU: {sku:20} → Normalized: {normalized:20} → Cost: Rs. {cost}")
    
    print("\n" + "=" * 80)
    print("Edit 'product_cost_prices.csv' to add/update your actual cost prices!")
    print("=" * 80)
