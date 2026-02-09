def generate_payout_summary_csv(output_path, db):
    """
    Generate a payout summary CSV matching the provided format using available data/models.
    Columns: Type, Status, Orders, Payout
    """
    import pandas as pd
    # Fetch all payments and orders
    payments = db.query(MeeshoPayment).all()
    orders = db.query(MeeshoOrder).all()
    returns = db.query(MeeshoReturn).all()

    # Build DataFrames
    df_payments = pd.DataFrame([
        {
            'sub_order_no': p.sub_order_no,
            'order_date': p.order_date,
            'final_settlement_amount': p.final_settlement_amount or 0,
            'total_sale_amount': p.total_sale_amount_incl_shipping_gst or 0,
            'total_return_amount': p.total_sale_return_amount_incl_shipping_gst or 0,
            'meesho_commission': p.meesho_commission_incl_gst or 0,
            'platform_fee': (p.meesho_gold_platform_fee_incl_gst or 0) + (p.meesho_mall_platform_fee_incl_gst or 0),
            'shipping_charge': p.shipping_charge_incl_gst or 0,
            'gst_compensation': p.gst_compensation_prp_shipping or 0,
            'tcs': p.tcs or 0,
            'tds': p.tds or 0,
            'compensation': p.compensation or 0,
            'claims': p.claims or 0,
            'recovery': p.recovery or 0,
            'net_payment': p.final_settlement_amount or 0,
        } for p in payments if p.sub_order_no
    ])
    df_orders = pd.DataFrame([
        {
            'order_status': getattr(o, 'order_status', ''),
        } for o in orders
    ])
    df_returns = pd.DataFrame([
        {
            'order_status': getattr(r, 'order_status', ''),
        } for r in returns
    ])


    # Calculate summary values
    delivered = df_orders[df_orders['order_status'].str.lower().str.contains('delivered')].shape[0]
    # ...rest of payout summary logic...

# ...existing code...

import numpy as np
from sqlalchemy.orm import Session
from models import MeeshoSale, MeeshoReturn, MeeshoOrder, MeeshoInventory, MeeshoPayment, MeeshoInvoice
from collections import defaultdict
import csv
import pandas as pd
import os
from datetime import datetime, timedelta
from constants import (
    B2CL_INVOICE_THRESHOLD, TransactionType, DBFields, 
    STATE_CODE_MAPPING, GSTR1Files, B2CLHeaders, CDNRHeaders,
    get_state_code, is_b2b_transaction, generate_note_number,
    NoteType
)
from error_handler import safe_float_conversion, safe_int_conversion


def normalize_rate(rate_value):
    """
    Normalize GST rate to percentage format (whole number).
    Converts 0.05 -> 5.0, 0.12 -> 12.0, 0.18 -> 18.0, 5 -> 5.0, etc.
    """
    if rate_value is None or rate_value == 0:
        return 0.0
    
    try:
        rate = float(rate_value)
    except (ValueError, TypeError):
        return 0.0
    
    # If rate is between 0 and 1 (decimal format like 0.05, 0.12, 0.18), multiply by 100
    if 0 < rate < 1:
        rate = rate * 100
    
    # Return as 2-decimal float (e.g., 5.0, 12.0, 18.0)
    return round(rate, 2)


# Advanced Product Analytics
def get_advanced_product_analytics(db: Session):
    """
    Returns advanced product analytics:
    - Product lifecycle stage (introduction, growth, maturity, decline)
    - Simple demand forecasting (moving average)
    - Stock optimization (reorder point, overstock alert)
    """
    try:
        orders = db.query(MeeshoOrder).all()
        inventories = db.query(MeeshoInventory).all()
        if not orders or not inventories:
            return {'error': 'No order or inventory data'}
        df_orders = pd.DataFrame([
            {
                'product_id': o.product_id,
                'product_name': o.product_name,
                'order_date': o.order_date,
                'quantity': o.quantity or 0
            } for o in orders if o.product_id and o.order_date is not None
        ])
        df_inv = pd.DataFrame([
            {
                'product_id': inv.product_id,
                'product_name': inv.product_name,
                'current_stock': inv.current_stock or 0
            } for inv in inventories if inv.product_id
        ])
        if df_orders.empty or df_inv.empty:
            return {'error': 'No usable order or inventory data'}

        # Demand trend per product (monthly)
        df_orders['order_month'] = pd.to_datetime(df_orders['order_date']).dt.to_period('M')
        demand_trends = df_orders.groupby(['product_id', 'order_month'])['quantity'].sum().reset_index()

        # Moving average demand (last 3 months)
        forecast = {}
        for pid, group in demand_trends.groupby('product_id'):
            group_sorted = group.sort_values('order_month')
            ma = group_sorted['quantity'].rolling(window=3, min_periods=1).mean().iloc[-1]
            forecast[pid] = ma

        # Product lifecycle stage (simple: growth if demand rising, decline if falling, else maturity)
        lifecycle = {}
        for pid, group in demand_trends.groupby('product_id'):
            group_sorted = group.sort_values('order_month')
            if len(group_sorted) < 2:
                lifecycle[pid] = 'introduction'
            else:
                trend = np.polyfit(range(len(group_sorted)), group_sorted['quantity'], 1)[0]
                if trend > 0.5:
                    lifecycle[pid] = 'growth'
                elif trend < -0.5:
                    lifecycle[pid] = 'decline'
                else:
                    lifecycle[pid] = 'maturity'

        # Stock optimization: reorder point (avg demand * 2), overstock alert (stock > 2*avg demand)
        stock_opt = {}
        for _, row in df_inv.iterrows():
            pid = row['product_id']
            stock = row['current_stock']
            avg_demand = forecast.get(pid, 0)
            reorder_point = avg_demand * 2
            overstock = stock > 2 * avg_demand if avg_demand > 0 else False
            stock_opt[pid] = {
                'product_name': row['product_name'],
                'current_stock': stock,
                'avg_monthly_demand': avg_demand,
                'reorder_point': reorder_point,
                'overstock': overstock
            }

        # Calculate total quantity sold per product for sorting
        total_qty_by_product = df_orders.groupby('product_id')['quantity'].sum().to_dict()
        
        # Merge all
        results = []
        for pid in df_inv['product_id'].unique():
            results.append({
                'product_id': pid,
                'product_name': df_inv[df_inv['product_id'] == pid]['product_name'].iloc[0],
                'lifecycle_stage': lifecycle.get(pid, 'unknown'),
                'avg_monthly_demand': round(forecast.get(pid, 0), 2),
                'current_stock': int(df_inv[df_inv['product_id'] == pid]['current_stock'].iloc[0]),
                'reorder_point': round(stock_opt[pid]['reorder_point'], 2) if pid in stock_opt else 0,
                'overstock': stock_opt[pid]['overstock'] if pid in stock_opt else False,
                'total_quantity_sold': int(total_qty_by_product.get(pid, 0))
            })
        
        # Sort by total quantity sold (most selling first)
        results = sorted(results, key=lambda x: x['total_quantity_sold'], reverse=True)
        
        return {'products': results}

    except Exception as e:
        return {'error': str(e)}

def get_order_analytics(financial_year: int, month_number: int, supplier_id: int, db: Session):
    """
    Returns a dictionary with order analytics for the dashboard:
    - fulfillment_rate: % of orders fulfilled (quantity > 0)
    - top_products: top 5 products by quantity
    - revenue_by_product: revenue grouped by product
    - revenue_by_state: revenue grouped by customer_state
    - revenue_by_date: revenue grouped by order_date
    - customer_segmentation: order count and revenue by state
    - order_to_invoice_mapping: count of orders with matching sales invoice (by sub_order_no)
    """

    # Query orders for the given period and supplier
    orders = db.query(MeeshoOrder).filter(
        MeeshoOrder.order_date != None
    ).all()
    if not orders:
        return {}
    df = pd.DataFrame([{
        'sub_order_no': o.sub_order_no,
        'order_date': o.order_date,
        'customer_state': o.customer_state,
        'product_name': o.product_name,
        'quantity': o.quantity,
        'supplier_listed_price': o.supplier_listed_price,
        'supplier_discounted_price': o.supplier_discounted_price
    } for o in orders])
    if df.empty:
        return {}

    # Fulfillment rate: orders with quantity > 0 / total orders
    fulfillment_rate = (df['quantity'] > 0).sum() / len(df) * 100

    # Top products by quantity
    top_products = (
        df.groupby('product_name')['quantity'].sum().sort_values(ascending=False).head(5)
        .reset_index().values.tolist()
    )

    # Revenue by product
    df['revenue'] = df['quantity'] * df['supplier_discounted_price']
    revenue_by_product = (
        df.groupby('product_name')['revenue'].sum().sort_values(ascending=False)
        .reset_index().values.tolist()
    )

    # Revenue by state
    revenue_by_state = (
        df.groupby('customer_state')['revenue'].sum().sort_values(ascending=False)
        .reset_index().values.tolist()
    )

    # Revenue by date
    revenue_by_date = (
        df.groupby('order_date')['revenue'].sum().sort_values(ascending=False)
        .reset_index().values.tolist()
    )

    # Customer segmentation: order count and revenue by state
    customer_segmentation = (
        df.groupby('customer_state').agg(order_count=('sub_order_no', 'count'), revenue=('revenue', 'sum'))
        .sort_values('revenue', ascending=False).reset_index().values.tolist()
    )

    # Order-to-invoice mapping: count of orders with matching sales invoice (by sub_order_no)
    sales_sub_orders = set(
        db.query(MeeshoSale.sub_order_num).filter(MeeshoSale.sub_order_num != None).all()
    )
    sales_sub_orders = set(x[0] for x in sales_sub_orders)
    mapped_count = df['sub_order_no'].isin(sales_sub_orders).sum()
    mapping_rate = mapped_count / len(df) * 100

    return {
        'fulfillment_rate': round(fulfillment_rate, 2),
        'top_products': top_products,
        'revenue_by_product': revenue_by_product,
        'revenue_by_state': revenue_by_state,
        'revenue_by_date': revenue_by_date,
        'customer_segmentation': customer_segmentation,
        'order_to_invoice_mapping': {
            'mapped_count': int(mapped_count),
            'total_orders': int(len(df)),
            'mapping_rate': round(mapping_rate, 2)
        }
    }

HARDCODED_SUPPLIER_GSTIN = {
    1258379: "06DHOPD4346E1ZG",
    567538: "06GETPD0854L1Z2",
    3268023: "23DHOPD4346E1ZK",
}

STATE_CODE_MAPPING = {
    # Official GST State/UT Codes - Latest from GST returns
    # Format: "STATE_NAME": "CODE-State Name"
    "JAMMU AND KASHMIR": "01-Jammu and Kashmir",
    "HIMACHAL PRADESH": "02-Himachal Pradesh",
    "PUNJAB": "03-Punjab",
    "CHANDIGARH": "04-Chandigarh",
    "UTTARAKHAND": "05-Uttarakhand",
    "HARYANA": "06-Haryana",
    "DELHI": "07-Delhi",
    "RAJASTHAN": "08-Rajasthan",
    "UTTAR PRADESH": "09-Uttar Pradesh",
    "BIHAR": "10-Bihar",
    "SIKKIM": "11-Sikkim",
    "ARUNACHAL PRADESH": "12-Arunachal Pradesh",
    "NAGALAND": "13-Nagaland",
    "MANIPUR": "14-Manipur",
    "MIZORAM": "15-Mizoram",
    "TRIPURA": "16-Tripura",
    "MEGHALAYA": "17-Meghalaya",
    "ASSAM": "18-Assam",
    "WEST BENGAL": "19-West Bengal",
    "JHARKHAND": "20-Jharkhand",
    "ODISHA": "21-Odisha",
    "CHHATTISGARH": "22-Chhattisgarh",
    "MADHYA PRADESH": "23-Madhya Pradesh",
    "GUJARAT": "24-Gujarat",
    "DADRA AND NAGAR HAVELI AND DAMAN AND DIU": "26-Dadra and Nagar Haveli and Daman and Diu",
    "MAHARASHTRA": "27-Maharashtra",
    "ANDHRA PRADESH": "37-Andhra Pradesh",
    "KARNATAKA": "29-Karnataka",
    "GOA": "30-Goa",
    "LAKSHADWEEP": "31-Lakshadweep",
    "KERALA": "32-Kerala",
    "TAMIL NADU": "33-Tamil Nadu",
    "PUDUCHERRY": "34-Puducherry",
    "ANDAMAN AND NICOBAR ISLANDS": "35-Andaman and Nicobar Islands",
    "TELANGANA": "36-Telangana",
    "LADAKH": "38-Ladakh",
    "OTHER TERRITORY": "97-Other Territory",
    
    # Alternative spellings
    "ORISSA": "21-Odisha",
    "PONDICHERRY": "34-Puducherry",
    "LEH LADAKH": "38-Ladakh",
    "ANDAMAN & NICOBAR": "35-Andaman and Nicobar Islands",
    "DAMAN": "26-Dadra and Nagar Haveli and Daman and Diu",
    "DAMAN AND DIU": "26-Dadra and Nagar Haveli and Daman and Diu",
    "DADRA": "26-Dadra and Nagar Haveli and Daman and Diu",
    "DADRA AND NAGAR HAVELI": "26-Dadra and Nagar Haveli and Daman and Diu",
    "JAMMU & KASHMIR": "01-Jammu and Kashmir",
}

