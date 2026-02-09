# Cost Price Management Guide

Complete guide for managing product cost prices and calculating true profitability.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [Understanding SKU Normalization](#understanding-sku-normalization)
3. [Generating Product Lists](#generating-product-lists)
4. [Entering Cost Prices](#entering-cost-prices)
5. [Troubleshooting](#troubleshooting)

---

## Quick Start

### The Problem
Your database has SKU variations like:
- `BLACK-100`, `BLACK_100`, `BLACK-100/.`, `BLACK-100-1`

Do you need to enter cost price 4 times? **NO!**

### The Solution
The system normalizes SKUs automatically. **Enter each product ONCE!**

### Step 1: Generate Normalized Product List

Run this command to extract all unique products from your database:

```powershell
python generate_normalized_sku_list.py
```

**What this does:**
- ✅ Reads all SKUs from your Meesho orders
- ✅ Normalizes them (removes duplicates)
- ✅ Creates `normalized_product_cost_prices.csv` with unique products
- ✅ Creates `sku_to_normalized_mapping.txt` showing all variations

**Example output:**
```
GENERATING NORMALIZED SKU LIST FOR COST PRICE ENTRY
====================================================================

[1/4] Extracting SKUs from Meesho orders...
   Found 1,543 Meesho orders
   Found 2,187 total SKU variations
   Normalized to 458 unique products

SUMMARY
====================================================================
Total SKU variations in database:    2,187
Normalized to unique products:        458
Reduction:                            79.1%
```

### Step 2: Enter Cost Prices

Open `normalized_product_cost_prices.csv` in Excel:

| normalized_sku | sample_variations | cost_price |
|----------------|-------------------|------------|
| BLACK 100 | BLACK-100, BLACK_100 | **50.00** ← Edit this! |
| BLUE 50 | BLUE-50, BLUE_50 | **30.00** ← Edit this! |

**Save the file** when done.

### Step 3: Rename File

```powershell
mv normalized_product_cost_prices.csv product_cost_prices.csv
```

### Step 4: Run Analysis

```powershell
python main.py
# Click 'Financial & Profitability' button
```

---

## Understanding SKU Normalization

### How It Works

**Input: Raw SKUs from orders**
```
BLACK-100
BLACK_100
BLACK-100/.
BLACK-100-1
```

**Output: One Normalized SKU**
```
BLACK 100
```

### Why It Matters

**When you enter:**
```csv
BLACK 100,50.00
```

**System automatically maps:**
- `BLACK-100` → Rs. 50.00 ✅
- `BLACK_100` → Rs. 50.00 ✅
- `BLACK-100/.` → Rs. 50.00 ✅
- `BLACK-100-1` → Rs. 50.00 ✅
- Any other variation → Rs. 50.00 ✅

**You enter ONCE, system handles ALL variations!**

### Example: Real Product with 17 Variations

**Normalized SKU:** `BLACK 100`

**All variations merged:**
- `-Black-100`
- `BLACK-100`
- `BLACK-100,`
- `BLACK-100-'`
- `BLACK-100-.`
- `BLACK-100-0`
- `BLACK-100-01`
- `BLACK-100-1`
- `BLACK-100-10`
- `BLACK-100/.`
- `BLACK_100`
- ... (17 total)

**Action:** Enter ONE cost price, all 17 variations get that cost!

---

## Generating Product Lists

### Output Files

#### 1. `normalized_product_cost_prices.csv` (EDIT THIS!)
```csv
normalized_sku,sample_variations,cost_price
BLACK 100,"BLACK-100, BLACK_100, BLACK-100/.",0.00
BLUE 50,"BLUE-50, BLUE_50",0.00
BLACK 25 BLUE 25,"BLACK-25+BLUE-25, BLUE-25+BLACK-25",0.00
RED 25,RED-25,0.00
```

**Columns:**
- `normalized_sku` - The canonical name (what system uses internally)
- `sample_variations` - Examples of raw SKUs (for reference only)
- `cost_price` - **YOU FILL THIS IN!**

#### 2. `sku_to_normalized_mapping.txt` (REFERENCE)
```
SKU NORMALIZATION MAPPING
======================================================================

NORMALIZED: BLACK 100
--------------------------------------------------
  -> BLACK-100
  -> BLACK_100
  -> BLACK-100/.
  -> BLACK-100-1

NORMALIZED: BLUE 50
--------------------------------------------------
  -> BLUE-50
  -> BLUE_50
```

**Use case:**
- Understand how normalization works
- Verify correct SKUs are being grouped
- Reference when entering cost prices

### When to Regenerate

Regenerate the product list when:
- ✅ You add new products
- ✅ You want to refresh the list
- ✅ You forgot what normalized SKUs look like
- ✅ You've imported new orders with new SKUs

---

## Entering Cost Prices

### Two Methods

#### Option 1: Raw SKUs (Works but More Work)
```csv
sku,cost_price
BLACK-100,50.0
BLACK_100,50.0
BLUE-50,30.0
```
- Enter any SKU variation from your orders
- System auto-normalizes behind the scenes
- Might enter same product multiple times (inefficient)

#### Option 2: Normalized SKUs ⭐ **RECOMMENDED**
```csv
sku,cost_price
BLACK 100,50.0
BLUE 50,30.0
```
- Enter each product ONLY ONCE
- All variations automatically covered
- **59-79% less work** (84-458 products vs 206-2,187 variations)

### File Format

**Simple CSV with two columns:**
```csv
sku,cost_price
BLACK 100,50.0
BLUE 50,30.0
RED 25,15.0
BLACK 25 BLUE 25,40.0
GREEN 10,8.0
```

### Combo Products

Combo products have their own cost:
```csv
BLACK 25 BLUE 25,40.0
```

**Note:** System automatically handles both order variations:
- `BLACK-25+BLUE-25` → Rs. 40
- `BLUE-25+BLACK-25` → Rs. 40 (same cost!)

### Missing Products

If product not in CSV → COGS = 0 (system still works, just shows marketplace costs only)

**You can add manually:**
```csv
NEW PRODUCT 123,45.00
```

### Example: Complete Workflow

**1. Generate list:**
```powershell
python generate_normalized_sku_list.py
```

**2. Open CSV in Excel:**
Double-click `normalized_product_cost_prices.csv`

**3. Fill cost prices:**
| normalized_sku | cost_price |
|----------------|------------|
| BLACK 100 | 50.00 |
| BLUE 50 | 30.00 |
| RED 25 | 15.00 |

**4. Save and rename:**
```powershell
mv normalized_product_cost_prices.csv product_cost_prices.csv
```

**5. Run analysis:**
```powershell
python main.py
# Click 'Financial & Profitability'
```

**6. View results:**
- Cost Breakdown shows "Cost of Goods Sold"
- Product profitability includes true margins
- All SKU variations automatically use correct cost!

---

## Troubleshooting

### Q: Script shows 0 products?
**A:** No Meesho orders in database yet. Import some orders first.

### Q: Some normalized SKUs look weird?
**A:** Check `sku_to_normalized_mapping.txt` to see source variations.

### Q: Can I use both raw and normalized SKUs in CSV?
**A:** Yes! System normalizes everything. But using normalized SKUs is cleaner.

### Q: Do I need to run generator every time?
**A:** No, only when:
- You add new products
- You want to refresh the list
- You forgot what normalized SKUs look like

### Q: What about Flipkart/Amazon products?
**A:** They use different identifiers (FSN/ASIN), not SKUs. COGS only works for Meesho orders.

### Q: Missing cost price for a product?
**A:** System defaults to COGS = 0. Just marketplace costs apply.

### Q: Can I edit CSV while app is running?
**A:** Yes - edit CSV anytime, changes apply on next analysis run.

### Q: What about products sold at different costs over time?
**A:** Use single average cost per SKU (CSV uses latest value).

---

## Summary

### Benefits

✅ **Enter Each Product Only ONCE**
- No need to remember all variations
- No duplicate entries
- Less work!

✅ **Automatic Mapping**
- System handles all variations
- Works with future orders
- Zero maintenance

✅ **Accurate Profitability**
- Includes product costs (COGS)
- True profit margins

✅ **Easy to Update**
- Just edit the CSV
- Changes apply immediately
- Simple and transparent

### Quick Reference

**Generate list:**
```powershell
python generate_normalized_sku_list.py
```

**Edit costs:**
Open `normalized_product_cost_prices.csv` in Excel

**Rename:**
```powershell
mv normalized_product_cost_prices.csv product_cost_prices.csv
```

**Analyze:**
```powershell
python main.py
# Click 'Financial & Profitability'
```

---

## Related Files

- **`generate_normalized_sku_list.py`** - Utility to generate product list
- **`normalized_product_cost_prices.csv`** - Generated cost price template
- **`sku_to_normalized_mapping.txt`** - Reference showing all mappings
- **`product_cost_prices.csv`** - Active cost prices (used by system)
- **`cost_price.py`** - Cost lookup logic
- **`analytics.py`** - Financial analysis with COGS
- **`FIXED_COSTS_PER_ORDER.md`** - Guide for operational fixed costs

---

## See Also

For information about fixed costs per order (packing charges, etc.), see **`FIXED_COSTS_PER_ORDER.md`**.

---

**Status:** ✅ Complete cost price management system ready to use!

**Last Updated:** November 22, 2025
