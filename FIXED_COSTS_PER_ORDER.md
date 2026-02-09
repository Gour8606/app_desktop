# Fixed Costs Per Order

**Date**: November 21, 2025  
**Feature**: Hard-coded operational costs (packing charges, etc.)

---

## 🎯 The Requirement

**User Question:**
> "There are some fixed cost per order like packing charges which should be hard coded right?"

**Answer:** YES! ✅

Fixed operational costs that apply to **every order** should be hard-coded and included in profit calculations.

---

## 💰 What Are Fixed Costs?

**Fixed costs per order** are operational expenses that occur for **every single order**, regardless of:
- Product type
- Order value
- Marketplace
- Quantity

### **Examples:**
- **Packing materials:** Boxes, bubble wrap, tape
- **Labels:** Shipping labels, product labels
- **Quality control:** Inspection time/costs
- **Handling:** Labor cost per order
- **Documentation:** Invoice printing

---

## ✅ Implementation

### **1. Constants (constants.py)**

Created new `FixedCosts` class:

```python
class FixedCosts:
    """Fixed costs per order (hard-coded operational costs)."""
    
    # Packing charges per order
    PACKING_CHARGE_PER_ORDER = 10.0  # Rs. 10 per order
    
    # TODO: Add more fixed costs as needed
    # LABEL_COST = 2.0  # Rs. 2 per order
    # TAPE_COST = 1.0   # Rs. 1 per order
    
    @classmethod
    def get_total_fixed_cost_per_order(cls) -> float:
        """Get total fixed cost per order (sum of all fixed costs)."""
        return cls.PACKING_CHARGE_PER_ORDER
        # Add more as needed:
        # return cls.PACKING_CHARGE_PER_ORDER + cls.LABEL_COST + cls.TAPE_COST
```

**Current Default:** Rs. 10 per order

---

### **2. Analytics Integration (analytics.py)**

#### **Step 1: Import**
```python
from constants import FixedCosts
```

#### **Step 2: Calculate at Start**
```python
fixed_cost_per_order = FixedCosts.get_total_fixed_cost_per_order()
```

#### **Step 3: Add to Order Data**
```python
meesho_order_data = [{
    ...
    'packing_charge': fixed_cost_per_order,  # Fixed cost per order
    ...
}]
```

#### **Step 4: Include in Cost Calculations**
```python
# Product-level costs
product_revenue['total_costs'] = (
    product_revenue['commission'] + 
    product_revenue['platform_fee'] + 
    product_revenue['shipping'] + 
    product_revenue['packing_charge'] +  # ← Fixed costs included!
    ...
)

# Overall costs
total_packing_charges = total_orders * fixed_cost_per_order
total_costs = (...other costs... + total_packing_charges)
```

#### **Step 5: Show in Cost Breakdown**
```python
cost_breakdown = [
    {'category': 'Packing Charges', 'amount': round(total_packing_charges, 2), ...},
    ...
]
```

---

## 📊 Impact on Financials

### **Before (Without Fixed Costs):**
```
Product: BLACK 100
Revenue: Rs. 100,000
Costs:
  - Commission: Rs. 15,000
  - Shipping: Rs. 5,000
  - Total Costs: Rs. 20,000
Profit: Rs. 80,000
Margin: 80%  ← Inflated!
```

### **After (With Fixed Costs):**
```
Product: BLACK 100
Revenue: Rs. 100,000
Orders: 1,000
Costs:
  - Commission: Rs. 15,000
  - Shipping: Rs. 5,000
  - Packing: Rs. 10,000  (1,000 orders × Rs. 10)
  - Total Costs: Rs. 30,000
Profit: Rs. 70,000
Margin: 70%  ← Accurate!
```

✅ **10% difference** in profit margin - significant for business decisions!

---

## 🔧 How to Customize

### **Change Packing Cost:**

Edit `constants.py`:
```python
class FixedCosts:
    PACKING_CHARGE_PER_ORDER = 15.0  # Changed to Rs. 15
```

### **Add More Fixed Costs:**

```python
class FixedCosts:
    PACKING_CHARGE_PER_ORDER = 10.0  # Rs. 10
    LABEL_COST = 2.0                 # Rs. 2
    TAPE_COST = 1.0                  # Rs. 1
    QC_COST = 5.0                    # Rs. 5 (Quality Control)
    
    @classmethod
    def get_total_fixed_cost_per_order(cls) -> float:
        return (cls.PACKING_CHARGE_PER_ORDER + 
                cls.LABEL_COST + 
                cls.TAPE_COST + 
                cls.QC_COST)
        # Total: Rs. 18 per order
```