def get_flipkart_gst_excel_path(config_path="config.json"):
    """
    Get the Flipkart GST Excel file path from configuration.
    Users should upload/import the file and configure the path.
    Returns the file path if configured, else None.
    """
    import json
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            return config.get('flipkart_gst_excel_path')
    except:
        return None

def set_flipkart_gst_excel_path(file_path, config_path="config.json"):
    """
    Set the Flipkart GST Excel file path in configuration.
    Call this after user uploads/selects the file through the UI.
    """
    import json
    try:
        config = {}
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
        except:
            pass
        
        config['flipkart_gst_excel_path'] = file_path
        with open(config_path, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"Error setting Flipkart GST Excel path: {e}")
        return False

def read_flipkart_gst_b2cs_data(excel_file_path):
    """
    Read B2CS (B2C Sales) data from Flipkart's GSTR-1 Excel file.
    Uses Section 7(B)(2) which contains state-wise B2C sales with IGST.
    Returns a dictionary keyed by (state, rate) with taxable values.
    """
    try:
        df = pd.read_excel(excel_file_path, sheet_name="Section 7(B)(2) in GSTR-1")
        
        data = {}
        for _, row in df.iterrows():
            state = str(row.get('Delivered State (PoS)', '')).strip()
            rate = row.get('IGST %', 0)
            taxable_value = row.get('Aggregate Taxable Value Rs.', 0)
            
            if state and taxable_value:
                # Normalize state to match our STATE_CODE_MAPPING format
                state_upper = state.upper()
                normalized_state = STATE_CODE_MAPPING.get(state_upper, state)
                rate_normalized = normalize_rate(rate)
                
                key = (normalized_state, rate_normalized)
                data[key] = data.get(key, 0) + taxable_value
        
        return data
    except Exception as e:
        print(f"Error reading Flipkart GST B2CS data: {e}")
        return None

def read_flipkart_gst_hsn_data(excel_file_path):
    """
    Read HSN-wise summary data from Flipkart's GSTR-1 Excel file.
    Uses Section 12 which contains HSN code aggregates.
    Returns a dictionary keyed by (hsn, rate) with detailed tax information.
    """
    try:
        df = pd.read_excel(excel_file_path, sheet_name="Section 12 in GSTR-1")
        
        data = {}
        for _, row in df.iterrows():
            hsn = str(row.get('HSN Number', '')).strip()
            qty = row.get('Total Quantity in Nos.', 0)
            total_value = row.get('Total\n Value Rs.', 0)
            taxable_value = row.get('Total Taxable Value Rs.', 0)
            igst = row.get('IGST Amount Rs.', 0)
            cgst = row.get('CGST Amount Rs.', 0)
            sgst = row.get('SGST Amount Rs.', 0)
            cess = row.get('Cess Rs.', 0)
            
            if hsn and taxable_value:
                # Calculate rate from tax amounts
                if igst and igst > 0:
                    rate = (igst / taxable_value) * 100 if taxable_value else 0
                elif cgst and sgst:
                    rate = ((cgst + sgst) / taxable_value) * 100 if taxable_value else 0
                else:
                    rate = 0
                
                rate_normalized = normalize_rate(rate)
                key = (hsn, rate_normalized)
                
                data[key] = {
                    'quantity': int(qty) if qty else 0,
                    'total_value': total_value,
                    'taxable_value': taxable_value,
                    'igst_amount': igst,
                    'cgst_amount': cgst,
                    'sgst_amount': sgst,
                    'cess_amount': cess
                }
        
        return data
    except Exception as e:
        print(f"Error reading Flipkart GST HSN data: {e}")
        return None
GST_SLABS = [5.0, 12.0, 18.0]

def approximate_gst_rate(raw_rate):
    return min(GST_SLABS, key=lambda x: abs(x - raw_rate))

def get_gstin_for_supplier(supplier_id: int, db: Session):
    gstin_obj = db.query(MeeshoSale.gstin).filter(
        MeeshoSale.supplier_id == supplier_id,
        MeeshoSale.gstin.isnot(None),
        MeeshoSale.gstin != ""
    ).first()
    if gstin_obj and gstin_obj[0]:
        return gstin_obj[0]
    return HARDCODED_SUPPLIER_GSTIN.get(supplier_id)

def get_monthly_summary(financial_year: int, month_number: int, supplier_id: int, db: Session):
    sales = db.query(MeeshoSale).filter_by(financial_year=financial_year, month_number=month_number, supplier_id=supplier_id).all()
    returns = db.query(MeeshoReturn).filter_by(financial_year=financial_year, month_number=month_number, supplier_id=supplier_id).all()

    total_sales = sum(s.quantity for s in sales)
    total_returns = sum(r.quantity for r in returns)
    final_sales = total_sales - total_returns
    final_amount = sum(s.total_taxable_sale_value or 0 for s in sales) - sum(r.total_taxable_sale_value or 0 for r in returns)

    return {
        "summary": {
            "total_sales": total_sales,
            "total_returns": total_returns,
            "final_sales": final_sales,
            "final_amount": round(final_amount, 2)
        }
    }

def _get_gst_pivot_data(financial_year: int, month_number: int, supplier_id: int, db: Session):
    sales = db.query(MeeshoSale).filter_by(
        financial_year=financial_year,
        month_number=month_number,
        supplier_id=supplier_id
    ).all()
    returns = db.query(MeeshoReturn).filter_by(
        financial_year=financial_year,
        month_number=month_number,
        supplier_id=supplier_id
    ).all()

    pivot = defaultdict(float)

    def normalize_state(state_raw: str) -> str:
        state_upper = str(state_raw or "").strip().upper()
        return STATE_CODE_MAPPING.get(state_upper, state_upper)

    for record in sales:
        pivot[(normalize_state(record.end_customer_state_new), float(record.gst_rate or 0))] += record.total_taxable_sale_value or 0

    for record in returns:
        pivot[(normalize_state(record.end_customer_state_new), float(record.gst_rate or 0))] -= record.total_taxable_sale_value or 0

    rows = [
        {"state": state, "gst_rate": gst_rate, "total_taxable_value": round(value, 2)}
        for (state, gst_rate), value in pivot.items() if state
    ]
    rows.sort(key=lambda r: (r["state"], r["gst_rate"]))
    return rows

def generate_gst_pivot_csv(financial_year, month_number, gstin_or_supplier_id, db,
                           file_path=None, output_folder=None):
    """
    Dynamic-path GST B2CS pivot generator - reads all marketplace data from database.
    
    Args:
        gstin_or_supplier_id: Either GSTIN string or legacy supplier_id integer
    """
    from models import FlipkartOrder, FlipkartReturn, AmazonOrder, AmazonReturn
    
    # Get GSTIN - accept either GSTIN string or legacy supplier_id
    if isinstance(gstin_or_supplier_id, str) and len(gstin_or_supplier_id) == 15:
        gstin = gstin_or_supplier_id
        supplier_id = None  # Not needed for new queries
    else:
        gstin = get_gstin_for_supplier(gstin_or_supplier_id, db)
        supplier_id = gstin_or_supplier_id
        if not gstin:
            raise ValueError(f"GSTIN not found for supplier ID {gstin_or_supplier_id}")

    combined_data = {}
    
    # 1. Meesho DB - query by GSTIN or supplier_id
    if isinstance(gstin_or_supplier_id, str) and len(gstin_or_supplier_id) == 15:
        # Query Meesho by GSTIN
        sales = db.query(MeeshoSale).filter_by(
            financial_year=financial_year,
            month_number=month_number,
            gstin=gstin_or_supplier_id
        ).all()
        returns = db.query(MeeshoReturn).filter_by(
            financial_year=financial_year,
            month_number=month_number,
            gstin=gstin_or_supplier_id
        ).all()
        
        # Process Meesho data
        def normalize_state(state_raw: str) -> str:
            state_upper = str(state_raw or "").strip().upper()
            return STATE_CODE_MAPPING.get(state_upper, state_upper)
        
        for record in sales:
            key = (normalize_state(record.end_customer_state_new), round(float(record.gst_rate or 0), 2))
            combined_data[key] = combined_data.get(key, 0) + (record.total_taxable_sale_value or 0)
        
        for record in returns:
            key = (normalize_state(record.end_customer_state_new), round(float(record.gst_rate or 0), 2))
            combined_data[key] = combined_data.get(key, 0) - (record.total_taxable_sale_value or 0)
    
    elif supplier_id:
        # Legacy path - use old function
        b2cs_rows = _get_gst_pivot_data(financial_year, month_number, supplier_id, db)
        for row in b2cs_rows:
            combined_data[(row["state"], round(row["gst_rate"], 2))] = combined_data.get((row["state"], round(row["gst_rate"], 2)), 0) + row["total_taxable_value"]

    # 2. Flipkart - Use certified GST Excel data when configured
    flipkart_excel = get_flipkart_gst_excel_path()
    if flipkart_excel and os.path.exists(flipkart_excel):
        # Use Flipkart's certified GSTR-1 report (Section 7(B)(2) for B2CS)
        flipkart_data = read_flipkart_gst_b2cs_data(flipkart_excel)
        if flipkart_data:
            for key, taxable_value in flipkart_data.items():
                combined_data[key] = combined_data.get(key, 0) + taxable_value
    else:
        # Fallback: Use database (if Excel not available)
        from datetime import datetime
        if month_number <= 3:
            year = financial_year
        else:
            year = financial_year - 1
        
        month_start = datetime(year, month_number, 1)
        if month_number == 12:
            month_end = datetime(year + 1, 1, 1)
        else:
            month_end = datetime(year, month_number + 1, 1)
        
        flipkart_query = db.query(FlipkartOrder).filter(
            FlipkartOrder.event_type == 'Sale',
            FlipkartOrder.order_date >= month_start,
            FlipkartOrder.order_date < month_end,
            FlipkartOrder.seller_gstin == gstin
        )
        flipkart_orders = flipkart_query.all()
        
        for order in flipkart_orders:
            delivery_state = str(order.customer_delivery_state or "").strip().upper()
            delivery_state_normalized = get_state_code(delivery_state)
            
            if order.igst_rate and order.igst_rate > 0:
                gst_rate = normalize_rate(order.igst_rate)
            elif order.cgst_rate and order.sgst_rate:
                gst_rate = normalize_rate(order.cgst_rate + order.sgst_rate)
            else:
                continue
            
            taxable_value = order.taxable_value or 0
            if taxable_value > 0:
                key = (delivery_state_normalized, gst_rate)
                combined_data[key] = combined_data.get(key, 0) + taxable_value

        flipkart_returns = db.query(FlipkartReturn).filter(
            FlipkartReturn.order_date >= month_start,
            FlipkartReturn.order_date < month_end,
            FlipkartReturn.seller_gstin == gstin
        ).all()
        
        for ret in flipkart_returns:
            delivery_state = str(ret.customer_delivery_state or "").strip().upper()
            delivery_state_normalized = get_state_code(delivery_state)
            
            if ret.igst_rate and ret.igst_rate > 0:
                gst_rate = normalize_rate(ret.igst_rate)
            elif ret.cgst_rate and ret.sgst_rate:
                gst_rate = normalize_rate(ret.cgst_rate + ret.sgst_rate)
            else:
                continue
            
            taxable_value = ret.taxable_value or 0
            if taxable_value > 0:
                key = (delivery_state_normalized, gst_rate)
                combined_data[key] = combined_data.get(key, 0) - taxable_value

    # 3. Amazon DB - aggregate by state and GST rate - ALWAYS filter by GSTIN to prevent data leakage
    amazon_query = db.query(AmazonOrder).filter(
        AmazonOrder.transaction_type == TransactionType.SHIPMENT,
        AmazonOrder.order_date >= month_start,
        AmazonOrder.order_date < month_end,
        AmazonOrder.seller_gstin == gstin
    )
    amazon_orders = amazon_query.all()
    
    for order in amazon_orders:
        # Normalize ship-to state
        delivery_state_normalized = get_state_code(order.ship_to_state) if order.ship_to_state else "Unknown"
        
        # Calculate GST rate: Interstate (IGST) or Intrastate (CGST + SGST) - normalize rate
        gst_rate = None
        if order.igst_rate:
            # Interstate - use IGST rate
            gst_rate = normalize_rate(order.igst_rate)
        elif order.cgst_rate and order.sgst_rate:
            # Intrastate - use CGST + SGST
            gst_rate = normalize_rate(order.cgst_rate + order.sgst_rate)
        else:
            continue  # Skip if no tax rate
        
        taxable_value = order.taxable_value or 0
        if taxable_value > 0:
            key = (delivery_state_normalized, gst_rate)
            combined_data[key] = combined_data.get(key, 0) + taxable_value

    # Amazon returns
    amazon_returns = db.query(AmazonReturn).filter(
        AmazonReturn.transaction_type == TransactionType.REFUND,
        AmazonReturn.order_date >= month_start,
        AmazonReturn.order_date < month_end,
        AmazonReturn.seller_gstin == gstin
    ).all()
    
    for ret in amazon_returns:
        # Normalize ship-to state
        delivery_state_normalized = get_state_code(ret.ship_to_state) if ret.ship_to_state else "Unknown"
        
        # Calculate GST rate: Interstate (IGST) or Intrastate (CGST + SGST) - use rate fields only (no approximation)
        gst_rate = None
        if ret.igst_rate:
            gst_rate = normalize_rate(ret.igst_rate)
        elif ret.cgst_rate and ret.sgst_rate:
            gst_rate = normalize_rate(ret.cgst_rate + ret.sgst_rate)
        else:
            continue  # Skip if no tax rate can be determined
        
        taxable_value = ret.taxable_value or 0
        if taxable_value > 0:
            key = (delivery_state_normalized, gst_rate)
            combined_data[key] = combined_data.get(key, 0) - taxable_value  # Subtract returns

    # 4. Output
    if not file_path:
        file_path = os.path.join(output_folder or "", "b2cs.csv")
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["Type", "Place Of Supply", "Rate", "Applicable % of Tax Rate", "Taxable Value", "Cess Amount", "E-Commerce GSTIN"])
        writer.writeheader()
        for (state, gst_rate), taxable_value in sorted(combined_data.items()):
            writer.writerow({"Type": "OE", "Place Of Supply": state, "Rate": gst_rate, "Applicable % of Tax Rate": "", "Taxable Value": round(taxable_value, 2), "Cess Amount": "", "E-Commerce GSTIN": ""})
    return f"✅ Combined GST CSV written to {file_path} with {len(combined_data)} aggregated rows (Meesho + Flipkart + Amazon)."

