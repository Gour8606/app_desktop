# 📊 Meesho Sales Dashboard

> **Multi-Marketplace GST Compliance Platform** - Version 2.0  
> Integrates Meesho, Flipkart & Amazon with GSTR-1 compliance

## Overview

The **Meesho Sales Dashboard** is a comprehensive business intelligence platform that:
- Integrates data from **3 marketplaces**: Meesho, Flipkart, Amazon
- Generates **7 GSTR-1 compliant reports** (B2B, B2C, HSN, Documents, etc.)
- Provides **25+ automated business analytics**
- Tracks inventory, payments, orders, sales, and returns
- Exports GST-ready CSV files for offline tool

### Key Features

✅ **Multi-Marketplace Integration**
- Meesho (10 data types), Flipkart (2 types), Amazon (2 types with B2B)

✅ **GSTR-1 Compliance** (7 of 8 applicable tables)
- Table 4A: B2B Invoices (rate-wise breakdown)
- Table 5: B2C Large (>₹2.5L)
- Table 7: B2C Small
- Table 9B: Credit/Debit Notes
- Table 12: HSN Summary (B2B + B2C)
- Table 13: Documents Issued

✅ **Business Intelligence**
- 25+ automated metrics
- Real-time inventory tracking
- Payment realization monitoring
- Multi-marketplace consolidated view

---

## Quick Start

### Installation
```bash
cd meesho_sales_app
pip install PySide6 sqlalchemy pandas openpyxl
python main.py
```

### Import Data (3 Steps)
```bash
1. Meesho: Upload ZIP, Import Inventory, Import Payments
2. Flipkart: Import Sales Report, Import GST Report
3. Amazon: Import B2B Report, Import B2C Report
```

### Generate GSTR-1 Reports
```bash
1. Select: FY, Month, Supplier
2. Click: B2CS, HSN, B2B, B2CL, CDNR, Docs buttons
3. Files saved to your base folder
```

---

## 📚 Documentation

| Document | Purpose |
|----------|---------|
| **📘 COMPREHENSIVE_DOCUMENTATION.md** | Complete guide (features, compliance, schema, troubleshooting) |
| **🚀 QUICK_START.md** | Getting started for end users |
| **👨‍💻 DEVELOPER_REFERENCE.md** | Code architecture for developers |
| **📝 CHANGELOG.md** | Version history and changes |

---

## 🎯 What's Included

### Database (14 Tables)
```
Meesho:   10 tables (orders, sales, returns, inventory, payments, etc.)
Flipkart: 2 tables (orders, returns with GST)
Amazon:   2 tables (orders, returns with B2B fields)
```

### GST Exports (7 Files)
```
✅ b2b,sez,de.csv      - B2B invoices (rate-wise)
✅ b2cl.csv             - Large B2C (>₹2.5L)
✅ b2cs.csv             - Small B2C
✅ cdnr.csv             - Credit/Debit notes
✅ hsn(b2b).csv         - HSN summary B2B
✅ hsn(b2c).csv         - HSN summary B2C
✅ docs.csv             - Documents issued
```

### Analytics (25+ Metrics)
```
Order Analytics:     7 metrics
Inventory Analytics: 6 metrics
Payment Analytics:   8 metrics
Financial Analytics: 4 metrics
```

---

## 📦 Technology Stack

- **Frontend**: PySide6 (Qt)
- **Backend**: Python 3.11+
- **Database**: SQLite with SQLAlchemy ORM
- **Data Processing**: pandas, openpyxl
- **Lines of Code**: ~4,100 lines

---

## � Recent Updates (v2.0 - Nov 20, 2025)

✅ **B2CL & CDNR Implementation**
- Added B2CL CSV generator for large B2C invoices (>₹2.5L)
- Added CDNR CSV generator for B2B credit/debit notes
- Complete GSTR-1 compliance (7 of 8 tables)

✅ **Amazon B2B Enhancement**
- Added 7 B2B fields (customer GSTIN, buyer name, etc.)
- Rate-wise breakdown for all GST exports
- Enhanced database schema

