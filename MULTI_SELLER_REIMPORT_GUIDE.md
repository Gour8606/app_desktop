# Multi-Seller Data Import Guide

**Updated:** November 22, 2025

## Problem Summary

After implementing multi-seller support, the following issues occurred:
1. **Inventory**: "Missing inventory data" when clicking "Inventory & Actions"
2. **Financial**: "No order data available" when clicking "Financial & Profitability"

**Root Cause:** All inventory, payment, and ads data imported before the migration have `seller_gstin = None`. When you select a specific seller, the app filters by GSTIN and finds no matching records.

## Your Actual File Naming Patterns

### Inventory Files
```
Inventory-Update-File_2025-11-21T23-52-21_1258379.xlsx
```

### Payment ZIP Files (contain Excel inside)
```
Payment-Report.zip
  ├── 1258379_SP_ORDER_ADS_REFERRAL_PAYMENT_FILE_PREVIOUS_PAYMENT_2025-10-01_2025-10-31.xlsx
```

The Excel filename **inside the ZIP** has the supplier ID at the start: `{supplier_id}_SP_ORDER_ADS_...`

## Updated Import Logic

### Inventory Import (`import_inventory_data`)
**Detects supplier ID from:**
- Pattern 1: `Inventory-Update-File_2025-11-21T23-52-21_{supplier_id}.xlsx`
- Pattern 2: `{supplier_id}_inventory.xlsx`

**Regex:** `r'_(\d{6,})(?:\.\w+)?$'` - Matches 6+ digits at end of filename

### Payment Import (`import_payments_data`)
**Detects supplier ID from:**
1. **ZIP filename** (if named like `Payment_Report_1258379.zip`)
2. **Excel filename inside ZIP** (like `1258379_SP_ORDER_ADS_REFERRAL_PAYMENT_FILE_...xlsx`)

**Regex for Excel inside ZIP:** `r'^(\d{6,})_'` - Matches 6+ digits at start of filename

**Also detects from:** `sub_order_no` by looking up in `MeeshoSale` table (fallback)

## What Was Fixed

### 1. Inventory Import (import_logic.py:535-563)
```python
# Updated regex to handle your filename format
match = re.search(r'_(\d{6,})(?:\.\w+)?$', filename)
# Matches: Inventory-Update-File_2025-11-21T23-52-21_1258379.xlsx → 1258379
```

### 2. Payment Import (import_logic.py:629-685)
```python
# NEW: Extract from Excel filename inside ZIP
excel_filename = os.path.basename(excel_file)
match = re.search(r'^(\d{6,})_', excel_filename)
# Matches: 1258379_SP_ORDER_ADS_REFERRAL_PAYMENT_FILE...xlsx → 1258379

# Then looks up GSTIN from SellerMapping table
mapping = db.query(SellerMapping).filter(SellerMapping.supplier_id == supplier_id).first()
```

### 3. Ads Cost Import
- Uses same `detected_gstin` from payment import
- Both sheets in same Excel file, so supplier ID detection happens once

## Re-Import Instructions

### Step 1: Delete Old Data (COMPLETED ✅)
```powershell
# Already deleted via scripts:
- 1,377 inventory records (all had seller_gstin = None)
- 16,636 payment records (all had seller_gstin = None)
- 280 ads cost records (all had seller_gstin = None)
```

### Step 2: Verify Seller Mappings
Your seller mappings are correct:
```
Supplier 567538  → GSTIN 06GETPD0854L1Z2 (ShreeEnterprizes)
Supplier 1258379 → GSTIN 06DHOPD4346E1ZG (Shreeman Enterprises)
Supplier 3268023 → GSTIN 23DHOPD4346E1ZK (Omly)
```

### Step 3: Re-Import Inventory
1. Open the Meesho Sales App
2. Click **"Upload Inventory"** button
3. Select each inventory file:
   - `Inventory-Update-File_2025-11-21T23-52-21_567538.xlsx`
   - `Inventory-Update-File_2025-11-21T23-52-21_1258379.xlsx`
   - `Inventory-Update-File_2025-11-21T23-52-21_3268023.xlsx`
4. Watch for success message: **"✅ Detected seller: Supplier {id} → GSTIN {gstin}"**