def generate_gst_hsn_pivot_csv(financial_year, month_number, gstin_or_supplier_id, db,
                               file_path=None, output_folder=None):
    """
    Dynamic-path GST HSN pivot generator - reads all marketplace data from database.
    
    Args:
        gstin_or_supplier_id: Either GSTIN string or legacy supplier_id integer
    """
    from models import FlipkartOrder, FlipkartReturn, AmazonOrder, AmazonReturn
    
    # Get GSTIN and handle both new GSTIN and legacy supplier_id
    if isinstance(gstin_or_supplier_id, str) and len(gstin_or_supplier_id) == 15:
        gstin_for_supplier = gstin_or_supplier_id
        # Query Meesho data by GSTIN
        sales = db.query(MeeshoSale).filter_by(
            financial_year=financial_year, 
            month_number=month_number, 
            gstin=gstin_or_supplier_id
        ).all()
        returns = db.query(MeeshoReturn).filter_by(
            financial_year=financial_year, 
            month_number=month_number, 
            gstin=gstin_or_supplier_id
        ).all()
    else:
        # Legacy supplier_id path
        gstin_for_supplier = get_gstin_for_supplier(gstin_or_supplier_id, db)
        sales = db.query(MeeshoSale).filter_by(
            financial_year=financial_year, 
            month_number=month_number, 
            supplier_id=gstin_or_supplier_id
        ).all()
        returns = db.query(MeeshoReturn).filter_by(
            financial_year=financial_year, 
            month_number=month_number, 
            supplier_id=gstin_or_supplier_id
        ).all()

    # derive supplier state from supplier GSTIN (first two digits)
    supplier_state_display = None
    if gstin_for_supplier and len(gstin_for_supplier) >= 2 and gstin_for_supplier[:2].isdigit():
        code = gstin_for_supplier[:2]
        # STATE_CODE_MAPPING values are like "23-Madhya Pradesh" — find the value that starts with the code
        for v in STATE_CODE_MAPPING.values():
            try:
                if str(v).startswith(f"{int(code):02d}-"):
                    supplier_state_display = v
                    break
            except Exception:
                continue

    def normalize_state(state_raw: str) -> str:
        state_upper = str(state_raw or "").strip().upper()
        return STATE_CODE_MAPPING.get(state_upper, state_upper)

    def is_intra(state):
        """Return True if the given destination state is intrastate (same as supplier state).

        We compare normalized state representations (e.g. "23-Madhya Pradesh") when possible.
        If supplier state can't be determined from GSTIN, conservatively return False.
        """
        norm = normalize_state(state)
        if supplier_state_display:
            return norm == supplier_state_display
        return False

    pivot_data = defaultdict(lambda: {"taxable_value": 0.0, "quantity": 0, "cgst_amount": 0.0, "sgst_amount": 0.0, "igst_amount": 0.0, "cess_amount": 0.0})

    for rec in sales:
        k = (str(rec.hsn_code or "UNKNOWN"), float(rec.gst_rate or 0))
        pivot_data[k]["quantity"] += int(rec.quantity or 0)
        pivot_data[k]["taxable_value"] += float(rec.total_taxable_sale_value or 0.0)
        if is_intra(rec.end_customer_state_new):
            pivot_data[k]["cgst_amount"] += (rec.total_taxable_sale_value or 0) * rec.gst_rate / 200
            pivot_data[k]["sgst_amount"] += (rec.total_taxable_sale_value or 0) * rec.gst_rate / 200
        else:
            pivot_data[k]["igst_amount"] += (rec.total_taxable_sale_value or 0) * rec.gst_rate / 100

    for rec in returns:
        k = (str(rec.hsn_code or "UNKNOWN"), float(rec.gst_rate or 0))
        pivot_data[k]["quantity"] -= int(rec.quantity or 0)
        pivot_data[k]["taxable_value"] -= float(rec.total_taxable_sale_value or 0.0)
        if is_intra(rec.end_customer_state_new):
            pivot_data[k]["cgst_amount"] -= (rec.total_taxable_sale_value or 0) * rec.gst_rate / 200
            pivot_data[k]["sgst_amount"] -= (rec.total_taxable_sale_value or 0) * rec.gst_rate / 200
        else:
            pivot_data[k]["igst_amount"] -= (rec.total_taxable_sale_value or 0) * rec.gst_rate / 100

    # Flipkart HSN merge - now from database
    from datetime import datetime
    if month_number <= 3:  # Jan-Mar
        year = financial_year
    else:  # Apr-Dec
        year = financial_year - 1
    
    month_start = datetime(year, month_number, 1)
    if month_number == 12:
        month_end = datetime(year + 1, 1, 1)
    else:
        month_end = datetime(year, month_number + 1, 1)
    
    flipkart_orders = []
    flipkart_returns = []
    hsn_rate_map = {}
    
    # Try to use Flipkart certified GST Excel data first
    flipkart_excel = get_flipkart_gst_excel_path()
    if flipkart_excel and os.path.exists(flipkart_excel):
        flipkart_hsn_data = read_flipkart_gst_hsn_data(flipkart_excel)
        if flipkart_hsn_data:
            for (hsn, rate), vals in flipkart_hsn_data.items():
                hsn_rate_map[hsn] = rate
                k = (hsn, rate)
                pivot_data[k]["quantity"] = vals.get('quantity', 0)
                pivot_data[k]["taxable_value"] = vals.get('taxable_value', 0)
                pivot_data[k]["igst_amount"] = vals.get('igst_amount', 0)
                pivot_data[k]["cgst_amount"] = vals.get('cgst_amount', 0)
                pivot_data[k]["sgst_amount"] = vals.get('sgst_amount', 0)
                pivot_data[k]["cess_amount"] = vals.get('cess_amount', 0)
    else:
        # Fallback: Use database if Excel not available
        flipkart_orders = db.query(FlipkartOrder).filter(
            FlipkartOrder.event_type == 'Sale',
            FlipkartOrder.order_date >= month_start,
            FlipkartOrder.order_date < month_end,
            FlipkartOrder.seller_gstin == gstin_for_supplier
        ).all()
        
        flipkart_returns = db.query(FlipkartReturn).filter(
            FlipkartReturn.order_date >= month_start,
            FlipkartReturn.order_date < month_end,
            FlipkartReturn.seller_gstin == gstin_for_supplier
        ).all()
        
        # Aggregate Flipkart sales by HSN
        for order in flipkart_orders:
            hsn = str(order.hsn_code or "UNKNOWN")
            if order.igst_rate and order.igst_rate > 0:
                rate = normalize_rate(order.igst_rate)
            elif order.cgst_rate and order.sgst_rate:
                rate = normalize_rate(order.cgst_rate + order.sgst_rate)
            else:
                rate = 0
            
            if hsn not in hsn_rate_map:
                hsn_rate_map[hsn] = rate
            
            k = (hsn, rate)
            pivot_data[k]["quantity"] += int(order.quantity or 0)
            pivot_data[k]["taxable_value"] += float(order.taxable_value or 0)
            pivot_data[k]["igst_amount"] += float(order.igst_amount or 0)
            pivot_data[k]["cgst_amount"] += float(order.cgst_amount or 0)
            pivot_data[k]["sgst_amount"] += float(order.sgst_amount or 0)
        
        # Subtract Flipkart returns
        for ret in flipkart_returns:
            hsn = str(ret.hsn_code or "UNKNOWN")
            
            if hsn in hsn_rate_map:
                rate = hsn_rate_map[hsn]
            else:
                if ret.igst_rate and ret.igst_rate > 0:
                    rate = normalize_rate(ret.igst_rate)
                elif ret.cgst_rate and ret.sgst_rate:
                    rate = normalize_rate(ret.cgst_rate + ret.sgst_rate)
                else:
                    rate = 0.0
                if hsn not in hsn_rate_map:
                    hsn_rate_map[hsn] = rate
            
            k = (hsn, rate)
            pivot_data[k]["quantity"] -= int(ret.quantity or 0)
            pivot_data[k]["taxable_value"] -= float(ret.taxable_value or 0)
            pivot_data[k]["igst_amount"] -= float(ret.igst_amount or 0)
            pivot_data[k]["cgst_amount"] -= float(ret.cgst_amount or 0)
            pivot_data[k]["sgst_amount"] -= float(ret.sgst_amount or 0)

    # Amazon HSN merge - aggregate from database
    amazon_orders = db.query(AmazonOrder).filter(
        AmazonOrder.transaction_type == TransactionType.SHIPMENT,
        AmazonOrder.order_date >= month_start,
        AmazonOrder.order_date < month_end,
        AmazonOrder.seller_gstin == gstin_for_supplier
    ).all()
    
    amazon_returns = db.query(AmazonReturn).filter(
        AmazonReturn.transaction_type == TransactionType.REFUND,
        AmazonReturn.order_date >= month_start,
        AmazonReturn.order_date < month_end,
        AmazonReturn.seller_gstin == gstin_for_supplier
    ).all()
    
    # Aggregate Amazon sales by HSN (update the map)
    for order in amazon_orders:
        hsn = str(order.hsn_sac or "UNKNOWN")
        # Calculate effective tax rate and normalize
        if order.igst_rate and order.igst_rate > 0:
            rate = normalize_rate(order.igst_rate)
        elif order.cgst_rate and order.sgst_rate:
            rate = normalize_rate(order.cgst_rate + order.sgst_rate)
        else:
            rate = 0
        
        # Store the rate for this HSN if not already set
        if hsn not in hsn_rate_map:
            hsn_rate_map[hsn] = rate
        
        k = (hsn, rate)
        pivot_data[k]["quantity"] += int(order.quantity or 0)
        pivot_data[k]["taxable_value"] += float(order.taxable_value or 0)
        pivot_data[k]["igst_amount"] += float(order.igst_amount or 0)
        pivot_data[k]["cgst_amount"] += float(order.cgst_amount or 0)
        pivot_data[k]["sgst_amount"] += float(order.sgst_amount or 0)
    
    # Subtract Amazon returns (use established HSN rate - NO approximation from tax amounts)
    for ret in amazon_returns:
        hsn = str(ret.hsn_sac or "UNKNOWN")
        
        # Use the rate established from sales (most reliable source)
        if hsn in hsn_rate_map:
            rate = hsn_rate_map[hsn]
        else:
            # For returns without prior sales, use the return's own rate fields (NORMALIZED)
            if ret.igst_rate and ret.igst_rate > 0:
                rate = normalize_rate(ret.igst_rate)
            elif ret.cgst_rate and ret.sgst_rate:
                rate = normalize_rate(ret.cgst_rate + ret.sgst_rate)
            else:
                rate = 0.0
            # Store this rate for future use
            if hsn not in hsn_rate_map:
                hsn_rate_map[hsn] = rate
        
        k = (hsn, rate)
        pivot_data[k]["quantity"] -= int(ret.quantity or 0)
        pivot_data[k]["taxable_value"] -= float(ret.taxable_value or 0)
        pivot_data[k]["igst_amount"] -= float(ret.igst_amount or 0)
        pivot_data[k]["cgst_amount"] -= float(ret.cgst_amount or 0)
        pivot_data[k]["sgst_amount"] -= float(ret.sgst_amount or 0)

    # Output - use pivot_data directly without consolidation
    # The hsn_rate_map ensures each HSN primarily uses one rate from sales
    if not file_path:
        file_path = os.path.join(output_folder or "", "hsn(b2c).csv")
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["HSN", "Description", "UQC", "Total Quantity", "Total Value", "Taxable Value", "Integrated Tax Amount", "Central Tax Amount", "State/UT Tax Amount", "Cess Amount", "Rate"])
        for (hsn, rate), vals in sorted(pivot_data.items()):
            # Skip rows with zero quantity (no transactions)
            if vals["quantity"] == 0:
                continue
            
            total_value = round(vals["taxable_value"] + vals["igst_amount"] + vals["cgst_amount"] + vals["sgst_amount"] + vals["cess_amount"], 2)
            # Ensure rate is normalized before output
            normalized_rate = normalize_rate(rate) if rate else 0
            writer.writerow([hsn, "", "NOS-NUMBERS", vals["quantity"], total_value, round(vals["taxable_value"], 2), round(vals["igst_amount"], 2), round(vals["cgst_amount"], 2), round(vals["sgst_amount"], 2), round(vals["cess_amount"], 2), normalized_rate])
    return f"✅ GST HSN pivot CSV saved as '{file_path}' for FY {financial_year}, Month {month_number}, GSTIN {gstin_or_supplier_id}"