✅ **Documentation Consolidation**
- Created COMPREHENSIVE_DOCUMENTATION.md
- Reduced from 18 MD files to 5 essential files
- Merged all technical and user guides

---

## � Getting Help

1. **Read**: COMPREHENSIVE_DOCUMENTATION.md (complete guide)
2. **Quick Start**: QUICK_START.md (user guide)
3. **Developers**: DEVELOPER_REFERENCE.md (code reference)
4. **Debug Output**: Check application's debug window for errors

---

## 🎓 Use Cases

- **GST Filing**: Export GSTR-1 compliant CSV files
- **Inventory Management**: Track stock levels across products
- **Payment Reconciliation**: Monitor settlement vs. sales
- **Product Performance**: Analyze top products and categories
- **Geographic Analysis**: Revenue distribution by state
- **Multi-Marketplace**: Consolidated view of all platforms

---

## ⚙️ Configuration

Application auto-generates:
- `config.json` - User preferences and folder paths
- `meesho_sales.db` - SQLite database with all data

No manual setup required!

---

## � Troubleshooting

**Issue**: No data in reports  
**Fix**: Import data first, ensure correct FY/Month/Supplier selected

**Issue**: Import fails  
**Fix**: Check file format matches requirements, see debug output

**Issue**: B2B CSV empty  
**Fix**: Ensure Amazon B2B data imported with valid customer GSTIN

See COMPREHENSIVE_DOCUMENTATION.md for detailed troubleshooting.

---

## � Support

- Check debug output window for errors
- Verify file formats match requirements
- Review COMPREHENSIVE_DOCUMENTATION.md
- Check CHANGELOG.md for recent changes

---

## � Status

```
✅ Production Ready
✅ Multi-Marketplace Support (Meesho, Flipkart, Amazon)
✅ GSTR-1 Compliance (7 of 8 tables)
✅ 25+ Business Analytics
✅ Comprehensive Documentation
```

---

**Last Updated**: November 20, 2025  
**Version**: 2.0  
**Status**: ✅ Ready for GST Filing

**Happy analyzing! 🎉**

---

## 📂 Advanced Features & Dynamic Filename Handling

### Dynamic Filenames: How the App Handles Changing File Names

All import functions are designed to handle files with dynamic elements in their names, such as seller ID, month, year, date, and random IDs. This means:
- You do NOT need to rename files before importing.
- The app uses pattern matching (not hardcoded names) to find the right files.

**Examples of Supported Patterns:**
- `567538_2025-10-01_2025-10-31_TAX_INVOICE.zip`
- `Inventory-Update-File_2025-11-19T23-31-33_567538.xlsx`
- `orders_ab080481-0a9c-4513-8c55-bf3466012140_1762703550000.csv`
- `gst_123456_September_2025.zip`

**How it works:**
- Uses `in`, `startswith`, and `endswith` for flexible matching
- Ignores seller ID, date, and UUID changes
- Works for Meesho, Flipkart, and Amazon imports

**Validation:**
- 30+ test cases with different seller IDs, dates, and formats: 100% pass rate
- No need to update code for new months or sellers

---

### GSTR-1 Excel Workbook Generator (All-in-One Export)

**New in v2.0:**
- Generate a single Excel file (`GSTR1_FY2024_November_2024.xlsx`) with all GSTR-1 tables as separate sheets
- Professional formatting: colored headers, auto column widths, summary sheet
- Compatible with GST offline tool and CA review

**Sheets Included:**
- Summary (overview, stats, instructions)
- B2B (Table 4A, 4B, 4C)
- B2CL (Table 5)
- B2CS (Table 7, if available)
- CDNR (Table 9B)
- HSN (Table 12)

**How to Use:**
1. Select FY, Month, Supplier
2. Click **"📗 GSTR-1 Excel Workbook (All-in-One)"**
3. File saved to your base folder

**Benefits:**
- All GSTR-1 data in one file
- Easy to share with CA or upload to GST portal
- No manual merging of CSVs needed

---

## 🧑‍💻 Developer Reference

See `DEVELOPER_GUIDE_CONSTANTS.md` for code patterns, constants, and error handling best practices.

---


