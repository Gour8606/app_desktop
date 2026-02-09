"""
export.py - Handles all CSV export/report generation functions for the Meesho Sales App.
"""

from models import MeeshoOrder, MeeshoPayment, MeeshoReturn, MeeshoInventory, MeeshoAdsCost
import os
import pandas as pd
from collections import defaultdict

def generate_catalog_summary_csv(output_path, db):
    """
    Generate a detailed catalog summary CSV matching the Meesho format with order values and fees.
    Includes: Orders by status, Order Values, Fees, Commission, Claims, Final Payout, etc.
    """
    orders = db.query(MeeshoOrder).all()
    payments = db.query(MeeshoPayment).all()
    returns = db.query(MeeshoReturn).all()
    inventory = db.query(MeeshoInventory).all()
    ads_costs = db.query(MeeshoAdsCost).all()

    # Build ads cost map by date
    ads_cost_total = sum(ac.total_ads_cost or 0 for ac in ads_costs)

    # Group orders by catalog (product_id from inventory)
    inventory_map = {}
    for inv in inventory:
        inventory_map[inv.product_id] = {
            'catalog_id': inv.catalog_id,
            'catalog_name': inv.catalog_name,
        }

    # Build summary by catalog_id (using numeric catalog ID from inventory)
    summary = defaultdict(lambda: {
        'Ready To Ship Orders': 0,
        'Ready To Ship Order Value': 0.0,
        'In Transit Orders': 0,
        'In Transit Order Value': 0.0,
        'Delivered Orders': 0,
        'Delivered Order Value': 0.0,
        'Cancelled Orders': 0,
        'Cancelled Order Value': 0.0,
        'Returned Orders': 0,
        'Returned Order Value': 0.0,
        'RTO Orders': 0,
        'RTO Order Value': 0.0,
        'Exchanged Orders': 0,
        'Exchanged Order Value': 0.0,
        'Commission': 0.0,
        'Return Shipping Fee': 0.0,
        'Exchange Shipping Fee': 0.0,
        'Claims': 0.0,
        'Ads Cost': 0.0,
    })

    # Process orders
    if orders:
        for order in orders:
            # Find matching catalog from inventory by product name
            catalog_key = None
            for inv in inventory:
                if inv.product_name and order.product_name and inv.product_name.lower() == order.product_name.lower():
                    catalog_key = inv.catalog_id
                    break
            
            if not catalog_key:
                catalog_key = order.product_name  # Fallback to product name if no catalog found
            
            status = (order.reason_for_credit_entry or '').upper()
            qty = order.quantity or 1
            value = (order.supplier_discounted_price or 0) * qty
            
            if 'READY' in status or 'READY TO SHIP' in status:
                summary[catalog_key]['Ready To Ship Orders'] += qty
                summary[catalog_key]['Ready To Ship Order Value'] += value
            elif 'TRANSIT' in status or 'IN TRANSIT' in status:
                summary[catalog_key]['In Transit Orders'] += qty
                summary[catalog_key]['In Transit Order Value'] += value
            elif 'DELIVERED' in status:
                summary[catalog_key]['Delivered Orders'] += qty
                summary[catalog_key]['Delivered Order Value'] += value
            elif 'CANCEL' in status:
                summary[catalog_key]['Cancelled Orders'] += qty
                summary[catalog_key]['Cancelled Order Value'] += value
            elif 'RETURN' in status:
                summary[catalog_key]['Returned Orders'] += qty
                summary[catalog_key]['Returned Order Value'] += value
            elif 'RTO' in status:
                summary[catalog_key]['RTO Orders'] += qty
                summary[catalog_key]['RTO Order Value'] += value
            elif 'EXCHANG' in status:
                summary[catalog_key]['Exchanged Orders'] += qty
                summary[catalog_key]['Exchanged Order Value'] += value

    # Process payments and fees
    if payments:
        for payment in payments:
            # Try to find corresponding order
            order = next((o for o in orders if o.sub_order_no == payment.sub_order_no), None)
            if order:
                catalog_key = None
                for inv in inventory:
                    if inv.product_name and order.product_name and inv.product_name.lower() == order.product_name.lower():
                        catalog_key = inv.catalog_id
                        break
                
                if not catalog_key:
                    catalog_key = order.product_name
                
                if catalog_key in summary:
                    summary[catalog_key]['Commission'] += payment.meesho_commission_incl_gst or 0
                    summary[catalog_key]['Return Shipping Fee'] += payment.shipping_charge_incl_gst or 0
                    summary[catalog_key]['Exchange Shipping Fee'] += (payment.meesho_gold_platform_fee_incl_gst or 0) + (payment.meesho_mall_platform_fee_incl_gst or 0)
                    summary[catalog_key]['Claims'] += payment.claims or 0
                    # Distribute ads cost across catalogs (proportional to order value)
                    if ads_cost_total > 0:
                        summary[catalog_key]['Ads Cost'] += ads_cost_total / max(len(summary), 1)

    # Build result rows
    result_rows = []
    for catalog_key, data in summary.items():
        # Get catalog name if it's a numeric ID
        catalog_name = ''
        catalog_id = catalog_key
        
        # Try to find in inventory
        for inv in inventory:
            if str(inv.catalog_id) == str(catalog_key):
                catalog_name = inv.catalog_name or ''
                catalog_id = inv.catalog_id
                break
        
        total_orders = (data['Ready To Ship Orders'] + data['In Transit Orders'] + 
                       data['Delivered Orders'] + data['Cancelled Orders'] + 
                       data['Returned Orders'] + data['RTO Orders'] + data['Exchanged Orders'])
        
        total_payout = (data['Delivered Order Value'] - data['Commission'] - 
                       data['Return Shipping Fee'] - data['Exchange Shipping Fee'] - 
                       data['Claims'] - data['Ads Cost'])
        
        row = {
            'Catalog ID': catalog_id,
            'Ready To Ship Orders': data['Ready To Ship Orders'],
            'Ready To Ship Order Value': round(data['Ready To Ship Order Value'], 2),
            'In Transit Orders': data['In Transit Orders'],
            'In Transit Order Value': round(data['In Transit Order Value'], 2),
            'Delivered Orders': data['Delivered Orders'],
            'Delivered Order Value': round(data['Delivered Order Value'], 2),
            'Cancelled Orders': data['Cancelled Orders'],
            'Cancelled Order Value': round(data['Cancelled Order Value'], 2),
            'Returned Orders': data['Returned Orders'],
            'Returned Order Value': round(data['Returned Order Value'], 2),
            'RTO Orders': data['RTO Orders'],
            'RTO Order Value': round(data['RTO Order Value'], 2),
            'Exchanged Orders': data['Exchanged Orders'],
            'Exchanged Order Value': round(data['Exchanged Order Value'], 2),
            'Total Orders': total_orders,
            'Total Orders Payout (A)': round(data['Delivered Order Value'], 2),
            'Commission (B)': round(data['Commission'], 2),
            'Return Shipping Fee (C)': round(data['Return Shipping Fee'], 2),
            'Tax Component (D)': 0.0,  # Not available in current data
            'Exchanged Orders.1': data['Exchanged Orders'],
            'Exchange Shipping Fee (E)': round(data['Exchange Shipping Fee'], 2),
            'Claims Accepted': 0,  # Count of claims
            'Claims Value (F)': round(data['Claims'], 2),
            'Ads Cost + Ads GST (G)': round(data['Ads Cost'], 2),
            'Final Payout (A+B+C+D+E+F+G)': round(total_payout, 2),
        }
        result_rows.append(row)

    df_out = pd.DataFrame(result_rows)
    df_out.to_csv(output_path, index=False)
    return output_path