def get_inventory_analytics(db: Session):
    """
    Returns inventory analytics for dashboard:
    - total_skus: total number of SKUs
    - out_of_stock: number of out-of-stock items
    - low_stock_threshold: count of items below threshold (< 5)
    - total_stock_value: aggregated inventory value
    - top_products_by_stock: top 10 products by sales volume (quantity sold)
    Note: Results sorted by most selling products
    """
    try:
        inventories = db.query(MeeshoInventory).all()
        orders = db.query(MeeshoOrder).all()
        
        if not inventories:
            return {}
        
        df = pd.DataFrame([{
            'product_name': inv.product_name,
            'product_id': inv.product_id,
            'catalog_name': inv.catalog_name,
            'current_stock': inv.current_stock or 0,
            'system_stock_count': inv.system_stock_count or 0,
            'variation': inv.variation
        } for inv in inventories])
        
        # Calculate total quantity sold per product
        df_orders = pd.DataFrame([
            {'product_id': o.product_id, 'quantity': o.quantity or 0}
            for o in orders if o.product_id
        ])
        
        if not df_orders.empty:
            total_qty_by_product = df_orders.groupby('product_id')['quantity'].sum()
            df['total_sold'] = df['product_id'].map(total_qty_by_product).fillna(0)
        else:
            df['total_sold'] = 0
        
        total_skus = len(df)
        out_of_stock = (df['current_stock'] == 0).sum()
        low_stock = (df['current_stock'] > 0) & (df['current_stock'] < 5)
        low_stock_count = low_stock.sum()
        total_stock = df['current_stock'].sum()
        
        # Top products by sales volume (most selling)
        top_products = (
            df.groupby('product_name').agg(
                current_stock=('current_stock', 'sum'),
                total_sold=('total_sold', 'sum')
            ).sort_values('total_sold', ascending=False).head(10)
            .reset_index().values.tolist()
        )
        
        # Stock status by catalog (sorted by total sales volume)
        by_catalog = (
            df.groupby('catalog_name').agg(
                total_stock=('current_stock', 'sum'),
                out_of_stock=('current_stock', lambda x: (x == 0).sum()),
                product_count=('product_name', 'count'),
                total_sold=('total_sold', 'sum')
            ).sort_values('total_sold', ascending=False).reset_index().values.tolist()
        )
        
        return {
            'total_skus': int(total_skus),
            'out_of_stock_count': int(out_of_stock),
            'low_stock_count': int(low_stock_count),
            'total_stock': int(total_stock),
            'top_products': top_products,
            'by_catalog': by_catalog,
            'stock_health': {
                'healthy': int(total_skus - out_of_stock - low_stock_count),
                'low_stock': int(low_stock_count),
                'out_of_stock': int(out_of_stock)
            }
        }
    except Exception as e:
        return {'error': str(e)}


def get_payment_analytics(db: Session):
    """
    Returns payment analytics for dashboard:
    - total_payments: total settlement amount
    - total_commissions: total Meesho commissions
    - total_deductions: total deductions
    - payment_realization_rate: % of orders paid
    - average_settlement: average settlement per order
    - top_payment_days: top days by payment volume
    """
    try:
        payments = db.query(MeeshoPayment).all()
        if not payments:
            return {}
        
        df = pd.DataFrame([{
            'sub_order_no': p.sub_order_no,
            'order_date': p.order_date,
            'payment_date': p.payment_date,
            'final_settlement_amount': p.final_settlement_amount or 0,
            'total_sale_amount': p.total_sale_amount_incl_shipping_gst or 0,
            'meesho_commission': p.meesho_commission_incl_gst or 0,
            'platform_fee': (p.meesho_gold_platform_fee_incl_gst or 0) + (p.meesho_mall_platform_fee_incl_gst or 0),
            'shipping_charge': p.shipping_charge_incl_gst or 0,
            'gst_compensation': p.gst_compensation_prp_shipping or 0,
            'tcs': p.tcs or 0,
            'tds': p.tds or 0,
            'compensation': p.compensation or 0,
            'recovery': p.recovery or 0
        } for p in payments])
        
        total_payments = df['final_settlement_amount'].sum()
        total_sales = df['total_sale_amount'].sum()
        total_commissions = df['meesho_commission'].sum()
        total_deductions = (
            df['meesho_commission'].sum() + 
            df['platform_fee'].sum() + 
            df['shipping_charge'].sum() + 
            df['tcs'].sum() + 
            df['tds'].sum()
        )
        
        # Payment realization rate
        realization_rate = (total_payments / total_sales * 100) if total_sales > 0 else 0
        average_settlement = total_payments / len(df) if len(df) > 0 else 0
        
        # Payment trends by date
        payment_by_date = (
            df.groupby('payment_date').agg(
                payment_amount=('final_settlement_amount', 'sum'),
                order_count=('sub_order_no', 'count')
            ).sort_values('payment_amount', ascending=False).head(10).reset_index().values.tolist()
        )
        
        # Deduction breakdown
        deductions = {
            'commission': round(total_commissions, 2),
            'platform_fee': round(df['platform_fee'].sum(), 2),
            'shipping_deduction': round(df['shipping_charge'].sum(), 2),
            'tcs_tds': round(df['tcs'].sum() + df['tds'].sum(), 2),
            'other': round(df['compensation'].sum() + df['recovery'].sum(), 2)
        }
        
        return {
            'total_payments': round(total_payments, 2),
            'total_sales': round(total_sales, 2),
            'total_commissions': round(total_commissions, 2),
            'total_deductions': round(total_deductions, 2),
            'realization_rate': round(realization_rate, 2),
            'average_settlement': round(average_settlement, 2),
            'total_orders': int(len(df)),
            'payment_by_date': payment_by_date,
            'deductions': deductions
        }
    except Exception as e:
        return {'error': str(e)}


def get_invoice_analytics(db: Session, fy: str = None, month: int = None, gstin: str = None):
    """
    Get invoice analytics including completion rate, invoicing speed, and compliance metrics.
    NOW INCLUDES DATA FROM ALL MARKETPLACES: Meesho, Flipkart, Amazon
    
    Args:
        db: Database session
        fy: Financial year filter (e.g., "2024-25" or None for all)
        month: Month filter (1-12 or None for all)
        gstin: Seller GSTIN filter (None for all sellers)
    """
    try:
        from models import FlipkartOrder, AmazonOrder
        
        # Query all marketplace invoices/orders with date filtering
        meesho_invoice_query = db.query(MeeshoInvoice)
        meesho_order_query = db.query(MeeshoOrder)
        flipkart_query = db.query(FlipkartOrder).filter(FlipkartOrder.event_type == 'Sale')
        amazon_query = db.query(AmazonOrder).filter(AmazonOrder.transaction_type == 'Shipment')
        
        # Apply GSTIN filter if provided
        if gstin:
            # MeeshoInvoice doesn't have gstin field, join with MeeshoSale via suborder_no
            meesho_invoice_query = meesho_invoice_query.join(
                MeeshoSale, MeeshoInvoice.suborder_no == MeeshoSale.sub_order_num
            ).filter(MeeshoSale.gstin == gstin)
            # MeeshoOrder doesn't have gstin field, join with MeeshoSale via sub_order_no
            meesho_order_query = meesho_order_query.join(
                MeeshoSale, MeeshoOrder.sub_order_no == MeeshoSale.sub_order_num
            ).filter(MeeshoSale.gstin == gstin)
            flipkart_query = flipkart_query.filter(FlipkartOrder.seller_gstin == gstin)
            amazon_query = amazon_query.filter(AmazonOrder.seller_gstin == gstin)
        
        # Apply date filters if provided
        if fy:
            # Extract start year from FY (e.g., "2024-25" -> 2024)
            start_year = int(fy.split('-')[0])
            # FY runs from April to March
            fy_start = f"{start_year}-04-01"
            fy_end = f"{start_year + 1}-03-31"
            
            meesho_invoice_query = meesho_invoice_query.filter(MeeshoInvoice.order_date.between(fy_start, fy_end))
            meesho_order_query = meesho_order_query.filter(MeeshoOrder.order_date.between(fy_start, fy_end))
            flipkart_query = flipkart_query.filter(FlipkartOrder.order_date.between(fy_start, fy_end))
            amazon_query = amazon_query.filter(AmazonOrder.order_date.between(fy_start, fy_end))
        
        if month:
            from sqlalchemy import extract
            meesho_invoice_query = meesho_invoice_query.filter(extract('month', MeeshoInvoice.order_date) == month)
            meesho_order_query = meesho_order_query.filter(extract('month', MeeshoOrder.order_date) == month)
            flipkart_query = flipkart_query.filter(extract('month', FlipkartOrder.order_date) == month)
            amazon_query = amazon_query.filter(extract('month', AmazonOrder.order_date) == month)
        
        meesho_invoices = meesho_invoice_query.all()
        meesho_orders = meesho_order_query.all()
        flipkart_orders = flipkart_query.all()
        amazon_orders = amazon_query.all()
        
        if not meesho_invoices and not flipkart_orders and not amazon_orders:
            return {'error': 'No invoice data found from any marketplace'}
        
        # === MEESHO INVOICES ===
        meesho_invoice_data = [{
            'marketplace': 'Meesho',
            'invoice_type': i.invoice_type,
            'order_date': i.order_date,
            'suborder_no': i.suborder_no,
            'product_description': i.product_description,
            'hsn_code': i.hsn_code,
            'invoice_no': i.invoice_no
        } for i in meesho_invoices]
        
        # === FLIPKART INVOICES (from orders) ===
        flipkart_invoice_data = [{
            'marketplace': o.marketplace,  # 'Flipkart' or 'Shopsy'
            'invoice_type': 'TAX INVOICE',
            'order_date': o.order_date,
            'suborder_no': o.order_item_id,
            'product_description': o.product_title,
            'hsn_code': o.hsn_code,  # FIXED: Flipkart uses hsn_code, not hsn_sac
            'invoice_no': o.buyer_invoice_id  # FIXED: Flipkart uses buyer_invoice_id, not invoice_number
        } for o in flipkart_orders]
        
        # === AMAZON INVOICES (from orders) ===
        amazon_invoice_data = [{
            'marketplace': 'Amazon',
            'invoice_type': 'TAX INVOICE',
            'order_date': o.order_date,
            'suborder_no': o.shipment_item_id,
            'product_description': o.item_description,
            'hsn_code': o.hsn_sac,  # Amazon uses hsn_sac
            'invoice_no': o.invoice_number
        } for o in amazon_orders]
        
        # Combine all marketplace invoices
        all_invoice_data = meesho_invoice_data + flipkart_invoice_data + amazon_invoice_data
        df_invoices = pd.DataFrame(all_invoice_data)
        
        if df_invoices.empty:
            return {'error': 'No invoice data available'}
        
        # Total counts
        invoice_count = len(df_invoices)
        order_count = len(meesho_orders) + len(flipkart_orders) + len(amazon_orders)
        
        # Invoice completion rate
        matched_orders = df_invoices['suborder_no'].nunique()
        completion_rate = (matched_orders / order_count * 100) if order_count > 0 else 0
        
        # Invoicing speed (days from order date to invoice import)
        df_invoices['invoicing_speed'] = (
            df_invoices['order_date'].apply(lambda x: (datetime.now() - pd.to_datetime(x)).days if pd.notna(x) else 0)
        )
        avg_invoicing_speed = df_invoices['invoicing_speed'].mean() if len(df_invoices) > 0 else 0
        
        # Top invoiced products
        top_products = (
            df_invoices['product_description'].value_counts().head(10).reset_index()
        )
        top_products_list = [[row['product_description'], int(row['count'])] 
                             for _, row in top_products.iterrows()]
        
        # HSN code coverage
        hsn_coverage = (df_invoices['hsn_code'].notna().sum() / len(df_invoices) * 100) if len(df_invoices) > 0 else 0
        
        # Invoice types distribution
        invoice_types = df_invoices['invoice_type'].value_counts().to_dict()
        
        # Credit note rate
        credit_notes = invoice_types.get('CREDIT NOTE', 0)
        credit_note_rate = (credit_notes / invoice_count * 100) if invoice_count > 0 else 0
        
        # Pending invoices (orders without invoices) - Meesho only for now
        invoiced_suborders = set(df_invoices[df_invoices['marketplace'] == 'Meesho']['suborder_no'].unique())
        all_meesho_suborders = set(o.sub_order_no for o in meesho_orders if o.sub_order_no)
        pending_invoices = all_meesho_suborders - invoiced_suborders
        
        # Monthly invoice volume
        df_invoices['order_date'] = pd.to_datetime(df_invoices['order_date'], errors='coerce')
        df_invoices['invoice_month'] = df_invoices['order_date'].dt.to_period('M')
        monthly_volume = (
            df_invoices.groupby('invoice_month').size().reset_index(name='count')
        )
        monthly_volume_list = [[str(row['invoice_month']), int(row['count'])] 
                               for _, row in monthly_volume.iterrows()]
        
        # HSN code distribution
        hsn_dist = df_invoices['hsn_code'].value_counts().head(10).reset_index()
        hsn_dist_list = [[row['hsn_code'], int(row['count'])] 
                         for _, row in hsn_dist.iterrows()]
        
        # Marketplace breakdown
        marketplace_invoices = df_invoices['marketplace'].value_counts().to_dict()
        
        return {
            'total_invoices': int(invoice_count),
            'total_orders': int(order_count),
            'completion_rate': round(completion_rate, 2),
            'avg_invoicing_speed_days': round(avg_invoicing_speed, 2),
            'top_invoiced_products': top_products_list,
            'hsn_coverage_rate': round(hsn_coverage, 2),
            'invoice_types': invoice_types,
            'credit_note_rate': round(credit_note_rate, 2),
            'pending_invoice_count': len(pending_invoices),
            'monthly_invoice_volume': monthly_volume_list,
            'hsn_distribution': hsn_dist_list,
            'marketplace_breakdown': marketplace_invoices
        }
    except Exception as e:
        return {'error': str(e)}


