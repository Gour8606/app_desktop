# Quick Start Guide - Meesho Sales Dashboard

## 🚀 Getting Started

### Step 1: Launch the Application
```bash
python main.py
```

### Step 2: Select Your Data Folder
- Click "Change Folder" button
- Navigate to folder containing your data files
- Application auto-detects Excel/CSV files

### Step 3: Import Data

#### Import Orders/Sales/Returns (Required)
```
1. Click "📂 Upload Meesho ZIP"
2. Select gst_*_10_2025.zip from your folder
3. Auto-imports: Orders CSV, Sales Excel, Returns Excel
4. Console shows: "✅ Orders data imported", "✅ Sales data imported", etc.
```

#### Import Inventory (Optional)
```
1. Click "📦 Import Inventory"
2. Select Inventory-Update-File_*.xlsx
3. Console shows: "✅ Inventory data imported: X products"
```

#### Import Payments (Optional)
```
1. Click "💰 Import Payments"
2. Select meesho_PREVIOUS_PAYMENT_*.zip
3. Console shows: "✅ Payment data imported: X payment records"
```

### Step 4: View Dashboard
```
1. Select Financial Year from dropdown (e.g., 2025)
2. Select Month from dropdown (e.g., 10 for October)
3. Select Supplier ID from dropdown (e.g., 3268023)
4. Click "📊 Dashboard"
5. View comprehensive analytics in "🪵 Debug Output" section
```

---

## 📊 Dashboard Output Includes

### Sales Summary (Table)
- FY-Month
- Supplier ID
- Total Sales Qty
- Total Returns Qty
- Final Sales Qty
- Final Amount

### Order Analytics
- ✅ Order Fulfillment Rate (%)
- ✅ Top 5 Products by Quantity
- ✅ Revenue by Product
- ✅ Revenue by State
- ✅ Revenue by Date (Top 5)
- ✅ Customer Segmentation (Top 5 States)
- ✅ Order-to-Invoice Mapping Rate

### Inventory Analytics
- ✅ Total SKUs
- ✅ Out of Stock Count
- ✅ Low Stock Count (< 5 units)
- ✅ Total Stock (units)
- ✅ Stock Health (Healthy/Low/OOS breakdown)
- ✅ Top 10 Products by Stock
- ✅ Stock Distribution by Catalog

### Payment Analytics
- ✅ Total Payments (₹)
- ✅ Total Sales (₹)
- ✅ Total Commissions (₹)
- ✅ Total Deductions (₹)
- ✅ Realization Rate (%)
- ✅ Average Settlement per Order
- ✅ Deduction Breakdown:
  - Commission
  - Platform Fee
  - Shipping Deduction
  - TCS/TDS
  - Other
- ✅ Top Payment Days

---

## 📁 File Format Requirements

### Inventory File
- **Format**: Excel (.xlsx)
- **Name Pattern**: `Inventory-Update-File_*_3268023.xlsx`
- **Columns**: SERIAL NO, CATALOG NAME, PRODUCT NAME, STOCK, etc.
- **Start Row**: 1 (header) + skip row for descriptions

### Payment File
- **Format**: ZIP containing Excel
- **Name Pattern**: `meesho_PREVIOUS_PAYMENT_*.zip`
- **Contains**: Excel file with multiple sheets
- **Primary Sheet**: "Order Payments" (use columns for settlement data)

### Orders File
- **Format**: CSV (inside ZIP)
- **Name Pattern**: `Orders_*.csv`
- **Columns**: Sub Order No, Order Date, Product Name, Quantity, Prices, etc.

### Sales/Returns Files
- **Format**: Excel (inside ZIP)
- **Names**: `tcs_sales.xlsx`, `tcs_sales_return.xlsx`
- **Auto-detected**: On ZIP upload

---

## 🔧 Troubleshooting

### Issue: "No Data" for Dashboard
**Solution**: 
- Ensure you uploaded the ZIP file first
- Select correct Financial Year and Month
- Check if supplier_id has data

### Issue: Inventory Not Showing
**Solution**:
- Click "📦 Import Inventory" first
- Select the correct Excel file
- Check console output for error messages

### Issue: Payments Not Showing
**Solution**:
- Click "💰 Import Payments" first
- Select the correct ZIP file
- Check console output for import status

### Issue: File Not Found
**Solution**:
- Click "Change Folder" and select correct base folder
- Ensure files are in the selected folder
- File names should match patterns

---

## 💡 Tips & Tricks

### Keyboard Shortcuts
- **Ctrl+L**: Focus on filters
- **F5**: Refresh dashboard (manual in some cases)

### Export Options
- **B2CS CSV**: For GST B2C Small reporting
- **HSN CSV**: For HSN-wise GST reporting
- **Documents CSV**: For invoice series documentation

### Filter Selection
- Once filters are loaded, dropdown shows all available values
- Select same filters to update dashboard with new data
- Financial Year auto-loads from imported data

### Performance Tips
- Import smaller zip files first to test
- Large inventory files may take a few seconds
- Payment ZIP extraction happens automatically

---

## 📞 Data Reference

### Key Tables & Fields

**MeeshoOrder**
- sub_order_no, order_date
- customer_state, product_name, quantity
- supplier_listed_price, supplier_discounted_price

**MeeshoInventory**
- product_id, product_name, catalog_name
- current_stock, system_stock_count, your_stock_count
- last_updated

**MeeshoPayment**
- sub_order_no, order_date, payment_date
- final_settlement_amount, total_sale_amount
- meesho_commission, platform_fee, shipping_charge
- tcs, tds, compensation, claims, recovery

**MeeshoSale / MeeshoReturn**
- sub_order_num, order_date, quantity
- gst_rate, total_taxable_sale_value, tax_amount
- end_customer_state_new, supplier_id, financial_year, month_number

---

## 🎯 Common Workflows

### Workflow 1: Quick Overview
```
1. Launch app
2. Change folder
3. Upload ZIP → Dashboard → View summary
```

### Workflow 2: Full Analysis
```
1. Launch app
2. Change folder
3. Upload ZIP
4. Import Inventory
5. Import Payments
6. Select filters (FY, Month, Supplier)
7. Dashboard → Full analytics
```

### Workflow 3: Generate Reports
```
1. Complete Workflow 2
2. Click B2CS CSV → Save to base_folder/b2cs.csv
3. Click HSN CSV → Save to base_folder/hsn(b2c).csv
4. Click Documents CSV → Save to base_folder/docs.csv
```

---

## 📊 Understanding Analytics Output

### Fulfillment Rate
- Percentage of orders with quantity > 0
- Higher is better (100% = all orders fulfilled)

### Realization Rate
- Percentage of sales converted to actual payments
- Formula: (Total Payments / Total Sales) × 100

### Stock Health
- **Healthy**: Stock > 5 units
- **Low Stock**: 0 < Stock < 5 units
- **Out of Stock**: Stock = 0 units

### Deduction Breakdown
- Shows where payments are reduced
- Commission: Meesho's cut
- Fees: Platform/warehousing charges
- Taxes: TCS/TDS deductions

