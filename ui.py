# UI logic for the Meesho Sales App
# Extracted from main.py for modularity

import sys
import os
import json
import re
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QLabel, QPushButton, QComboBox,
    QVBoxLayout, QWidget, QTableWidget, QTableWidgetItem, QTextEdit,
    QFileDialog, QMessageBox, QHBoxLayout, QDialog, QProgressBar, QInputDialog,
    QScrollArea, QGridLayout
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from database import SessionLocal
from models import MeeshoSale, MeeshoOrder
from import_logic import (
    import_from_zip, import_invoice_data, import_inventory_data, 
    import_payments_data, import_flipkart_sales, import_amazon_sales
)
from logic import (
    generate_gst_pivot_csv, generate_gst_hsn_pivot_csv, get_invoice_analytics, 
    get_enhanced_gst_analytics, generate_b2b_csv, generate_hsn_b2b_csv, 
    generate_b2cl_csv, generate_cdnr_csv, generate_gstr1_excel_workbook,
    get_monthly_summary, get_order_analytics, generate_returns_json
)
from analytics import (
    get_inventory_analytics, get_payment_analytics, 
    get_predictive_alerts_analytics, get_advanced_product_analytics
)
from export import generate_catalog_summary_csv
from constants import Config
from error_handler import handle_export_errors
from docissued import generate_docs_issued_csv

CONFIG_FILE = Config.CONFIG_FILE


