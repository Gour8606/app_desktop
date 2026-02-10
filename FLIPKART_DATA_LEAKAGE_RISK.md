# CRITICAL: Flipkart Data Leakage Risk & Prevention Guide

**Severity**: 🔴 **CRITICAL**  
**Date**: February 10, 2026  
**Issue**: Data from one Flipkart seller can contaminate another seller's records

---

## What's The Problem?

### The Vulnerability

**Flipkart Sales Reports don't contain seller GSTIN.**

The system relies on a temporary file (`temp_flipkart_gstin.json`) to track which seller's GSTIN to use. This creates a **data leakage risk**:

```
Scenario: Data contamination through wrong GSTIN

1. User A imports Flipkart GST Report for GSTIN-A
   → System saves GSTIN-A to temp file

2. User B imports Flipkart Sales Report for GSTIN-B
   → System STILL uses GSTIN-A from temp file
   → ❌ GSTIN-B's sales data is now tagged as GSTIN-A

3. When User B generates B2CS report for GSTIN-B:
   → MISSING: Their own Flipkart sales data
   → LEAK: Contains GSTIN-A's data instead

Result: TWO sellers have contaminated data
```

---

## How To Prevent This

### ✅ SAFE IMPORT PROCEDURE

**Step 1: Import Flipkart GST Report**
```
1. Click "Import Flipkart GST Data"
2. Select Flipkart GST Report Excel (the official report you file)
3. System extracts and saves: GSTIN-A
4. Message shows: "GSTIN saved: 27AABCT1234B1Z0"
```

**Step 2: Immediately Import Sales Report for SAME SELLER**
```
1. Click "Import Flipkart Sales"
2. Select Sales Report Excel for SAME seller (GSTIN-A)
3. System uses saved GSTIN-A
4. ✅ Data is correctly tagged

⚠️ DO NOT DO ANYTHING ELSE BETWEEN STEPS 1-2
⚠️ DO NOT OPEN REPORTS, GENERATE CSV, OR SWITCH SELLERS
```

**Step 3: To Switch To Different Seller**
```
If you need to import data for GSTIN-B:

1. FIRST: Import Flipkart GST Report for GSTIN-B
   (this overwrites the temp GSTIN-A)
2. THEN: Immediately import Flipkart Sales Report for GSTIN-B
3. ✅ GSTIN-B data is now correctly saved
```

### ❌ DANGEROUS Sequences

**DON'T DO THIS:**
```
❌ Import GST for GSTIN-A
   ↓
❌ Generate Reports
   ↓
❌ Import GST for GSTIN-B
   ↓
❌ Import Sales for GSTIN-A (WRONG! Uses GSTIN-B's temp)
   ↓
DATA LEAKAGE - Sales contaminated
```

**DON'T DO THIS:**
```
❌ Import GST for GSTIN-A
   ↓
❌ Import Sales for GSTIN-A
   ↓
❌ Import GST for GSTIN-B
   ↓
❌ Import Sales for GSTIN-B
   (This reuses GSTIN-B from temp file)
   ↓
But wait... then go back to GSTIN-A
✅ Import Sales for GSTIN-A again
   (Uses GSTIN-A from... wait, temp file has GSTIN-B!)
   ↓
DATA LEAKAGE - Sales contaminated
```

---

## How To Verify You Have Clean Data

### Check 1: Review Temp File Status

The system now logs when GSTIN is saved. Look for:
```
✅ Message: "GSTIN saved: 27AABCT1234B1Z0"
✅ Followed by: "Import Sales Report for THIS SELLER next"
```

If you see this → You're safe to import Sales Report

### Check 2: Database Verification

After importing Flipkart Sales, verify GSTIN is correct:

```sql
-- Check what GSTIN was assigned to Flipkart orders
SELECT DISTINCT seller_gstin FROM flipkart_orders;

-- Should show ONLY your expected GSTIN(s)
-- If you see extra GSTINs → Data leakage occurred
```

### Check 3: Report Sanity Check

When generating B2CS report for GSTIN-A:
```
1. Select GSTIN-A from dropdown
2. Generate B2CS report
3. Open in Excel - check:
   ☑ Total Taxable Value matches your expectations
   ☑ No unexpected state codes
   ☑ Number of rows seems reasonable
```

