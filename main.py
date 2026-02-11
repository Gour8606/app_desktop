import sys
import os
import json
import re
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QPushButton, QComboBox,
    QVBoxLayout, QWidget, QTableWidget, QTableWidgetItem, QTextEdit,
    QFileDialog, QMessageBox, QHBoxLayout, QDialog, QProgressBar
)
from PySide6.QtCore import Qt



from database import SessionLocal, engine, Base
from models import MeeshoSale
from import_logic import (
    import_from_zip, import_invoice_data, import_flipkart_sales, import_flipkart_b2c,
    import_amazon_mtr, import_amazon_gstr1,
    validate_meesho_tax_invoice_zip, validate_invoices_zip,
    validate_flipkart_sales_excel, validate_flipkart_gst_excel, validate_amazon_zip
)
from docissued import append_meesho_docs_from_db, append_flipkart_docs_from_db, append_amazon_docs_from_db
from logic import (
    generate_gst_pivot_csv, generate_gst_hsn_pivot_csv,
    generate_b2b_csv, generate_hsn_b2b_csv, generate_b2cl_csv, generate_cdnr_csv, generate_gstr1_excel_workbook
)
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
        

        # Style all buttons
        all_buttons = [
            self.btn_upload, self.btn_import_invoices,
            self.btn_import_flipkart_sales, self.btn_import_flipkart_gst,
            self.btn_import_amazon_b2b, self.btn_import_amazon_b2c, self.btn_import_amazon_gstr1,
            self.btn_b2cs_csv, self.btn_hsn_csv, self.btn_b2b, self.btn_hsn_b2b,
            self.btn_b2cl, self.btn_cdnr, self.btn_docs_csv, self.btn_gstr1_excel
        ]
        for btn in all_buttons:
            btn.setFixedHeight(35)
            btn.setMinimumWidth(140)

        # Row 1: Import data
        layout.addWidget(QLabel("Import Data:"))
        row1 = QHBoxLayout()
        row1.addWidget(self.btn_upload)
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
        

    # --- Helper UI methods ---
    def _label_text(self, name, path):
        return f"{name}: {os.path.basename(path) if path else 'Not Selected'}"

    # Manual selectors
    # --- Config load/save ---
    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    cfg = json.load(f)
                self.base_folder = cfg.get("base_folder", os.getcwd())
                self.meesho_file = cfg.get("meesho_file", "")
                self.flipkart_file = cfg.get("flipkart_file", "")
                self.amz_gstr_file = cfg.get("amz_gstr_file", "")
                self.amz_mtr_file = cfg.get("amz_mtr_file", "")
            except (json.JSONDecodeError, IOError):
                pass

    def save_config(self):
        cfg = {
            "base_folder": self.base_folder,
            "meesho_file": self.meesho_file,
            "flipkart_file": self.flipkart_file,
            "amz_gstr_file": self.amz_gstr_file,
            "amz_mtr_file": self.amz_mtr_file
        }
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f)

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

            # Save the Excel path so B2CS/HSN generators use official certified values
            from logic import set_flipkart_gst_excel_path
            set_flipkart_gst_excel_path(file_path)

            QMessageBox.information(self, "Success", "Flipkart GST data imported successfully!\n\nOfficial GST values will be used for B2CS and HSN reports.")
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

    def _validate_gstin_selected(self):
        """Validate that a valid GSTIN is selected. Returns (gstin, True) or (None, False)."""
        gstin = self.supplier_combo.currentText().strip()
        if not gstin or len(gstin) != 15:
            QMessageBox.warning(
                self, "No Seller Selected",
                "Please select a valid Seller GSTIN before generating reports."
            )
            return None, False
        return gstin, True

    def generate_b2cs_csv(self):
        gstin, valid = self._validate_gstin_selected()
        if not valid:
            return
        try:
            fy = int(self.year_combo.currentText())
            mn = int(self.month_combo.currentText())
            csv_debug = generate_gst_pivot_csv(fy, mn, gstin, self.db,
                output_folder=self.base_folder)
            QMessageBox.information(self, "Success", "B2CS CSV generated.")
            self.debug_output.append(csv_debug)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"{e}")

    def generate_hsn_csv(self):
        gstin, valid = self._validate_gstin_selected()
        if not valid:
            return
        try:
            fy = int(self.year_combo.currentText())
            mn = int(self.month_combo.currentText())
            debug_csv = generate_gst_hsn_pivot_csv(fy, mn, gstin, self.db,
                output_folder=self.base_folder)
            QMessageBox.information(self, "Success", "HSN WISE B2CS CSV generated.")
            self.debug_output.append(debug_csv)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"{e}")

    def generate_docs_csv(self):
        gstin, valid = self._validate_gstin_selected()
        if not valid:
            return
        try:
            
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
        gstin, valid = self._validate_gstin_selected()
        if not valid:
            return
        try:
            fy = int(self.year_combo.currentText())
            mn = int(self.month_combo.currentText())
            csv_path = generate_b2b_csv(fy, mn, gstin, self.db, output_folder=self.base_folder)
            QMessageBox.information(self, "Success", f"B2B CSV saved at:\n{csv_path}")
            self.debug_output.append(f"✅ Generated: {csv_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Generation failed: {e}")
            self.debug_output.append(f"❌ Error: {e}")

    def export_hsn_b2b(self):
        """Generate HSN B2B summary CSV."""
        gstin, valid = self._validate_gstin_selected()
        if not valid:
            return
        try:
            fy = int(self.year_combo.currentText())
            mn = int(self.month_combo.currentText())
            csv_path = generate_hsn_b2b_csv(fy, mn, gstin, self.db, output_folder=self.base_folder)
            QMessageBox.information(self, "Success", f"HSN B2B CSV saved at:\n{csv_path}")
            self.debug_output.append(f"✅ Generated: {csv_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Generation failed: {e}")
            self.debug_output.append(f"❌ Error: {e}")

    def export_b2cl(self):
        """Generate B2CL large invoices CSV."""
        gstin, valid = self._validate_gstin_selected()
        if not valid:
            return
        try:
            fy = int(self.year_combo.currentText())
            mn = int(self.month_combo.currentText())
            csv_path = generate_b2cl_csv(fy, mn, gstin, self.db, output_folder=self.base_folder)
            QMessageBox.information(self, "Success", f"B2CL CSV saved at:\n{csv_path}")
            self.debug_output.append(f"✅ Generated: {csv_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Generation failed: {e}")
            self.debug_output.append(f"❌ Error: {e}")

    def export_cdnr(self):
        """Generate credit/debit notes CSV."""
        gstin, valid = self._validate_gstin_selected()
        if not valid:
            return
        try:
            fy = int(self.year_combo.currentText())
            mn = int(self.month_combo.currentText())
            csv_path = generate_cdnr_csv(fy, mn, gstin, self.db, output_folder=self.base_folder)
            QMessageBox.information(self, "Success", f"CDNR CSV saved at:\n{csv_path}")
            self.debug_output.append(f"✅ Generated: {csv_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Generation failed: {e}")
            self.debug_output.append(f"❌ Error: {e}")

    def export_gstr1_excel(self):
        """Generate complete GSTR-1 Excel workbook with all sheets."""
        gstin, valid = self._validate_gstin_selected()
        if not valid:
            return
        try:
            fy = int(self.year_combo.currentText())
            mn = int(self.month_combo.currentText())
            excel_path = generate_gstr1_excel_workbook(fy, mn, gstin, self.db, output_folder=self.base_folder)
            QMessageBox.information(self, "Success", f"Complete GSTR-1 Excel saved at:\n{excel_path}")
            self.debug_output.append(f"✅ Generated: {excel_path}")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Generation failed: {e}")
            self.debug_output.append(f"❌ Error: {e}")
    

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