class DashboardApp(QMainWindow):
    """Main application window for Meesho Sales & GST Dashboard."""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("📊 Meesho Sales & GST Dashboard - Multi-Marketplace Platform")
        self.setGeometry(100, 100, 1400, 900)
        
        # Initialize database session
        self.db = SessionLocal()
        
        # Load configuration
        self.config = self.load_config()
        
        # Set up UI
        self.init_ui()
    
    def init_ui(self):
        """Initialize the user interface."""
        # Main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        
        # Title label
        title_label = QLabel("📊 Multi-Marketplace GST Dashboard")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        # Subtitle
        subtitle_label = QLabel("Meesho | Flipkart | Amazon - GSTR-1 Compliant Reports")
        subtitle_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(subtitle_label)
        
        # Selection panel
        selection_layout = QHBoxLayout()
        
        # Financial Year dropdown
        fy_label = QLabel("Financial Year:")
        self.fy_combo = QComboBox()
        self.fy_combo.addItems([str(y) for y in range(2020, 2031)])
        self.fy_combo.setCurrentText(str(self.config.get("financial_year", 2024)))
        
        # Month dropdown
        month_label = QLabel("Month:")
        self.month_combo = QComboBox()
        months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", 
                  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        self.month_combo.addItems(months)
        self.month_combo.setCurrentIndex(self.config.get("month_number", 1) - 1)
        
        # Supplier dropdown
        supplier_label = QLabel("Supplier:")
        self.supplier_combo = QComboBox()
        self.supplier_combo.addItems(["1258379", "567538", "3268023"])
        self.supplier_combo.setCurrentText(str(self.config.get("supplier_id", 1258379)))
        
        selection_layout.addWidget(fy_label)
        selection_layout.addWidget(self.fy_combo)
        selection_layout.addWidget(month_label)
        selection_layout.addWidget(self.month_combo)
        selection_layout.addWidget(supplier_label)
        selection_layout.addWidget(self.supplier_combo)
        selection_layout.addStretch()
        
        main_layout.addLayout(selection_layout)
        
        # Button panel - Import buttons
        import_label = QLabel("📥 Import Data:")
        import_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        main_layout.addWidget(import_label)
        
        import_layout = QHBoxLayout()
        
        # Meesho imports
        self.btn_import_zip = QPushButton("📦 Import Meesho ZIP")
        self.btn_import_inventory = QPushButton("📋 Import Inventory")
        self.btn_import_payments = QPushButton("💰 Import Payments")
        self.btn_import_invoices = QPushButton("📄 Import Invoices")
        
        # Flipkart imports
        self.btn_import_flipkart = QPushButton("🛒 Import Flipkart")
        self.btn_import_flipkart_gst = QPushButton("📊 Import Flipkart GST Excel")
        
        # Amazon imports
        self.btn_import_amazon = QPushButton("📦 Import Amazon")
        
        for btn in [self.btn_import_zip, self.btn_import_inventory, 
                    self.btn_import_payments, self.btn_import_invoices,
                    self.btn_import_flipkart, self.btn_import_flipkart_gst,
                    self.btn_import_amazon]:
            btn.setMinimumHeight(35)
            import_layout.addWidget(btn)
        
        main_layout.addLayout(import_layout)
        
        # Flipkart GST Excel status
        gst_status_layout = QHBoxLayout()
        gst_status_layout.addWidget(QLabel("Flipkart GST Excel Status:"))
        self.label_flipkart_gst_status = QLabel("❌ Not found")
        self.label_flipkart_gst_status.setStyleSheet("color: red;")
        gst_status_layout.addWidget(self.label_flipkart_gst_status)
        gst_status_layout.addStretch()
        main_layout.addLayout(gst_status_layout)
        gst_label = QLabel("📊 Generate GSTR-1 Reports:")
        gst_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        main_layout.addWidget(gst_label)
        
        gst_layout = QHBoxLayout()
        
        self.btn_b2cs = QPushButton("B2CS (Table 7)")
        self.btn_hsn_b2c = QPushButton("HSN (B2C)")
        self.btn_b2b = QPushButton("B2B (Table 4)")
        self.btn_hsn_b2b = QPushButton("HSN (B2B)")
        self.btn_b2cl = QPushButton("B2CL (Table 5)")
        self.btn_cdnr = QPushButton("CDNR (Table 9B)")
        self.btn_docs = QPushButton("Docs (Table 13)")
        self.btn_gstr1_excel = QPushButton("📑 Complete GSTR-1 Excel")
        
        for btn in [self.btn_b2cs, self.btn_hsn_b2c, self.btn_b2b, 
                    self.btn_hsn_b2b, self.btn_b2cl, self.btn_cdnr,
                    self.btn_docs, self.btn_gstr1_excel]:
            btn.setMinimumHeight(35)
            gst_layout.addWidget(btn)
        
        main_layout.addLayout(gst_layout)
        
        # Returns JSON Generator section
        returns_label = QLabel("📋 Returns JSON Generator:")
        returns_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        main_layout.addWidget(returns_label)
        
        returns_layout = QGridLayout()
        
        # B2CS file selection
        returns_layout.addWidget(QLabel("B2CS CSV:"), 0, 0)
        self.btn_browse_b2cs = QPushButton("Browse...")
        self.label_b2cs_file = QLabel("No file selected")
        self.label_b2cs_file.setStyleSheet("color: gray; font-size: 9pt;")
        self.btn_browse_b2cs.setMaximumWidth(100)
        returns_layout.addWidget(self.btn_browse_b2cs, 0, 1)
        returns_layout.addWidget(self.label_b2cs_file, 0, 2)
        
        # HSN file selection
        returns_layout.addWidget(QLabel("HSN CSV:"), 1, 0)
        self.btn_browse_hsn = QPushButton("Browse...")
        self.label_hsn_file = QLabel("No file selected")
        self.label_hsn_file.setStyleSheet("color: gray; font-size: 9pt;")
        self.btn_browse_hsn.setMaximumWidth(100)
        returns_layout.addWidget(self.btn_browse_hsn, 1, 1)
        returns_layout.addWidget(self.label_hsn_file, 1, 2)
        
        # HSN_SAC Excel file selection (optional)
        returns_layout.addWidget(QLabel("HSN_SAC.xlsx (Optional):"), 2, 0)
        self.btn_browse_hsn_sac = QPushButton("Browse...")
        self.label_hsn_sac_file = QLabel("Not selected")
        self.label_hsn_sac_file.setStyleSheet("color: gray; font-size: 9pt;")
        self.btn_browse_hsn_sac.setMaximumWidth(100)
        returns_layout.addWidget(self.btn_browse_hsn_sac, 2, 1)
        returns_layout.addWidget(self.label_hsn_sac_file, 2, 2)
        
        # Version input
        returns_layout.addWidget(QLabel("Version:"), 3, 0)
        self.input_json_version = QComboBox()
        self.input_json_version.addItems(["GST3.2.3", "GST3.2.2", "GST3.2.1"])
        self.input_json_version.setCurrentText("GST3.2.3")
        self.input_json_version.setMaximumWidth(150)
        returns_layout.addWidget(self.input_json_version, 3, 1)
        
        # Generate button
        self.btn_generate_returns_json = QPushButton("✅ Generate Returns JSON")
        self.btn_generate_returns_json.setMinimumHeight(35)
        self.btn_generate_returns_json.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        returns_layout.addWidget(self.btn_generate_returns_json, 4, 0, 1, 3)
        
        main_layout.addLayout(returns_layout)
        
        # Analytics and Reports buttons
        analytics_label = QLabel("📈 Analytics & Reports:")
        analytics_label.setStyleSheet("font-weight: bold; font-size: 12pt;")
        main_layout.addWidget(analytics_label)
        
        analytics_layout = QHBoxLayout()
        
        self.btn_dashboard = QPushButton("📊 Generate Dashboard")
        self.btn_catalog_summary = QPushButton("📋 Catalog Summary")
        self.btn_refresh = QPushButton("🔄 Refresh View")
        
        for btn in [self.btn_dashboard, self.btn_catalog_summary, self.btn_refresh]:
            btn.setMinimumHeight(35)
            analytics_layout.addWidget(btn)
        
        main_layout.addLayout(analytics_layout)
        
        # Output text area
        output_label = QLabel("📝 Output / Debug:")
        output_label.setStyleSheet("font-weight: bold;")
        main_layout.addWidget(output_label)
        
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setMinimumHeight(300)
        main_layout.addWidget(self.output_text)
        
        # Connect buttons to handlers
        self.connect_signals()
        
        # Show welcome message
        self.show_welcome()
    
    def connect_signals(self):
        """Connect all button signals to their handlers."""
        # Import buttons
        self.btn_import_zip.clicked.connect(self.import_zip)
        self.btn_import_inventory.clicked.connect(self.import_inventory)
        self.btn_import_payments.clicked.connect(self.import_payments)
        self.btn_import_invoices.clicked.connect(self.import_invoices)
        self.btn_import_flipkart.clicked.connect(self.import_flipkart)
        self.btn_import_amazon.clicked.connect(self.import_amazon)
        
        # GST export buttons
        self.btn_b2cs.clicked.connect(self.export_b2cs)
        self.btn_hsn_b2c.clicked.connect(self.export_hsn_b2c)
        self.btn_b2b.clicked.connect(self.export_b2b)
        self.btn_hsn_b2b.clicked.connect(self.export_hsn_b2b)
        self.btn_b2cl.clicked.connect(self.export_b2cl)
        self.btn_cdnr.clicked.connect(self.export_cdnr)
        self.btn_docs.clicked.connect(self.export_docs)
        self.btn_gstr1_excel.clicked.connect(self.export_gstr1_excel)
        
        # Returns JSON buttons
        self.btn_browse_b2cs.clicked.connect(self.browse_b2cs_file)
        self.btn_browse_hsn.clicked.connect(self.browse_hsn_file)
        self.btn_browse_hsn_sac.clicked.connect(self.browse_hsn_sac_file)
        self.btn_generate_returns_json.clicked.connect(self.export_returns_json)
        
        # Analytics buttons
        self.btn_dashboard.clicked.connect(self.generate_dashboard)
        self.btn_catalog_summary.clicked.connect(self.export_catalog_summary)
        self.btn_refresh.clicked.connect(self.refresh_view)
        
        # Dropdown change handlers
        self.fy_combo.currentTextChanged.connect(self.save_config)
        self.month_combo.currentIndexChanged.connect(self.save_config)
        self.supplier_combo.currentTextChanged.connect(self.save_config)
    
    def load_config(self):
        """Load configuration from JSON file."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def save_config(self):
        """Save current selections to configuration file."""
        self.config = {
            "financial_year": int(self.fy_combo.currentText()),
            "month_number": self.month_combo.currentIndex() + 1,
            "supplier_id": int(self.supplier_combo.currentText())
        }
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            self.log(f"⚠️ Could not save config: {e}")
    
    def log(self, message):
        """Append message to output text area."""
        self.output_text.append(message)
        self.output_text.ensureCursorVisible()
    
    def show_welcome(self):
        """Display welcome message."""
        welcome = """