def generate_order_summary_csv(output_path, db):
    """
    Generate an order summary CSV matching the provided format using available data/models.
    Columns: Sub orderId, Catalog ID, Quantity, Price, Order Date, Order Status, Payout Value, Payout Status, Claim Status, SKU ID
    """
    orders = db.query(MeeshoOrder).all()
    payments = db.query(MeeshoPayment).all()
    df_orders = pd.DataFrame([
        {
            'Sub orderId': o.sub_order_no,
            'Catalog ID': o.product_name,
            'Quantity': o.quantity or 0,
            'Price': o.supplier_discounted_price or 0,
            'Order Date': o.order_date.strftime('%Y-%m-%d') if o.order_date else '',
            'Order Status': o.reason_for_credit_entry or '',
            'SKU ID': o.sku or '',
        } for o in orders if o.sub_order_no
    ])
    payout_map = {}
    for p in payments:
        payout_map[p.sub_order_no] = {
            'Payout Value': p.final_settlement_amount or 0,
            'Payout Status': getattr(p, 'payout_status', 'PENDING'),
            'Claim Status': getattr(p, 'claim_status', ''),
        }
    if not df_orders.empty:
        df_orders['Payout Value'] = df_orders['Sub orderId'].map(lambda x: payout_map.get(x, {}).get('Payout Value', 0))
        df_orders['Payout Status'] = df_orders['Sub orderId'].map(lambda x: payout_map.get(x, {}).get('Payout Status', 'PENDING'))
        df_orders['Claim Status'] = df_orders['Sub orderId'].map(lambda x: payout_map.get(x, {}).get('Claim Status', ''))
    df_orders.to_csv(output_path, index=False)
    return output_path

