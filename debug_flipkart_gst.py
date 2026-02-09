import pandas as pd

file_path = '79be20c8-f53e-4d5b-a144-edd63c54eca4_1770333916000.xlsx'

# Section 7(B)(2) - B2C Sales
b2c_data = pd.read_excel(file_path, sheet_name='Section 7(B)(2) in GSTR-1')
print('=== Section 7(B)(2) - B2C Sales (Interstate) ===')
print('Total rows:', len(b2c_data))
print('Total Taxable Value:', b2c_data['Aggregate Taxable Value Rs.'].sum())
print()

# Section 12 - HSN Summary
hsn_data = pd.read_excel(file_path, sheet_name='Section 12 in GSTR-1')
print('=== Section 12 - HSN Summary ===')
print('Total rows:', len(hsn_data))
print('Total Taxable Value:', hsn_data['Total Taxable Value Rs.'].sum())
print()

print('=== Section 7(B)(2) Detail ===')
cols = ['Delivered State (PoS)', 'IGST %', 'Aggregate Taxable Value Rs.']
for idx, row in b2c_data.iterrows():
    print(f"{row['Delivered State (PoS)']:20} | {row['IGST %']:6} | {row['Aggregate Taxable Value Rs.']:12.2f}")
print()

print('=== Section 12 Detail ===')
for idx, row in hsn_data.iterrows():
    qty = row['Total Quantity in Nos.'] if pd.notna(row['Total Quantity in Nos.']) else 0
    val = row['Total Taxable Value Rs.'] if pd.notna(row['Total Taxable Value Rs.']) else 0
    hsn = row['HSN Number']
    print(f"HSN: {hsn:20} | Qty: {qty:8} | Taxable: {val:12.2f}")