**No code changes needed in analytics.py!** Just update constants.

---

## 📈 Example Calculation

### **Scenario:**
- 10,000 orders
- Fixed cost: Rs. 10 per order

### **Calculation:**
```
Total Packing Charges = 10,000 orders × Rs. 10 = Rs. 100,000
```

### **Cost Breakdown:**
```
Commission:       Rs. 500,000  (20.0%)
Platform Fee:     Rs. 50,000   (2.0%)
Shipping:         Rs. 200,000  (8.0%)
Packing Charges:  Rs. 100,000  (4.0%)  ← New!
Ads Cost:         Rs. 50,000   (2.0%)
TCS:              Rs. 10,000   (0.4%)
TDS:              Rs. 10,000   (0.4%)
-------------------------------------------
Total Costs:      Rs. 920,000  (36.8%)
```

---

## 🎯 Key Benefits

### ✅ **1. Accurate Profitability**
- Includes ALL operational costs
- True profit per order
- Better pricing decisions

### ✅ **2. Product-Level Insights**
- Fixed costs allocated to each product
- High-volume products show true margin impact
- Low-volume products don't carry disproportionate burden

### ✅ **3. Scalability**
- Easy to add more fixed costs
- Centralized in one place (constants.py)
- No code changes in multiple places

### ✅ **4. Visibility**
- Shows in cost breakdown
- Separate line item
- Easy to track and optimize

---

## 📝 Cost Breakdown Display

### **Financial Dashboard Shows:**
```
COST BREAKDOWN:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Category                Amount      %
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Commission              500,000   20.0%
Platform Fee             50,000    2.0%
Shipping                200,000    8.0%
Packing Charges         100,000    4.0%  ← New!
Ads Cost                 50,000    2.0%
TCS                      10,000    0.4%
TDS                      10,000    0.4%
GST Compensation        -20,000   -0.8%
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
TOTAL                   900,000   36.0%
```

---

## 🔍 Per-Product Impact

### **High-Volume Product:**
```
Product: BLACK 100
Orders: 5,000
Fixed Cost Impact: 5,000 × Rs. 10 = Rs. 50,000
Per-Order: Rs. 10 (consistent)
```

### **Low-Volume Product:**
```
Product: CUSTOM COMBO
Orders: 10
Fixed Cost Impact: 10 × Rs. 10 = Rs. 100
Per-Order: Rs. 10 (consistent)
```

✅ **Fair allocation** - each order pays the same fixed cost!

---

## 🎓 Best Practices

### **1. Review Regularly**
- Audit actual packing costs quarterly
- Adjust constants.py if needed
- Track cost trends

### **2. Be Comprehensive**
- Include ALL per-order costs
- Don't forget small items (tape, labels, etc.)
- Add up to true operational cost

### **3. Document Assumptions**
```python
class FixedCosts:
    # Packing cost breakdown:
    # - Box: Rs. 5
    # - Bubble wrap: Rs. 2
    # - Tape: Rs. 1
    # - Label: Rs. 2
    # Total: Rs. 10
    PACKING_CHARGE_PER_ORDER = 10.0
```

### **4. Test Impact**
- Run financial analysis before/after
- Verify profit margins make sense
- Check cost breakdown percentages

---

## 📖 Related Files

- **`constants.py`** - FixedCosts class definition
- **`analytics.py`** - Integration and calculations
- **Financial Dashboard** - Displays packing charges in cost breakdown

---

## 🎯 Summary

**Fixed Costs Implementation:**

1. ✅ **Hard-coded** in constants.py (Rs. 10 default)
2. ✅ **Applied to all orders** (Meesho, Flipkart, Amazon)
3. ✅ **Included in calculations** (product-level & overall)
4. ✅ **Visible in reports** (cost breakdown)
5. ✅ **Easy to customize** (change one constant)
6. ✅ **Extensible** (add more fixed costs easily)

**Result:**
- More accurate profitability analysis
- Better business decisions
- True operational cost visibility

**Current Setting:** Rs. 10 per order (customizable in `constants.py`)

---

**Commit:** `6686cbd` - "feat: Add fixed costs per order (packing charges)"

**Status:** ✅ **READY TO USE**