def get_enhanced_gst_analytics(db: Session, fy: str = None, month: int = None, gstin: str = None):
    """
    Get enhanced GST analytics including tax liability and state-wise breakdown.
    NOW INCLUDES DATA FROM ALL MARKETPLACES: Meesho, Flipkart, Amazon
    
    Args:
        db: Database session
        fy: Financial year filter (e.g., "2024-25" or None for all)
        month: Month filter (1-12 or None for all)
        gstin: Seller GSTIN filter (None for all sellers)
    """
    try:
        from models import FlipkartOrder, FlipkartReturn, AmazonOrder, AmazonReturn
        
        # Query all marketplaces with date filtering
        meesho_sales_query = db.query(MeeshoSale)
        meesho_returns_query = db.query(MeeshoReturn)
        flipkart_orders_query = db.query(FlipkartOrder).filter(FlipkartOrder.event_type == 'Sale')
        flipkart_returns_query = db.query(FlipkartReturn)
        amazon_orders_query = db.query(AmazonOrder).filter(AmazonOrder.transaction_type == 'Shipment')
        amazon_returns_query = db.query(AmazonReturn).filter(AmazonReturn.transaction_type == 'Refund')
        
        # Apply GSTIN filter if provided
        if gstin:
            meesho_sales_query = meesho_sales_query.filter(MeeshoSale.gstin == gstin)
            meesho_returns_query = meesho_returns_query.filter(MeeshoReturn.gstin == gstin)
            flipkart_orders_query = flipkart_orders_query.filter(FlipkartOrder.seller_gstin == gstin)
            flipkart_returns_query = flipkart_returns_query.filter(FlipkartReturn.seller_gstin == gstin)
            amazon_orders_query = amazon_orders_query.filter(AmazonOrder.seller_gstin == gstin)
            amazon_returns_query = amazon_returns_query.filter(AmazonReturn.seller_gstin == gstin)
        
        # Apply date filters if provided
        if fy:
            # Extract start year from FY (e.g., "2024-25" -> 2024)
            start_year = int(fy.split('-')[0])
            # FY runs from April to March
            fy_start = f"{start_year}-04-01"
            fy_end = f"{start_year + 1}-03-31"
            
            meesho_sales_query = meesho_sales_query.filter(MeeshoSale.order_date.between(fy_start, fy_end))
            meesho_returns_query = meesho_returns_query.filter(MeeshoReturn.order_date.between(fy_start, fy_end))
            flipkart_orders_query = flipkart_orders_query.filter(FlipkartOrder.order_date.between(fy_start, fy_end))
            flipkart_returns_query = flipkart_returns_query.filter(FlipkartReturn.order_date.between(fy_start, fy_end))
            amazon_orders_query = amazon_orders_query.filter(AmazonOrder.order_date.between(fy_start, fy_end))
            amazon_returns_query = amazon_returns_query.filter(AmazonReturn.order_date.between(fy_start, fy_end))
        
        if month:
            from sqlalchemy import extract
            meesho_sales_query = meesho_sales_query.filter(extract('month', MeeshoSale.order_date) == month)
            meesho_returns_query = meesho_returns_query.filter(extract('month', MeeshoReturn.order_date) == month)
            flipkart_orders_query = flipkart_orders_query.filter(extract('month', FlipkartOrder.order_date) == month)
            flipkart_returns_query = flipkart_returns_query.filter(extract('month', FlipkartReturn.order_date) == month)
            amazon_orders_query = amazon_orders_query.filter(extract('month', AmazonOrder.order_date) == month)
            amazon_returns_query = amazon_returns_query.filter(extract('month', AmazonReturn.order_date) == month)
        
        meesho_sales = meesho_sales_query.all()
        meesho_returns = meesho_returns_query.all()
        flipkart_orders = flipkart_orders_query.all()
        flipkart_returns = flipkart_returns_query.all()
        amazon_orders = amazon_orders_query.all()
        amazon_returns = amazon_returns_query.all()
        
        if not meesho_sales and not flipkart_orders and not amazon_orders:
            return {'error': 'No sales data found from any marketplace'}
        
        # === MEESHO DATA ===
        meesho_sales_data = [{
            'marketplace': 'Meesho',
            'gst_rate': s.gst_rate,
            'tax_amount': s.tax_amount or 0,
            'total_taxable_sale_value': s.total_taxable_sale_value or 0,
            'end_customer_state_new': s.end_customer_state_new,
            'hsn_code': s.hsn_code,
            'quantity': s.quantity or 0
        } for s in meesho_sales]
        
        # === FLIPKART DATA ===
        flipkart_sales_data = [{
            'marketplace': o.marketplace,  # 'Flipkart' or 'Shopsy'
            'gst_rate': (o.igst_rate or o.cgst_rate or o.sgst_rate or 0),  # FIXED: Use any available rate field
            'tax_amount': ((o.igst_amount or 0) + (o.cgst_amount or 0) + (o.sgst_amount or 0)),  # FIXED: Sum all tax components
            'total_taxable_sale_value': o.taxable_value or 0,  # FIXED: Use taxable_value, not invoice_amount
            'end_customer_state_new': o.customer_delivery_state,
            'hsn_code': o.hsn_code,  # FIXED: Flipkart uses hsn_code, not hsn_sac
            'quantity': o.quantity or 0
        } for o in flipkart_orders]
        
        # === AMAZON DATA ===
        amazon_sales_data = [{
            'marketplace': 'Amazon',
            'gst_rate': (o.igst_rate or o.cgst_rate or o.sgst_rate or 0),  # FIXED: Use any available rate field
            'tax_amount': ((o.cgst_amount or 0) + (o.sgst_amount or 0) + (o.igst_amount or 0) + (o.utgst_amount or 0)),
            'total_taxable_sale_value': o.taxable_value or 0,  # FIXED: Use taxable_value, not invoice_amount
            'end_customer_state_new': o.ship_to_state,
            'hsn_code': o.hsn_sac,  # Amazon uses hsn_sac
            'quantity': o.quantity or 0
        } for o in amazon_orders]
        
        # Combine all marketplace data
        all_sales_data = meesho_sales_data + flipkart_sales_data + amazon_sales_data
        df_sales = pd.DataFrame(all_sales_data)
        
        if df_sales.empty:
            return {'error': 'No sales data available'}
        
        # Calculate total tax liability from sales
        total_tax_from_sales = df_sales['tax_amount'].sum()
        
        # === CALCULATE TAX FROM RETURNS - ALL MARKETPLACES ===
        total_tax_from_returns = 0
        
        # Meesho returns
        if meesho_returns:
            meesho_return_tax = sum(r.tax_amount or 0 for r in meesho_returns)
            total_tax_from_returns += meesho_return_tax
        
        # Flipkart returns - FIXED: Sum individual tax components, not total_tax_amount
        if flipkart_returns:
            flipkart_return_tax = sum((r.igst_amount or 0) + (r.cgst_amount or 0) + (r.sgst_amount or 0) for r in flipkart_returns)
            total_tax_from_returns += flipkart_return_tax
        
        # Amazon returns - FIXED: AmazonReturn doesn't have utgst_amount field
        if amazon_returns:
            amazon_return_tax = sum((r.cgst_amount or 0) + (r.sgst_amount or 0) + (r.igst_amount or 0) for r in amazon_returns)
            total_tax_from_returns += amazon_return_tax
        
        net_tax_liability = total_tax_from_sales - total_tax_from_returns
        
        # GST by state - ALL MARKETPLACES
        gst_by_state = (
            df_sales.groupby('end_customer_state_new')['tax_amount'].sum()
            .sort_values(ascending=False).head(15).reset_index()
        )
        gst_state_list = [[row['end_customer_state_new'], round(row['tax_amount'], 2)] 
                          for _, row in gst_by_state.iterrows()]
        
        # GST by product (HSN) - ALL MARKETPLACES
        gst_by_hsn = (
            df_sales.groupby('hsn_code')['tax_amount'].sum()
            .sort_values(ascending=False).head(15).reset_index()
        )
        gst_hsn_list = [[row['hsn_code'], round(row['tax_amount'], 2)] 
                        for _, row in gst_by_hsn.iterrows()]
        
        # GST rate distribution - ALL MARKETPLACES
        rate_dist = df_sales['gst_rate'].value_counts().to_dict()
        
        # Tax credit tracking (simplified)
        total_value_with_tax = df_sales['total_taxable_sale_value'].sum() + total_tax_from_sales
        
        # Filing readiness check - ALL MARKETPLACES
        filing_ready = {
            'has_sales_data': len(all_sales_data) > 0,
            'has_return_data': (len(meesho_returns) + len(flipkart_returns) + len(amazon_returns)) > 0,
            'hsn_codes_present': df_sales['hsn_code'].notna().sum() / len(df_sales) > 0.9,  # 90% coverage
            'state_info_complete': df_sales['end_customer_state_new'].notna().sum() / len(df_sales) > 0.9  # 90% coverage
        }
        
        # Marketplace breakdown
        marketplace_tax = df_sales.groupby('marketplace')['tax_amount'].sum().to_dict()
        
        return {
            'net_tax_liability': round(net_tax_liability, 2),
            'total_sales_tax': round(total_tax_from_sales, 2),
            'total_return_tax': round(total_tax_from_returns, 2),
            'gst_by_state': gst_state_list,
            'gst_by_product_hsn': gst_hsn_list,
            'gst_rate_distribution': rate_dist,
            'total_taxable_value': round(df_sales['total_taxable_sale_value'].sum(), 2),
            'total_value_with_tax': round(total_value_with_tax, 2),
            'filing_ready': filing_ready,
            'total_transactions': len(all_sales_data),
            'marketplace_breakdown': {k: round(v, 2) for k, v in marketplace_tax.items()}
        }
    except Exception as e:
        return {'error': str(e)}


