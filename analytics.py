"""
analytics.py - Contains business analytics functions for the Meesho Sales App.
"""

from sqlalchemy.orm import Session
from models import MeeshoSale, MeeshoReturn, MeeshoOrder, MeeshoInventory, MeeshoPayment, MeeshoInvoice, MeeshoAdsCost
import pandas as pd
from collections import defaultdict
from datetime import datetime
from constants import FixedCosts
from cost_price import load_cost_prices, get_cost_price

# Predictive Alerts Analytics
# ...functions will be moved here from logic.py...

def get_predictive_alerts_analytics(db: Session):
    """
    Returns predictive alerts:
    - Low stock alerts (current_stock < threshold)
    - Payment delay alerts (orders with no payment after X days)
    - Unusual return rate alerts (products with high return ratio)
    Note: Alerts are sorted by most selling products (total quantity sold)
    """
    try:
        inventories = db.query(MeeshoInventory).all()
        payments = db.query(MeeshoPayment).all()
        orders = db.query(MeeshoOrder).all()
        returns = db.query(MeeshoReturn).all()
        
        import pandas as pd
        
        # Calculate total quantity sold per product for sorting
        df_orders_full = pd.DataFrame([
            {'product_id': o.product_id, 'product_name': o.product_name, 'quantity': o.quantity or 0} 
            for o in orders if o.product_id
        ])
        total_qty_by_product = df_orders_full.groupby('product_id')['quantity'].sum().to_dict() if not df_orders_full.empty else {}
        
        alerts = []
        
        # Low stock
        for inv in inventories:
            if inv.current_stock is not None and inv.current_stock < 5:
                total_sold = total_qty_by_product.get(inv.product_id, 0)
                alerts.append({
                    'type': 'Low Stock', 
                    'product': inv.product_name, 
                    'product_id': inv.product_id,
                    'current_stock': inv.current_stock,
                    'total_sold': total_sold
                })
        
        # Payment delays
        df_payments = pd.DataFrame([
            {'sub_order_no': p.sub_order_no, 'order_date': p.order_date, 'payment_date': p.payment_date} for p in payments
        ])
        if not df_payments.empty:
            df_payments['order_date'] = pd.to_datetime(df_payments['order_date'])
            df_payments['payment_date'] = pd.to_datetime(df_payments['payment_date'])
            df_payments['delay_days'] = (df_payments['payment_date'] - df_payments['order_date']).dt.days
            delayed = df_payments[df_payments['delay_days'] > 10]
            for _, row in delayed.iterrows():
                alerts.append({
                    'type': 'Payment Delay', 
                    'sub_order_no': row['sub_order_no'], 
                    'delay_days': int(row['delay_days']),
                    'total_sold': 0  # For consistent sorting
                })
        
        # Unusual return rates
        df_orders = pd.DataFrame([
            {'product_id': o.product_id, 'product_name': o.product_name, 'quantity': o.quantity or 0} for o in orders if o.product_id
        ])
        df_returns = pd.DataFrame([
            {'product_id': r.product_id, 'quantity': r.quantity or 0} for r in returns if r.product_id
        ])
        if not df_orders.empty and not df_returns.empty:
            order_qty = df_orders.groupby('product_id')['quantity'].sum()
            return_qty = df_returns.groupby('product_id')['quantity'].sum()
            return_rate = (return_qty / order_qty).fillna(0)
            for pid, rate in return_rate.items():
                if rate > 0.3 and order_qty.get(pid, 0) > 10:
                    pname = df_orders[df_orders['product_id'] == pid]['product_name'].iloc[0]
                    total_sold = total_qty_by_product.get(pid, 0)
                    alerts.append({
                        'type': 'High Return Rate', 
                        'product': pname, 
                        'product_id': pid,
                        'return_rate': round(rate*100, 2),
                        'total_sold': total_sold
                    })
        
        # Sort alerts by most selling products (total_sold descending)
        alerts = sorted(alerts, key=lambda x: x.get('total_sold', 0), reverse=True)
        
        return {'alerts': alerts}
    except Exception as e:
        return {'error': str(e)}