def generate_payout_summary_csv(output_path, db):
    """
    Generate a payout summary CSV matching the provided format using available data/models.
    Columns: Type, Status, Orders, Payout
    """
    payments = db.query(MeeshoPayment).all()
    orders = db.query(MeeshoOrder).all()
    returns = db.query(MeeshoReturn).all()
    ads_costs = db.query(MeeshoAdsCost).all()
    
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
            'order_status': o.reason_for_credit_entry or '',
        } for o in orders
    ])
    df_returns = pd.DataFrame([
        {
            'order_status': getattr(r, 'order_status', ''),
        } for r in returns
    ])
    
    # Calculate Ads Cost from ads_costs table
    ads_cost_total = sum(ac.total_ads_cost or 0 for ac in ads_costs)
    
    delivered = df_orders[df_orders['order_status'].str.lower().str.contains('delivered')].shape[0]
    in_transit = df_orders[df_orders['order_status'].str.lower().str.contains('transit')].shape[0]
    cancelled = df_orders[df_orders['order_status'].str.lower().str.contains('cancel')].shape[0]
    rto = df_orders[df_orders['order_status'].str.lower().str.contains('rto')].shape[0]
    returned = df_orders[df_orders['order_status'].str.lower().str.contains('return')].shape[0]
    exchanged = df_orders[df_orders['order_status'].str.lower().str.contains('exchange')].shape[0]
    payout_delivered = df_payments['final_settlement_amount'].sum()
    payout_in_transit = 0
    payout_cancelled = 0
    payout_rto = 0
    payout_returned = 0
    payout_exchanged = 0
    commission = df_payments['meesho_commission'].sum()
    tax_component = df_payments['gst_compensation'].sum() * -1
    return_shipping_fee = 0
    exchange_shipping_fee = 0
    claim_details = df_payments['claims'].sum()
    affiliate_fee_recovery = df_payments['recovery'].sum()
    rows = [
        {'Type': 'Orders', 'Status': 'Delivered', 'Orders': delivered, 'Payout': round(payout_delivered, 2)},
        {'Type': 'Orders', 'Status': 'In Transit', 'Orders': in_transit, 'Payout': round(payout_in_transit, 2)},
        {'Type': 'Orders', 'Status': 'Cancelled', 'Orders': cancelled, 'Payout': round(payout_cancelled, 2)},
        {'Type': 'Orders', 'Status': 'RTO', 'Orders': rto, 'Payout': round(payout_rto, 2)},
        {'Type': 'Orders', 'Status': 'Returned', 'Orders': returned, 'Payout': round(payout_returned, 2)},
        {'Type': 'Orders', 'Status': 'Exchanged', 'Orders': exchanged, 'Payout': round(payout_exchanged, 2)},
        {'Type': 'Commission', 'Status': '-', 'Orders': '-', 'Payout': round(commission, 2)},
        {'Type': 'Tax Component', 'Status': '-', 'Orders': '-', 'Payout': round(tax_component, 2)},
        {'Type': 'Return Shipping Fee', 'Status': 'Returned Orders', 'Orders': returned, 'Payout': round(return_shipping_fee, 2)},
        {'Type': 'Exchange Shipping Fee', 'Status': 'Exchange Orders', 'Orders': exchanged, 'Payout': round(exchange_shipping_fee, 2)},
        {'Type': 'Claim Details', 'Status': 'Claims Accepted', 'Orders': '-', 'Payout': round(claim_details, 2)},
        {'Type': 'Ads Cost + Ads GST', 'Status': '', 'Orders': '', 'Payout': round(ads_cost_total, 2)},
        {'Type': 'Additional Services', 'Status': 'AFFILIATE_FEE_RECOVERY', 'Orders': '', 'Payout': round(affiliate_fee_recovery, 2)},
    ]
    df_out = pd.DataFrame(rows)
    df_out.to_csv(output_path, index=False)
    return output_path
