# GST Desktop Dashboard

Desktop application for importing e-commerce sales data from multiple Indian marketplaces and generating GSTR-1 compliance reports.

## Supported Marketplaces

- **Meesho** - GST reports (ZIP), Tax invoices (ZIP)
- **Flipkart** - Sales reports (Excel), GST reports (Excel)
- **Amazon** - B2B/B2C MTR reports (ZIP), GSTR-1 reports (ZIP)

## GSTR-1 Reports Generated

| Table | Description |
|-------|-------------|
| B2CS (Table 7) | B2C Small - State-wise consolidated sales |
| B2B (Table 4) | Business-to-Business invoices |
| B2CL (Table 5) | B2C Large - Inter-state invoices > Rs 2.5L |
| CDNR (Table 9B) | Credit/Debit notes for registered persons |
| HSN Summary | HSN-wise summary (B2C and B2B) |
| Docs (Table 13) | Document issued register |
| Complete GSTR-1 | Multi-sheet Excel workbook with all tables |

## Tech Stack

- **GUI**: PySide6 (Qt6)
- **Database**: SQLAlchemy + SQLite
- **Data Processing**: pandas, openpyxl

## Setup

```bash
pip install -r requirements.txt
```

## Usage

```bash
python main.py
```

1. Select a working folder (base folder for output files)
2. Import data files from each marketplace using the import buttons
3. Select Financial Year, Month, and Seller GSTIN from the filters
4. Generate reports using the export buttons

## Project Structure

```
main.py           - PySide6 GUI application entry point
import_logic.py   - Marketplace-specific import handlers
logic.py          - GSTR-1 report generation logic
docissued.py      - Document issued (Table 13) generation
models.py         - SQLAlchemy ORM models
database.py       - Database connection setup
constants.py      - GST constants, state codes, enums
auto_migrate.py   - Automatic database schema migration
```

## Financial Year Convention

This application uses the **end-year convention** for financial years:
- FY 2026 = April 2025 to March 2026
- Month 1 (January) in FY 2026 = January 2026
- Month 4 (April) in FY 2026 = April 2025
