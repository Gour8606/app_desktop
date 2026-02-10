# Multi-Seller GST Filing - Safety Best Practices

**Version**: 1.0  
**Date**: February 10, 2026  
**Audience**: GST Operation Teams, Compliance Officers

---

## 🔒 Data Isolation Guarantees

### What The System Ensures
✅ Each GSTR-1 report contains data from **ONE seller (GSTIN) only**  
✅ Data from different sellers **cannot accidentally mix** in reports  
✅ All imports are **validated** for single-seller consistency  
✅ Marketplace data (Meesho, Flipkart, Amazon) is **properly separated**  

---

## 📋 Safe Import Procedures

### Step 1: Verify Import Files

**Before importing Meesho:**
- GST Report ZIP should be from **ONE Meesho account**
- Look for: `tcs_sales.xlsx` + `tcs_sales_return.xlsx`
- Check file names for account identifier

**Before importing Flipkart:**
- Sales Report should be from **ONE Flipkart seller account**
- Must first import Flipkart GST Report to capture seller GSTIN
- System blocks import if GSTIN not found

**Before importing Amazon:**
```
⚠️ NEW VALIDATION (Feb 2026):
CSV must contain data from ONE seller GSTIN only
System will BLOCK import if multiple GSTINs detected
```

### Step 2: Import in Correct Order

**Recommended Import Sequence:**
1. **Meesho**: Import GST Report + Invoice Details
2. **Flipkart**: Import GST Report first, then Sales Report
3. **Amazon**: Import GSTR-1 Report, then MTR reports

### Step 3: Verify GSTIN in UI

After all imports:
1. Open application
2. Look at "Seller GSTIN" dropdown
3. Verify you see: Your business GSTIN(s) only
4. If wrong GSTIN appears: ❌ **DO NOT PROCEED** - Contact support

---

## ⚠️ Red Flags - When to STOP

### 🚨 CRITICAL: Stop and Investigate If:

1. **Import Shows Multiple GSTINs**
   ```
   ❌ IMPORT BLOCKED: Multiple seller GSTINs detected
   GSTINs found in this file:
   • 27AABCT1234B1Z0 (100 records)
   • 18AABCT5678B2Z0 (50 records)
   ```
   **ACTION**: Do not retry. Contact your Amazon/Flipkart account team. Request separate file per GSTIN.

2. **Wrong GSTIN in Dropdown**
   - If dropdown shows a GSTIN you don't recognize
   - Stop immediately
   - Check your imports

3. **Duplicate Data**
   - If importing same month twice
   - Previous import will be replaced (by design)
   - Confirm this is intentional

4. **Different GSTIN Selected**
   - Always double-check "Seller GSTIN" dropdown shows correct business
   - Before generating reports
   - Critical for filing!

---

## 📝 Report Generation Safety

### Before Generating Reports:

```
CHECKLIST:
☐ Financial Year is correct
☐ Month number is correct  
☐ Seller GSTIN dropdown shows YOUR GSTIN (not parent company, not partner)
☐ I've imported data for this GSTIN/month combination
☐ I've reviewed DATA_ISOLATION_ANALYSIS.md
```

### Report Generation Process:

```
1. Select Financial Year (e.g., 2025 for FY 2025-26)
2. Select Month (1-12)
3. Select Seller GSTIN (CRITICAL: Correct business entity)
4. Click "Generate B2CS" or other report type
5. Output file is saved to working directory
```

### Safety Features:

- ✅ System warns if GSTIN not selected
- ✅ System blocks report if GSTIN invalid
- ✅ Each report file is filtered to selected GSTIN only
- ✅ No mixing of seller data is possible

---

## 🎯 Multi-Seller Setup (Advanced)

### Scenario: You have 2 GSTINs for 2 separate businesses

```
Setup:
├── GSTIN-A (Business 1): 27AABCT1234B1Z0
│   ├── Meesho data
│   ├── Flipkart data  
│   └── Amazon data
│
└── GSTIN-B (Business 2): 18AABCT5678B2Z0
    ├── Meesho data
    ├── Flipkart data
    └── Amazon data
```

### Import Process:

**Business 1 (GSTIN-A) Month 1:**
1. Import Meesho files for GSTIN-A, Month 1
2. Import Flipkart files for GSTIN-A, Month 1
3. Import Amazon files for GSTIN-A, Month 1

