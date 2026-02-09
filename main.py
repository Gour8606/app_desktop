import sys
import os
import json
import re
import traceback
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QPushButton, QComboBox,
    QVBoxLayout, QWidget, QTableWidget, QTableWidgetItem, QTextEdit,
    QFileDialog, QMessageBox, QHBoxLayout, QDialog, QProgressBar
)
from PySide6.QtCore import Qt



from database import SessionLocal, engine, Base
from models import MeeshoSale
from import_logic import (
    import_from_zip, import_inventory_data, import_payments_data,
    import_invoice_data, import_flipkart_sales, import_flipkart_b2c, import_amazon_mtr, import_amazon_gstr1,
    validate_meesho_tax_invoice_zip, validate_inventory_excel, validate_payments_zip, validate_invoices_zip,
    validate_flipkart_sales_excel, validate_flipkart_gst_excel, validate_amazon_zip
)
from docissued import append_meesho_docs, append_meesho_docs_from_db, append_flipkart_section13, append_flipkart_docs_from_db, append_amazon_document_series, append_amazon_docs_from_db, generate_docs_csv_from_all
from logic import (
    generate_gst_pivot_csv, generate_gst_hsn_pivot_csv, get_monthly_summary,
    generate_b2b_csv, generate_hsn_b2b_csv, generate_b2cl_csv, generate_cdnr_csv, generate_gstr1_excel_workbook,
    get_invoice_analytics, get_enhanced_gst_analytics,
    get_inventory_analytics, get_payment_analytics, get_advanced_product_analytics
)
from analytics import (
    get_business_dashboard_analytics, get_product_inventory_insights, get_financial_analysis,
    get_action_items_analytics, get_customer_segmentation_analytics,
    get_compliance_audit_analytics, get_product_profitability_analytics
)
from export import generate_catalog_summary_csv
from auto_migrate import auto_migrate, verify_multi_seller_setup

CONFIG_FILE = "config.json"

# Automatic database migration on app startup
def initialize_database():
    """
    Automatically migrates database schema on startup.
    Creates missing tables and adds missing columns.
    Safe to run every time - idempotent operation.
    """
    print("\n" + "="*60)
    print("DATABASE INITIALIZATION")
    print("="*60)
    
    # Run auto-migration
    migration_messages = auto_migrate()
    for msg in migration_messages:
        print(msg)
    
    # Verify multi-seller setup
    print("\nMulti-Seller Setup Status:")
    verify_messages = verify_multi_seller_setup()
    for msg in verify_messages:
        print(msg)
    
    print("="*60 + "\n")

# Run database initialization before launching the app
initialize_database()

class DashboardApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Meesho Sales & GST Desktop Dashboard")
        self.setMinimumSize(1000, 600)

        # Defaults
        self.base_folder = os.getcwd()
        self.meesho_file = ""
        self.flipkart_file = ""
        self.amz_gstr_file = ""
        self.amz_mtr_file = ""

        self.load_config()

        layout = QVBoxLayout()

        # --- Base folder row ---
        self.folder_label = QLabel(f"Current Folder: {self.base_folder}")
        self.btn_change_folder = QPushButton("Change Folder")
        folder_row = QHBoxLayout()
        folder_row.addWidget(self.folder_label)
        folder_row.addWidget(self.btn_change_folder)
        layout.addLayout(folder_row)
        self.btn_change_folder.clicked.connect(self.change_base_folder)

        # --- File selectors (label+button in same row) ---
        # Note: All marketplace data (Meesho, Flipkart, Amazon) are imported to database via import buttons
        # No manual file selection needed for any GST or Docs calculations
        
        self._validate_config_paths_and_update_labels()

        # --- Filters in one row ---
        self.year_combo = QComboBox()
        self.month_combo = QComboBox()
        self.supplier_combo = QComboBox()
        filters_row = QHBoxLayout()
        filters_row.addWidget(QLabel("Financial Year:"))
        filters_row.addWidget(self.year_combo)
        filters_row.addWidget(QLabel("Month Number:"))
        filters_row.addWidget(self.month_combo)
        filters_row.addWidget(QLabel("Seller GSTIN:"))
        filters_row.addWidget(self.supplier_combo)
        layout.addLayout(filters_row)

        # --- Action buttons in multiple rows ---
        # Import buttons
        self.btn_upload = QPushButton("Import Meesho GST Report (ZIP)")
        self.btn_import_inventory = QPushButton("Import Meesho Inventory (Excel)")
        self.btn_import_payments = QPushButton("Import Meesho Payments (ZIP)")
        self.btn_import_invoices = QPushButton("Import Meesho Tax Invoice (ZIP)")
        self.btn_import_flipkart_sales = QPushButton("Import Flipkart Sales (Excel)")
        self.btn_import_flipkart_gst = QPushButton("Import Flipkart GST (Excel)")
        self.btn_import_amazon_b2b = QPushButton("Import Amazon B2B (ZIP)")
        self.btn_import_amazon_b2c = QPushButton("Import Amazon B2C (ZIP)")
        self.btn_import_amazon_gstr1 = QPushButton("Import Amazon GSTR1 (ZIP)")
        
        # GST export buttons
        self.btn_b2cs_csv = QPushButton("B2CS (Table 7)")
        self.btn_hsn_csv = QPushButton("HSN (B2C)")
        self.btn_b2b = QPushButton("B2B (Table 4)")
        self.btn_hsn_b2b = QPushButton("HSN (B2B)")
        self.btn_b2cl = QPushButton("B2CL (Table 5)")
        self.btn_cdnr = QPushButton("CDNR (Table 9B)")
        self.btn_docs_csv = QPushButton("Docs (Table 13)")
        self.btn_gstr1_excel = QPushButton("Complete GSTR-1 Excel")
        
        # Analytics buttons (4) - Consolidated for Business Growth Focus
        self.btn_growth_dashboard = QPushButton("Growth Dashboard")
        self.btn_financial_profitability = QPushButton("Financial & Profitability")
        self.btn_inventory_actions = QPushButton("Inventory & Actions")
        self.btn_gst_compliance = QPushButton("GST & Compliance")

        # Style all buttons
        all_buttons = [
            self.btn_upload, self.btn_import_inventory, self.btn_import_payments,
            self.btn_import_invoices, self.btn_import_flipkart_sales, self.btn_import_flipkart_gst, 
            self.btn_import_amazon_b2b, self.btn_import_amazon_b2c, self.btn_import_amazon_gstr1,
            self.btn_b2cs_csv, self.btn_hsn_csv, self.btn_b2b, self.btn_hsn_b2b,
            self.btn_b2cl, self.btn_cdnr, self.btn_docs_csv, self.btn_gstr1_excel,
            self.btn_growth_dashboard, self.btn_financial_profitability, 
            self.btn_inventory_actions, self.btn_gst_compliance
        ]
        for btn in all_buttons:
            btn.setFixedHeight(35)
            btn.setMinimumWidth(140)

        # Row 1: Import data
        layout.addWidget(QLabel("Import Data:"))
        row1 = QHBoxLayout()
        row1.addWidget(self.btn_upload)
        row1.addWidget(self.btn_import_inventory)
        row1.addWidget(self.btn_import_payments)
        row1.addWidget(self.btn_import_invoices)
        layout.addLayout(row1)
        
        row1b = QHBoxLayout()
        row1b.addWidget(self.btn_import_flipkart_sales)
        row1b.addWidget(self.btn_import_flipkart_gst)
        layout.addLayout(row1b)
        
        row1c = QHBoxLayout()
        row1c.addWidget(self.btn_import_amazon_b2b)
        row1c.addWidget(self.btn_import_amazon_b2c)
        row1c.addWidget(self.btn_import_amazon_gstr1)
        layout.addLayout(row1c)

        # Row 2: GST Exports
        layout.addWidget(QLabel("GST Reports (GSTR-1):"))
        row2 = QHBoxLayout()
        row2.addWidget(self.btn_b2cs_csv)
        row2.addWidget(self.btn_hsn_csv)
        row2.addWidget(self.btn_b2b)
        row2.addWidget(self.btn_hsn_b2b)
        layout.addLayout(row2)
        
        row3 = QHBoxLayout()
        row3.addWidget(self.btn_b2cl)
        row3.addWidget(self.btn_cdnr)
        row3.addWidget(self.btn_docs_csv)
        row3.addWidget(self.btn_gstr1_excel)
        layout.addLayout(row3)
        
        # Row 4: Analytics - Business Growth Focus (Consolidated from 8 to 4)
        layout.addWidget(QLabel("Analytics - Business Growth Focus:"))
        row4 = QHBoxLayout()
        row4.addWidget(self.btn_growth_dashboard)
        row4.addWidget(self.btn_financial_profitability)
        row4.addWidget(self.btn_inventory_actions)
        row4.addWidget(self.btn_gst_compliance)
        layout.addLayout(row4)

        # --- Output table (main display area) ---
        layout.addWidget(QLabel("Results:"))
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setWordWrap(True)
        self.table.verticalHeader().setDefaultSectionSize(30)  # Row height
        layout.addWidget(self.table)
        
        # Debug output for error messages (hidden by default)
        self.debug_output = QTextEdit()
        self.debug_output.setReadOnly(True)
        self.debug_output.setVisible(False)  # Hidden by default

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.db = SessionLocal()
        self.load_filters()

        # Button connections
        # Import actions
        self.btn_upload.clicked.connect(self.import_meesho_gst_report)
        self.btn_import_inventory.clicked.connect(self.import_inventory)
        self.btn_import_payments.clicked.connect(self.import_payments)
        self.btn_import_invoices.clicked.connect(self.import_invoices)
        self.btn_import_flipkart_sales.clicked.connect(self.import_flipkart_sales)
        self.btn_import_flipkart_gst.clicked.connect(self.import_flipkart_gst)
        self.btn_import_amazon_b2b.clicked.connect(self.import_amazon_b2b)
        self.btn_import_amazon_b2c.clicked.connect(self.import_amazon_b2c)
        self.btn_import_amazon_gstr1.clicked.connect(self.import_amazon_gstr1)
        
        # GST exports
        self.btn_b2cs_csv.clicked.connect(self.generate_b2cs_csv)
        self.btn_hsn_csv.clicked.connect(self.generate_hsn_csv)
        self.btn_b2b.clicked.connect(self.export_b2b)
        self.btn_hsn_b2b.clicked.connect(self.export_hsn_b2b)
        self.btn_b2cl.clicked.connect(self.export_b2cl)
        self.btn_cdnr.clicked.connect(self.export_cdnr)
        self.btn_docs_csv.clicked.connect(self.generate_docs_csv)
        self.btn_gstr1_excel.clicked.connect(self.export_gstr1_excel)
        
        # Analytics - Consolidated for Business Growth Focus
        self.btn_growth_dashboard.clicked.connect(self.show_growth_dashboard)
        self.btn_financial_profitability.clicked.connect(self.show_financial_profitability)
        self.btn_inventory_actions.clicked.connect(self.show_inventory_actions)
        self.btn_gst_compliance.clicked.connect(self.show_gst_compliance)

    # --- Helper UI methods ---
    def _label_text(self, name, path):
        return f"{name}: {os.path.basename(path) if path else 'Not Selected'}"

    # Manual selectors
    # --- Config load/save ---
    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                cfg = json.load(open(CONFIG_FILE))
                self.base_folder = cfg.get("base_folder", os.getcwd())
                self.meesho_file = cfg.get("meesho_file", "")
                self.flipkart_file = cfg.get("flipkart_file", "")
                self.amz_gstr_file = cfg.get("amz_gstr_file", "")
                self.amz_mtr_file = cfg.get("amz_mtr_file", "")
            except:
                pass

    def save_config(self):
        cfg = {
            "base_folder": self.base_folder,
            "meesho_file": self.meesho_file,
            "flipkart_file": self.flipkart_file,
            "amz_gstr_file": self.amz_gstr_file,
            "amz_mtr_file": self.amz_mtr_file
        }
        json.dump(cfg, open(CONFIG_FILE, "w"))

    def _validate_config_paths_and_update_labels(self):
        for attr in ["meesho_file", "flipkart_file", "amz_gstr_file", "amz_mtr_file"]:
            val = getattr(self, attr, "")
            if val and not val.startswith(self.base_folder):
                setattr(self, attr, "")

    # --- Change folder + auto detection ---
    def change_base_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder", self.base_folder)
        if not folder:
            return
        self.base_folder = folder
        self.folder_label.setText(f"Current Folder: {self.base_folder}")

        self._reset_file_selections()

        # Auto-set filters from folder name
        folder_name = os.path.basename(folder)
        m = re.match(r"gst_(\d+)_(\d+)_(\d+)", folder_name)
        if m:
            supplier_id, month_num, fin_year = m.groups()
            self.load_filters()
            if fin_year in [self.year_combo.itemText(i) for i in range(self.year_combo.count())]:
                self.year_combo.setCurrentText(fin_year)
            if month_num in [self.month_combo.itemText(i) for i in range(self.month_combo.count())]:
                self.month_combo.setCurrentText(month_num)
            if supplier_id in [self.supplier_combo.itemText(i) for i in range(self.supplier_combo.count())]:
                self.supplier_combo.setCurrentText(supplier_id)

        # Auto-pick files except Flipkart
        for file in os.listdir(folder):
            fpath = os.path.join(folder, file)
            fl = file.lower()
            if fl == "tax_invoice_details.xlsx":
                self.meesho_file = fpath
            elif "gstr" in fl and fl.endswith(".xlsx"):
                self.amz_gstr_file = fpath
            elif "mtr" in fl and fl.endswith(".csv"):
                self.amz_mtr_file = fpath

        self._validate_config_paths_and_update_labels()
        self.save_config()

    def _reset_file_selections(self):
        self.meesho_file = ""
        self.flipkart_file = ""
        self.amz_gstr_file = ""
        self.amz_mtr_file = ""
        self._validate_config_paths_and_update_labels()

    # --- Filters load ---
    def load_filters(self):
        from models import FlipkartOrder, AmazonOrder
        from datetime import datetime
        
        self.year_combo.clear()
        self.month_combo.clear()
        self.supplier_combo.clear()
        
        # Get financial years from all marketplaces
        years = set()
        
        # Meesho financial years
        meesho_years = {r[0] for r in self.db.query(MeeshoSale.financial_year).distinct() if r[0]}
        years.update(meesho_years)
        
        # Flipkart order years (convert to financial year: Apr-Mar)
        flipkart_dates = self.db.query(FlipkartOrder.order_date).filter(FlipkartOrder.order_date.isnot(None)).distinct().all()
        for (date,) in flipkart_dates:
            if date:
                # Financial year: if month >= 4, FY = year+1, else FY = year
                fy = date.year + 1 if date.month >= 4 else date.year
                years.add(fy)
        
        # Amazon order years (convert to financial year)
        amazon_dates = self.db.query(AmazonOrder.order_date).filter(AmazonOrder.order_date.isnot(None)).distinct().all()
        for (date,) in amazon_dates:
            if date:
                fy = date.year + 1 if date.month >= 4 else date.year
                years.add(fy)
        
        # Month dropdown (always 1-12)
        months = list(range(1, 13))
        
        # GSTIN dropdown - collect unique GSTINs from all marketplaces
        gstins = set()
        
        # Get Meesho GSTINs
        meesho_gstins = {r[0] for r in self.db.query(MeeshoSale.gstin).distinct() if r[0]}
        gstins.update(meesho_gstins)
        
        # Get Flipkart GSTINs
        flipkart_gstins = {r[0] for r in self.db.query(FlipkartOrder.seller_gstin).distinct() if r[0]}
        gstins.update(flipkart_gstins)
        
        # Get Amazon GSTINs
        amazon_gstins = {r[0] for r in self.db.query(AmazonOrder.seller_gstin).distinct() if r[0]}
        gstins.update(amazon_gstins)
        
        self.year_combo.addItems([str(y) for y in sorted(years)])
        self.month_combo.addItems([str(m) for m in months])
        self.supplier_combo.addItems(sorted(gstins))  # Now populating with GSTINs

    # --- Actions ---
    def import_meesho_gst_report(self):
        """Import Meesho GST Report (ZIP file containing sales, returns, and tax data)."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Meesho GST Report ZIP", self.base_folder, "ZIP files (*.zip)")
        if not file_path: 
            return
        
        # Validate file before importing
        is_valid, message = validate_meesho_tax_invoice_zip(file_path)
        if not is_valid:
            QMessageBox.warning(self, "Invalid File", message)
            self.debug_output.append(message)
            return
        
        try:
            result = import_from_zip(file_path, self.db)
            QMessageBox.information(self, "Success", "Meesho GST Report imported successfully!")
            self.debug_output.append(f"\n{'='*60}")
            self.debug_output.append(f"📦 MEESHO GST REPORT IMPORT")
            self.debug_output.append(f"{'='*60}")
            self.debug_output.append(f"File: {os.path.basename(file_path)}")
            if result:
                self.debug_output.append('\n'.join(result))
            self.debug_output.append(f"{'='*60}\n")
            self.load_filters()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed: {e}")
            self.debug_output.append(f"❌ Error: {e}")
    
    def import_inventory(self):
        """Import inventory data from Excel file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Inventory Excel File", self.base_folder, "Excel Files (*.xlsx *.xls)"
        )
        if not file_path:
            return
        
        # Validate file before importing
        is_valid, message = validate_inventory_excel(file_path)
        if not is_valid:
            QMessageBox.warning(self, "Invalid File", message)
            self.debug_output.append(message)
            return
        
        try:
            result = import_inventory_data(file_path, self.db)
            QMessageBox.information(self, "Success", "Inventory imported successfully!")
            self.debug_output.append(f"\n{'='*60}")
            self.debug_output.append(f"📋 MEESHO INVENTORY IMPORT")
            self.debug_output.append(f"{'='*60}")
            self.debug_output.append(f"File: {os.path.basename(file_path)}")
            self.debug_output.append('\n'.join(result))
            self.debug_output.append(f"{'='*60}\n")
            self.load_filters()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Import failed: {e}")
            self.debug_output.append(f"❌ Error: {e}")
    
    def import_payments(self):
        """Import payment data from ZIP file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Payments ZIP File", self.base_folder, "ZIP Files (*.zip)"
        )
        if not file_path:
            return
        
        # Validate file before importing
        is_valid, message = validate_payments_zip(file_path)
        if not is_valid:
            QMessageBox.warning(self, "Invalid File", message)
            self.debug_output.append(message)
            return
        
        try:
            result = import_payments_data(file_path, self.db)
            QMessageBox.information(self, "Success", "Payments imported successfully!")
            self.debug_output.append(f"\n{'='*60}")
            self.debug_output.append(f"💰 MEESHO PAYMENTS IMPORT")
            self.debug_output.append(f"{'='*60}")
            self.debug_output.append(f"File: {os.path.basename(file_path)}")
            self.debug_output.append('\n'.join(result))
            self.debug_output.append(f"{'='*60}\n")
            self.load_filters()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Import failed: {e}")
            self.debug_output.append(f"❌ Error: {e}")
    
    def import_invoices(self):
        """Import Meesho Tax Invoice Details from ZIP file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Meesho Tax Invoice Details ZIP", self.base_folder, "ZIP Files (*.zip)"
        )
        if not file_path:
            return
        
        # Validate file before importing
        is_valid, message = validate_invoices_zip(file_path)
        if not is_valid:
            QMessageBox.warning(self, "Invalid File", message)
            self.debug_output.append(message)
            return
        
        try:
            result = import_invoice_data(file_path, self.db)
            QMessageBox.information(self, "Success", "Meesho Tax Invoice Details imported successfully!")
            self.debug_output.append(f"\n{'='*60}")
            self.debug_output.append(f"📄 MEESHO TAX INVOICE DETAILS IMPORT")
            self.debug_output.append(f"{'='*60}")
            self.debug_output.append(f"File: {os.path.basename(file_path)}")
            self.debug_output.append('\n'.join(result))
            self.debug_output.append(f"{'='*60}\n")
            self.load_filters()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Import failed: {e}")
            self.debug_output.append(f"❌ Error: {e}")
    
    def import_flipkart_sales(self):
        """Import Flipkart sales data from Excel file (Sales Report sheet)."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Flipkart Sales Report", self.base_folder, "Excel Files (*.xlsx *.xls)"
        )
        if not file_path:
            return
        
        # Validate file before importing
        is_valid, message = validate_flipkart_sales_excel(file_path)
        if not is_valid:
            QMessageBox.warning(self, "Invalid File", message)
            self.debug_output.append(message)
            return
        
        try:
            result = import_flipkart_sales(file_path, self.db)
            QMessageBox.information(self, "Success", "Flipkart sales data imported successfully!")
            self.debug_output.append(f"\n{'='*60}")
            self.debug_output.append(f"🛒 FLIPKART SALES IMPORT")
            self.debug_output.append(f"{'='*60}")
            self.debug_output.append(f"File: {os.path.basename(file_path)}")
            self.debug_output.append('\n'.join(result))
            self.debug_output.append(f"{'='*60}\n")
            self.load_filters()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Import failed: {e}")
            self.debug_output.append(f"❌ Error: {e}")
    
    def import_flipkart_gst(self):
        """Import Flipkart GST data from Excel file (GSTR-1 sections)."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Flipkart GST Report", self.base_folder, "Excel Files (*.xlsx *.xls)"
        )
        if not file_path:
            return
        
        # Validate file before importing
        is_valid, message = validate_flipkart_gst_excel(file_path)
        if not is_valid:
            QMessageBox.warning(self, "Invalid File", message)
            self.debug_output.append(message)
            return
        
        try:
            result = import_flipkart_b2c(file_path, self.db)
            QMessageBox.information(self, "Success", "Flipkart GST data imported successfully!")
            self.debug_output.append(f"\n{'='*60}")
            self.debug_output.append(f"📊 FLIPKART GST IMPORT")
            self.debug_output.append(f"{'='*60}")
            self.debug_output.append(f"File: {os.path.basename(file_path)}")
            self.debug_output.append('\n'.join(result))
            self.debug_output.append(f"{'='*60}\n")
            self.load_filters()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Import failed: {e}")
            self.debug_output.append(f"❌ Error: {e}")
    
    def import_amazon_b2b(self):
        """Import Amazon B2B sales data from ZIP containing MTR CSV."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Amazon B2B Report ZIP", self.base_folder, "ZIP Files (*.zip)"
        )
        if not file_path:
            return
        
        # Validate file before importing
        is_valid, message = validate_amazon_zip(file_path, expected_type="B2B")
        if not is_valid:
            QMessageBox.warning(self, "Invalid File", message)
            self.debug_output.append(message)
            return
        
        try:
            result = import_amazon_mtr(file_path, self.db)
            QMessageBox.information(self, "Success", "Amazon B2B data imported successfully!")
            self.debug_output.append(f"\n{'='*60}")
            self.debug_output.append(f"📦 AMAZON B2B IMPORT")
            self.debug_output.append(f"{'='*60}")
            self.debug_output.append(f"File: {os.path.basename(file_path)}")
            self.debug_output.append('\n'.join(result))
            self.debug_output.append(f"{'='*60}\n")
            self.load_filters()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Import failed: {e}")
            self.debug_output.append(f"❌ Error: {e}")
    
    def import_amazon_b2c(self):
        """Import Amazon B2C sales data from ZIP containing MTR CSV."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Amazon B2C Report ZIP", self.base_folder, "ZIP Files (*.zip)"
        )
        if not file_path:
            return
        
        # Validate file before importing
        is_valid, message = validate_amazon_zip(file_path, expected_type="B2C")
        if not is_valid:
            QMessageBox.warning(self, "Invalid File", message)
            self.debug_output.append(message)
            return
        
        try:
            result = import_amazon_mtr(file_path, self.db)
            QMessageBox.information(self, "Success", "Amazon B2C data imported successfully!")
            self.debug_output.append(f"\n{'='*60}")
            self.debug_output.append(f"🛍️ AMAZON B2C IMPORT")
            self.debug_output.append(f"{'='*60}")
            self.debug_output.append(f"File: {os.path.basename(file_path)}")
            self.debug_output.append('\n'.join(result))
            self.debug_output.append(f"{'='*60}\n")
            self.load_filters()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Import failed: {e}")
            self.debug_output.append(f"❌ Error: {e}")
    
    def import_amazon_gstr1(self):
        """Import Amazon GSTR1 data from ZIP containing Excel file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Amazon GSTR1 Report ZIP", self.base_folder, "ZIP Files (*.zip)"
        )
        if not file_path:
            return
        
        # Validate file before importing
        is_valid, message = validate_amazon_zip(file_path, expected_type="GSTR1")
        if not is_valid:
            QMessageBox.warning(self, "Invalid File", message)
            self.debug_output.append(message)
            return
        
        try:
            result = import_amazon_gstr1(file_path, self.db)
            QMessageBox.information(self, "Success", "Amazon GSTR1 data imported successfully!")
            self.debug_output.append(f"\n{'='*60}")
            self.debug_output.append(f"📊 AMAZON GSTR1 IMPORT")
            self.debug_output.append(f"{'='*60}")
            self.debug_output.append(f"File: {os.path.basename(file_path)}")
            self.debug_output.append('\n'.join(result))
            self.debug_output.append(f"{'='*60}\n")
            self.load_filters()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Import failed: {e}")
            self.debug_output.append(f"❌ Error: {e}")
    
    def get_month_filter(self):
        """Get current month filter value."""
        try:
            return int(self.month_combo.currentText())
        except (ValueError, AttributeError):
            return None
    
    def get_year_filter(self):
        """Get current year filter value."""
        try:
            return int(self.year_combo.currentText())
        except (ValueError, AttributeError):
            return None

    def generate_dashboard(self):
        """Generate comprehensive dashboard with sales, inventory, and payment analytics."""
        self.debug_output.clear()
        self.debug_output.append("="*80)
        self.debug_output.append("COMPREHENSIVE DASHBOARD - Multi-Marketplace Analytics")
        self.debug_output.append("="*80)
        
        try:
            fy = int(self.year_combo.currentText())
            mn = int(self.month_combo.currentText())
            sid = int(self.supplier_combo.currentText())
            
            # 1. Monthly Sales Summary
            self.debug_output.append("\nMONTHLY SALES SUMMARY")
            self.debug_output.append("-" * 40)
            data = get_monthly_summary(fy, mn, sid, self.db)
            summary = data.get("summary", {})
            if summary:
                self.debug_output.append(f"  Total Sales:        {summary.get('total_sales', 0)} units")
                self.debug_output.append(f"  Total Returns:      {summary.get('total_returns', 0)} units")
                self.debug_output.append(f"  Net Sales:          {summary.get('final_sales', 0)} units")
                self.debug_output.append(f"  Revenue:            {summary.get('final_amount', 0):,.2f}")
                
                # Update table with summary
                rows = [[f"{fy}-{mn}", sid, summary.get("total_sales", 0),
                         summary.get("total_returns", 0), summary.get("final_sales", 0),
                         f"{summary.get('final_amount', 0):.2f}"]]
                self.update_table(rows, ["FY-Month", "Supplier", "Total Sales", "Total Returns", "Final Qty", "Final Amount"])
            else:
                self.debug_output.append("  No sales data for selected period.")
            
            # 2. Inventory Analytics
            self.debug_output.append("\nINVENTORY ANALYTICS")
            self.debug_output.append("-" * 40)
            inv_analytics = get_inventory_analytics(self.db)
            if inv_analytics and 'error' not in inv_analytics:
                self.debug_output.append(f"  Total SKUs:         {inv_analytics.get('total_skus', 0)}")
                self.debug_output.append(f"  Out of Stock:       {inv_analytics.get('out_of_stock_count', 0)} items")
                self.debug_output.append(f"  Low Stock (<5):     {inv_analytics.get('low_stock_count', 0)} items")
                self.debug_output.append(f"  Total Stock Units:  {inv_analytics.get('total_stock', 0)}")
                
                # Show top products
                if 'top_products' in inv_analytics:
                    self.debug_output.append("\n  Top 5 Products by Stock:")
                    for i, product in enumerate(inv_analytics['top_products'][:5], 1):
                        self.debug_output.append(f"    {i}. {product[0][:40]}: {int(product[1])} units")
            else:
                self.debug_output.append("  No inventory data available.")
            
            # 3. Payment Analytics
            self.debug_output.append("\nPAYMENT ANALYTICS")
            self.debug_output.append("-" * 40)
            payment_analytics = get_payment_analytics(self.db)
            if payment_analytics and 'error' not in payment_analytics:
                self.debug_output.append(f"  Total Payments:     {payment_analytics.get('total_payments', 0):,.2f}")
                self.debug_output.append(f"  Total Sales Value:  {payment_analytics.get('total_sales', 0):,.2f}")
                self.debug_output.append(f"  Commissions:        {payment_analytics.get('total_commissions', 0):,.2f}")
                self.debug_output.append(f"  Deductions:         {payment_analytics.get('total_deductions', 0):,.2f}")
                self.debug_output.append(f"  Realization Rate:   {payment_analytics.get('realization_rate', 0):.2f}%")
                self.debug_output.append(f"  Total Orders:       {payment_analytics.get('total_orders', 0)}")
                
                # Show deduction breakdown
                if 'deductions' in payment_analytics:
                    deductions = payment_analytics['deductions']
                    self.debug_output.append("\n  Deduction Breakdown:")
                    self.debug_output.append(f"    Commission:       {deductions.get('commission', 0):,.2f}")
                    self.debug_output.append(f"    Platform Fee:     {deductions.get('platform_fee', 0):,.2f}")
                    self.debug_output.append(f"    Shipping:         {deductions.get('shipping_deduction', 0):,.2f}")
                    self.debug_output.append(f"    TCS/TDS:          {deductions.get('tcs_tds', 0):,.2f}")
            else:
                self.debug_output.append("  No payment data available.")
            
            self.debug_output.append("\n" + "="*80)
            self.debug_output.append("Dashboard generated successfully!")
            self.debug_output.append("="*80)
            
        except Exception as e:
            self.debug_output.append(f"\nError generating dashboard: {e}")
            QMessageBox.critical(self, "Error", f"Dashboard generation failed: {e}")

    def generate_b2cs_csv(self):
        try:
            fy = int(self.year_combo.currentText())
            mn = int(self.month_combo.currentText())
            gstin = self.supplier_combo.currentText()  # Now a GSTIN string, not supplier_id
            csv_debug = generate_gst_pivot_csv(fy, mn, gstin, self.db,
                output_folder=self.base_folder)
            QMessageBox.information(self, "Success", "B2CS CSV generated.")
            self.debug_output.append(csv_debug)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"{e}")

    def generate_hsn_csv(self):
        try:
            fy = int(self.year_combo.currentText())
            mn = int(self.month_combo.currentText())
            gstin = self.supplier_combo.currentText()  # Now a GSTIN string, not supplier_id
            debug_csv = generate_gst_hsn_pivot_csv(fy, mn, gstin, self.db,
                output_folder=self.base_folder)
            QMessageBox.information(self, "Success", "HSN WISE B2CS CSV generated.")
            self.debug_output.append(debug_csv)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"{e}")

    def generate_docs_csv(self):
        try:
            # Get selected GSTIN
            gstin = self.supplier_combo.currentText()
            if not gstin or gstin == "All Suppliers":
                QMessageBox.warning(self, "No Supplier Selected", "Please select a specific supplier (GSTIN) to generate documents.")
                return
            
            files_used = []
            supplied_files = {}
            
            # Check if Meesho data exists in database for this GSTIN
            from models import MeeshoInvoice, MeeshoSale
            has_meesho_db = self.db.query(MeeshoInvoice).join(
                MeeshoSale, MeeshoInvoice.suborder_no == MeeshoSale.sub_order_num
            ).filter(MeeshoSale.gstin == gstin).count() > 0
            if has_meesho_db:
                supplied_files["meesho_db"] = True
                files_used.append("Meesho (from database)")
            
            # Check if Flipkart data exists in database for this GSTIN
            from models import FlipkartOrder
            has_flipkart_db = self.db.query(FlipkartOrder).filter(
                FlipkartOrder.buyer_invoice_id.isnot(None),
                FlipkartOrder.seller_gstin == gstin
            ).count() > 0
            if has_flipkart_db:
                supplied_files["flipkart_db"] = True
                files_used.append("Flipkart (from database)")
            
            # Check if Amazon data exists in database for this GSTIN
            from models import AmazonOrder
            has_amazon_db = self.db.query(AmazonOrder).filter(
                AmazonOrder.transaction_type == 'Shipment',
                AmazonOrder.invoice_number.isnot(None),
                AmazonOrder.seller_gstin == gstin
            ).count() > 0
            if has_amazon_db:
                supplied_files["amazon_db"] = True
                files_used.append("Amazon (from database)")
            
            if not files_used:
                QMessageBox.warning(self, "No Data", f"No invoice data found for GSTIN: {gstin}")
                return
            
            output_path = os.path.join(self.base_folder, "docs.csv")
            csv_rows = []
            
            # Pass GSTIN to filter functions
            if supplied_files.get("meesho_db"):
                append_meesho_docs_from_db(self.db, csv_rows, gstin=gstin)
            if supplied_files.get("flipkart_db"):
                append_flipkart_docs_from_db(self.db, csv_rows, gstin=gstin)
            if supplied_files.get("amazon_db"):
                append_amazon_docs_from_db(self.db, csv_rows, gstin=gstin)
            
            if not csv_rows:
                QMessageBox.warning(self, "No Data", "No document rows generated.")
                return
            
            import csv
            with open(output_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Nature of Document", "Sr. No. From", "Sr. No. To", "Total Number", "Cancelled"])
                writer.writerows(csv_rows)
            
            QMessageBox.information(self, "Success", f"Docs CSV saved to: {output_path}\n\nMarketplaces: {', '.join(files_used)}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"{e}")
    
    def export_b2b(self):
        """Generate B2B invoices CSV."""
        try:
            fy = int(self.year_combo.currentText())
            mn = int(self.month_combo.currentText())
            gstin = self.supplier_combo.currentText()  # Now a GSTIN string, not supplier_id
            csv_path = generate_b2b_csv(fy, mn, gstin, self.db, output_folder=self.base_folder)
            QMessageBox.information(self, "Success", f"B2B CSV saved at:\n{csv_path}")
            self.debug_output.append(f"✅ Generated: {csv_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Generation failed: {e}")
            self.debug_output.append(f"❌ Error: {e}")
    
    def export_hsn_b2b(self):
        """Generate HSN B2B summary CSV."""
        try:
            fy = int(self.year_combo.currentText())
            mn = int(self.month_combo.currentText())
            gstin = self.supplier_combo.currentText()  # Now a GSTIN string, not supplier_id
            csv_path = generate_hsn_b2b_csv(fy, mn, gstin, self.db, output_folder=self.base_folder)
            QMessageBox.information(self, "Success", f"HSN B2B CSV saved at:\n{csv_path}")
            self.debug_output.append(f"✅ Generated: {csv_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Generation failed: {e}")
            self.debug_output.append(f"❌ Error: {e}")
    
    def export_b2cl(self):
        """Generate B2CL large invoices CSV."""
        try:
            fy = int(self.year_combo.currentText())
            mn = int(self.month_combo.currentText())
            gstin = self.supplier_combo.currentText()  # Now a GSTIN string, not supplier_id
            csv_path = generate_b2cl_csv(fy, mn, gstin, self.db, output_folder=self.base_folder)
            QMessageBox.information(self, "Success", f"B2CL CSV saved at:\n{csv_path}")
            self.debug_output.append(f"✅ Generated: {csv_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Generation failed: {e}")
            self.debug_output.append(f"❌ Error: {e}")
    
    def export_cdnr(self):
        """Generate credit/debit notes CSV."""
        try:
            fy = int(self.year_combo.currentText())
            mn = int(self.month_combo.currentText())
            gstin = self.supplier_combo.currentText()  # Now a GSTIN string, not supplier_id
            csv_path = generate_cdnr_csv(fy, mn, gstin, self.db, output_folder=self.base_folder)
            QMessageBox.information(self, "Success", f"CDNR CSV saved at:\n{csv_path}")
            self.debug_output.append(f"✅ Generated: {csv_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Generation failed: {e}")
            self.debug_output.append(f"❌ Error: {e}")
    
    def export_gstr1_excel(self):
        """Generate complete GSTR-1 Excel workbook with all sheets."""
        try:
            fy = int(self.year_combo.currentText())
            mn = int(self.month_combo.currentText())
            gstin = self.supplier_combo.currentText()  # Now a GSTIN string, not supplier_id
            excel_path = generate_gstr1_excel_workbook(fy, mn, gstin, self.db, output_folder=self.base_folder)
            QMessageBox.information(self, "Success", f"Complete GSTR-1 Excel saved at:\n{excel_path}")
            self.debug_output.append(f"✅ Generated: {excel_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Generation failed: {e}")
            self.debug_output.append(f"❌ Error: {e}")
    
    # ========================================================================
    # ANALYTICS HANDLERS - CONSOLIDATED FOR BUSINESS GROWTH FOCUS
    # ========================================================================
    
    def show_growth_dashboard(self):
        """Save comprehensive growth dashboard to file: multi-marketplace overview + customer insights."""
        from datetime import datetime
        
        # Get filter values
        fy = self.year_combo.currentText()
        month = self.month_combo.currentText()
        supplier = self.supplier_combo.currentText()
        
        try:
            # Pass filters to analytics (if "All" is selected, pass None for no filtering)
            fy_filter = None if fy == "All" else fy
            month_filter = None if month == "All" else int(month)
            gstin_filter = None if supplier == "All" else supplier
            
            analytics = get_business_dashboard_analytics(self.db, fy_filter, month_filter, gstin_filter)
            
            if 'error' in analytics:
                QMessageBox.warning(self, "Error", f"Growth dashboard error: {analytics['error']}")
                return
            
            # Overview
            overview = analytics.get('overview', {})
            marketplace = analytics.get('marketplace_breakdown', {})
            status = analytics.get('status_breakdown', {})
            top_products = analytics.get('top_products', [])
            top_states = analytics.get('top_states', [])
            financial = analytics.get('financial_summary', {})
            
            # Build report content
            filter_parts = []
            if fy != "All":
                filter_parts.append(f"FY: {fy}")
            if month != "All":
                filter_parts.append(f"Month: {month}")
            if supplier != "All":
                filter_parts.append(f"Supplier: {supplier}")
            filter_info = " | ".join(filter_parts) if filter_parts else "All Time Data"
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            report_lines = [
                "="*80,
                "GROWTH DASHBOARD - Multi-Marketplace Overview",
                "="*80,
                f"Generated: {timestamp}",
                f"Filters: {filter_info}",
                "",
                "BUSINESS OVERVIEW",
                "-"*80,
                f"Total Orders:        {overview.get('total_orders', 0):,}",
                f"Total Quantity:      {overview.get('total_quantity', 0):,} units",
                f"Total Revenue:       ₹{overview.get('total_revenue', 0):,.2f}",
                f"Avg Order Value:     ₹{overview.get('avg_order_value', 0):,.2f}",
                ""
            ]
            
            # Marketplace breakdown
            if marketplace:
                report_lines.append("MARKETPLACE BREAKDOWN")
                report_lines.append("-"*80)
                for name, stats in marketplace.items():
                    report_lines.append(f"  {name:20} {stats.get('orders', 0):,} orders | ₹{stats.get('revenue', 0):,.2f}")
                report_lines.append("")
            
            # Order status
            if status:
                report_lines.append("ORDER STATUS")
                report_lines.append("-"*80)
                report_lines.append(f"  Delivered:         {status.get('delivered', 0):,}")
                report_lines.append(f"  RTO:               {status.get('rto', 0):,}")
                report_lines.append(f"  Returned:          {status.get('returned', 0):,}")
                report_lines.append(f"  Cancelled:         {status.get('cancelled', 0):,}")
                report_lines.append(f"  In Transit:        {status.get('in_transit', 0):,}")
                report_lines.append("")
            
            # Financial Summary
            if financial:
                report_lines.append("FINANCIAL SUMMARY")
                report_lines.append("-"*80)
                report_lines.append(f"  Total Sales:       ₹{financial.get('total_sales', 0):,.2f}")
                report_lines.append(f"  Commission:        ₹{financial.get('total_commission', 0):,.2f}")
                report_lines.append(f"  Platform Fee:      ₹{financial.get('total_platform_fee', 0):,.2f}")
                report_lines.append(f"  Net Payout:        ₹{financial.get('net_payout', 0):,.2f}")
                report_lines.append("")
            
            # Top Products
            if top_products:
                report_lines.append("TOP 10 PRODUCTS (by quantity)")
                report_lines.append("-"*80)
                for i, product in enumerate(top_products[:10], 1):
                    product_name = product['product_name'][:50]
                    report_lines.append(f"  {i:2}. [{product['marketplace']}] {product_name}")
                    report_lines.append(f"      Qty: {product['total_quantity']:,} | Revenue: ₹{product['total_revenue']:,.2f}")
                report_lines.append("")
            
            # Top States
            if top_states:
                report_lines.append("TOP 10 STATES BY REVENUE")
                report_lines.append("-"*80)
                for i, state in enumerate(top_states[:10], 1):
                    report_lines.append(f"  {i:2}. {state['state']:30} ₹{state['revenue']:,.2f}")
                report_lines.append("")
            
            # Customer Insights
            customer_analytics = get_customer_segmentation_analytics(self.db)
            if 'error' not in customer_analytics:
                top_regions = customer_analytics.get('top_regions', [])
                if top_regions:
                    report_lines.append("CUSTOMER TARGETING - TOP REGIONS")
                    report_lines.append("-"*80)
                    for i, region in enumerate(top_regions[:10], 1):
                        report_lines.append(
                            f"  {i:2}. {region['customer_state']:30} "
                            f"{region['order_count']:,} orders | "
                            f"₹{region['total_revenue']:,.2f} ({region['revenue_share_pct']:.1f}%)"
                        )
            
            report_lines.append("")
            report_lines.append("="*80)
            report_lines.append("End of Report")
            report_lines.append("="*80)
            
            # Save to file
            filename = f"growth_dashboard_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            filepath = os.path.join(self.base_folder, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write('\n'.join(report_lines))
            
            QMessageBox.information(self, "Success", f"✅ Growth dashboard saved to:\n{filepath}")
            
        except Exception as e:
            error_details = traceback.format_exc()
            QMessageBox.critical(self, "Error", f"Failed to generate dashboard:\n{e}\n\n{error_details}")
    
    def show_financial_profitability(self):
        """Save comprehensive financial analysis to file."""
        from datetime import datetime
        
        # Get filter values
        fy = self.year_combo.currentText()
        month = self.month_combo.currentText()
        supplier = self.supplier_combo.currentText()
        
        try:
            # Pass filters to analytics (if "All" is selected, pass None for no filtering)
            fy_filter = None if fy == "All" else fy
            month_filter = None if month == "All" else int(month)
            gstin_filter = None if supplier == "All" else supplier
            
            # Get financial analysis data
            financial = get_financial_analysis(self.db, fy_filter, month_filter, gstin_filter)
            
            if 'error' in financial:
                QMessageBox.warning(self, "Error", f"Financial analysis error: {financial['error']}")
                return
            
            overview = financial.get('overview', {})
            order_status = financial.get('order_status_summary', [])
            costs = financial.get('cost_breakdown', [])
            products = financial.get('product_profitability', [])
            
            # Build report
            filter_parts = []
            if fy != "All":
                filter_parts.append(f"FY: {fy}")
            if month != "All":
                filter_parts.append(f"Month: {month}")
            if supplier != "All":
                filter_parts.append(f"Supplier: {supplier}")
            filter_info = " | ".join(filter_parts) if filter_parts else "All Time Data"
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            report_lines = [
                "="*80,
                "FINANCIAL & PROFITABILITY ANALYSIS",
                "="*80,
                f"Generated: {timestamp}",
                f"Filters: {filter_info}",
                "",
                "REVENUE OVERVIEW",
                "-"*80,
                f"Total Sales (All Orders):    ₹{overview.get('total_sales', 0):,.2f}",
                f"  - Delivered Revenue:        ₹{overview.get('delivered_revenue', 0):,.2f}",
                f"  - Returned Revenue:         ₹{overview.get('returned_revenue', 0):,.2f}",
                f"Total Returns (Refunds):      ₹{overview.get('total_returns', 0):,.2f}",
                f"Net Sales:                    ₹{overview.get('net_sales', 0):,.2f}",
                "",
                f"SETTLEMENT:                   ₹{overview.get('total_settlement', 0):,.2f}",
                "",
                "COST BREAKDOWN",
                "-"*80,
                f"COGS - Delivered Orders:      ₹{overview.get('delivered_cogs', 0):,.2f}",
                f"COGS - RTO Damaged ({overview.get('rto_count', 0)} orders):    ₹{overview.get('rto_cogs', 0):,.2f}",
                f"COGS - Returns Damaged ({overview.get('returned_count', 0)} returns): ₹{overview.get('returned_cogs', 0):,.2f}",
                f"COGS - Cancelled:             ₹{overview.get('cancelled_cogs', 0):,.2f}",
                f"Total COGS:                   ₹{overview.get('total_cogs', 0):,.2f}",
                f"Packing (incl. repacking):    ₹{overview.get('total_costs', 0) - overview.get('total_cogs', 0):,.2f}",
                f"Return Shipping:              ₹{overview.get('total_return_shipping', 0):,.2f}",
                f"Total Out-of-Pocket Costs:    ₹{overview.get('total_costs', 0):,.2f}",
                f"Less: Compensation/Claims:    ₹{overview.get('total_compensation_claims', 0):,.2f}",
                f"Net Costs After Compensation: ₹{overview.get('net_costs_after_compensation', 0):,.2f}",
                "",
                "PROFITABILITY",
                "-"*80,
                f"GROSS PROFIT:                 ₹{overview.get('gross_profit', 0):,.2f}",
                f"PROFIT MARGIN:                {overview.get('profit_margin', 0):.1f}%",
                "",
                "ORDER STATUS SUMMARY",
                "-"*80
            ]
            
            for status in order_status:
                report_lines.append(f"  {status['status']:20} ({status['orders']:,} orders)  ₹{status['payout']:,.2f}")
            
            report_lines.append("")
            report_lines.append("DETAILED COSTS (% of Net Sales)")
            report_lines.append("-"*80)
            for cost in costs:
                report_lines.append(f"  {cost['category']:30} ₹{cost['amount']:,.2f} ({cost['percentage']:.1f}%)")
            
            report_lines.append("")
            report_lines.append("TOP 20 REVENUE GENERATORS")
            report_lines.append("-"*80)
            for i, product in enumerate(products[:20], 1):
                product_name = product['product_name'][:50]
                report_lines.append(f"  {i:2}. {product_name}")
                report_lines.append(f"      Qty: {product['quantity']:,} | Revenue: ₹{product['revenue']:,.2f} | Profit: ₹{product['gross_profit']:,.2f} | Margin: {product['profit_margin']:.1f}%")
            
            report_lines.append("")
            report_lines.append("="*80)
            report_lines.append("End of Report")
            report_lines.append("="*80)
            
            # Save to file
            filename = f"financial_profitability_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            filepath = os.path.join(self.base_folder, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write('\n'.join(report_lines))
            
            QMessageBox.information(self, "Success", f"✅ Financial analysis saved to:\n{filepath}")
            
        except Exception as e:
            error_details = traceback.format_exc()
            QMessageBox.critical(self, "Error", f"Failed to generate analysis:\n{e}\n\n{error_details}")
    
    def show_inventory_actions(self):
        """Save inventory insights + prioritized action items to file."""
        from datetime import datetime
        
        # Get filter values
        fy = self.year_combo.currentText()
        month = self.month_combo.currentText()
        supplier = self.supplier_combo.currentText()
        
        try:
            # Pass filters to analytics (if "All" is selected, pass None for no filtering)
            fy_filter = None if fy == "All" else fy
            month_filter = None if month == "All" else int(month)
            gstin_filter = None if supplier == "All" else supplier
            
            # Get analytics
            inventory = get_product_inventory_insights(self.db, fy_filter, month_filter, gstin_filter)
            actions = get_action_items_analytics(self.db, fy_filter, month_filter, gstin_filter)
            
            if 'error' in inventory:
                QMessageBox.warning(self, "Error", f"Inventory error: {inventory['error']}")
                return
            
            filter_parts = []
            if fy != "All":
                filter_parts.append(f"FY: {fy}")
            if month != "All":
                filter_parts.append(f"Month: {month}")
            if supplier != "All":
                filter_parts.append(f"Supplier: {supplier}")
            filter_info = " | ".join(filter_parts) if filter_parts else "All Time Data"
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            report_lines = [
                "="*80,
                "INVENTORY & ACTIONS - Purchasing Decisions & Alerts",
                "="*80,
                f"Generated: {timestamp}",
                f"Filters: {filter_info}",
                "",
                "INVENTORY SUMMARY",
                "-"*80
            ]
            
            summary = inventory.get('summary', {})
            report_lines.append(f"  Total Products:    {summary.get('total_products', 0):,}")
            report_lines.append(f"  Out of Stock:      {summary.get('out_of_stock', 0):,}")
            report_lines.append(f"  Low Stock:         {summary.get('low_stock', 0):,}")
            report_lines.append(f"  Dead Stock:        {summary.get('dead_stock', 0):,}")
            report_lines.append(f"  High Returns:      {summary.get('high_returns', 0):,}")
            report_lines.append(f"  Healthy:           {summary.get('healthy', 0):,}")
            report_lines.append("")
            
            # Products requiring action
            products = inventory.get('products', [])
            if products:
                report_lines.append("PRODUCTS REQUIRING ACTION (Top 20)")
                report_lines.append("-"*80)
                
                action_needed = [p for p in products if p['status'] != 'HEALTHY'][:20]
                for i, product in enumerate(action_needed, 1):
                    status_icon = {
                        'OUT_OF_STOCK': '[OUT OF STOCK]',
                        'LOW_STOCK': '[LOW STOCK]',
                        'DEAD_STOCK': '[DEAD STOCK]',
                        'HIGH_RETURNS': '[HIGH RETURNS]'
                    }.get(product['status'], '')
                    
                    report_lines.append(f"  {i:2}. {status_icon} {product['product_name'][:60]}")
                    report_lines.append(f"      Stock: {product['current_stock']:,} | Sales(30d): {product['sales_30d']:,} | Days Left: {product['days_remaining']}")
                    report_lines.append(f"      Return Rate: {product['return_rate']:.1f}%")
                    report_lines.append(f"      ACTION: {product['action']}")
                    report_lines.append("")
            
            # Prioritized action items
            if 'error' not in actions:
                action_summary = actions.get('summary', {})
                report_lines.append("PRIORITIZED ACTION ITEMS SUMMARY")
                report_lines.append("-"*80)
                report_lines.append(f"  Critical:          {action_summary.get('critical', 0):,}")
                report_lines.append(f"  High:              {action_summary.get('high', 0):,}")
                report_lines.append(f"  Medium:            {action_summary.get('medium', 0):,}")
                report_lines.append(f"  Low:               {action_summary.get('low', 0):,}")
                report_lines.append("")
                
                items = actions.get('action_items', [])
                if items:
                    report_lines.append("TOP 15 ACTION ITEMS")
                    report_lines.append("-"*80)
                    
                    for i, item in enumerate(items[:15], 1):
                        priority_icon = {
                            'CRITICAL': '[CRITICAL]',
                            'HIGH': '[HIGH]',
                            'MEDIUM': '[MEDIUM]',
                            'LOW': '[LOW]'
                        }.get(item['priority'], '')
                        
                        report_lines.append(f"  {i:2}. {priority_icon} {item['category']}: {item['issue']}")
                        report_lines.append(f"      Impact: {item['impact']}")
                        report_lines.append(f"      Action: {item['action']}")
                        report_lines.append("")
            
            report_lines.append("="*80)
            report_lines.append("End of Report")
            report_lines.append("="*80)
            
            # Save to file
            filename = f"inventory_actions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            filepath = os.path.join(self.base_folder, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write('\n'.join(report_lines))
            
            QMessageBox.information(self, "Success", f"✅ Inventory & Actions report saved to:\n{filepath}")
            
        except Exception as e:
            error_details = traceback.format_exc()
            QMessageBox.critical(self, "Error", f"Failed to generate insights:\n{e}\n\n{error_details}")
    
    def show_gst_compliance(self):
        """Save GST & invoice analytics + compliance audit to file."""
        from datetime import datetime
        
        # Get filter values
        fy = self.year_combo.currentText()
        month = self.month_combo.currentText()
        supplier = self.supplier_combo.currentText()
        
        try:
            # Pass filters to analytics (if "All" is selected, pass None for no filtering)
            fy_filter = None if fy == "All" else fy
            month_filter = None if month == "All" else int(month)
            gstin_filter = None if supplier == "All" else supplier
            
            # Get analytics
            gst_analytics = get_enhanced_gst_analytics(self.db, fy_filter, month_filter, gstin_filter)
            invoice_analytics = get_invoice_analytics(self.db, fy_filter, month_filter, gstin_filter)
            compliance = get_compliance_audit_analytics(self.db, fy_filter, month_filter, gstin_filter)
            
            filter_parts = []
            if fy != "All":
                filter_parts.append(f"FY: {fy}")
            if month != "All":
                filter_parts.append(f"Month: {month}")
            if supplier != "All":
                filter_parts.append(f"Supplier: {supplier}")
            filter_info = " | ".join(filter_parts) if filter_parts else "All Time Data"
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            report_lines = [
                "="*80,
                "GST & COMPLIANCE - Tax Filing & Audit",
                "="*80,
                f"Generated: {timestamp}",
                f"Filters: {filter_info}",
                ""
            ]
            
            # Invoice Analytics
            if 'error' not in invoice_analytics:
                report_lines.append("INVOICE OVERVIEW")
                report_lines.append("-"*80)
                report_lines.append(f"  Total Invoices:          {invoice_analytics.get('total_invoices', 0):,}")
                report_lines.append(f"  Total Orders:            {invoice_analytics.get('total_orders', 0):,}")
                report_lines.append(f"  Completion Rate:         {invoice_analytics.get('completion_rate', 0):.2f}%")
                report_lines.append(f"  Avg Invoicing Speed:     {invoice_analytics.get('avg_invoicing_speed_days', 0):.1f} days")
                report_lines.append(f"  HSN Coverage:            {invoice_analytics.get('hsn_coverage_rate', 0):.2f}%")
                report_lines.append(f"  Credit Note Rate:        {invoice_analytics.get('credit_note_rate', 0):.2f}%")
                report_lines.append(f"  Pending Invoices:        {invoice_analytics.get('pending_invoice_count', 0):,}")
                report_lines.append("")
                
                top_products = invoice_analytics.get('top_invoiced_products', [])
                if top_products:
                    report_lines.append("TOP 10 INVOICED PRODUCTS")
                    report_lines.append("-"*80)
                    for i, (product, count) in enumerate(top_products[:10], 1):
                        report_lines.append(f"  {i:2}. {product[:60]:60} {count:,}")
                    report_lines.append("")
            
            # GST Tax Analytics
            if 'error' not in gst_analytics:
                report_lines.append("GST TAX OVERVIEW")
                report_lines.append("-"*80)
                report_lines.append(f"  Net Tax Liability:       ₹{gst_analytics.get('net_tax_liability', 0):,.2f}")
                report_lines.append(f"  Total Sales Tax:         ₹{gst_analytics.get('total_sales_tax', 0):,.2f}")
                report_lines.append(f"  Total Return Tax:        ₹{gst_analytics.get('total_return_tax', 0):,.2f}")
                report_lines.append(f"  Total Taxable Value:     ₹{gst_analytics.get('total_taxable_value', 0):,.2f}")
                report_lines.append(f"  Total with Tax:          ₹{gst_analytics.get('total_value_with_tax', 0):,.2f}")
                report_lines.append(f"  Total Transactions:      {gst_analytics.get('total_transactions', 0):,}")
                report_lines.append("")
                
                top_states = gst_analytics.get('gst_by_state', [])
                if top_states:
                    report_lines.append("TOP 15 STATES BY TAX LIABILITY")
                    report_lines.append("-"*80)
                    for i, (state, tax) in enumerate(top_states[:15], 1):
                        report_lines.append(f"  {i:2}. {state[:40]:40} ₹{tax:,.2f}")
                    report_lines.append("")
                
                filing = gst_analytics.get('filing_ready', {})
                if filing:
                    report_lines.append("GSTR-1 FILING READINESS")
                    report_lines.append("-"*80)
                    report_lines.append(f"  Sales Data:              {'Yes' if filing.get('has_sales_data') else 'No'}")
                    report_lines.append(f"  Return Data:             {'Yes' if filing.get('has_return_data') else 'No'}")
                    report_lines.append(f"  HSN Codes:               {'Complete' if filing.get('hsn_codes_present') else 'Missing'}")
                    report_lines.append(f"  State Info:              {'Complete' if filing.get('state_info_complete') else 'Incomplete'}")
                    report_lines.append("")
            
            # Compliance Audit
            if 'error' not in compliance:
                comp_summary = compliance.get('summary', {})
                report_lines.append("COMPLIANCE AUDIT")
                report_lines.append("-"*80)
                report_lines.append(f"  Total Invoices:          {comp_summary.get('total_invoices', 0):,}")
                report_lines.append(f"  Duplicate Invoices:      {comp_summary.get('duplicate_invoices', 0):,}")
                report_lines.append(f"  HSN Anomalies:           {comp_summary.get('hsn_anomalies', 0):,}")
                report_lines.append("")
                
                issues = compliance.get('issues', [])
                if issues:
                    report_lines.append("COMPLIANCE ISSUES FOUND")
                    report_lines.append("-"*80)
                    for i, issue in enumerate(issues[:20], 1):
                        report_lines.append(f"  {i:2}. {issue['type']} - Invoice: {issue.get('invoice_no', 'N/A')}")
                else:
                    report_lines.append("NO COMPLIANCE ISSUES - All Clear!")
                    report_lines.append("-"*80)
            
            report_lines.append("")
            report_lines.append("="*80)
            report_lines.append("End of Report")
            report_lines.append("="*80)
            
            # Save to file
            filename = f"gst_compliance_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            filepath = os.path.join(self.base_folder, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write('\n'.join(report_lines))
            
            QMessageBox.information(self, "Success", f"✅ GST & Compliance report saved to:\n{filepath}")
            
        except Exception as e:
            error_details = traceback.format_exc()
            QMessageBox.critical(self, "Error", f"Failed to generate analysis:\n{e}\n\n{error_details}")

    def update_table(self, data, headers):
        self.table.setRowCount(len(data))
        self.table.setColumnCount(len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        for r, row in enumerate(data):
            for c, val in enumerate(row):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignCenter)
                self.table.setItem(r, c, item)
                


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = DashboardApp()
    w.show()
    sys.exit(app.exec())