def generate_b2b_csv(financial_year, month_number, gstin_or_supplier_id, db,
                     file_path=None, output_folder=None):
    """
    Generate B2B invoice-level CSV from Amazon B2B transactions (where customer_bill_to_gstid is present).
    Complies with GSTR-1 Table 4A, 4B, 4C format with rate-wise breakdown.
    
    Args:
        gstin_or_supplier_id: Either GSTIN string or legacy supplier_id integer
    
    GSTR-1 Compliance:
    - Invoice-level details for all B2B supplies (Table 4A)
    - Rate-wise breakdown (multiple rows per invoice if different GST rates)
    - Includes recipient GSTIN for ITC claim
    - Place of Supply for destination-based taxation
    
    Format: GSTIN of Supplier, Trade/Legal name, Receiver GSTIN, Invoice Number, Invoice date,
            Invoice Value, Place of Supply, Reverse Charge, Invoice Type, E-Commerce GSTIN, 
            Rate, Taxable Value, Cess Amount
    """
    from models import AmazonOrder, AmazonReturn
    from datetime import datetime
    
    # Calculate month start and end dates
    if month_number <= 3:  # Jan-Mar
        year = financial_year
    else:  # Apr-Dec
        year = financial_year - 1
    
    month_start = datetime(year, month_number, 1)
    if month_number == 12:
        month_end = datetime(year + 1, 1, 1)
    else:
        month_end = datetime(year, month_number + 1, 1)
    
    # Query B2B transactions (where customer GSTIN is present)
    b2b_orders = db.query(AmazonOrder).filter(
        AmazonOrder.transaction_type == TransactionType.SHIPMENT,
        AmazonOrder.customer_bill_to_gstid.isnot(None),
        AmazonOrder.customer_bill_to_gstid != '',
        AmazonOrder.customer_bill_to_gstid != 'nan',
        AmazonOrder.order_date >= month_start,
        AmazonOrder.order_date < month_end
    ).all()
    
    b2b_returns = db.query(AmazonReturn).filter(
        AmazonReturn.customer_bill_to_gstid.isnot(None),
        AmazonReturn.customer_bill_to_gstid != '',
        AmazonReturn.customer_bill_to_gstid != 'nan',
        AmazonReturn.order_date >= month_start,
        AmazonReturn.order_date < month_end
    ).all()
    
    # Group by (invoice_no, rate) to create rate-wise breakdown per invoice (GSTR-1 requirement)
    invoice_data = {}
    
    for order in b2b_orders:
        invoice_no = order.invoice_number or "UNKNOWN"
        
        # Calculate GST rate for this order
        if order.igst_rate and order.igst_rate > 0:
            rate = round(order.igst_rate, 2)
        elif order.cgst_rate and order.sgst_rate:
            rate = round(order.cgst_rate + order.sgst_rate, 2)
        else:
            rate = 0
        
        # Key: (invoice_no, rate) for rate-wise breakdown
        key = (invoice_no, rate)
        
        if key not in invoice_data:
            invoice_data[key] = {
                'receiver_gstin': order.customer_bill_to_gstid or "",
                'receiver_name': order.buyer_name or "",
                'invoice_date': order.invoice_date,
                'place_of_supply': get_state_code(order.bill_to_state or order.ship_to_state),
                'invoice_value': 0,
                'taxable_value': 0,
                'igst_amount': 0,
                'cgst_amount': 0,
                'sgst_amount': 0,
                'rate': rate
            }
        
        invoice_data[key]['invoice_value'] += (order.invoice_amount or 0)
        invoice_data[key]['taxable_value'] += (order.taxable_value or 0)
        invoice_data[key]['igst_amount'] += (order.igst_amount or 0)
        invoice_data[key]['cgst_amount'] += (order.cgst_amount or 0)
        invoice_data[key]['sgst_amount'] += (order.sgst_amount or 0)
    
    # Subtract returns (rate-wise)
    for ret in b2b_returns:
        invoice_no = ret.invoice_number or "UNKNOWN"
        
        # Calculate GST rate from return amounts
        taxable = ret.taxable_value or 0
        if taxable > 0:
            total_tax = (ret.igst_amount or 0) + (ret.cgst_amount or 0) + (ret.sgst_amount or 0)
            rate = round((total_tax / taxable * 100), 2)
        else:
            rate = 0
        
        key = (invoice_no, rate)
        if key in invoice_data:
            invoice_data[key]['taxable_value'] -= (ret.taxable_value or 0)
            invoice_data[key]['igst_amount'] -= (ret.igst_amount or 0)
            invoice_data[key]['cgst_amount'] -= (ret.cgst_amount or 0)
            invoice_data[key]['sgst_amount'] -= (ret.sgst_amount or 0)
    
    # Get supplier GSTIN - accept either GSTIN string or legacy supplier_id
    if isinstance(gstin_or_supplier_id, str) and len(gstin_or_supplier_id) == 15:
        supplier_gstin = gstin_or_supplier_id
    else:
        supplier_gstin = get_gstin_for_supplier(gstin_or_supplier_id, db)
    
    # Output B2B CSV (GSTR-1 Table 4A format with rate-wise breakdown)
    if not file_path:
        file_path = os.path.join(output_folder or "", "b2b.csv")
    
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "GSTIN of Supplier", "Trade/Legal name of the Recipient", "GSTIN/UIN of Recipient",
            "Invoice Number", "Invoice date", "Invoice Value", "Place Of Supply", "Reverse Charge",
            "Invoice Type", "E-Commerce GSTIN", "Rate", "Taxable Value", "Cess Amount"
        ])
        writer.writeheader()
        
        for (invoice_no, rate), data in sorted(invoice_data.items()):
            invoice_date_str = data['invoice_date'].strftime("%d-%m-%Y") if data['invoice_date'] else ""
            writer.writerow({
                "GSTIN of Supplier": supplier_gstin,
                "Trade/Legal name of the Recipient": data['receiver_name'],
                "GSTIN/UIN of Recipient": data['receiver_gstin'],
                "Invoice Number": invoice_no,
                "Invoice date": invoice_date_str,
                "Invoice Value": round(data['invoice_value'], 2),
                "Place Of Supply": data['place_of_supply'],
                "Reverse Charge": "N",
                "Invoice Type": "Regular",
                "E-Commerce GSTIN": "",
                "Rate": data['rate'],
                "Taxable Value": round(data['taxable_value'], 2),
                "Cess Amount": ""
            })
    
    return f"✅ B2B CSV written to {file_path} with {len(invoice_data)} invoices (Amazon B2B transactions)."


def generate_hsn_b2b_csv(financial_year, month_number, gstin_or_supplier_id, db,
                         file_path=None, output_folder=None):
    """
    Generate HSN-wise summary CSV for B2B transactions.
    
    Args:
        gstin_or_supplier_id: Either GSTIN string or legacy supplier_id integer
        
    Format: HSN, Description, UQC, Total Quantity, Total Value, Taxable Value,
            Integrated Tax Amount, Central Tax Amount, State/UT Tax Amount, Cess Amount
    """
    from models import AmazonOrder, AmazonReturn
    from datetime import datetime
    
    # Calculate month start and end dates
    if month_number <= 3:  # Jan-Mar
        year = financial_year
    else:  # Apr-Dec
        year = financial_year - 1
    
    month_start = datetime(year, month_number, 1)
    if month_number == 12:
        month_end = datetime(year + 1, 1, 1)
    else:
        month_end = datetime(year, month_number + 1, 1)
    
    # Query B2B transactions (where customer GSTIN is present)
    b2b_orders = db.query(AmazonOrder).filter(
        AmazonOrder.transaction_type == TransactionType.SHIPMENT,
        AmazonOrder.customer_bill_to_gstid.isnot(None),
        AmazonOrder.customer_bill_to_gstid != '',
        AmazonOrder.customer_bill_to_gstid != 'nan',
        AmazonOrder.order_date >= month_start,
        AmazonOrder.order_date < month_end
    ).all()
    
    b2b_returns = db.query(AmazonReturn).filter(
        AmazonReturn.customer_bill_to_gstid.isnot(None),
        AmazonReturn.customer_bill_to_gstid != '',
        AmazonReturn.customer_bill_to_gstid != 'nan',
        AmazonReturn.order_date >= month_start,
        AmazonReturn.order_date < month_end
    ).all()
    
    # Aggregate by HSN
    hsn_data = {}
    
    for order in b2b_orders:
        hsn = str(order.hsn_sac or "UNKNOWN")
        if hsn not in hsn_data:
            hsn_data[hsn] = {
                'description': order.item_description or "",
                'quantity': 0,
                'total_value': 0,
                'taxable_value': 0,
                'igst_amount': 0,
                'cgst_amount': 0,
                'sgst_amount': 0
            }
        
        hsn_data[hsn]['quantity'] += (order.quantity or 0)
        hsn_data[hsn]['total_value'] += (order.invoice_amount or 0)
        hsn_data[hsn]['taxable_value'] += (order.taxable_value or 0)
        hsn_data[hsn]['igst_amount'] += (order.igst_amount or 0)
        hsn_data[hsn]['cgst_amount'] += (order.cgst_amount or 0)
        hsn_data[hsn]['sgst_amount'] += (order.sgst_amount or 0)
    
    # Subtract returns
    for ret in b2b_returns:
        hsn = str(ret.hsn_sac or "UNKNOWN")
        if hsn in hsn_data:
            hsn_data[hsn]['quantity'] -= (ret.quantity or 0)
            hsn_data[hsn]['taxable_value'] -= (ret.taxable_value or 0)
            hsn_data[hsn]['igst_amount'] -= (ret.igst_amount or 0)
            hsn_data[hsn]['cgst_amount'] -= (ret.cgst_amount or 0)
            hsn_data[hsn]['sgst_amount'] -= (ret.sgst_amount or 0)
    
    # Output HSN B2B CSV
    if not file_path:
        file_path = os.path.join(output_folder or "", "hsn(b2b).csv")
    
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "HSN", "Description", "UQC", "Total Quantity", "Total Value",
            "Taxable Value", "Integrated Tax Amount", "Central Tax Amount",
            "State/UT Tax Amount", "Cess Amount"
        ])
        writer.writeheader()
        
        for hsn, data in sorted(hsn_data.items()):
            writer.writerow({
                "HSN": hsn,
                "Description": data['description'][:30] if data['description'] else "",  # Truncate for readability
                "UQC": "NOS",  # Unit: Numbers
                "Total Quantity": data['quantity'],
                "Total Value": round(data['total_value'], 2),
                "Taxable Value": round(data['taxable_value'], 2),
                "Integrated Tax Amount": round(data['igst_amount'], 2),
                "Central Tax Amount": round(data['cgst_amount'], 2),
                "State/UT Tax Amount": round(data['sgst_amount'], 2),
                "Cess Amount": ""
            })
    
    return f"✅ HSN (B2B) CSV written to {file_path} with {len(hsn_data)} HSN codes (Amazon B2B transactions)."