**Business 2 (GSTIN-B) Month 1:**
1. Import Meesho files for GSTIN-B, Month 1
2. Import Flipkart files for GSTIN-B, Month 1
3. Import Amazon files for GSTIN-B, Month 1

### Report Generation:

```
For Business 1 (GSTIN-A):
- Select GSTIN-A from dropdown
- Generate reports
- ✅ Reports contain ONLY GSTIN-A data

For Business 2 (GSTIN-B):
- Select GSTIN-B from dropdown
- Generate reports
- ✅ Reports contain ONLY GSTIN-B data
```

### Data Isolation Guarantee:
✅ **Reports from GSTIN-A will NEVER contain GSTIN-B data**  
✅ **Reports from GSTIN-B will NEVER contain GSTIN-A data**  

---

## 🔍 Verification Procedures

### Verify Import Was Successful:

1. **Count Check**
   ```
   If importing 100 orders, message should show:
   ✅ 100 shipments
   ✅ X returns/cancellations
   ```

2. **GSTIN Verification**
   ```
   Message should show:
   ✅ Seller GSTIN: 27AABCT1234B1Z0
   ```

3. **No Errors**
   ```
   Should NOT show:
   ❌ IMPORT BLOCKED
   ❌ Multiple seller GSTINs
   ❌ No valid Seller GSTIN
   ```

### Verify Report Before Filing:

1. **Open Generated CSV in Excel**
2. **Check First Row**: Should show your business name/GSTIN values only
3. **Spot Check Data**: Values should match your sales, not competitors'
4. **Total Calculations**: Should reflect expected monthly business volume

### Database Verification (Technical):

For tech teams, verify isolation at database level:
```sql
-- Check Meesho records for GSTIN-A only
SELECT COUNT(*) FROM meesho_sales WHERE gstin = '27AABCT1234B1Z0';

-- Check Flipkart records for GSTIN-A only
SELECT COUNT(*) FROM flipkart_orders WHERE seller_gstin = '27AABCT1234B1Z0';

-- Check Amazon records for GSTIN-A only  
SELECT COUNT(*) FROM amazon_orders WHERE seller_gstin = '27AABCT1234B1Z0';

-- Verify no other GSTINs in these tables
SELECT DISTINCT gstin FROM meesho_sales;
SELECT DISTINCT seller_gstin FROM flipkart_orders;
SELECT DISTINCT seller_gstin FROM amazon_orders;
```

---

## 📞 Support & Issue Resolution

### Issue: Import Shows Wrong GSTIN

1. Check source file - does it actually belong to this seller?
2. If file is correct: Contact Amazon/Flipkart support for new file
3. If file is wrong: Use correct file for this seller

### Issue: GSTIN Dropdown Missing Expected Value

1. Check if you've imported data for that GSTIN
2. Verify import messages showed "✅ Success"
3. Try re-importing the file
4. If issue persists: Check database file for corruption

### Issue: Generated Report Looks Wrong

1. Verify GSTIN selected in dropdown
2. Verify month and year are correct
3. Check that data was imported for this month
4. Compare row counts with import messages

### Issue: Multi-Seller Data Mixed

1. Do NOT file this report
2. Delete generated file
3. Check database for contamination (see verification section)
4. Contact support immediately

---

## 📚 Documentation Reference

- **DATA_ISOLATION_ANALYSIS.md**: Technical architecture review
- **IMPLEMENTATION_REPORT.md**: Recent improvements and validations

---

## ✅ Filing Checklist

Before filing GSTR-1 on GST portal:

```
☐ I have selected correct Seller GSTIN from dropdown
☐ I have generated reports for correct month/year
☐ I have verified report data looks reasonable
☐ I see NO data from other sellers/GSTINs
☐ I have spot-checked values against my records
☐ CSV file has been reviewed in Excel
☐ I understand this validates single-seller data only
☐ I am ready to file this report
```

---

## Summary

**The system is designed to prevent cross-seller data leakage through:**

1. ✅ Database schema (GSTIN fields required)
2. ✅ Import validation (single-seller enforcement)
3. ✅ Report generation (GSTIN-filtered queries)
4. ✅ UI controls (GSTIN selection required)

**Your responsibility:**
- Verify you import correct files for correct GSTINs
- Confirm GSTIN selection before generating reports
- Review generated reports before filing

**With both system controls + user diligence = Safe multi-seller filing**

---

**Questions?** Review the analysis documents or contact support  
**Found a bug?** Report data isolation issues immediately  
**Feedback?** Help us improve these safety procedures
