from database import SessionLocal
from models import FlipkartOrder, FlipkartReturn, AmazonOrder, AmazonReturn, MeeshoSale, MeeshoReturn
from datetime import datetime
from collections import defaultdict
import pandas as pd

db = SessionLocal()

# November 2025 - month 11
financial_year = 2025
month_number = 11

if month_number <= 3:
    year = financial_year
else:
    year = financial_year - 1

from datetime import datetime
month_start = datetime(year, month_number, 1)
if month_number == 12:
    month_end = datetime(year + 1, 1, 1)
else:
    month_end = datetime(year, month_number + 1, 1)

print(f"Date range: {month_start} to {month_end}")
print()

# Get Flipkart data
flipkart_orders = db.query(FlipkartOrder).filter(
    FlipkartOrder.event_type == 'Sale',
    FlipkartOrder.order_date >= month_start,
    FlipkartOrder.order_date < month_end
).all()

flipkart_returns = db.query(FlipkartReturn).filter(
    FlipkartReturn.order_date >= month_start,
    FlipkartReturn.order_date < month_end
).all()

print("=== FLIPKART SALES ===")
print(f"Total orders: {len(flipkart_orders)}")
sales_by_hsn = defaultdict(float)
for o in flipkart_orders:
    hsn = str(o.hsn_code or "UNKNOWN")
    sales_by_hsn[hsn] += o.taxable_value or 0

print(f"Total taxable value: {sum(sales_by_hsn.values()):.2f}")
print("\nByHSN:")
for hsn in sorted(sales_by_hsn.keys()):
    print(f"  {hsn}: {sales_by_hsn[hsn]:.2f}")

print()
print("=== FLIPKART RETURNS ===")
print(f"Total returns: {len(flipkart_returns)}")
returns_by_hsn = defaultdict(float)
for r in flipkart_returns:
    hsn = str(r.hsn_code or "UNKNOWN")
    returns_by_hsn[hsn] += r.taxable_value or 0

print(f"Total taxable value: {sum(returns_by_hsn.values()):.2f}")
print("\nBy HSN:")
for hsn in sorted(returns_by_hsn.keys()):
    print(f"  {hsn}: {returns_by_hsn[hsn]:.2f}")

print()
print("=== NET FLIPKART (Sales - Returns) ===")
all_hsns = set(sales_by_hsn.keys()) | set(returns_by_hsn.keys())
net_total = 0
for hsn in sorted(all_hsns):
    sales = sales_by_hsn.get(hsn, 0)
    returns = returns_by_hsn.get(hsn, 0)
    net = sales - returns
    net_total += net
    if net != 0:
        print(f"  {hsn}: Sales={sales:.2f}, Returns={returns:.2f}, Net={net:.2f}")

print(f"\nTotal Net: {net_total:.2f}")

db.close()