def generate_b2cl_csv(financial_year, month_number, gstin_or_supplier_id, db,
                      file_path=None, output_folder=None):
    """
    Generate B2CL (B2C Large) CSV for B2C transactions with invoice value > Rs 2.5 Lakhs.
    Complies with GSTR-1 Table 5 format.
    
    Args:
        gstin_or_supplier_id: Either GSTIN string or legacy supplier_id integer
    
    GSTR-1 Compliance:
    - Invoice-level details for B2C supplies where invoice value > 2,50,000
    - Inter-state supplies only (as per GSTR-1 requirement)
    - Rate-wise breakdown per invoice
    
    Format: Invoice Number, Invoice date, Invoice Value, Place Of Supply, Applicable % of Tax Rate,
            Rate, Taxable Value, Cess Amount, E-Commerce GSTIN
    """
    from models import AmazonOrder, AmazonReturn
    from datetime import datetime
    
    # Calculate month start and end dates
    if month_number <= 3:  # Jan-Mar
        year = financial_year
    else:  # Apr-Dec
        year = financial_year - 1
    
    month_start = datetime(year, month_number, 1)
    if month_number == 12:
        month_end = datetime(year + 1, 1, 1)
    else:
        month_end = datetime(year, month_number + 1, 1)
    
    # Get supplier state for determining inter/intra state - accept either GSTIN string or legacy supplier_id
    if isinstance(gstin_or_supplier_id, str) and len(gstin_or_supplier_id) == 15:
        supplier_gstin = gstin_or_supplier_id
    else:
        supplier_gstin = get_gstin_for_supplier(gstin_or_supplier_id, db)
    supplier_state_code = supplier_gstin[:2] if supplier_gstin and len(supplier_gstin) >= 2 else None
    
    # Query B2C Large transactions (no customer GSTIN and invoice value > threshold)
    # Note: For simplicity, we're checking individual order amounts. In production, 
    # you may need to aggregate by invoice first to get true invoice value
    large_orders = db.query(AmazonOrder).filter(
        AmazonOrder.transaction_type == TransactionType.SHIPMENT,
        AmazonOrder.order_date >= month_start,
        AmazonOrder.order_date < month_end,
        # B2C: No customer GSTIN or empty
        (AmazonOrder.customer_bill_to_gstid.is_(None) | 
         (AmazonOrder.customer_bill_to_gstid == '') | 
         (AmazonOrder.customer_bill_to_gstid == 'nan')),
        # Large: Invoice value > B2CL threshold
        AmazonOrder.invoice_amount > B2CL_INVOICE_THRESHOLD
    ).all()
    
    # Group by (invoice_no, rate) for rate-wise breakdown
    invoice_data = {}
    
    for order in large_orders:
        invoice_no = order.invoice_number or "UNKNOWN"
        
        # Calculate GST rate
        if order.igst_rate and order.igst_rate > 0:
            rate = round(order.igst_rate, 2)
        elif order.cgst_rate and order.sgst_rate:
            rate = round(order.cgst_rate + order.sgst_rate, 2)
        else:
            rate = 0
        
        # Determine if inter-state (GSTR-1 requirement: B2CL is for inter-state only)
        ship_to_state_code = None
        if order.ship_to_state:
            # Use helper function to get state code
            state_code_formatted = get_state_code(order.ship_to_state)
            if state_code_formatted and '-' in state_code_formatted:
                ship_to_state_code = state_code_formatted.split('-')[0]
        
        # Only include inter-state supplies (ship_to_state != supplier_state)
        if supplier_state_code and ship_to_state_code and supplier_state_code == ship_to_state_code:
            continue  # Skip intra-state supplies
        
        key = (invoice_no, rate)
        
        if key not in invoice_data:
            invoice_data[key] = {
                'invoice_date': order.invoice_date,
                'place_of_supply': get_state_code(order.ship_to_state) if order.ship_to_state else "",
                'invoice_value': 0,
                'taxable_value': 0,
                'rate': rate
            }
        
        invoice_data[key]['invoice_value'] += (order.invoice_amount or 0)
        invoice_data[key]['taxable_value'] += (order.taxable_value or 0)
    
    # Output B2CL CSV
    if not file_path:
        file_path = os.path.join(output_folder or "", "b2cl.csv")
    
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "Invoice Number", "Invoice date", "Invoice Value", "Place Of Supply",
            "Applicable % of Tax Rate", "Rate", "Taxable Value", "Cess Amount", "E-Commerce GSTIN"
        ])
        writer.writeheader()
        
        for (invoice_no, rate), data in sorted(invoice_data.items()):
            invoice_date_str = data['invoice_date'].strftime("%d-%b-%y") if data['invoice_date'] else ""
            writer.writerow({
                "Invoice Number": invoice_no,
                "Invoice date": invoice_date_str,
                "Invoice Value": round(data['invoice_value'], 2),
                "Place Of Supply": data['place_of_supply'],
                "Applicable % of Tax Rate": "",  # Optional field
                "Rate": rate,
                "Taxable Value": round(data['taxable_value'], 2),
                "Cess Amount": "",
                "E-Commerce GSTIN": ""  # Blank if not e-commerce operator
            })
    
    return f"✅ B2CL CSV written to {file_path} with {len(invoice_data)} large B2C invoices (>2.5L, inter-state)."


def generate_cdnr_csv(financial_year, month_number, supplier_id, db,
                      file_path=None, output_folder=None):
    """
    Generate CDNR (Credit/Debit Notes - Registered) CSV for returns/adjustments to B2B customers.
    Complies with GSTR-1 Table 9B format.
    
    GSTR-1 Compliance:
    - Credit notes issued to registered persons (with GSTIN)
    - Debit notes for additional charges
    - Note-level details with reference to original supply
    
    Format: GSTIN/UIN of Recipient, Receiver Name, Note Number, Note Date, Note Type, 
            Place Of Supply, Reverse Charge, Note Supply Type, Note Value, Applicable % of Tax Rate,
            Rate, Taxable Value, Cess Amount
    """
    from models import AmazonReturn
    from datetime import datetime
    
    # Calculate month start and end dates
    if month_number <= 3:  # Jan-Mar
        year = financial_year
    else:  # Apr-Dec
        year = financial_year - 1
    
    month_start = datetime(year, month_number, 1)
    if month_number == 12:
        month_end = datetime(year + 1, 1, 1)
    else:
        month_end = datetime(year, month_number + 1, 1)
    
    # Query returns to B2B customers (those with GSTIN)
    b2b_returns = db.query(AmazonReturn).filter(
        AmazonReturn.transaction_type.in_([TransactionType.REFUND, TransactionType.CANCEL]),
        AmazonReturn.customer_bill_to_gstid.isnot(None),
        AmazonReturn.customer_bill_to_gstid != '',
        AmazonReturn.customer_bill_to_gstid != 'nan',
        AmazonReturn.order_date >= month_start,
        AmazonReturn.order_date < month_end
    ).all()
    
    # Group by (invoice_no, rate) for rate-wise breakdown
    note_data = {}
    
    for ret in b2b_returns:
        # Generate note number using helper function
        note_no = generate_note_number(
            ret.invoice_number or ret.order_id,
            NoteType.CREDIT
        )
        
        # Calculate GST rate from return amounts
        taxable = abs(ret.taxable_value or 0)
        if taxable > 0:
            total_tax = abs(ret.igst_amount or 0) + abs(ret.cgst_amount or 0) + abs(ret.sgst_amount or 0)
            rate = round((total_tax / taxable * 100), 2)
        else:
            rate = 0
        
        key = (note_no, rate)
        
        if key not in note_data:
            note_data[key] = {
                'receiver_gstin': ret.customer_bill_to_gstid or "",
                'receiver_name': ret.buyer_name or "",
                'note_date': ret.invoice_date,
                'note_type': NoteType.CREDIT,  # Credit Note for returns
                'place_of_supply': get_state_code(ret.ship_to_state) if ret.ship_to_state else "",
                'note_value': 0,
                'taxable_value': 0,
                'rate': rate
            }
        
        # Return amounts are typically negative, so take absolute value
        note_data[key]['note_value'] += abs(ret.return_amount or 0)
        note_data[key]['taxable_value'] += abs(ret.taxable_value or 0)
    
    # Output CDNR CSV
    if not file_path:
        file_path = os.path.join(output_folder or "", "cdnr.csv")
    
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "GSTIN/UIN of Recipient", "Receiver Name", "Note Number", "Note Date", "Note Type",
            "Place Of Supply", "Reverse Charge", "Note Supply Type", "Note Value",
            "Applicable % of Tax Rate", "Rate", "Taxable Value", "Cess Amount"
        ])
        writer.writeheader()
        
        for (note_no, rate), data in sorted(note_data.items()):
            note_date_str = data['note_date'].strftime("%d-%b-%y") if data['note_date'] else ""
            writer.writerow({
                "GSTIN/UIN of Recipient": data['receiver_gstin'],
                "Receiver Name": data['receiver_name'],
                "Note Number": note_no,
                "Note Date": note_date_str,
                "Note Type": data['note_type'],  # C or D
                "Place Of Supply": data['place_of_supply'],
                "Reverse Charge": "N",
                "Note Supply Type": "Regular B2B",
                "Note Value": round(data['note_value'], 2),
                "Applicable % of Tax Rate": "",
                "Rate": rate,
                "Taxable Value": round(data['taxable_value'], 2),
                "Cess Amount": ""
            })
    
    return f"✅ CDNR CSV written to {file_path} with {len(note_data)} credit/debit notes (B2B returns)."


def generate_gstr1_excel_workbook(financial_year, month_number, gstin_or_supplier_id, db,
                                   file_path=None, output_folder=None):
    """
    Generate comprehensive GSTR-1 Excel Workbook with all tables in separate sheets.
    This creates a single Excel file similar to the official GSTR1_Excel_Workbook_Template.
    
    Args:
        gstin_or_supplier_id: Either GSTIN string or legacy supplier_id integer
    
    Includes all major GSTR-1 tables:
    - B2B (Table 4A, 4B, 4C) - Business to Business supplies
    - B2CL (Table 5) - Large B2C invoices (>2.5L, inter-state)
    - B2CS (Table 7) - Small B2C invoices (consolidated)
    - CDNR (Table 9B) - Credit/Debit notes for registered persons
    - HSN (Table 12) - HSN-wise summary
    - DOCS (Table 13) - Document details
    
    Args:
        financial_year: FY starting year (e.g., 2024 for FY 2024-25)
        month_number: Month (1-12)
        supplier_id: Supplier database ID
        db: SQLAlchemy database session
        file_path: Optional custom output file path
        output_folder: Optional output directory
        
    Returns:
        Success message with file path and summary
    """
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from datetime import datetime
    import tempfile
    import csv as csv_module
    
    # Determine output file path
    if not file_path:
        # Calculate calendar year from financial year and month
        # FY 2025 = Apr 2025 to Mar 2026
        # Months 4-12: Use financial_year (e.g., Oct 2025 for FY 2025)
        # Months 1-3: Use financial_year + 1 (e.g., Jan 2026 for FY 2025)
        if month_number <= 3:
            year = financial_year + 1
        else:
            year = financial_year
        
        month_name = datetime(year, month_number, 1).strftime("%B")
        file_name = f"GSTR1_FY{financial_year}_{month_name}_{year}.xlsx"
        file_path = os.path.join(output_folder or "", file_name)
    
    # Create workbook
    wb = Workbook()
    wb.remove(wb.active)  # Remove default sheet
    
    # Create a summary sheet as the default/first sheet to avoid the openpyxl warning
    ws_summary = wb.create_sheet("Summary", 0)
    ws_summary['A1'] = f"GSTR-1 Report"
    ws_summary['A2'] = f"Financial Year: {financial_year}"
    ws_summary['A3'] = f"Month: {month_number}"
    
    # Define styling
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
    header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin_border = Border(
        left=Side(style='thin'),
        right=Side(style='thin'),
        top=Side(style='thin'),
        bottom=Side(style='thin')
    )
    
    def style_header_row(ws, row_num=1):
        """Apply header styling to a row."""
        for cell in ws[row_num]:
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = thin_border
    
    def auto_adjust_column_width(ws):
        """Auto-adjust column widths based on content."""
        for column in ws.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)
            
            for cell in column:
                try:
                    if cell.value:
                        max_length = max(max_length, len(str(cell.value)))
                except:
                    pass
            
            adjusted_width = min(max_length + 2, 50)  # Max width 50
            ws.column_dimensions[column_letter].width = adjusted_width
    
    # Generate each CSV in memory and add to workbook
    table_count = 0
    total_records = 0
    
    # 1. B2B Sheet
    try:
        temp_csv = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', newline='', encoding='utf-8')
        temp_csv_path = temp_csv.name
        temp_csv.close()
        
        result = generate_b2b_csv(financial_year, month_number, gstin_or_supplier_id, db, file_path=temp_csv_path)
        
        # Read CSV and add to Excel
        ws = wb.create_sheet("B2B")
        with open(temp_csv_path, 'r', encoding='utf-8') as csvfile:
            reader = csv_module.reader(csvfile)
            for row_idx, row in enumerate(reader, 1):
                for col_idx, value in enumerate(row, 1):
                    cell = ws.cell(row=row_idx, column=col_idx, value=value)
                    if row_idx == 1:
                        cell.border = thin_border
        
        style_header_row(ws, 1)
        auto_adjust_column_width(ws)
        os.unlink(temp_csv_path)
        
        # Extract record count from result message
        import re
        match = re.search(r'with (\d+)', result)
        if match:
            count = int(match.group(1))
            total_records += count
        table_count += 1
    except Exception as e:
        print(f"⚠️  Warning: Could not generate B2B sheet: {e}")
    
    # 2. B2CL Sheet
    try:
        temp_csv = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', newline='', encoding='utf-8')
        temp_csv_path = temp_csv.name
        temp_csv.close()
        
        result = generate_b2cl_csv(financial_year, month_number, gstin_or_supplier_id, db, file_path=temp_csv_path)
        
        ws = wb.create_sheet("B2CL")
        with open(temp_csv_path, 'r', encoding='utf-8') as csvfile:
            reader = csv_module.reader(csvfile)
            for row_idx, row in enumerate(reader, 1):
                for col_idx, value in enumerate(row, 1):
                    ws.cell(row=row_idx, column=col_idx, value=value)
        
        style_header_row(ws, 1)
        auto_adjust_column_width(ws)
        os.unlink(temp_csv_path)
        
        match = re.search(r'with (\d+)', result)
        if match:
            count = int(match.group(1))
            total_records += count
        table_count += 1
    except Exception as e:
        print(f"⚠️  Warning: Could not generate B2CL sheet: {e}")
    
    # 3. B2CS Sheet (B2C Small - using generate_gst_pivot_csv)
    try:
        temp_csv = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', newline='', encoding='utf-8')
        temp_csv_path = temp_csv.name
        temp_csv.close()
        
        # B2CS data is generated by generate_gst_pivot_csv function
        result = generate_gst_pivot_csv(financial_year, month_number, gstin_or_supplier_id, db, file_path=temp_csv_path)
        
        ws = wb.create_sheet("B2CS")
        with open(temp_csv_path, 'r', encoding='utf-8') as csvfile:
            reader = csv_module.reader(csvfile)
            for row_idx, row in enumerate(reader, 1):
                for col_idx, value in enumerate(row, 1):
                    ws.cell(row=row_idx, column=col_idx, value=value)
        
        style_header_row(ws, 1)
        auto_adjust_column_width(ws)
        os.unlink(temp_csv_path)
        
        match = re.search(r'with (\d+)', result)
        if match:
            count = int(match.group(1))
            total_records += count
        table_count += 1
    except Exception as e:
        print(f"⚠️  Warning: Could not generate B2CS sheet: {e}")
    
    # 4. CDNR Sheet
    try:
        temp_csv = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', newline='', encoding='utf-8')
        temp_csv_path = temp_csv.name
        temp_csv.close()
        
        result = generate_cdnr_csv(financial_year, month_number, gstin_or_supplier_id, db, file_path=temp_csv_path)
        
        ws = wb.create_sheet("CDNR")
        with open(temp_csv_path, 'r', encoding='utf-8') as csvfile:
            reader = csv_module.reader(csvfile)
            for row_idx, row in enumerate(reader, 1):
                for col_idx, value in enumerate(row, 1):
                    ws.cell(row=row_idx, column=col_idx, value=value)
        
        style_header_row(ws, 1)
        auto_adjust_column_width(ws)
        os.unlink(temp_csv_path)
        
        match = re.search(r'with (\d+)', result)
        if match:
            count = int(match.group(1))
            total_records += count
        table_count += 1
    except Exception as e:
        print(f"⚠️  Warning: Could not generate CDNR sheet: {e}")
    
    # 5. HSN Summary Sheet
    try:
        temp_csv = tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.csv', newline='', encoding='utf-8')
        temp_csv_path = temp_csv.name
        temp_csv.close()
        
        result = generate_hsn_b2b_csv(financial_year, month_number, gstin_or_supplier_id, db, file_path=temp_csv_path)
        
        ws = wb.create_sheet("HSN")
        with open(temp_csv_path, 'r', encoding='utf-8') as csvfile:
            reader = csv_module.reader(csvfile)
            for row_idx, row in enumerate(reader, 1):
                for col_idx, value in enumerate(row, 1):
                    ws.cell(row=row_idx, column=col_idx, value=value)
        
        style_header_row(ws, 1)
        auto_adjust_column_width(ws)
        os.unlink(temp_csv_path)
        
        match = re.search(r'with (\d+)', result)
        if match:
            count = int(match.group(1))
            total_records += count
        table_count += 1
    except Exception as e:
        print(f"⚠️  Warning: Could not generate HSN sheet: {e}")
    
    # 6. Add summary/index sheet as first sheet
    ws_summary = wb.create_sheet("Summary", 0)
    
    # Add summary information
    # Financial year runs April to March
    # April-December (months 4-12): Use financial_year as calendar year
    # January-March (months 1-3): Use financial_year + 1 as calendar year
    if month_number <= 3:
        year = financial_year + 1  # Jan-Mar are in next calendar year
    else:
        year = financial_year  # Apr-Dec are in same calendar year
    
    month_name = datetime(year, month_number, 1).strftime("%B %Y")
    
    summary_data = [
        ["GSTR-1 Return Summary"],
        [""],
        ["Financial Year:", f"FY {financial_year}-{financial_year+1}"],
        ["Period:", month_name],
        ["Generated On:", datetime.now().strftime("%d-%b-%Y %H:%M:%S")],
        [""],
        ["Tables Included:", ""],
        ["  - B2B (Business to Business)", "Invoices to registered persons"],
        ["  - B2CL (B2C Large)", "B2C invoices >₹2.5L (inter-state)"],
        ["  - B2CS (B2C Small)", "Consolidated B2C supplies"],
        ["  - CDNR (Credit/Debit Notes)", "Notes for registered persons"],
        ["  - HSN Summary", "HSN-wise summary"],
        [""],
        ["Statistics:", ""],
        [f"  Total Tables Generated:", table_count],
        [f"  Total Records:", total_records],
        [""],
        ["Instructions:", ""],
        ["  1. Review each sheet for accuracy"],
        ["  2. Upload to GST portal offline tool"],
        ["  3. Validate before filing"],
        [""],
        ["⚠️ Note:", "This is auto-generated data. Please verify before filing."]
    ]
    
    for row_idx, row_data in enumerate(summary_data, 1):
        for col_idx, value in enumerate(row_data, 1):
            cell = ws_summary.cell(row=row_idx, column=col_idx, value=value)
            
            # Style first row as title
            if row_idx == 1:
                cell.font = Font(bold=True, size=16, color="FFFFFF")
                cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
                cell.alignment = Alignment(horizontal="center", vertical="center")
            
            # Style section headers
            elif col_idx == 1 and value and value.endswith(":") and len(value) > 5:
                cell.font = Font(bold=True, size=11)
    
    ws_summary.column_dimensions['A'].width = 30
    ws_summary.column_dimensions['B'].width = 50
    
    # Save workbook
    wb.save(file_path)
    
    return f"✅ GSTR-1 Excel Workbook created: {file_path}\n   📊 {table_count} tables with {total_records} total records"


