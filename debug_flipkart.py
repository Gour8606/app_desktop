from database import SessionLocal
from models import FlipkartOrder, FlipkartReturn
from datetime import datetime
from collections import defaultdict

db = SessionLocal()

# November 2025 data
month_start = datetime(2025, 11, 1)
month_end = datetime(2025, 12, 1)

# Query Flipkart orders
flipkart_orders = db.query(FlipkartOrder).filter(
    FlipkartOrder.event_type == 'Sale',
    FlipkartOrder.order_date >= month_start,
    FlipkartOrder.order_date < month_end
).all()

flipkart_returns = db.query(FlipkartReturn).filter(
    FlipkartReturn.order_date >= month_start,
    FlipkartReturn.order_date < month_end
).all()

print("=== FLIPKART DATA SUMMARY ===")
print(f"Total Flipkart orders: {len(flipkart_orders)}")
print(f"Total Flipkart returns: {len(flipkart_returns)}")
print()

# Calculate totals
orders_taxable = sum(o.taxable_value or 0 for o in flipkart_orders)
returns_taxable = sum(r.taxable_value or 0 for r in flipkart_returns)
net_taxable = orders_taxable - returns_taxable

print(f"Orders taxable value: {orders_taxable:.2f}")
print(f"Returns taxable value: {returns_taxable:.2f}")
print(f"Net taxable (orders - returns): {net_taxable:.2f}")
print()

# Check by rate
print("=== ORDERS BY RATE ===")
orders_by_rate = defaultdict(float)
for o in flipkart_orders:
    if o.igst_rate and o.igst_rate > 0:
        rate = o.igst_rate
    elif o.cgst_rate and o.sgst_rate:
        rate = o.cgst_rate + o.sgst_rate
    else:
        rate = 0
    orders_by_rate[rate] += o.taxable_value or 0

for rate in sorted(orders_by_rate.keys()):
    print(f"Rate {rate}: {orders_by_rate[rate]:.2f}")

print()
print("=== RETURNS BY RATE ===")
returns_by_rate = defaultdict(float)
for r in flipkart_returns:
    if r.igst_rate and r.igst_rate > 0:
        rate = r.igst_rate
    elif r.cgst_rate and r.sgst_rate:
        rate = r.cgst_rate + r.sgst_rate
    else:
        rate = 0
    returns_by_rate[rate] += r.taxable_value or 0

for rate in sorted(returns_by_rate.keys()):
    print(f"Rate {rate}: {returns_by_rate[rate]:.2f}")

db.close()
