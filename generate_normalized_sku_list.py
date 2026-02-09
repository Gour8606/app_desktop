"""
Generate Normalized SKU List for Cost Price Entry

This utility extracts all unique SKUs from your orders, normalizes them,
and generates a CSV template with normalized SKU names.

This way you only enter cost prices ONCE per product, not for every variation!

Example:
    Raw SKUs in database: BLACK-100, BLACK_100, BLACK-100/., BLACK-100-1
    Normalized SKU: BLACK 100
    You enter cost price ONCE for "BLACK 100"
"""

import csv
from pathlib import Path
from collections import defaultdict
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import MeeshoPayment, FlipkartOrder, AmazonOrder
from sku_normalizer import normalize_product_name

# Database configuration
DB_PATH = "meesho_sales.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"


def generate_normalized_sku_list(output_csv="normalized_product_cost_prices.csv"):
    """
    Extract all SKUs from orders, normalize them, and create a mapping file.
    
    Output CSV format:
    normalized_sku,sample_variations,cost_price
    BLACK 100,"BLACK-100, BLACK_100, BLACK-100/.",0.00
    BLUE 50,"BLUE-50, BLUE_50",0.00
    BLACK 25 BLUE 25,"BLACK-25+BLUE-25, BLACK_25,BLUE_25",0.00
    """
    
    print("\n" + "="*70)
    print("GENERATING NORMALIZED SKU LIST FOR COST PRICE ENTRY")
    print("="*70)
    
    # Connect to database
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # Collect all raw SKUs from Meesho payments (this is what analytics.py uses)
        print("\n[1/4] Extracting SKUs from Meesho payments...")
        
        meesho_payments = session.query(MeeshoPayment).all()
        
        # Map: normalized_sku -> set of raw SKU variations
        sku_mapping = defaultdict(set)
        
        # Extract SKUs from payments
        for payment in meesho_payments:
            if payment.supplier_sku:
                raw_sku = payment.supplier_sku.strip()
                if raw_sku:
                    # Normalize using existing logic
                    normalized = normalize_product_name(payment.product_name, raw_sku)
                    sku_mapping[normalized].add(raw_sku)
        
        print(f"   Found {len(meesho_payments)} Meesho payment records")
        print(f"   Found {sum(len(v) for v in sku_mapping.values())} total SKU variations")
        print(f"   Normalized to {len(sku_mapping)} unique products")
        
        # Sort by normalized SKU
        print("\n[2/4] Sorting products...")
        sorted_skus = sorted(sku_mapping.items(), key=lambda x: x[0])
        
        # Generate CSV with normalized SKUs and their variations
        print(f"\n[3/4] Writing to {output_csv}...")
        with open(output_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['normalized_sku', 'sample_variations', 'cost_price'])
            
            for normalized_sku, variations in sorted_skus:
                # Show up to 5 sample variations
                sample_vars = sorted(list(variations))[:5]
                variations_str = ', '.join(sample_vars)
                if len(variations) > 5:
                    variations_str += f' (+{len(variations)-5} more)'
                
                writer.writerow([normalized_sku, variations_str, '0.00'])
        
        print(f"   Wrote {len(sorted_skus)} normalized products")
        
        # Create reverse mapping file for reference
        mapping_file = "sku_to_normalized_mapping.txt"
        print(f"\n[4/4] Creating reverse mapping file: {mapping_file}...")
        with open(mapping_file, 'w', encoding='utf-8') as f:
            f.write("SKU NORMALIZATION MAPPING\n")
            f.write("="*70 + "\n\n")
            f.write("This file shows how each raw SKU variation maps to a normalized SKU.\n")
            f.write("Use the NORMALIZED SKU when entering cost prices.\n\n")
            
            for normalized_sku, variations in sorted_skus:
                f.write(f"\nNORMALIZED: {normalized_sku}\n")
                f.write("-" * 50 + "\n")
                for var in sorted(variations):
                    f.write(f"  -> {var}\n")
        
        # Print summary
        print("\n" + "="*70)
        print("SUMMARY")
        print("="*70)
        total_variations = sum(len(v) for v in sku_mapping.values())
        print(f"Total SKU variations in database:    {total_variations}")
        print(f"Normalized to unique products:        {len(sku_mapping)}")
        if total_variations > 0:
            print(f"Reduction:                            {100*(1-len(sku_mapping)/total_variations):.1f}%")
        else:
            print("Reduction:                            N/A (no data)")
        
        print("\n" + "="*70)
        print("OUTPUT FILES")
        print("="*70)
        print(f"1. {output_csv}")
        print("   -> EDIT THIS FILE to enter cost prices")
        print("   -> Only contains NORMALIZED SKUs (no duplicates!)")
        print("   -> Format: normalized_sku,sample_variations,cost_price")
        print()
        print(f"2. {mapping_file}")
        print("   -> Reference file showing all SKU variations")
        print("   -> See how each raw SKU maps to normalized name")
        
        print("\n" + "="*70)
        print("NEXT STEPS")
        print("="*70)
        print(f"1. Open '{output_csv}' in Excel or text editor")
        print("2. Enter cost prices in the 'cost_price' column")
        print("3. Save the file")
        print("4. System will automatically map ALL variations to the cost you enter")
        print()
        print("Example:")
        print("  You enter: BLACK 100, 50.00")
        print("  System maps: BLACK-100 -> 50.00")
        print("               BLACK_100 -> 50.00")
        print("               BLACK-100/. -> 50.00")
        print("               BLACK-100-1 -> 50.00")
        print("  (All automatically!)")
        
        print("\n" + "="*70)
        print("[SUCCESS] Normalized SKU list generated successfully!")
        print("="*70 + "\n")
        
        return sorted_skus
        
    except Exception as e:
        print(f"\n[ERROR] Failed to generate SKU list: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        session.close()


def show_normalization_examples():
    """Show examples of how SKU normalization works"""
    print("\n" + "="*70)
    print("SKU NORMALIZATION EXAMPLES")
    print("="*70)
    
    examples = [
        ("BLACK-100", "BLACK 100"),
        ("BLACK_100", "BLACK 100"),
        ("BLACK-100/.", "BLACK 100"),
        ("BLACK-100-1", "BLACK 100"),
        ("BLUE-50", "BLUE 50"),
        ("BLUE_50", "BLUE 50"),
        ("BLACK-25+BLUE-25", "BLACK 25 BLUE 25"),
        ("BLACK_25,BLUE_25", "BLACK 25 BLUE 25"),
        ("RED-25", "RED 25"),
    ]
    
    print("\nRaw SKU                  ->  Normalized SKU")
    print("-" * 70)
    for raw, normalized in examples:
        actual_normalized = normalize_product_name(None, raw)
        status = "[OK]" if actual_normalized == normalized else "[MISMATCH]"
        print(f"{raw:25} ->  {actual_normalized:30} {status}")
    
    print("\n" + "="*70)
    print("KEY POINTS:")
    print("="*70)
    print("1. All variations of same product -> Same normalized SKU")
    print("2. Combos are order-independent (BLACK+BLUE = BLUE+BLACK)")
    print("3. You only enter cost price ONCE per normalized SKU")
    print("4. System automatically handles ALL variations")
    print("="*70 + "\n")


if __name__ == "__main__":
    # Show examples first
    show_normalization_examples()
    
    # Generate normalized SKU list
    result = generate_normalized_sku_list()
    
    if result:
        print("\n[INFO] You can now:")
        print("  1. Review 'sku_to_normalized_mapping.txt' to see all mappings")
        print("  2. Edit 'normalized_product_cost_prices.csv' to enter cost prices")
        print("  3. Run financial analysis to see true profitability")