def generate_returns_json(b2cs_csv_path, hsn_csv_path, gstin, financial_year, month_number, 
                         output_folder=None, version=None, hsn_sac_xlsx_path=None):
    """
    Generate a returns JSON file compatible with GST offline tool from B2CS and HSN CSV files.
    
    Args:
        b2cs_csv_path (str): Path to b2cs.csv file
        hsn_csv_path (str): Path to hsn(b2c).csv file  
        gstin (str): 15-character GSTIN
        financial_year (int): Financial year
        month_number (int): Month number (1-12)
        output_folder (str): Output folder for JSON file
        version (str): JSON version (default: "GST3.2.3" from config)
        hsn_sac_xlsx_path (str): Optional path to HSN_SAC.xlsx for description enrichment
        
    Returns:
        str: Success/error message with file path
    """
    import json
    import csv
    from datetime import datetime
    from constants import STATE_CODE_MAPPING, Config
    
    try:
        # Validation
        if not gstin or len(gstin) != 15:
            return f"❌ Invalid GSTIN: must be 15 characters"
        
        if not os.path.exists(b2cs_csv_path):
            return f"❌ B2CS CSV file not found: {b2cs_csv_path}"
        
        if not os.path.exists(hsn_csv_path):
            return f"❌ HSN CSV file not found: {hsn_csv_path}"
        
        if hsn_sac_xlsx_path and not os.path.exists(hsn_sac_xlsx_path):
            return f"❌ HSN_SAC Excel file not found: {hsn_sac_xlsx_path}"
        
        # Use default version if not provided
        if not version:
            version = getattr(Config, 'OFFLINE_JSON_VERSION', 'GST3.2.3')
        
        # Calculate filing period
        if month_number <= 3:  # Jan-Mar
            fp_year = financial_year
        else:  # Apr-Dec
            fp_year = financial_year - 1
        fp = f"{month_number:02d}{fp_year}"
        
        # Get supplier state code from GSTIN
        supplier_state_code = gstin[:2].zfill(2)
        
        # Load HSN descriptions from Excel if provided
        hsn_descriptions = {}
        if hsn_sac_xlsx_path:
            try:
                from openpyxl import load_workbook
                wb = load_workbook(hsn_sac_xlsx_path)
                ws = wb.active
                for row in ws.iter_rows(min_row=2, values_only=True):
                    if row and len(row) >= 2:
                        hsn_code = str(row[0]).strip() if row[0] else ""
                        description = str(row[1]).strip() if row[1] else ""
                        if hsn_code and description:
                            hsn_descriptions[hsn_code] = description
            except Exception as e:
                print(f"⚠️  Warning: Could not load HSN descriptions from Excel: {e}")
        
        # Parse B2CS CSV
        b2cs_data = []
        try:
            with open(b2cs_csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if not row or not row.get("Place Of Supply"):
                        continue
                    
                    place_of_supply = str(row.get("Place Of Supply", "")).strip()
                    # Extract pos code from "NN-State Name" format
                    pos = place_of_supply.split("-")[0].strip().zfill(2) if "-" in place_of_supply else "00"
                    
                    rate_str = str(row.get("Rate", "0")).strip()
                    rate = int(float(rate_str)) if rate_str else 0
                    
                    txval_str = str(row.get("Taxable Value", "0")).strip()
                    txval = float(txval_str) if txval_str else 0.0
                    
                    if txval > 0 and rate >= 0:
                        # Determine supply type: INTRA if pos == supplier_state_code, else INTER
                        sply_ty = "INTRA" if pos == supplier_state_code else "INTER"
                        
                        # Calculate tax amounts
                        if sply_ty == "INTER":
                            iamt = round(txval * rate / 100, 2)
                            # Build INTER record: only include iamt, not camt/samt
                            b2cs_data.append({
                                "sply_ty": sply_ty,
                                "rt": rate,
                                "typ": "OE",
                                "pos": pos,
                                "txval": round(txval, 2),
                                "iamt": iamt,
                                "csamt": 0.0
                            })
                        else:  # INTRA
                            camt = round(txval * rate / 200, 2)
                            samt = round(txval * rate / 200, 2)
                            # Build INTRA record: only include camt/samt, not iamt
                            b2cs_data.append({
                                "sply_ty": sply_ty,
                                "rt": rate,
                                "typ": "OE",
                                "pos": pos,
                                "txval": round(txval, 2),
                                "camt": camt,
                                "samt": samt,
                                "csamt": 0.0
                            })
        except Exception as e:
            return f"❌ Error parsing B2CS CSV: {str(e)}"
        
        # Parse HSN CSV
        hsn_data = []
        num_counter = 1
        try:
            with open(hsn_csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if not row or not row.get("HSN"):
                        continue
                    
                    hsn_code = str(row.get("HSN", "")).strip()
                    if not hsn_code:
                        continue
                    
                    # Get description from CSV or enriched from Excel
                    csv_desc = str(row.get("Description", "")).strip()
                    description = hsn_descriptions.get(hsn_code, csv_desc)
                    
                    # UQC - use standard "NOS" for numbers/quantity
                    uqc = "NOS"
                    
                    qty_str = str(row.get("Total Quantity", "0")).strip()
                    qty = int(float(qty_str)) if qty_str else 0
                    
                    rate_str = str(row.get("Rate", "0")).strip()
                    rate = int(float(rate_str)) if rate_str else 0
                    
                    txval_str = str(row.get("Taxable Value", "0")).strip()
                    txval = float(txval_str) if txval_str else 0.0
                    
                    igst_str = str(row.get("Integrated Tax Amount", "0")).strip()
                    igst = float(igst_str) if igst_str else 0.0
                    
                    cgst_str = str(row.get("Central Tax Amount", "0")).strip()
                    cgst = float(cgst_str) if cgst_str else 0.0
                    
                    sgst_str = str(row.get("State/UT Tax Amount", "0")).strip()
                    sgst = float(sgst_str) if sgst_str else 0.0
                    
                    if txval >= 0:  # Include even zero value for completeness
                        iamt = round(igst, 2)
                        camt = round(cgst, 2)
                        samt = round(sgst, 2)
                        
                        hsn_data.append({
                            "num": num_counter,
                            "hsn_sc": hsn_code,
                            "desc": description,
                            "uqc": uqc,
                            "qty": qty,
                            "rt": rate,
                            "txval": round(txval, 2),
                            "iamt": iamt,
                            "camt": camt,
                            "samt": samt,
                            "csamt": 0.0
                        })
                        num_counter += 1
        except Exception as e:
            return f"❌ Error parsing HSN CSV: {str(e)}"
        
        # Build JSON structure
        json_data = {
            "gstin": gstin,
            "fp": fp,
            "version": version,
            "hash": "hash",
            "b2cs": b2cs_data,
            "hsn": {
                "hsn_b2c": hsn_data
            }
        }
        
        # Write JSON file
        if not output_folder:
            output_folder = os.path.dirname(b2cs_csv_path) or ""
        
        current_date = datetime.now().strftime("%d%m%Y")
        filename = f"returns_{current_date}_R1_{gstin}_offline.json"
        file_path = os.path.join(output_folder, filename)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, separators=(',', ':'), ensure_ascii=False)
        
        b2cs_count = len(b2cs_data)
        hsn_count = len(hsn_data)
        
        return f"✅ Returns JSON created: {filename}\n   📄 B2CS records: {b2cs_count}\n   📊 HSN records: {hsn_count}\n   💾 Location: {file_path}"
    
    except Exception as e:
        return f"❌ Unexpected error: {str(e)}"