def get_compliance_audit_analytics(db: Session, fy: str = None, month: int = None, gstin: str = None):
    """
    Returns compliance & audit analytics:
    - Scan invoice and tax data for duplicate or anomalous invoices
    - Flag compliance issues (duplicate invoice numbers, HSN/GST mismatches)
    NOW INCLUDES DATA FROM ALL MARKETPLACES: Meesho, Flipkart, Amazon
    
    Args:
        db: Database session
        fy: Financial year filter (e.g., "2024-25" or None for all)
        month: Month filter (1-12 or None for all)
        gstin: Seller GSTIN filter (None for all sellers)
    """
    try:
        import pandas as pd
        from models import FlipkartOrder, AmazonOrder
        
        # Query all marketplace invoices with date filtering
        meesho_query = db.query(MeeshoInvoice)
        flipkart_query = db.query(FlipkartOrder).filter(FlipkartOrder.event_type == 'Sale')
        amazon_query = db.query(AmazonOrder).filter(AmazonOrder.transaction_type == 'Shipment')
        
        # Apply GSTIN filter if provided
        if gstin:
            # MeeshoInvoice doesn't have gstin field, join with MeeshoSale via suborder_no
            meesho_query = meesho_query.join(
                MeeshoSale, MeeshoInvoice.suborder_no == MeeshoSale.sub_order_num
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
            
            meesho_query = meesho_query.filter(MeeshoInvoice.order_date.between(fy_start, fy_end))
            flipkart_query = flipkart_query.filter(FlipkartOrder.order_date.between(fy_start, fy_end))
            amazon_query = amazon_query.filter(AmazonOrder.order_date.between(fy_start, fy_end))
        
        if month:
            from sqlalchemy import extract
            meesho_query = meesho_query.filter(extract('month', MeeshoInvoice.order_date) == month)
            flipkart_query = flipkart_query.filter(extract('month', FlipkartOrder.order_date) == month)
            amazon_query = amazon_query.filter(extract('month', AmazonOrder.order_date) == month)
        
        meesho_invoices = meesho_query.all()
        flipkart_orders = flipkart_query.all()
        amazon_orders = amazon_query.all()
        
        if not meesho_invoices and not flipkart_orders and not amazon_orders:
            return {'error': 'No invoice data from any marketplace'}
        
        # Build combined invoice dataframe
        meesho_data = [{
            'marketplace': 'Meesho',
            'invoice_no': i.invoice_no,
            'suborder_no': i.suborder_no,
            'order_date': i.order_date,
            'hsn_code': i.hsn_code
        } for i in meesho_invoices if i.invoice_no]
        
        flipkart_data = [{
            'marketplace': o.marketplace,
            'invoice_no': o.buyer_invoice_id,  # FIXED: Flipkart uses buyer_invoice_id, not invoice_number
            'suborder_no': o.order_item_id,
            'order_date': o.order_date,
            'hsn_code': o.hsn_code  # FIXED: Flipkart uses hsn_code, not hsn_sac
        } for o in flipkart_orders if o.buyer_invoice_id]  # FIXED: Check buyer_invoice_id
        
        amazon_data = [{
            'marketplace': 'Amazon',
            'invoice_no': o.invoice_number,
            'suborder_no': o.shipment_item_id,
            'order_date': o.order_date,
            'hsn_code': o.hsn_sac  # Amazon uses hsn_sac
        } for o in amazon_orders if o.invoice_number]
        
        all_invoice_data = meesho_data + flipkart_data + amazon_data
        df_inv = pd.DataFrame(all_invoice_data)
        
        if df_inv.empty:
            return {'error': 'No invoice data available'}
        
        issues = []
        
        # Duplicate invoice numbers (within same marketplace)
        for marketplace in df_inv['marketplace'].unique():
            marketplace_invoices = df_inv[df_inv['marketplace'] == marketplace]
            dupes = marketplace_invoices['invoice_no'][marketplace_invoices['invoice_no'].duplicated()].unique()
            for inv in dupes:
                issues.append({
                    'type': 'Duplicate Invoice',
                    'invoice_no': inv,
                    'marketplace': marketplace
                })
        
        # HSN code anomalies (missing or invalid)
        hsn_anomalies = df_inv[df_inv['hsn_code'].isnull() | (df_inv['hsn_code'] == '')]
        for _, row in hsn_anomalies.iterrows():
            issues.append({
                'type': 'Missing HSN Code',
                'invoice_no': row['invoice_no'],
                'marketplace': row['marketplace']
            })
        
        # Summary by marketplace
        marketplace_summary = {}
        for marketplace in df_inv['marketplace'].unique():
            marketplace_invoices = df_inv[df_inv['marketplace'] == marketplace]
            marketplace_dupes = marketplace_invoices['invoice_no'][marketplace_invoices['invoice_no'].duplicated()].nunique()
            marketplace_hsn_issues = len(marketplace_invoices[marketplace_invoices['hsn_code'].isnull() | (marketplace_invoices['hsn_code'] == '')])
            
            marketplace_summary[marketplace] = {
                'total_invoices': len(marketplace_invoices),
                'duplicate_invoices': int(marketplace_dupes),
                'hsn_anomalies': int(marketplace_hsn_issues)
            }
        
        # Overall summary
        total_dupes = sum([s['duplicate_invoices'] for s in marketplace_summary.values()])
        total_hsn_issues = sum([s['hsn_anomalies'] for s in marketplace_summary.values()])
        
        summary = {
            'total_invoices': len(df_inv),
            'duplicate_invoices': total_dupes,
            'hsn_anomalies': total_hsn_issues,
            'marketplace_breakdown': marketplace_summary
        }
        
        return {
            'issues': issues,
            'summary': summary
        }
    except Exception as e:
        return {'error': str(e)}

def get_product_profitability_analytics(db: Session):
    """
    Returns product-level profitability analytics:
    - Revenue, returns, commissions, stock cost, and net profit per product
    - Top profitable and loss-making products
    """
    try:
        orders = db.query(MeeshoOrder).all()
        payments = db.query(MeeshoPayment).all()
        inventories = db.query(MeeshoInventory).all()
        if not orders or not payments or not inventories:
            return {'error': 'Missing order, payment, or inventory data'}
        import pandas as pd
        df_orders = pd.DataFrame([
            {
                'product_id': o.product_id,
                'product_name': o.product_name,
                'quantity': o.quantity or 0,
                'supplier_discounted_price': o.supplier_discounted_price or 0
            } for o in orders if o.product_id
        ])
        df_payments = pd.DataFrame([
            {
                'sub_order_no': p.sub_order_no,
                'meesho_commission': p.meesho_commission_incl_gst or 0,
                'platform_fee': (p.meesho_gold_platform_fee_incl_gst or 0) + (p.meesho_mall_platform_fee_incl_gst or 0),
                'shipping_charge': p.shipping_charge_incl_gst or 0,
                'final_settlement_amount': p.final_settlement_amount or 0,
                'total_sale_amount': p.total_sale_amount_incl_shipping_gst or 0,
                'total_return_amount': p.total_sale_return_amount_incl_shipping_gst or 0
            } for p in payments
        ])
        df_inv = pd.DataFrame([
            {
                'product_id': inv.product_id,
                'product_name': inv.product_name,
                'current_stock': inv.current_stock or 0,
                'your_stock_count': inv.your_stock_count or 0
            } for inv in inventories if inv.product_id
        ])
        if df_orders.empty or df_payments.empty or df_inv.empty:
            return {'error': 'No usable data for profitability analysis'}

        # Revenue per product
        df_orders['revenue'] = df_orders['quantity'] * df_orders['supplier_discounted_price']
        revenue_by_product = df_orders.groupby('product_id').agg(
            product_name=('product_name', 'first'),
            total_revenue=('revenue', 'sum'),
            total_qty=('quantity', 'sum')
        ).reset_index()

        # Returns per product (negative revenue)
        # For simplicity, assume returns are negative quantities in orders (if modeled)
        # Otherwise, use payment data's total_return_amount if available
        # Here, we use payment data
        returns_by_product = df_payments.groupby('sub_order_no')['total_return_amount'].sum().reset_index()

        # Commissions and fees per product (approximate by dividing total by quantity share)
        # Map payments to products by sub_order_no if possible
        # For simplicity, sum all commissions/fees and allocate by revenue share
        total_commission = df_payments['meesho_commission'].sum()
        total_platform_fee = df_payments['platform_fee'].sum()
        total_shipping = df_payments['shipping_charge'].sum()
        total_revenue = revenue_by_product['total_revenue'].sum()
        revenue_by_product['commission'] = (revenue_by_product['total_revenue'] / total_revenue * total_commission).fillna(0)
        revenue_by_product['platform_fee'] = (revenue_by_product['total_revenue'] / total_revenue * total_platform_fee).fillna(0)
        revenue_by_product['shipping'] = (revenue_by_product['total_revenue'] / total_revenue * total_shipping).fillna(0)

        # Stock cost (if available, use your_stock_count as proxy for costed units)
        # For demo, assume cost per unit = 60% of discounted price
        revenue_by_product['stock_cost'] = revenue_by_product['total_qty'] * (revenue_by_product['total_revenue'] / revenue_by_product['total_qty'] * 0.6)
        revenue_by_product['stock_cost'] = revenue_by_product['stock_cost'].fillna(0)

        # Net profit
        revenue_by_product['net_profit'] = revenue_by_product['total_revenue'] \
            - revenue_by_product['commission'] \
            - revenue_by_product['platform_fee'] \
            - revenue_by_product['shipping'] \
            - revenue_by_product['stock_cost']

        # Sort by most selling (total quantity sold) - descending
        revenue_by_product = revenue_by_product.sort_values('total_qty', ascending=False)

        # Top profitable and loss-making products
        top_profit = revenue_by_product.sort_values('net_profit', ascending=False).head(5).to_dict(orient='records')
        top_loss = revenue_by_product.sort_values('net_profit').head(5).to_dict(orient='records')

        return {
            'profitability': revenue_by_product.to_dict(orient='records'),
            'top_profit': top_profit,
            'top_loss': top_loss
        }
    except Exception as e:
        return {'error': str(e)}

def get_customer_segmentation_analytics(db: Session):
    """
    Returns customer segmentation analytics:
    - Orders and revenue by state/region
    - Top regions for targeted marketing
    - Customer counts and revenue share
    NOW INCLUDES DATA FROM ALL MARKETPLACES: Meesho, Flipkart, Amazon
    """
    try:
        import pandas as pd
        from models import FlipkartOrder, AmazonOrder
        
        # Query all marketplaces
        # Note: Use MeeshoSale instead of MeeshoOrder (same reason as Growth Dashboard)
        meesho_sales = db.query(MeeshoSale).all()
        flipkart_orders = db.query(FlipkartOrder).filter(FlipkartOrder.event_type == 'Sale').all()
        amazon_orders = db.query(AmazonOrder).filter(AmazonOrder.transaction_type == 'Shipment').all()
        
        if not meesho_sales and not flipkart_orders and not amazon_orders:
            return {'error': 'No order data'}
        
        # Build unified dataframe from all marketplaces
        meesho_data = [{
            'marketplace': 'Meesho',
            'customer_state': s.end_customer_state_new,
            'order_date': s.order_date,
            'product_name': f"Product #{s.identifier}" if s.identifier else "Unknown",
            'quantity': s.quantity or 0,
            'price': (s.total_taxable_sale_value or 0) / s.quantity if s.quantity and s.quantity > 0 else 0
        } for s in meesho_sales if s.end_customer_state_new]
        
        flipkart_data = [{
            'marketplace': o.marketplace,  # 'Flipkart' or 'Shopsy'
            'customer_state': o.customer_delivery_state,
            'order_date': o.order_date,
            'product_name': o.product_title,
            'quantity': o.quantity or 0,
            'price': o.final_invoice_amount / o.quantity if o.quantity > 0 else 0
        } for o in flipkart_orders if o.customer_delivery_state]
        
        amazon_data = [{
            'marketplace': 'Amazon',
            'customer_state': o.ship_to_state,
            'order_date': o.order_date,
            'product_name': o.item_description,
            'quantity': o.quantity or 0,
            'price': o.invoice_amount / o.quantity if o.quantity > 0 else 0
        } for o in amazon_orders if o.ship_to_state]
        
        all_order_data = meesho_data + flipkart_data + amazon_data
        df = pd.DataFrame(all_order_data)
        
        if df.empty:
            return {'error': 'No usable order data'}

        df['revenue'] = df['quantity'] * df['price']
        state_group = df.groupby('customer_state').agg(
            order_count=('quantity', 'sum'),
            total_revenue=('revenue', 'sum')
        ).sort_values('total_revenue', ascending=False).reset_index()

        # Calculate revenue share
        total_revenue = state_group['total_revenue'].sum()
        state_group['revenue_share_pct'] = (state_group['total_revenue'] / total_revenue * 100).round(2)

        # Suggest top 5 regions for retargeting
        top_regions = state_group.head(5).to_dict(orient='records')

        return {
            'segmentation': state_group.to_dict(orient='records'),
            'top_regions': top_regions
        }
    except Exception as e:
        return {'error': str(e)}

def get_catalog_summary_analytics(db: Session):
    """
    Returns catalog summary analytics with order counts and values by status.
    Replaces CSV export with displayable data.
    """
    try:
        from collections import defaultdict
        orders = db.query(MeeshoOrder).all()
        payments = db.query(MeeshoPayment).all()
        inventory = db.query(MeeshoInventory).all()
        ads_costs = db.query(MeeshoAdsCost).all()
        
        if not orders:
            return {'error': 'No order data'}
        
        # Build inventory map for catalog lookup
        inventory_map = {}
        for inv in inventory:
            if inv.product_name:
                inventory_map[inv.product_name.lower().strip()] = {
                    'catalog_id': inv.catalog_id,
                    'catalog_name': inv.catalog_name,
                    'product_id': inv.product_id
                }
        
        # Build summary by catalog
        summary = defaultdict(lambda: {
            'catalog_name': '',
            'product_id': '',
            'delivered_orders': 0,
            'delivered_value': 0.0,
            'in_transit_orders': 0,
            'in_transit_value': 0.0,
            'cancelled_orders': 0,
            'cancelled_value': 0.0,
            'returned_orders': 0,
            'returned_value': 0.0,
            'total_orders': 0,
            'total_value': 0.0,
            'total_sold': 0
        })
        
        # Process orders
        for order in orders:
            if not order.product_name:
                continue
                
            # Find catalog info
            key = order.product_name.lower().strip()
            catalog_info = inventory_map.get(key, {})
            catalog_id = catalog_info.get('catalog_id', order.product_name)
            
            qty = order.quantity or 1
            value = (order.supplier_discounted_price or 0) * qty
            status = (order.reason_for_credit_entry or '').upper()
            
            if catalog_id not in summary:
                summary[catalog_id]['catalog_name'] = catalog_info.get('catalog_name', order.product_name)
                summary[catalog_id]['product_id'] = catalog_info.get('product_id', '')
            
            summary[catalog_id]['total_orders'] += qty
            summary[catalog_id]['total_value'] += value
            summary[catalog_id]['total_sold'] += qty
            
            if 'DELIVERED' in status:
                summary[catalog_id]['delivered_orders'] += qty
                summary[catalog_id]['delivered_value'] += value
            elif 'TRANSIT' in status:
                summary[catalog_id]['in_transit_orders'] += qty
                summary[catalog_id]['in_transit_value'] += value
            elif 'CANCEL' in status:
                summary[catalog_id]['cancelled_orders'] += qty
                summary[catalog_id]['cancelled_value'] += value
            elif 'RETURN' in status:
                summary[catalog_id]['returned_orders'] += qty
                summary[catalog_id]['returned_value'] += value
        
        # Convert to list and sort by most selling
        catalog_list = [
            {
                'catalog_id': cid,
                'catalog_name': data['catalog_name'],
                'product_id': data['product_id'],
                'delivered_orders': data['delivered_orders'],
                'delivered_value': round(data['delivered_value'], 2),
                'in_transit_orders': data['in_transit_orders'],
                'in_transit_value': round(data['in_transit_value'], 2),
                'cancelled_orders': data['cancelled_orders'],
                'cancelled_value': round(data['cancelled_value'], 2),
                'returned_orders': data['returned_orders'],
                'returned_value': round(data['returned_value'], 2),
                'total_orders': data['total_orders'],
                'total_value': round(data['total_value'], 2),
                'total_sold': data['total_sold']
            }
            for cid, data in summary.items()
        ]
        
        # Sort by most selling
        catalog_list = sorted(catalog_list, key=lambda x: x['total_sold'], reverse=True)
        
        return {
            'catalogs': catalog_list,
            'total_catalogs': len(catalog_list),
            'summary': {
                'total_delivered': sum(c['delivered_orders'] for c in catalog_list),
                'total_delivered_value': round(sum(c['delivered_value'] for c in catalog_list), 2),
                'total_cancelled': sum(c['cancelled_orders'] for c in catalog_list),
                'total_returned': sum(c['returned_orders'] for c in catalog_list)
            }
        }
    except Exception as e:
        return {'error': str(e)}

def get_order_summary_analytics(db: Session):
    """
    Returns order summary analytics with key order metrics.
    Replaces CSV export with displayable data.
    """
    try:
        orders = db.query(MeeshoOrder).all()
        payments = db.query(MeeshoPayment).all()
        
        if not orders:
            return {'error': 'No order data'}
        
        import pandas as pd
        
        # Build payout map
        payout_map = {}
        for p in payments:
            payout_map[p.sub_order_no] = {
                'payout_value': p.final_settlement_amount or 0,
                'total_sale_amount': p.total_sale_amount_incl_shipping_gst or 0,
                'commission': p.meesho_commission_incl_gst or 0
            }
        
        # Calculate total sales by product
        df_orders = pd.DataFrame([
            {'product_id': o.product_id, 'quantity': o.quantity or 0}
            for o in orders if o.product_id
        ])
        total_qty_by_product = df_orders.groupby('product_id')['quantity'].sum().to_dict() if not df_orders.empty else {}
        
        # Process orders
        order_list = []
        for o in orders:
            if not o.sub_order_no:
                continue
            
            payout_info = payout_map.get(o.sub_order_no, {})
            total_sold = total_qty_by_product.get(o.product_id, 0)
            
            order_list.append({
                'sub_order_no': o.sub_order_no,
                'product_name': o.product_name,
                'product_id': o.product_id,
                'quantity': o.quantity or 0,
                'price': o.supplier_discounted_price or 0,
                'order_date': o.order_date.strftime('%Y-%m-%d') if o.order_date else '',
                'order_status': o.reason_for_credit_entry or '',
                'payout_value': round(payout_info.get('payout_value', 0), 2),
                'total_sold': total_sold
            })
        
        # Sort by most selling
        order_list = sorted(order_list, key=lambda x: x['total_sold'], reverse=True)
        
        # Calculate summary
        total_orders = len(order_list)
        total_quantity = sum(o['quantity'] for o in order_list)
        total_value = sum(o['price'] * o['quantity'] for o in order_list)
        total_payout = sum(o['payout_value'] for o in order_list)
        
        return {
            'orders': order_list,
            'summary': {
                'total_orders': total_orders,
                'total_quantity': total_quantity,
                'total_order_value': round(total_value, 2),
                'total_payout': round(total_payout, 2)
            }
        }
    except Exception as e:
        return {'error': str(e)}

def get_payout_summary_analytics(db: Session):
    """
    Returns payout summary analytics with financial breakdown.
    Replaces CSV export with displayable data.
    """
    try:
        payments = db.query(MeeshoPayment).all()
        orders = db.query(MeeshoOrder).all()
        ads_costs = db.query(MeeshoAdsCost).all()
        
        if not payments:
            return {'error': 'No payment data'}
        
        import pandas as pd
        
        df_payments = pd.DataFrame([
            {
                'final_settlement_amount': p.final_settlement_amount or 0,
                'total_sale_amount': p.total_sale_amount_incl_shipping_gst or 0,
                'total_return_amount': p.total_sale_return_amount_incl_shipping_gst or 0,
                'meesho_commission': p.meesho_commission_incl_gst or 0,
                'platform_fee': (p.meesho_gold_platform_fee_incl_gst or 0) + (p.meesho_mall_platform_fee_incl_gst or 0),
                'shipping_charge': p.shipping_charge_incl_gst or 0,
                'gst_compensation': p.gst_compensation_prp_shipping or 0,
                'tcs': p.tcs or 0,
                'tds': p.tds or 0,
            } for p in payments
        ])
        
        df_orders = pd.DataFrame([
            {'order_status': o.reason_for_credit_entry or ''}
            for o in orders
        ])
        
        # Calculate order counts by status
        delivered = df_orders[df_orders['order_status'].str.lower().str.contains('delivered', na=False)].shape[0]
        in_transit = df_orders[df_orders['order_status'].str.lower().str.contains('transit', na=False)].shape[0]
        cancelled = df_orders[df_orders['order_status'].str.lower().str.contains('cancel', na=False)].shape[0]
        returned = df_orders[df_orders['order_status'].str.lower().str.contains('return', na=False)].shape[0]
        
        # Calculate financial metrics
        total_sales = df_payments['total_sale_amount'].sum()
        total_returns = df_payments['total_return_amount'].sum()
        total_commission = df_payments['meesho_commission'].sum()
        total_platform_fee = df_payments['platform_fee'].sum()
        total_shipping = df_payments['shipping_charge'].sum()
        total_payout = df_payments['final_settlement_amount'].sum()
        ads_cost_total = sum(ac.total_ads_cost or 0 for ac in ads_costs)
        
        # Net profit (simplified)
        net_profit = total_payout - ads_cost_total
        
        payout_breakdown = [
            {'type': 'Orders', 'status': 'Delivered', 'count': delivered, 'amount': round(total_payout, 2)},
            {'type': 'Orders', 'status': 'In Transit', 'count': in_transit, 'amount': 0},
            {'type': 'Orders', 'status': 'Cancelled', 'count': cancelled, 'amount': 0},
            {'type': 'Orders', 'status': 'Returned', 'count': returned, 'amount': round(total_returns, 2)},
            {'type': 'Deductions', 'status': 'Commission', 'count': '-', 'amount': round(total_commission, 2)},
            {'type': 'Deductions', 'status': 'Platform Fee', 'count': '-', 'amount': round(total_platform_fee, 2)},
            {'type': 'Deductions', 'status': 'Shipping', 'count': '-', 'amount': round(total_shipping, 2)},
            {'type': 'Deductions', 'status': 'Ads Cost', 'count': '-', 'amount': round(ads_cost_total, 2)},
        ]
        
        return {
            'breakdown': payout_breakdown,
            'summary': {
                'total_sales': round(total_sales, 2),
                'total_returns': round(total_returns, 2),
                'total_commission': round(total_commission, 2),
                'total_platform_fee': round(total_platform_fee, 2),
                'total_ads_cost': round(ads_cost_total, 2),
                'final_payout': round(total_payout, 2),
                'net_profit': round(net_profit, 2)
            }
        }
    except Exception as e:
        return {'error': str(e)}

# ============================================================================
# CONSOLIDATED BUSINESS ANALYTICS - Business Decision Support
# ============================================================================

def get_business_dashboard_analytics(db: Session, fy: str = None, month: int = None, gstin: str = None):
    """
    Comprehensive business dashboard combining sales, orders, revenue, and trends.
    Includes data from Meesho, Flipkart, and Amazon marketplaces.
    Replaces: Dashboard, Catalog Summary, Order Summary, Customer Segmentation
    
    Args:
        db: Database session
        fy: Financial year filter (e.g., "2024-25" or None for all)
        month: Month filter (1-12 or None for all)
        gstin: Seller GSTIN filter (None for all sellers)
    """
    try:
        import pandas as pd
        from datetime import datetime, timedelta
        from models import FlipkartOrder, AmazonOrder
        
        # Query all marketplace orders with date filtering
        # Note: Use MeeshoSale instead of MeeshoOrder because MeeshoOrder is only populated
        # from payments ZIP (optional import), while MeeshoSale is from tax invoices (always imported)
        meesho_query = db.query(MeeshoSale)
        flipkart_query = db.query(FlipkartOrder).filter(FlipkartOrder.event_type == 'Sale')
        amazon_query = db.query(AmazonOrder).filter(AmazonOrder.transaction_type == 'Shipment')
        payments_query = db.query(MeeshoPayment)
        
        # Apply GSTIN filter if provided
        if gstin:
            meesho_query = meesho_query.filter(MeeshoSale.gstin == gstin)
            flipkart_query = flipkart_query.filter(FlipkartOrder.seller_gstin == gstin)
            amazon_query = amazon_query.filter(AmazonOrder.seller_gstin == gstin)
            payments_query = payments_query.filter(MeeshoPayment.seller_gstin == gstin)  # Filter payments by GSTIN
        
        # Apply date filters if provided
        if fy:
            # Extract start year from FY (e.g., "2024-25" -> 2024)
            start_year = int(fy.split('-')[0])
            # FY runs from April to March
            fy_start = f"{start_year}-04-01"
            fy_end = f"{start_year + 1}-03-31"
            
            meesho_query = meesho_query.filter(MeeshoSale.order_date.between(fy_start, fy_end))
            flipkart_query = flipkart_query.filter(FlipkartOrder.order_date.between(fy_start, fy_end))
            amazon_query = amazon_query.filter(AmazonOrder.order_date.between(fy_start, fy_end))
            payments_query = payments_query.filter(MeeshoPayment.payment_date.between(fy_start, fy_end))
        
        if month:
            from sqlalchemy import extract
            meesho_query = meesho_query.filter(extract('month', MeeshoSale.order_date) == month)
            flipkart_query = flipkart_query.filter(extract('month', FlipkartOrder.order_date) == month)
            amazon_query = amazon_query.filter(extract('month', AmazonOrder.order_date) == month)
            payments_query = payments_query.filter(extract('month', MeeshoPayment.payment_date) == month)
        
        meesho_sales = meesho_query.all()
        flipkart_orders = flipkart_query.all()
        amazon_orders = amazon_query.all()
        payments = payments_query.all()
        
        # Query inventory with GSTIN filter
        inventory_query = db.query(MeeshoInventory)
        if gstin:
            inventory_query = inventory_query.filter(MeeshoInventory.seller_gstin == gstin)
        inventory = inventory_query.all()
        
        # DEBUG: Log query results
        print(f"[DEBUG] Dashboard Analytics - Found {len(meesho_sales)} Meesho sales, {len(flipkart_orders)} Flipkart orders, {len(amazon_orders)} Amazon orders")
        
        if not meesho_sales and not flipkart_orders and not amazon_orders:
            return {'error': 'No order data available'}
        
        # Build product_id -> product_name mapping from MeeshoInventory
        product_name_map = {}
        if inventory:
            for inv in inventory:
                if inv.product_id and inv.product_name:
                    product_name_map[inv.product_id] = inv.product_name
        
        # Build unified orders dataframe from Meesho (using MeeshoSale data)
        meesho_data = [{
            'marketplace': 'Meesho',
            'sub_order_no': s.sub_order_num,
            'order_date': s.order_date,
            'product_id': s.identifier,  # Using identifier as product ID
            'product_name': product_name_map.get(s.identifier, f"Product #{s.identifier}") if s.identifier else "Unknown",
            'quantity': s.quantity or 0,
            'price': (s.total_taxable_sale_value or 0) / s.quantity if s.quantity and s.quantity > 0 else 0,
            'status': 'Delivered',  # MeeshoSale records are delivered sales
            'state': s.end_customer_state_new or 'Unknown'
        } for s in meesho_sales]
        
        # Build unified orders dataframe from Flipkart
        flipkart_data = [{
            'marketplace': o.marketplace,  # 'Flipkart' or 'Shopsy'
            'sub_order_no': o.order_item_id,
            'order_date': o.order_date,
            'product_id': o.fsn,  # FSN as product ID
            'product_name': o.product_title,
            'quantity': o.quantity or 0,
            'price': o.final_invoice_amount / o.quantity if o.quantity > 0 else 0,
            'status': o.event_sub_type or '',
            'state': o.customer_delivery_state or 'Unknown'
        } for o in flipkart_orders]
        
        # Build unified orders dataframe from Amazon
        amazon_data = [{
            'marketplace': 'Amazon',
            'sub_order_no': o.shipment_item_id,
            'order_date': o.order_date,
            'product_id': o.asin,  # ASIN as product ID
            'product_name': o.item_description,
            'quantity': o.quantity or 0,
            'price': o.invoice_amount / o.quantity if o.quantity > 0 else 0,
            'status': 'Shipped',
            'state': o.ship_to_state or 'Unknown'
        } for o in amazon_orders]
        
        # Combine all marketplaces
        all_order_data = meesho_data + flipkart_data + amazon_data
        df_orders = pd.DataFrame(all_order_data)
        
        # DEBUG: Show marketplace composition
        print(f"[DEBUG] Combined DataFrame has {len(df_orders)} rows from {len(meesho_data)} Meesho + {len(flipkart_data)} Flipkart + {len(amazon_data)} Amazon")
        if not df_orders.empty:
            print(f"[DEBUG] Marketplaces in DataFrame: {df_orders['marketplace'].value_counts().to_dict()}")
        
        df_orders['revenue'] = df_orders['quantity'] * df_orders['price']
        df_orders['order_date'] = pd.to_datetime(df_orders['order_date'])
        
        # === MARKETPLACE BREAKDOWN ===
        marketplace_stats = df_orders.groupby('marketplace').agg({
            'sub_order_no': 'count',
            'revenue': 'sum',
            'quantity': 'sum'
        }).to_dict(orient='index')
        
        # === SALES OVERVIEW ===
        total_orders = len(df_orders)
        total_quantity = df_orders['quantity'].sum()
        total_revenue = df_orders['revenue'].sum()
        avg_order_value = total_revenue / total_orders if total_orders > 0 else 0
        
        # === ORDER STATUS BREAKDOWN ===
        status_counts = {
            'delivered': df_orders[df_orders['status'].str.contains('DELIVERED', case=False, na=False)].shape[0],
            'in_transit': df_orders[df_orders['status'].str.contains('TRANSIT', case=False, na=False)].shape[0],
            'cancelled': df_orders[df_orders['status'].str.contains('CANCEL', case=False, na=False)].shape[0],
            'returned': df_orders[df_orders['status'].str.contains('RETURN', case=False, na=False)].shape[0]
        }
        
        # === TOP PRODUCTS (by revenue and quantity) - sorted by most selling ===
        top_products_revenue = df_orders.groupby(['marketplace', 'product_id', 'product_name']).agg({
            'revenue': 'sum',
            'quantity': 'sum'
        }).sort_values('quantity', ascending=False).head(10).reset_index()
        
        top_products = [{
            'marketplace': row['marketplace'],
            'product_id': row['product_id'],
            'product_name': row['product_name'],
            'total_revenue': round(row['revenue'], 2),
            'total_quantity': int(row['quantity'])
        } for _, row in top_products_revenue.iterrows()]
        
        # === TIME TRENDS (Last 30 days) ===
        df_orders_recent = df_orders[df_orders['order_date'] >= (datetime.now() - timedelta(days=30))]
        daily_trends = df_orders_recent.groupby(df_orders_recent['order_date'].dt.date).agg({
            'sub_order_no': 'count',
            'revenue': 'sum'
        }).tail(7).to_dict(orient='index')
        
        trends = [{
            'date': str(date),
            'orders': data['sub_order_no'],
            'revenue': round(data['revenue'], 2)
        } for date, data in daily_trends.items()]
        
        # === TOP STATES (by revenue) ===
        top_states = df_orders.groupby('state')['revenue'].sum().sort_values(ascending=False).head(5)
        state_breakdown = [{
            'state': state,
            'revenue': round(revenue, 2)
        } for state, revenue in top_states.items()]
        
        # === FINANCIAL SUMMARY FROM PAYMENTS (Meesho only for now) ===
        if payments:
            df_payments = pd.DataFrame([{
                'total_sale': p.total_sale_amount_incl_shipping_gst or 0,
                'commission': p.meesho_commission_incl_gst or 0,
                'platform_fee': (p.meesho_gold_platform_fee_incl_gst or 0) + (p.meesho_mall_platform_fee_incl_gst or 0),
                'final_payout': p.final_settlement_amount or 0
            } for p in payments])
            
            financial = {
                'total_sales': round(df_payments['total_sale'].sum(), 2),
                'total_commission': round(df_payments['commission'].sum(), 2),
                'total_platform_fee': round(df_payments['platform_fee'].sum(), 2),
                'net_payout': round(df_payments['final_payout'].sum(), 2)
            }
        else:
            financial = {
                'total_sales': round(total_revenue, 2),
                'total_commission': 0,
                'total_platform_fee': 0,
                'net_payout': 0
            }
        
        return {
            'overview': {
                'total_orders': total_orders,
                'total_quantity': int(total_quantity),
                'total_revenue': round(total_revenue, 2),
                'avg_order_value': round(avg_order_value, 2)
            },
            'marketplace_breakdown': {
                marketplace: {
                    'orders': int(stats['sub_order_no']),
                    'revenue': round(stats['revenue'], 2),
                    'quantity': int(stats['quantity'])
                } for marketplace, stats in marketplace_stats.items()
            },
            'status_breakdown': status_counts,
            'top_products': top_products,
            'time_trends': trends,
            'top_states': state_breakdown,
            'financial_summary': financial
        }
    except Exception as e:
        return {'error': str(e)}

def get_product_inventory_insights(db: Session, fy: str = None, month: int = None, gstin: str = None):
    """
    Product and inventory insights for purchasing decisions.
    Replaces: Product Analytics, Predictive Alerts (Low Stock), Inventory Analytics
    NOW INCLUDES DATA FROM ALL MARKETPLACES: Meesho, Flipkart, Amazon
    
    Args:
        db: Database session
        fy: Financial year filter (e.g., "2024-25" or None for all)
        month: Month filter (1-12 or None for all)
        gstin: Seller GSTIN filter (None for all sellers)
    """
    try:
        import pandas as pd
        from datetime import datetime, timedelta
        from models import FlipkartOrder, FlipkartReturn, AmazonOrder, AmazonReturn
        
        # Query all marketplaces with date filtering
        # Use MeeshoSale instead of MeeshoOrder (MeeshoOrder doesn't have gstin)
        meesho_query = db.query(MeeshoSale)
        flipkart_query = db.query(FlipkartOrder).filter(FlipkartOrder.event_type == 'Sale')
        amazon_query = db.query(AmazonOrder).filter(AmazonOrder.transaction_type == 'Shipment')
        
        # Apply GSTIN filter if provided
        if gstin:
            meesho_query = meesho_query.filter(MeeshoSale.gstin == gstin)
            flipkart_query = flipkart_query.filter(FlipkartOrder.seller_gstin == gstin)
            amazon_query = amazon_query.filter(AmazonOrder.seller_gstin == gstin)
        
        # Apply date filters if provided
        if fy:
            # Extract start year from FY (e.g., "2024-25" -> 2024)
            start_year = int(fy.split('-')[0])
            # FY runs from April to March
            fy_start = f"{start_year}-04-01"
            fy_end = f"{start_year + 1}-03-31"
            
            meesho_query = meesho_query.filter(MeeshoSale.order_date.between(fy_start, fy_end))
            flipkart_query = flipkart_query.filter(FlipkartOrder.order_date.between(fy_start, fy_end))
            amazon_query = amazon_query.filter(AmazonOrder.order_date.between(fy_start, fy_end))
        
        if month:
            from sqlalchemy import extract
            meesho_query = meesho_query.filter(extract('month', MeeshoSale.order_date) == month)
            flipkart_query = flipkart_query.filter(extract('month', FlipkartOrder.order_date) == month)
            amazon_query = amazon_query.filter(extract('month', AmazonOrder.order_date) == month)
        
        meesho_sales = meesho_query.all()
        flipkart_orders = flipkart_query.all()
        amazon_orders = amazon_query.all()
        
        # Query inventory with GSTIN filter
        inventory_query = db.query(MeeshoInventory)
        if gstin:
            inventory_query = inventory_query.filter(MeeshoInventory.seller_gstin == gstin)
        inventory = inventory_query.all()
        
        meesho_returns_query = db.query(MeeshoReturn)
        flipkart_returns_query = db.query(FlipkartReturn)
        amazon_returns_query = db.query(AmazonReturn).filter(AmazonReturn.transaction_type == 'Refund')
        
        # Apply GSTIN filter to returns
        if gstin:
            meesho_returns_query = meesho_returns_query.filter(MeeshoReturn.gstin == gstin)
            flipkart_returns_query = flipkart_returns_query.filter(FlipkartReturn.seller_gstin == gstin)
            amazon_returns_query = amazon_returns_query.filter(AmazonReturn.seller_gstin == gstin)
        
        meesho_returns = meesho_returns_query.all()
        flipkart_returns = flipkart_returns_query.all()
        amazon_returns = amazon_returns_query.all()
        
        if not inventory:
            return {'error': 'Missing inventory data'}
        
        # Build product_id -> product_name mapping from MeeshoInventory
        product_name_map = {}
        for inv in inventory:
            if inv.product_id and inv.product_name:
                product_name_map[inv.product_id] = inv.product_name
        
        # Build dataframes for all marketplaces
        # MeeshoSale uses 'identifier' as product_id
        meesho_order_data = [{
            'product_id': s.identifier,
            'product_name': product_name_map.get(s.identifier, f"Product #{s.identifier}") if s.identifier else "Unknown",
            'order_date': s.order_date,
            'quantity': s.quantity or 0
        } for s in meesho_sales if s.identifier]
        
        # Note: Flipkart/Amazon use different product IDs, so inventory mapping won't work directly
        # We'll focus on Meesho products for now but track total sales velocity
        
        df_orders = pd.DataFrame(meesho_order_data)
        
        if df_orders.empty:
            df_orders = pd.DataFrame(columns=['product_id', 'product_name', 'order_date', 'quantity'])
        
        df_inv = pd.DataFrame([{
            'product_id': inv.product_id,
            'product_name': inv.product_name,
            'catalog_id': inv.catalog_id,
            'current_stock': inv.current_stock or 0
        } for inv in inventory if inv.product_id])
        
        # Returns (Meesho only for product matching)
        df_returns = pd.DataFrame([{
            'product_id': r.product_id,
            'quantity': r.quantity or 0
        } for r in meesho_returns if r.product_id])
        
        # === CALCULATE SALES VELOCITY (Last 30 days) ===
        if not df_orders.empty:
            df_orders['order_date'] = pd.to_datetime(df_orders['order_date'])
            recent_orders = df_orders[df_orders['order_date'] >= (datetime.now() - timedelta(days=30))]
            
            sales_velocity = recent_orders.groupby('product_id')['quantity'].sum()
            total_sales = df_orders.groupby('product_id')['quantity'].sum()
        else:
            sales_velocity = pd.Series()
            total_sales = pd.Series()
        
        # === RETURN RATE ===
        return_qty = df_returns.groupby('product_id')['quantity'].sum() if not df_returns.empty else pd.Series()
        
        # === MERGE AND ANALYZE ===
        product_insights = []
        for _, inv_row in df_inv.iterrows():
            pid = inv_row['product_id']
            current_stock = inv_row['current_stock']
            velocity_30d = sales_velocity.get(pid, 0)
            total_sold = total_sales.get(pid, 0)
            returns = return_qty.get(pid, 0)
            
            # Calculate days of stock remaining
            days_remaining = (current_stock / velocity_30d * 30) if velocity_30d > 0 else 999
            
            # Return rate
            return_rate = (returns / total_sold * 100) if total_sold > 0 else 0
            
            # Determine status and action
            if current_stock == 0 and velocity_30d > 0:
                status = 'OUT_OF_STOCK'
                action = 'REORDER URGENTLY'
            elif days_remaining < 7 and velocity_30d > 0:
                status = 'LOW_STOCK'
                action = 'REORDER SOON'
            elif velocity_30d == 0 and current_stock > 10:
                status = 'DEAD_STOCK'
                action = 'REVIEW LISTING'
            elif return_rate > 20:
                status = 'HIGH_RETURNS'
                action = 'CHECK QUALITY'
            else:
                status = 'HEALTHY'
                action = 'NO ACTION'
            
            product_insights.append({
                'product_id': pid,
                'product_name': inv_row['product_name'],
                'catalog_id': inv_row['catalog_id'],
                'current_stock': int(current_stock),
                'sales_30d': int(velocity_30d),
                'total_sold': int(total_sold),
                'days_remaining': round(days_remaining, 1) if days_remaining < 999 else '>90',
                'return_rate': round(return_rate, 1),
                'status': status,
                'action': action
            })
        
        # Sort by urgency: Out of stock > Low stock > High returns > Total sold
        priority_order = {'OUT_OF_STOCK': 0, 'LOW_STOCK': 1, 'HIGH_RETURNS': 2, 'DEAD_STOCK': 3, 'HEALTHY': 4}
        product_insights.sort(key=lambda x: (priority_order.get(x['status'], 5), -x['total_sold']))
        
        # === SUMMARY STATISTICS ===
        summary = {
            'total_products': len(product_insights),
            'out_of_stock': sum(1 for p in product_insights if p['status'] == 'OUT_OF_STOCK'),
            'low_stock': sum(1 for p in product_insights if p['status'] == 'LOW_STOCK'),
            'dead_stock': sum(1 for p in product_insights if p['status'] == 'DEAD_STOCK'),
            'high_returns': sum(1 for p in product_insights if p['status'] == 'HIGH_RETURNS'),
            'healthy': sum(1 for p in product_insights if p['status'] == 'HEALTHY')
        }
        
        return {
            'products': product_insights,
            'summary': summary
        }
    except Exception as e:
        return {'error': str(e)}

def get_financial_analysis(db: Session, fy: str = None, month: int = None, gstin: str = None):
    """
    Comprehensive financial analysis: revenue, costs, profit margins.
    Includes Payout Summary data: order status breakdown with payout values.
    NOW INCLUDES DATA FROM ALL MARKETPLACES: Meesho, Flipkart, Amazon
    USES MeeshoSale (tax invoice data) instead of MeeshoOrder for better data availability.
    
    NEW: Groups products by normalized SKU to combine profit from similar variations
    (e.g., BLACK-100/., BLACK_100, BLACK-100-1 all become "BLACK 100")
    
    LOGS SKU MAPPINGS: Creates sku_mapping_log.txt showing which raw SKUs merged into which products
    
    Args:
        db: Database session
        fy: Financial year filter (e.g., "2024-25" or None for all)
        month: Month filter (1-12 or None for all)
        gstin: Seller GSTIN filter (None for all sellers)
    """
    try:
        import pandas as pd
        from models import MeeshoSale, MeeshoInventory, FlipkartOrder, FlipkartReturn, AmazonOrder, AmazonReturn
        from sku_normalizer import normalize_product_name
        from datetime import datetime
        
        # Query all marketplaces with date filtering - Use MeeshoSale instead of MeeshoOrder
        meesho_query = db.query(MeeshoSale)
        flipkart_query = db.query(FlipkartOrder).filter(FlipkartOrder.event_type == 'Sale')
        amazon_query = db.query(AmazonOrder).filter(AmazonOrder.transaction_type == 'Shipment')
        payments_query = db.query(MeeshoPayment)
        
        # Apply GSTIN filter if provided
        if gstin:
            meesho_query = meesho_query.filter(MeeshoSale.gstin == gstin)
            flipkart_query = flipkart_query.filter(FlipkartOrder.seller_gstin == gstin)
            amazon_query = amazon_query.filter(AmazonOrder.seller_gstin == gstin)
            payments_query = payments_query.filter(MeeshoPayment.seller_gstin == gstin)  # Filter payments by GSTIN
        
        # Apply date filters if provided
        if fy:
            # Extract start year from FY (e.g., "2024-25" -> 2024)
            start_year = int(fy.split('-')[0])
            # FY runs from April to March
            fy_start = f"{start_year}-04-01"
            fy_end = f"{start_year + 1}-03-31"
            
            meesho_query = meesho_query.filter(MeeshoSale.order_date.between(fy_start, fy_end))
            flipkart_query = flipkart_query.filter(FlipkartOrder.order_date.between(fy_start, fy_end))
            amazon_query = amazon_query.filter(AmazonOrder.order_date.between(fy_start, fy_end))
            payments_query = payments_query.filter(MeeshoPayment.payment_date.between(fy_start, fy_end))
        
        if month:
            from sqlalchemy import extract
            meesho_query = meesho_query.filter(extract('month', MeeshoSale.order_date) == month)
            flipkart_query = flipkart_query.filter(extract('month', FlipkartOrder.order_date) == month)
            amazon_query = amazon_query.filter(extract('month', AmazonOrder.order_date) == month)
            payments_query = payments_query.filter(extract('month', MeeshoPayment.payment_date) == month)
        
        meesho_sales = meesho_query.all()
        flipkart_orders = flipkart_query.all()
        amazon_orders = amazon_query.all()
        payments = payments_query.all()
        
        # Query ads costs with GSTIN filter
        ads_costs_query = db.query(MeeshoAdsCost)
        if gstin:
            ads_costs_query = ads_costs_query.filter(MeeshoAdsCost.seller_gstin == gstin)
        ads_costs = ads_costs_query.all()
        
        # Query returns with GSTIN filter
        meesho_returns_query = db.query(MeeshoReturn)
        flipkart_returns_query = db.query(FlipkartReturn)
        amazon_returns_query = db.query(AmazonReturn).filter(AmazonReturn.transaction_type == 'Refund')
        
        # Apply GSTIN filter to returns
        if gstin:
            meesho_returns_query = meesho_returns_query.filter(MeeshoReturn.gstin == gstin)
            flipkart_returns_query = flipkart_returns_query.filter(FlipkartReturn.seller_gstin == gstin)
            amazon_returns_query = amazon_returns_query.filter(AmazonReturn.seller_gstin == gstin)
        
        meesho_returns = meesho_returns_query.all()
        flipkart_returns = flipkart_returns_query.all()
        amazon_returns = amazon_returns_query.all()
        
        if not meesho_sales and not flipkart_orders and not amazon_orders:
            return {'error': 'No financial data available'}
        
        # === PAYMENT DATA (Meesho only for now) ===
        df_payments = pd.DataFrame([{
            'total_sale': p.total_sale_amount_incl_shipping_gst or 0,
            'total_return': p.total_sale_return_amount_incl_shipping_gst or 0,
            'total_return_amount': p.total_sale_return_amount_incl_shipping_gst or 0,  # Alias for compatibility
            'commission': p.meesho_commission_incl_gst or 0,
            'platform_fee': (p.meesho_gold_platform_fee_incl_gst or 0) + (p.meesho_mall_platform_fee_incl_gst or 0),
            'shipping': p.shipping_charge_incl_gst or 0,
            'return_shipping': p.return_shipping_charge_incl_gst or 0,
            'gst_compensation': p.gst_compensation_prp_shipping or 0,
            'tcs': p.tcs or 0,
            'tds': p.tds or 0,
            'compensation': p.compensation or 0,
            'claims': p.claims or 0,
            'recovery': p.recovery or 0,
            'final_payout': p.final_settlement_amount or 0,
            'final_settlement_amount': p.final_settlement_amount or 0  # Alias for compatibility
        } for p in payments]) if payments else pd.DataFrame()
        
        # === ORDER DATA FOR PRODUCT-LEVEL ANALYSIS - ALL MARKETPLACES ===
        # FIXED: Include actual costs from payment data (not proportional allocation later!)
        # Each payment record has complete cost breakdown per sub-order
        # SKU-ONLY: Normalize using ONLY the SKU field, ignore product names
        # NEW: Include fixed costs per order (packing charges, etc.)
        # NEW: Include COGS (Cost of Goods Sold) from cost price file
        fixed_cost_per_order = FixedCosts.get_total_fixed_cost_per_order()
        cost_prices = load_cost_prices()  # Load cost prices from CSV
        
        meesho_order_data = [{
            'marketplace': 'Meesho',
            'product_id': normalize_product_name(None, p.supplier_sku),  # SKU-ONLY normalization
            'product_name': normalize_product_name(None, p.supplier_sku),  # SKU-ONLY normalization
            'raw_sku': p.supplier_sku,  # Keep original SKU for reference
            'quantity': p.quantity or 0,
            'revenue': p.total_sale_amount_incl_shipping_gst or 0,  # Total revenue for this order
            'commission': p.meesho_commission_incl_gst or 0,
            'platform_fee': (p.meesho_gold_platform_fee_incl_gst or 0) + (p.meesho_mall_platform_fee_incl_gst or 0),
            'shipping': abs(p.shipping_charge_incl_gst or 0),
            'tcs': p.tcs or 0,
            'tds': p.tds or 0,
            'gst_compensation': p.gst_compensation_prp_shipping or 0,
            'packing_charge': fixed_cost_per_order,  # Fixed cost per order
            'cogs': get_cost_price(p.supplier_sku, cost_prices) * (p.quantity or 0),  # Cost of Goods Sold
            'order_status': (p.live_order_status or 'DELIVERED').upper()
        } for p in payments if p.product_name or p.sub_order_no]
        
        # === LOG SKU MAPPINGS FOR USER REVIEW ===
        # Create a mapping report showing which raw SKUs merged into which normalized products
        # SKU-ONLY: Only track SKUs, not product names
        sku_mapping = {}
        for p in payments:
            if p.supplier_sku:
                normalized = normalize_product_name(None, p.supplier_sku)  # SKU-ONLY
                
                if normalized not in sku_mapping:
                    sku_mapping[normalized] = {
                        'raw_skus': set(),
                        'sample_revenue': []
                    }
                
                sku_mapping[normalized]['raw_skus'].add(p.supplier_sku)
                sku_mapping[normalized]['sample_revenue'].append(p.total_sale_amount_incl_shipping_gst or 0)
        
        # Write mapping log to file
        log_path = 'sku_mapping_log.txt'
        with open(log_path, 'w', encoding='utf-8') as f:
            f.write("=" * 100 + "\n")
            f.write("SKU NORMALIZATION MAPPING LOG (SKU-ONLY)\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 100 + "\n\n")
            f.write("This file shows which raw SKUs were merged into normalized products.\n")
            f.write("SKU-ONLY normalization: Product names are NOT used for grouping.\n")
            f.write("Review this to verify groupings are correct. Suggest corrections if needed.\n\n")
            f.write("=" * 100 + "\n\n")
            
            # Sort by total revenue (most important products first)
            sorted_mapping = sorted(
                sku_mapping.items(),
                key=lambda x: sum(x[1]['sample_revenue']),
                reverse=True
            )
            
            for i, (normalized, data) in enumerate(sorted_mapping, 1):
                total_revenue = sum(data['sample_revenue'])
                order_count = len(data['sample_revenue'])
                
                f.write(f"{i}. NORMALIZED PRODUCT: {normalized}\n")
                f.write(f"   Total Revenue: Rs. {total_revenue:,.2f} | Orders: {order_count}\n")
                f.write(f"   Raw SKUs ({len(data['raw_skus'])} variations):\n")
                
                for sku in sorted(data['raw_skus']):
                    f.write(f"      - {sku}\n")
                
                f.write("\n" + "-" * 100 + "\n\n")
            
            f.write("\n" + "=" * 100 + "\n")
            f.write(f"Total Normalized Products: {len(sku_mapping)}\n")
            f.write(f"Total Raw SKUs: {sum(len(d['raw_skus']) for d in sku_mapping.values())}\n")
            f.write(f"Total Orders: {sum(len(d['sample_revenue']) for d in sku_mapping.values())}\n")
            f.write("=" * 100 + "\n")
        
        print(f"SKU mapping log written to: {log_path}")
        
        # Flipkart orders (costs not available in detail, will allocate proportionally later)
        flipkart_order_data = [{
            'marketplace': o.marketplace,  # 'Flipkart' or 'Shopsy'
            'product_id': o.fsn,
            'product_name': o.product_title,
            'quantity': o.quantity or 0,
            'revenue': o.final_invoice_amount or 0,
            'commission': 0,  # Will be allocated proportionally
            'platform_fee': 0,
            'shipping': 0,
            'tcs': 0,
            'tds': 0,
            'gst_compensation': 0,
            'packing_charge': fixed_cost_per_order,  # Fixed cost per order
            'cogs': 0,  # Flipkart uses different SKU system - COGS not available
            'order_status': (o.event_sub_type or '').upper()
        } for o in flipkart_orders]
        
        # Amazon orders (costs not available in detail, will allocate proportionally later)
        amazon_order_data = [{
            'marketplace': 'Amazon',
            'product_id': o.asin,
            'product_name': o.item_description,
            'quantity': o.quantity or 0,
            'revenue': o.invoice_amount or 0,
            'commission': 0,  # Will be allocated proportionally
            'platform_fee': 0,
            'shipping': 0,
            'tcs': 0,
            'tds': 0,
            'gst_compensation': 0,
            'packing_charge': fixed_cost_per_order,  # Fixed cost per order
            'cogs': 0,  # Amazon uses ASIN - COGS not available
            'order_status': 'SHIPPED'
        } for o in amazon_orders]
        
        # Combine all marketplaces
        all_order_data = meesho_order_data + flipkart_order_data + amazon_order_data
        df_orders = pd.DataFrame(all_order_data)
        
        if df_orders.empty:
            return {'error': 'No order data available'}
        
        # Revenue is already included in the data, no need to calculate from quantity * price
        
        # === ORDER STATUS BREAKDOWN (Payout Summary Integration) ===
        order_status_summary = []
        # Delivered orders
        delivered_orders = df_orders[df_orders['order_status'].str.contains('DELIVERED', na=False)]
        delivered_count = len(delivered_orders)
        delivered_payout = df_payments['final_settlement_amount'].sum() if not df_payments.empty else 0
        order_status_summary.append({
            'status': 'Delivered',
            'orders': delivered_count,
            'payout': round(delivered_payout, 2)
        })
        
        # In Transit orders
        in_transit_orders = df_orders[df_orders['order_status'].str.contains('TRANSIT', na=False)]
        order_status_summary.append({
            'status': 'In Transit',
            'orders': len(in_transit_orders),
            'payout': 0.0  # No payout until delivered
        })
        
        # Cancelled orders
        cancelled_orders = df_orders[df_orders['order_status'].str.contains('CANCEL', na=False)]
        order_status_summary.append({
            'status': 'Cancelled',
            'orders': len(cancelled_orders),
            'payout': 0.0
        })
        
        # RTO orders
        rto_orders = df_orders[df_orders['order_status'].str.contains('RTO', na=False)]
        order_status_summary.append({
            'status': 'RTO',
            'orders': len(rto_orders),
            'payout': 0.0
        })
        
        # Returned orders
        returned_orders = df_orders[df_orders['order_status'].str.contains('RETURN', na=False)]
        order_status_summary.append({
            'status': 'Returned',
            'orders': len(returned_orders),
            'payout': round(df_payments['total_return_amount'].sum() * -1, 2) if not df_payments.empty else 0.0
        })
        
        # Exchanged orders
        exchanged_orders = df_orders[df_orders['order_status'].str.contains('EXCHANG', na=False)]
        order_status_summary.append({
            'status': 'Exchanged',
            'orders': len(exchanged_orders),
            'payout': 0.0
        })
        
        # === OVERALL FINANCIALS - COMBINED FROM ALL MARKETPLACES ===
        # Total revenue from all orders (including RTO/Cancelled that never materialized)
        total_sales = df_orders['revenue'].sum()
        
        # Returns (from all marketplaces) - actual refunds paid to customers
        meesho_return_amount = sum((r.total_invoice_value or 0) for r in meesho_returns)
        flipkart_return_amount = sum(abs(r.return_amount or 0) for r in flipkart_returns)
        amazon_return_amount = sum(abs(r.return_amount or 0) for r in amazon_returns)
        total_returns = meesho_return_amount + flipkart_return_amount + amazon_return_amount
        
        # Calculate actual realized sales (exclude RTO and Cancelled - never received payment)
        delivered_revenue = df_orders[df_orders['order_status'].str.contains('DELIVERED', na=False)]['revenue'].sum()
        returned_revenue = df_orders[df_orders['order_status'].str.contains('RETURN', na=False)]['revenue'].sum()
        
        # Net sales = Delivered + Returned (returned orders were paid, then refunded)
        # This is different from total_sales which includes RTO/Cancelled
        net_sales = delivered_revenue + returned_revenue
        
        # Costs (from Meesho payments, estimate for others)
        # NOTE: For RTO orders, platform doesn't charge shipping (forward or return)
        # Shipping charges only apply to delivered and returned orders
        total_commission = df_payments['commission'].sum() if not df_payments.empty else 0
        total_platform_fee = df_payments['platform_fee'].sum() if not df_payments.empty else 0
        
        # Calculate shipping only for delivered and returned orders (RTO = no shipping charge)
        delivered_orders = df_orders[df_orders['order_status'].str.contains('DELIVERED', na=False)]
        returned_orders = df_orders[df_orders['order_status'].str.contains('RETURN', na=False)]
        exchanged_orders = df_orders[df_orders['order_status'].str.contains('EXCHANGE', na=False)]
        
        # Shipping: Only count for orders that actually shipped and reached customer
        total_shipping = delivered_orders['shipping'].sum() + returned_orders['shipping'].sum() + exchanged_orders['shipping'].sum()
        
        # Return shipping: Only for actual returns (not RTO)
        total_return_shipping = df_payments['return_shipping'].sum() if not df_payments.empty else 0
        
        total_gst_compensation = df_payments['gst_compensation'].sum() if not df_payments.empty else 0
        total_tcs = df_payments['tcs'].sum() if not df_payments.empty else 0
        total_tds = df_payments['tds'].sum() if not df_payments.empty else 0
        total_compensation_claims = df_payments['compensation'].sum() if not df_payments.empty else 0
        
        # Fixed costs (packing charges)
        # All orders need packing (including RTO/Cancelled), RTO needs repacking
        total_orders = len(df_orders)
        rto_count = len(df_orders[df_orders['order_status'].str.contains('RTO', na=False)])
        returned_count = len(df_orders[df_orders['order_status'].str.contains('RETURN', na=False)])
        
        # Packing cost: All orders + extra for RTO (repack) + extra for returns (repack if reselling)
        total_packing_charges = (total_orders + rto_count + returned_count) * fixed_cost_per_order
        
        # Cost of Goods Sold (COGS)
        # Only count COGS for delivered orders + damaged returns (not resellable)
        # For now, assume all delivered orders = COGS incurred
        delivered_cogs = df_orders[df_orders['order_status'].str.contains('DELIVERED', na=False)]['cogs'].sum()
        
        # For RTO and Cancelled: Only COGS if product is damaged/unsellable (assume 20% damage rate)
        rto_cogs = df_orders[df_orders['order_status'].str.contains('RTO', na=False)]['cogs'].sum() * 0.2
        cancelled_cogs = df_orders[df_orders['order_status'].str.contains('CANCEL', na=False)]['cogs'].sum() * 0.1
        
        # For Returns: COGS if damaged (assume 30% damage rate for returns)
        returned_cogs = df_orders[df_orders['order_status'].str.contains('RETURN', na=False)]['cogs'].sum() * 0.3
        
        total_cogs = delivered_cogs + rto_cogs + cancelled_cogs + returned_cogs
        
        # Estimate commission for Flipkart/Amazon (approx 15-20% of revenue)
        flipkart_revenue = sum(row['revenue'] for row in flipkart_order_data)
        amazon_revenue = sum(row['revenue'] for row in amazon_order_data)
        estimated_flipkart_commission = flipkart_revenue * 0.18
        estimated_amazon_commission = amazon_revenue * 0.15
        total_commission += estimated_flipkart_commission + estimated_amazon_commission
        
        # Ads cost - use absolute value (data may be stored as negative)
        ads_cost_total = sum(abs(ac.total_ads_cost or 0) for ac in ads_costs)
        
        # CORRECTED PROFIT CALCULATION:
        # Profit = Settlement Amount - Your Actual Costs + Compensation
        # Settlement = What you actually receive (delivered payout - return refunds)
        # Your Costs = COGS (adjusted) + Packing (including repacking) + Ads + Return Shipping
        
        # Total settlement amount (what platform actually pays you)
        total_settlement = delivered_payout + abs(df_payments['total_return_amount'].sum() * -1) if not df_payments.empty else delivered_payout
        
        # Your actual out-of-pocket costs
        actual_out_of_pocket_costs = (
            total_cogs +                    # Adjusted COGS (delivered + damaged items)
            total_packing_charges +         # Packing + repacking
            ads_cost_total +                # Ads
            abs(total_return_shipping)      # Return shipping you pay
        )
        
        # Add compensation/claims you received back
        net_costs_after_compensation = actual_out_of_pocket_costs - abs(total_compensation_claims)
        
        # True profit = Settlement - (Your Costs - Compensation)
        gross_profit = total_settlement - net_costs_after_compensation
        net_profit = gross_profit
        
        # Profit margin based on net sales
        profit_margin = (gross_profit / net_sales * 100) if net_sales > 0 else 0
        
        # For cost breakdown display, we still show individual components
        # but total_costs now represents actual costs you pay
        total_costs = actual_out_of_pocket_costs
        
        # === PRODUCT-LEVEL PROFITABILITY - ALL MARKETPLACES ===
        # FIXED: Aggregate actual costs from payment data (not proportional allocation!)
        product_revenue = df_orders.groupby(['marketplace', 'product_id', 'product_name']).agg({
            'revenue': 'sum',
            'quantity': 'sum',
            'commission': 'sum',
            'platform_fee': 'sum',
            'shipping': 'sum',
            'tcs': 'sum',
            'tds': 'sum',
            'gst_compensation': 'sum',
            'packing_charge': 'sum',  # Sum fixed costs across all orders
            'cogs': 'sum'  # Sum cost of goods sold
        }).reset_index()
        
        # Calculate actual product-level profit using real costs (not proportional!)
        product_revenue['total_costs'] = (
            product_revenue['commission'] + 
            product_revenue['platform_fee'] + 
            product_revenue['shipping'] + 
            product_revenue['tcs'] +
            product_revenue['tds'] +
            product_revenue['packing_charge'] +  # Add fixed costs
            product_revenue['cogs'] -  # Add cost of goods sold
            product_revenue['gst_compensation']  # Credit, so subtract
        )
        
        # Allocate ads cost proportionally (not tracked per order)
        total_revenue = product_revenue['revenue'].sum()
        if total_revenue > 0:
            product_revenue['allocated_ads'] = product_revenue['revenue'] / total_revenue * ads_cost_total
            product_revenue['total_costs'] += product_revenue['allocated_ads']
        
        product_revenue['gross_profit'] = product_revenue['revenue'] - product_revenue['total_costs']
        product_revenue['profit_margin'] = (product_revenue['gross_profit'] / product_revenue['revenue'] * 100).fillna(0)
        
        product_revenue = product_revenue.sort_values('revenue', ascending=False)
        
        product_profitability = [{
            'marketplace': row['marketplace'],
            'product_id': row['product_id'],
            'product_name': row['product_name'],
            'revenue': round(row['revenue'], 2),
            'quantity': int(row['quantity']),
            'gross_profit': round(row['gross_profit'], 2) if 'gross_profit' in row else 0,
            'profit_margin': round(row['profit_margin'], 1) if 'profit_margin' in row else 0
        } for _, row in product_revenue.head(20).iterrows()]
        
        # === COST BREAKDOWN ===
        cost_breakdown = [
            {'category': 'Cost of Goods Sold (COGS)', 'amount': round(total_cogs, 2), 'percentage': round(total_cogs/net_sales*100, 1) if net_sales > 0 else 0},
            {'category': 'Commission', 'amount': round(total_commission, 2), 'percentage': round(total_commission/net_sales*100, 1) if net_sales > 0 else 0},
            {'category': 'Platform Fee', 'amount': round(total_platform_fee, 2), 'percentage': round(total_platform_fee/net_sales*100, 1) if net_sales > 0 else 0},
            {'category': 'Shipping', 'amount': round(abs(total_shipping), 2), 'percentage': round(abs(total_shipping)/net_sales*100, 1) if net_sales > 0 else 0},
            {'category': 'Return Shipping', 'amount': round(abs(total_return_shipping), 2), 'percentage': round(abs(total_return_shipping)/net_sales*100, 1) if net_sales > 0 else 0},
            {'category': 'Packing Charges (incl. repacking)', 'amount': round(total_packing_charges, 2), 'percentage': round(total_packing_charges/net_sales*100, 1) if net_sales > 0 else 0},
            {'category': 'Ads Cost', 'amount': round(ads_cost_total, 2), 'percentage': round(ads_cost_total/net_sales*100, 1) if net_sales > 0 else 0},
            {'category': 'TCS', 'amount': round(total_tcs, 2), 'percentage': round(total_tcs/net_sales*100, 1) if net_sales > 0 else 0},
            {'category': 'TDS', 'amount': round(total_tds, 2), 'percentage': round(total_tds/net_sales*100, 1) if net_sales > 0 else 0},
            {'category': 'GST Compensation (Credit)', 'amount': round(total_gst_compensation, 2), 'percentage': round(total_gst_compensation/net_sales*100, 1) if net_sales > 0 else 0},
            {'category': 'Compensation/Claims (Credit)', 'amount': round(abs(total_compensation_claims), 2), 'percentage': round(abs(total_compensation_claims)/net_sales*100, 1) if net_sales > 0 else 0},
        ]
        
        return {
            'overview': {
                'total_sales': round(total_sales, 2),
                'delivered_revenue': round(delivered_revenue, 2),
                'returned_revenue': round(returned_revenue, 2),
                'total_returns': round(total_returns, 2),
                'net_sales': round(net_sales, 2),
                'total_settlement': round(total_settlement, 2),  # What you actually receive
                'total_costs': round(total_costs, 2),  # Your actual out-of-pocket costs
                'net_costs_after_compensation': round(net_costs_after_compensation, 2),
                'total_compensation_claims': round(abs(total_compensation_claims), 2),
                'delivered_cogs': round(delivered_cogs, 2),
                'rto_cogs': round(rto_cogs, 2),
                'cancelled_cogs': round(cancelled_cogs, 2),
                'returned_cogs': round(returned_cogs, 2),
                'total_cogs': round(total_cogs, 2),
                'rto_count': rto_count,
                'returned_count': returned_count,
                'total_return_shipping': round(abs(total_return_shipping), 2),
                'gross_profit': round(gross_profit, 2),
                'net_profit': round(net_profit, 2),
                'profit_margin': round(profit_margin, 1)
            },
            'order_status_summary': order_status_summary,
            'cost_breakdown': cost_breakdown,
            'product_profitability': product_profitability
        }
    except Exception as e:
        return {'error': str(e)}

def get_action_items_analytics(db: Session, fy: str = None, month: int = None, gstin: str = None):
    """
    Prioritized action items and alerts for immediate attention.
    Replaces: Predictive Alerts, Compliance Audit
    Sorted by business impact (revenue/profit at risk)
    NOW INCLUDES DATA FROM ALL MARKETPLACES: Meesho, Flipkart, Amazon
    
    Args:
        db: Database session
        fy: Financial year filter (e.g., "2024-25" or None for all)
        month: Month filter (1-12 or None for all)
        gstin: Seller GSTIN filter (None for all sellers)
    """
    try:
        import pandas as pd
        from models import FlipkartOrder, FlipkartReturn, AmazonOrder, AmazonReturn
        
        # Query all marketplaces with date filtering
        # Use MeeshoSale instead of MeeshoOrder (MeeshoOrder doesn't have gstin)
        meesho_query = db.query(MeeshoSale)
        flipkart_query = db.query(FlipkartOrder).filter(FlipkartOrder.event_type == 'Sale')
        amazon_query = db.query(AmazonOrder).filter(AmazonOrder.transaction_type == 'Shipment')
        payments_query = db.query(MeeshoPayment)
        
        # Apply GSTIN filter if provided
        if gstin:
            meesho_query = meesho_query.filter(MeeshoSale.gstin == gstin)
            flipkart_query = flipkart_query.filter(FlipkartOrder.seller_gstin == gstin)
            amazon_query = amazon_query.filter(AmazonOrder.seller_gstin == gstin)
            payments_query = payments_query.filter(MeeshoPayment.seller_gstin == gstin)  # Filter payments by GSTIN
        
        # Apply date filters if provided
        if fy:
            # Extract start year from FY (e.g., "2024-25" -> 2024)
            start_year = int(fy.split('-')[0])
            # FY runs from April to March
            fy_start = f"{start_year}-04-01"
            fy_end = f"{start_year + 1}-03-31"
            
            meesho_query = meesho_query.filter(MeeshoSale.order_date.between(fy_start, fy_end))
            flipkart_query = flipkart_query.filter(FlipkartOrder.order_date.between(fy_start, fy_end))
            amazon_query = amazon_query.filter(AmazonOrder.order_date.between(fy_start, fy_end))
            payments_query = payments_query.filter(MeeshoPayment.payment_date.between(fy_start, fy_end))
        
        if month:
            from sqlalchemy import extract
            meesho_query = meesho_query.filter(extract('month', MeeshoSale.order_date) == month)
            flipkart_query = flipkart_query.filter(extract('month', FlipkartOrder.order_date) == month)
            amazon_query = amazon_query.filter(extract('month', AmazonOrder.order_date) == month)
            payments_query = payments_query.filter(extract('month', MeeshoPayment.payment_date) == month)
        
        meesho_sales = meesho_query.all()
        flipkart_orders = flipkart_query.all()
        amazon_orders = amazon_query.all()
        payments = payments_query.all()
        
        # Query inventory with GSTIN filter
        inventory_query = db.query(MeeshoInventory)
        if gstin:
            inventory_query = inventory_query.filter(MeeshoInventory.seller_gstin == gstin)
        inventory = inventory_query.all()
        
        meesho_returns_query = db.query(MeeshoReturn)
        flipkart_returns_query = db.query(FlipkartReturn)
        amazon_returns_query = db.query(AmazonReturn).filter(AmazonReturn.transaction_type == 'Refund')
        
        # Apply GSTIN filter to returns
        if gstin:
            meesho_returns_query = meesho_returns_query.filter(MeeshoReturn.gstin == gstin)
            flipkart_returns_query = flipkart_returns_query.filter(FlipkartReturn.seller_gstin == gstin)
            amazon_returns_query = amazon_returns_query.filter(AmazonReturn.seller_gstin == gstin)
        
        meesho_returns = meesho_returns_query.all()
        flipkart_returns = flipkart_returns_query.all()
        amazon_returns = amazon_returns_query.all()
        
        invoices = db.query(MeeshoInvoice).all()
        
        action_items = []
        
        # Build product_id -> product_name mapping from inventory
        product_name_map = {}
        for inv in inventory:
            if inv.product_id and inv.product_name:
                product_name_map[inv.product_id] = inv.product_name
        
        # Calculate total sales per product for prioritization - ALL MARKETPLACES
        # MeeshoSale uses 'identifier' as product_id and has 'total_taxable_sale_value' / 'quantity' for price
        meesho_order_data = [{
            'product_id': s.identifier,
            'product_name': product_name_map.get(s.identifier, f"Product #{s.identifier}") if s.identifier else "Unknown",
            'quantity': s.quantity or 0,
            'price': (s.total_taxable_sale_value or 0) / s.quantity if s.quantity and s.quantity > 0 else 0
        } for s in meesho_sales if s.identifier]
        
        df_orders = pd.DataFrame(meesho_order_data) if meesho_order_data else pd.DataFrame(columns=['product_id', 'product_name', 'quantity', 'price'])
        
        if not df_orders.empty:
            df_orders['revenue'] = df_orders['quantity'] * df_orders['price']
            total_revenue_by_product = df_orders.groupby('product_id').agg({
                'revenue': 'sum',
                'quantity': 'sum'
            }).to_dict('index')
        else:
            total_revenue_by_product = {}
        
        # === 1. CRITICAL: OUT OF STOCK ON BEST SELLERS ===
        for inv in inventory:
            if inv.current_stock == 0 and inv.product_id:
                product_info = total_revenue_by_product.get(inv.product_id, {})
                revenue = product_info.get('revenue', 0)
                quantity = product_info.get('quantity', 0)
                
                if quantity > 10:  # Only alert if it's a selling product
                    action_items.append({
                        'priority': 'CRITICAL',
                        'category': 'Inventory',
                        'issue': f'OUT OF STOCK: {inv.product_name[:50]}',
                        'impact': f'Lost revenue potential: ₹{round(revenue/quantity*30, 0)} (30 days)',
                        'action': 'Reorder immediately',
                        'impact_score': revenue
                    })
        
        # === 2. HIGH: LOW STOCK ON FAST-MOVING ITEMS ===
        for inv in inventory:
            if 0 < (inv.current_stock or 0) < 5 and inv.product_id:
                product_info = total_revenue_by_product.get(inv.product_id, {})
                quantity = product_info.get('quantity', 0)
                
                if quantity > 5:
                    action_items.append({
                        'priority': 'HIGH',
                        'category': 'Inventory',
                        'issue': f'LOW STOCK: {inv.product_name[:50]} ({inv.current_stock} units)',
                        'impact': f'Selling {quantity} units total',
                        'action': 'Reorder within 3-5 days',
                        'impact_score': product_info.get('revenue', 0)
                    })
        
        # === 3. HIGH: PAYMENT DELAYS ===
        if payments:
            df_payments = pd.DataFrame([{
                'sub_order_no': p.sub_order_no,
                'order_date': p.order_date,
                'payment_date': p.payment_date,
                'amount': p.final_settlement_amount or 0
            } for p in payments if p.order_date and p.payment_date])
            
            if not df_payments.empty:
                df_payments['order_date'] = pd.to_datetime(df_payments['order_date'])
                df_payments['payment_date'] = pd.to_datetime(df_payments['payment_date'])
                df_payments['delay_days'] = (df_payments['payment_date'] - df_payments['order_date']).dt.days
                
                delayed = df_payments[df_payments['delay_days'] > 15]
                if len(delayed) > 0:
                    total_delayed_amount = delayed['amount'].sum()
                    action_items.append({
                        'priority': 'HIGH',
                        'category': 'Finance',
                        'issue': f'{len(delayed)} orders with payment delays >15 days',
                        'impact': f'Cash flow impact: ₹{round(total_delayed_amount, 2)}',
                        'action': 'Review with Meesho support',
                        'impact_score': total_delayed_amount
                    })
        
        # === 4. MEDIUM: HIGH RETURN RATE PRODUCTS - ALL MARKETPLACES ===
        if df_orders.empty:
            pass  # Skip if no order data
        else:
            # Combine returns from all marketplaces (Meesho only for product matching)
            df_returns = pd.DataFrame([{
                'product_id': r.product_id,
                'quantity': r.quantity or 0
            } for r in meesho_returns if r.product_id])
            
            if not df_returns.empty and not df_orders.empty:
                return_qty = df_returns.groupby('product_id')['quantity'].sum()
                order_qty = df_orders.groupby('product_id')['quantity'].sum()
                
                for pid in return_qty.index:
                    if pid in order_qty.index:
                        return_rate = return_qty[pid] / order_qty[pid] * 100
                        if return_rate > 20 and order_qty[pid] > 10:
                            product_name = df_orders[df_orders['product_id'] == pid]['product_name'].iloc[0]
                            revenue = total_revenue_by_product.get(pid, {}).get('revenue', 0)
                            
                            action_items.append({
                                'priority': 'MEDIUM',
                                'category': 'Quality',
                                'issue': f'HIGH RETURN RATE: {product_name[:50]} ({round(return_rate, 1)}%)',
                                'impact': f'Return cost + lost revenue',
                                'action': 'Check product quality, images, description',
                                'impact_score': revenue * return_rate / 100
                            })
        
        # === 5. MEDIUM: MISSING HSN CODES (Compliance) ===
        if invoices:
            missing_hsn = [inv for inv in invoices if not inv.hsn_code or inv.hsn_code == '']
            if len(missing_hsn) > 0:
                action_items.append({
                    'priority': 'MEDIUM',
                    'category': 'Compliance',
                    'issue': f'{len(missing_hsn)} invoices missing HSN codes',
                    'impact': 'GST filing may fail',
                    'action': 'Update HSN codes in invoice records',
                    'impact_score': 1000  # Fixed priority for compliance
                })
        
        # === 6. LOW: DUPLICATE INVOICES (Compliance) ===
        if invoices:
            df_invoices = pd.DataFrame([{
                'invoice_no': inv.invoice_no
            } for inv in invoices if inv.invoice_no])
            
            if not df_invoices.empty:
                duplicates = df_invoices[df_invoices.duplicated('invoice_no', keep=False)]
                if len(duplicates) > 0:
                    action_items.append({
                        'priority': 'LOW',
                        'category': 'Compliance',
                        'issue': f'{len(duplicates)} duplicate invoice numbers found',
                        'impact': 'Data integrity issue',
                        'action': 'Review and merge duplicate records',
                        'impact_score': 500
                    })
        
        # Sort by priority and impact score
        priority_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        action_items.sort(key=lambda x: (priority_order.get(x['priority'], 4), -x['impact_score']))
        
        # Count by priority
        summary = {
            'total_items': len(action_items),
            'critical': sum(1 for x in action_items if x['priority'] == 'CRITICAL'),
            'high': sum(1 for x in action_items if x['priority'] == 'HIGH'),
            'medium': sum(1 for x in action_items if x['priority'] == 'MEDIUM'),
            'low': sum(1 for x in action_items if x['priority'] == 'LOW')
        }
        
        return {
            'action_items': action_items,
            'summary': summary
        }
    except Exception as e:
        return {'error': str(e)}