### Step 4: Re-Import Payments
1. Click **"Upload Payments"** button
2. Select each payment ZIP file
3. The app will extract the Excel file and detect supplier ID from:
   - Excel filename inside: `1258379_SP_ORDER_ADS_REFERRAL_PAYMENT_FILE_...xlsx`
4. Watch for success message: **"✅ Detected seller from Excel filename: Supplier {id} → GSTIN {gstin}"**

### Step 5: Verify Import
Run check script:
```powershell
C:/Users/dhaka/anaconda3/python.exe check_gstin_data.py
```

Expected output:
```
=== DATA CHECK FOR GSTIN: 06DHOPD4346E1ZG ===
Meesho Sales: 3468
Meesho Payments: >0 (should have data now!)
Inventory: >0 (should have data now!)

=== DATA CHECK FOR GSTIN: 06GETPD0854L1Z2 ===
Meesho Sales: 14140
Flipkart Orders: 104
Amazon Orders: 9
Meesho Payments: >0 (should have data now!)
Inventory: >0 (should have data now!)
```

### Step 6: Test in Application
1. **Select each seller** from dropdown
2. Click **"Inventory & Actions"** → Should show inventory insights
3. Click **"Financial & Profitability"** → Should show financial analysis
4. Click **"Dashboard"** → Should show filtered data
5. Click **"GST Compliance"** → Should show GST data for that seller

## Important Notes

### Filename Requirements
- **Supplier ID must be 6+ digits** (your IDs: 567538, 1258379, 3268023)
- Inventory: Supplier ID at **END** of filename (before extension)
- Payment Excel: Supplier ID at **START** of filename

### What Happens During Import
1. App extracts supplier ID from filename using regex
2. Looks up GSTIN in `seller_mapping` table
3. Tags all imported records with `seller_gstin`
4. Duplicate checking prevents re-importing same data

### Multi-Seller Benefits
✅ Each seller's data is completely isolated
✅ Analytics filter correctly by GSTIN
✅ GST reports generate separately for each seller
✅ No cross-contamination between sellers
✅ Can import/update one seller without affecting others

## Troubleshooting

### "⚠️ Warning: seller_gstin not detected"
**Cause:** Filename doesn't match expected pattern or mapping doesn't exist
**Fix:**
1. Check filename has supplier ID in correct position
2. Verify supplier ID exists in seller_mapping table
3. Import GST data first if new seller

### "No inventory data" after re-import
**Cause:** Selected wrong seller in dropdown
**Fix:** Select "All" or verify correct GSTIN selected

### "No order data available" after re-import
**Cause:** Payment data not yet re-imported
**Fix:** Re-import payment ZIP files

## Data That Doesn't Need Re-Import

### Already Has GSTIN ✅
- **Meesho Sales (GST/Invoice data):** 17,647 records - All have proper GSTIN
- **Flipkart Orders:** 104 records - All tagged with 06GETPD0854L1Z2
- **Amazon Orders:** 9 records - All tagged with 06GETPD0854L1Z2

These were imported via GST reports which include GSTIN in the data.

### Needs Re-Import ❌
- **Meesho Inventory:** Deleted, needs re-import
- **Meesho Payments:** Deleted, needs re-import
- **Meesho Ads Cost:** Deleted, needs re-import

## Prevention for Future

1. **Always import GST data FIRST** for new sellers (creates seller mapping)
2. **Use consistent filenames** with supplier ID in correct position
3. **Verify detection message** appears during import
4. **Test with "All" filter first** before selecting specific sellers

## Scripts Created

- `check_inventory.py` - Check inventory data and GSTIN status
- `check_orders.py` - Check order data across all marketplaces
- `check_payments.py` - Check payment data GSTIN status
- `check_gstin_data.py` - Comprehensive check for specific GSTIN
- `delete_inventory.py` - Delete inventory without confirmation
- `delete_payments_ads.py` - Delete payment/ads data
- `fix_inventory_gstin.py` - Delete inventory with confirmation (interactive)

## Files Modified

- `import_logic.py` (lines 535-563, 629-685)
  - Updated inventory import regex pattern
  - Added Excel filename detection for payments
  - Both now support your actual file naming format