If values look too high/low → Data may be mixed

---

## If You Suspect Data Leakage

### Immediate Actions

**STOP: Do NOT file returns yet**

**Step 1: Backup & Investigate**
```
Make a backup copy of:
- meesho_sales.db (database file)
- Any generated CSV/Excel files
```

**Step 2: Check Which GSTINs Got Contaminated**
```sql
-- List all GSTINs in Flipkart table
SELECT DISTINCT seller_gstin FROM flipkart_orders;

-- Count records per GSTIN
SELECT seller_gstin, COUNT(*) FROM flipkart_orders 
GROUP BY seller_gstin;

-- Compare with what you imported
-- If unexpected GSTINs exist → leakage confirmed
```

**Step 3: Clean The Database**
```sql
-- Delete contaminated Flipkart data
DELETE FROM flipkart_orders 
WHERE seller_gstin IN (SELECT DISTINCT seller_gstin FROM flipkart_orders)
AND id > [highest_id_before_contamination];

-- Alternatively, delete all Flipkart data and re-import correctly
DELETE FROM flipkart_orders;
DELETE FROM flipkart_returns;

-- Delete temp file to force re-import
-- (Delete temp_flipkart_gstin.json)
```

**Step 4: Re-Import Correctly**
```
1. Import Flipkart GST Report (for correct GSTIN)
2. Immediately import Flipkart Sales (don't delay)
3. Verify using Check 2 above
```

**Step 5: Regenerate Reports**
```
Generate all reports fresh after data is clean
```

---

## Architecture Explanation

### Why This Design Exists

**Flipkart's System Design:**
- Flipkart Sales Report = Customer-level transaction data
- Flipkart GST Report = Official tax filing document
- **Neither file contains seller GSTIN openly**
- Sales Report needs external GSTIN source

### Why Temp File Is Dangerous

The temp file approach works fine for single-seller operation:
- One user with one seller ✅

But fails for multi-seller:
- User switches sellers without clearing temp ❌
- Multiple users importing independently ❌
- Concurrent imports aren't protected ❌

### Better Solution (Future)

Database-backed GSTIN tracking:
```python
# Instead of temp file:
def get_flipkart_seller_gstin():
    # Query database for most recent GSTIN
    last_import = db.query(FlipkartOrder)\
        .order_by(FlipkartOrder.imported_at.desc())\
        .first()
    if last_import:
        return last_import.seller_gstin
    return None
```

**Benefits:**
- No temp files ✅
- Multi-user safe ✅
- Concurrent import aware ✅
- Audit trail ✅

---

## Checklist: Am I Safe?

```
☑ I imported Flipkart GST Report FIRST
☑ System showed "GSTIN saved: [MY_GSTIN]"
☑ I immediately imported Sales Report after (no other actions)
☑ Both imports showed success messages
☑ When I query database, I see only MY GSTIN in seller_gstin
☑ Generated reports show reasonable values
☑ I only work with one seller at a time
☑ If switching sellers, I re-import GST Report first
```

If all checked → **You're safe ✅**

---

## Questions & Answers

**Q: Can Meesho Sales have the same issue?**  
A: No - Meesho files contain GSTIN in each row. No temp file needed.

**Q: Can Amazon Sales have the same issue?**  
A: No - Amazon CSV files contain Seller GSTIN in each row.

**Q: Why not just extract GSTIN from Sales Report?**  
A: Flipkart doesn't provide it in that report. We'd need customer to manually specify it.

**Q: What if I have 2 sellers but 1 computer?**  
A: Import GST → Import Sales → Generate reports for seller 1. Then repeat for seller 2.

**Q: Can the system auto-detect the seller?**  
A: Not without significant architecture changes. Current design is temp-file based.

---

## When To Contact Support

- ❌ You suspect data contamination
- ❌ GSTIN mismatch warnings appear
- ❌ Generated report values look wrong
- ✅ You need clarification on proper import sequence

---

**Remember: With great multi-seller power comes great responsibility for data isolation.**

The system can handle multiple sellers, but you must follow the import sequence carefully.

**Better to prevent contamination than clean it up later.**