╔══════════════════════════════════════════════════════════════╗
║  Welcome to Meesho Sales & GST Dashboard                    ║
║  Multi-Marketplace Platform (Meesho, Flipkart, Amazon)       ║
╚══════════════════════════════════════════════════════════════╝

📥 Import your data using the import buttons above
📊 Generate GSTR-1 compliant reports for filing
📈 View comprehensive business analytics

✨ Ready to process your marketplace data!
"""
        self.log(welcome)
    
    # ==================== Import Handlers ====================
    
    def import_zip(self):
        """Import Meesho data from ZIP file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Meesho ZIP File", "", "ZIP Files (*.zip)"
        )
        if file_path:
            self.log(f"\n📦 Importing from: {file_path}")
            try:
                result = import_from_zip(file_path, self.db)
                self.log(result)
                QMessageBox.information(self, "Success", "Data imported successfully!")
            except Exception as e:
                self.log(f"❌ Error: {e}")
                QMessageBox.critical(self, "Error", f"Import failed: {e}")
    
    def import_inventory(self):
        """Import inventory data from Excel."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Inventory Excel File", "", "Excel Files (*.xlsx *.xls)"
        )
        if file_path:
            self.log(f"\n📋 Importing inventory from: {file_path}")
            try:
                result = import_inventory_data(file_path, self.db)
                self.log(result)
                QMessageBox.information(self, "Success", "Inventory imported!")
            except Exception as e:
                self.log(f"❌ Error: {e}")
                QMessageBox.critical(self, "Error", f"Import failed: {e}")
    
    def import_payments(self):
        """Import payment data from ZIP."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Payments ZIP File", "", "ZIP Files (*.zip)"
        )
        if file_path:
            self.log(f"\n💰 Importing payments from: {file_path}")
            try:
                result = import_payments_data(file_path, self.db)
                self.log(result)
                QMessageBox.information(self, "Success", "Payments imported!")
            except Exception as e:
                self.log(f"❌ Error: {e}")
                QMessageBox.critical(self, "Error", f"Import failed: {e}")
    
    def import_invoices(self):
        """Import invoice data."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Invoice File", "", "Excel Files (*.xlsx *.xls)"
        )
        if file_path:
            self.log(f"\n📄 Importing invoices from: {file_path}")
            try:
                result = import_invoice_data(file_path, self.db)
                self.log(result)
                QMessageBox.information(self, "Success", "Invoices imported!")
            except Exception as e:
                self.log(f"❌ Error: {e}")
                QMessageBox.critical(self, "Error", f"Import failed: {e}")
    
    def import_flipkart(self):
        """Import Flipkart sales data."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Flipkart Sales Report", "", "Excel Files (*.xlsx *.xls)"
        )
        if file_path:
            self.log(f"\n🛒 Importing Flipkart data from: {file_path}")
            try:
                result = import_flipkart_sales(file_path, self.db)
                self.log(result)
                QMessageBox.information(self, "Success", "Flipkart data imported!")
            except Exception as e:
                self.log(f"❌ Error: {e}")
                QMessageBox.critical(self, "Error", f"Import failed: {e}")
    
    def import_amazon(self):
        """Import Amazon sales data."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Amazon Sales Report", "", "Excel Files (*.xlsx *.xls)"
        )
        if file_path:
            self.log(f"\n📦 Importing Amazon data from: {file_path}")
            try:
                result = import_amazon_sales(file_path, self.db)
                self.log(result)
                QMessageBox.information(self, "Success", "Amazon data imported!")
            except Exception as e:
                self.log(f"❌ Error: {e}")
                QMessageBox.critical(self, "Error", f"Import failed: {e}")
    
    # ==================== GST Export Handlers ====================
    
    def get_export_params(self):
        """Get current financial year, month, and supplier for exports."""
        fy = int(self.fy_combo.currentText())
        month = self.month_combo.currentIndex() + 1
        supplier = self.supplier_combo.currentText()  # Now a GSTIN string, not supplier_id
        return fy, month, supplier
    
    def export_b2cs(self):
        """Export B2CS (B2C Small) CSV."""
        self.log("\n📊 Generating B2CS report...")
        try:
            fy, month, supplier = self.get_export_params()
            result = generate_gst_pivot_csv(fy, month, supplier, self.db)
            self.log(result)
            QMessageBox.information(self, "Success", "B2CS CSV generated!")
        except Exception as e:
            self.log(f"❌ Error: {e}")
            QMessageBox.critical(self, "Error", f"Export failed: {e}")
    
    def export_hsn_b2c(self):
        """Export HSN (B2C) summary."""
        self.log("\n📊 Generating HSN (B2C) report...")
        try:
            fy, month, supplier = self.get_export_params()
            result = generate_gst_hsn_pivot_csv(fy, month, supplier, self.db)
            self.log(result)
            QMessageBox.information(self, "Success", "HSN (B2C) CSV generated!")
        except Exception as e:
            self.log(f"❌ Error: {e}")
            QMessageBox.critical(self, "Error", f"Export failed: {e}")
    
    def export_b2b(self):
        """Export B2B invoices."""
        self.log("\n📊 Generating B2B report...")
        try:
            fy, month, supplier = self.get_export_params()
            result = generate_b2b_csv(fy, month, supplier, self.db)
            self.log(result)
            QMessageBox.information(self, "Success", "B2B CSV generated!")
        except Exception as e:
            self.log(f"❌ Error: {e}")
            QMessageBox.critical(self, "Error", f"Export failed: {e}")
    
    def export_hsn_b2b(self):
        """Export HSN (B2B) summary."""
        self.log("\n📊 Generating HSN (B2B) report...")
        try:
            fy, month, supplier = self.get_export_params()
            result = generate_hsn_b2b_csv(fy, month, supplier, self.db)
            self.log(result)
            QMessageBox.information(self, "Success", "HSN (B2B) CSV generated!")
        except Exception as e:
            self.log(f"❌ Error: {e}")
            QMessageBox.critical(self, "Error", f"Export failed: {e}")
    
    def export_b2cl(self):
        """Export B2CL (B2C Large) invoices."""
        self.log("\n📊 Generating B2CL report...")
        try:
            fy, month, supplier = self.get_export_params()
            result = generate_b2cl_csv(fy, month, supplier, self.db)
            self.log(result)
            QMessageBox.information(self, "Success", "B2CL CSV generated!")
        except Exception as e:
            self.log(f"❌ Error: {e}")
            QMessageBox.critical(self, "Error", f"Export failed: {e}")
    
    def export_cdnr(self):
        """Export CDNR (Credit/Debit Notes)."""
        self.log("\n📊 Generating CDNR report...")
        try:
            fy, month, supplier = self.get_export_params()
            result = generate_cdnr_csv(fy, month, supplier, self.db)
            self.log(result)
            QMessageBox.information(self, "Success", "CDNR CSV generated!")
        except Exception as e:
            self.log(f"❌ Error: {e}")
            QMessageBox.critical(self, "Error", f"Export failed: {e}")
    
    def export_docs(self):
        """Export Documents Issued report."""
        self.log("\n📊 Generating Documents Issued report...")
        try:
            fy, month, supplier = self.get_export_params()
            result = generate_docs_issued_csv(fy, month, supplier, self.db)
            self.log(result)
            QMessageBox.information(self, "Success", "Docs CSV generated!")
        except Exception as e:
            self.log(f"❌ Error: {e}")
            QMessageBox.critical(self, "Error", f"Export failed: {e}")
    
    def export_gstr1_excel(self):
        """Export complete GSTR-1 Excel workbook."""
        self.log("\n📑 Generating complete GSTR-1 Excel workbook...")
        try:
            fy, month, supplier = self.get_export_params()
            result = generate_gstr1_excel_workbook(fy, month, supplier, self.db)
            self.log(result)
            QMessageBox.information(self, "Success", "Complete GSTR-1 Excel workbook generated!")
        except Exception as e:
            self.log(f"❌ Error: {e}")
            QMessageBox.critical(self, "Error", f"Export failed: {e}")
    
    # ==================== Returns JSON Handlers ====================
    
    def browse_b2cs_file(self):
        """Browse and select B2CS CSV file."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Select B2CS CSV", "", "CSV Files (*.csv)")
        if file_path:
            self.b2cs_file_path = file_path
            file_name = os.path.basename(file_path)
            self.label_b2cs_file.setText(file_name)
            self.label_b2cs_file.setStyleSheet("color: green; font-size: 9pt;")
    
    def browse_hsn_file(self):
        """Browse and select HSN CSV file."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Select HSN CSV", "", "CSV Files (*.csv)")
        if file_path:
            self.hsn_file_path = file_path
            file_name = os.path.basename(file_path)
            self.label_hsn_file.setText(file_name)
            self.label_hsn_file.setStyleSheet("color: green; font-size: 9pt;")
    
    def browse_hsn_sac_file(self):
        """Browse and select HSN_SAC Excel file (optional)."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Select HSN_SAC Excel (Optional)", "", "Excel Files (*.xlsx)")
        if file_path:
            self.hsn_sac_file_path = file_path
            file_name = os.path.basename(file_path)
            self.label_hsn_sac_file.setText(file_name)
            self.label_hsn_sac_file.setStyleSheet("color: green; font-size: 9pt;")
    
    def export_returns_json(self):
        """Generate Returns JSON from selected CSV files."""
        self.log("\n📋 Generating Returns JSON...")
        try:
            # Check if files are selected
            if not hasattr(self, 'b2cs_file_path') or not hasattr(self, 'hsn_file_path'):
                QMessageBox.warning(self, "Missing Files", "Please select both B2CS and HSN CSV files.")
                return
            
            # Get parameters
            fy, month, supplier = self.get_export_params()
            version = self.input_json_version.currentText()
            
            # Optional HSN_SAC file
            hsn_sac_path = getattr(self, 'hsn_sac_file_path', None)
            
            # Output folder (same as B2CS file location)
            output_folder = os.path.dirname(self.b2cs_file_path)
            
            # Call the generation function
            result = generate_returns_json(
                b2cs_csv_path=self.b2cs_file_path,
                hsn_csv_path=self.hsn_file_path,
                gstin=supplier,
                financial_year=fy,
                month_number=month,
                output_folder=output_folder,
                version=version,
                hsn_sac_xlsx_path=hsn_sac_path
            )
            
            self.log(result)
            
            if result.startswith("✅"):
                QMessageBox.information(self, "Success", "Returns JSON generated successfully!")
            else:
                QMessageBox.warning(self, "Warning", result)
        
        except Exception as e:
            self.log(f"❌ Error: {e}")
            QMessageBox.critical(self, "Error", f"JSON generation failed: {e}")
    
    # ==================== Analytics Handlers ====================
    
    def generate_dashboard(self):
        """Generate comprehensive analytics dashboard."""
        self.log("\n" + "="*80)
        self.log("📊 GENERATING COMPREHENSIVE DASHBOARD")
        self.log("="*80)
        
        try:
            fy, month, supplier = self.get_export_params()
            
            # Monthly summary
            self.log("\n📈 Monthly Summary:")
            summary = get_monthly_summary(fy, month, supplier, self.db)
            if summary and 'summary' in summary:
                s = summary['summary']
                self.log(f"  Total Sales: {s.get('total_sales', 0)} units")
                self.log(f"  Total Returns: {s.get('total_returns', 0)} units")
                self.log(f"  Net Sales: {s.get('final_sales', 0)} units")
                self.log(f"  Revenue: ₹{s.get('final_amount', 0):,.2f}")
            
            # Order analytics
            self.log("\n📦 Order Analytics:")
            order_analytics = get_order_analytics(fy, month, supplier, self.db)
            if order_analytics:
                self.log(f"  Fulfillment Rate: {order_analytics.get('fulfillment_rate', 0)}%")
                if 'order_to_invoice_mapping' in order_analytics:
                    mapping = order_analytics['order_to_invoice_mapping']
                    self.log(f"  Orders Mapped to Invoices: {mapping['mapped_count']}/{mapping['total_orders']} ({mapping['mapping_rate']}%)")
            
            # Inventory analytics
            self.log("\n📋 Inventory Analytics:")
            inv_analytics = get_inventory_analytics(self.db)
            if inv_analytics and 'error' not in inv_analytics:
                self.log(f"  Total SKUs: {inv_analytics.get('total_skus', 0)}")
                self.log(f"  Out of Stock: {inv_analytics.get('out_of_stock_count', 0)}")
                self.log(f"  Low Stock: {inv_analytics.get('low_stock_count', 0)}")
                self.log(f"  Total Stock: {inv_analytics.get('total_stock', 0)} units")
            
            # Payment analytics
            self.log("\n💰 Payment Analytics:")
            payment_analytics = get_payment_analytics(self.db)
            if payment_analytics and 'error' not in payment_analytics:
                self.log(f"  Total Payments: ₹{payment_analytics.get('total_payments', 0):,.2f}")
                self.log(f"  Total Commissions: ₹{payment_analytics.get('total_commissions', 0):,.2f}")
                self.log(f"  Realization Rate: {payment_analytics.get('realization_rate', 0)}%")
            
            # Product insights
            self.log("\n🔍 Advanced Product Insights:")
            product_analytics = get_advanced_product_analytics(self.db)
            if product_analytics and 'products' in product_analytics:
                top_products = product_analytics['products'][:5]
                for i, p in enumerate(top_products, 1):
                    self.log(f"  {i}. {p['product_name'][:40]} - {p['lifecycle_stage']} stage")
            
            # Alerts
            self.log("\n⚠️ Predictive Alerts:")
            alerts = get_predictive_alerts_analytics(self.db)
            if alerts and 'alerts' in alerts:
                alert_list = alerts['alerts'][:5]
                for alert in alert_list:
                    self.log(f"  • {alert['type']}: {alert.get('product', 'N/A')[:40]}")
            
            self.log("\n" + "="*80)
            self.log("✅ Dashboard generated successfully!")
            self.log("="*80)
            
        except Exception as e:
            self.log(f"\n❌ Error generating dashboard: {e}")
            QMessageBox.critical(self, "Error", f"Dashboard generation failed: {e}")
    
    def export_catalog_summary(self):
        """Export catalog summary CSV."""
        self.log("\n📋 Generating catalog summary...")
        try:
            output_path, _ = QFileDialog.getSaveFileName(
                self, "Save Catalog Summary", "catalog_summary.csv", "CSV Files (*.csv)"
            )
            if output_path:
                result = generate_catalog_summary_csv(output_path, self.db)
                self.log(result)
                QMessageBox.information(self, "Success", "Catalog summary exported!")
        except Exception as e:
            self.log(f"❌ Error: {e}")
            QMessageBox.critical(self, "Error", f"Export failed: {e}")
    
    def refresh_view(self):
        """Refresh the current view."""
        self.log("\n🔄 Refreshing view...")
        self.output_text.clear()
        self.show_welcome()
        self.log("✅ View refreshed!")
    
    def closeEvent(self, event):
        """Handle application close event."""
        self.db.close()
        event.accept()
