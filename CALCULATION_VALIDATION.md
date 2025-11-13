# Calculation Validation Guide

## Overview

The enhanced validator now performs **comprehensive calculation verification** to ensure all totals and calculations in the Excel file are correct. This is the **crucial part** of Excel validation.

## What Gets Validated

### 1. Line Item Calculations

For each line item, the validator checks:

- **Extended List Price = Quantity × Unit List Price**
  - Formula: `Qty × Unit List Price = Extended List Price`
  - Example: `1 × $77,658.39 = $77,658.39`

- **Extended Net Price = Quantity × Unit Net Price**
  - Formula: `Qty × Unit Net Price = Extended Net Price`
  - Example: `1 × $58,991.55 = $58,991.55`

- **Discount % Calculation**
  - Formula: `((Unit List Price - Unit Net Price) / Unit List Price) × 100`
  - Example: `(($77,658.39 - $58,991.55) / $77,658.39) × 100 = 24.04%`

### 2. Grand Total Calculations

The validator verifies that:

- **Sum of All Extended List Prices = List Grand Total**
  - Adds up all line item extended list prices
  - Compares against the "List Grand Total" field
  - Example: `$77,658.39 + $11,648.76 + ... = $101,880.85`

- **Sum of All Extended Net Prices = Net Grand Total**
  - Adds up all line item extended net prices
  - Compares against the "Net Grand Total" field
  - Example: `$58,991.55 + $8,848.40 + ... = $77,390.93`

### 3. Discount Calculation

- **Total Discount % = ((List Total - Net Total) / List Total) × 100**
  - Calculates discount from grand totals
  - Compares against the "Total Discount" field
  - Example: `(($101,880.85 - $77,390.93) / $101,880.85) × 100 = 24.04%`

### 4. Excel Internal Calculations

The validator also checks that Excel's own calculations are correct:

- **Excel List Total = Sum of Excel Extended List Prices**
- **Excel Net Total = Sum of Excel Extended Net Prices**

## Validation Output

When you run validation, you'll see results like:

```
[OK] Calculations/calc_ext_list_SG5812A-001-48TB:
    Expected: 77658.39
    Found:    77658.39
    Message:  Qty(1) × Unit List(77658.39) = 77658.39

[OK] Calculations/calc_grand_list_total:
    Expected: 101880.85
    Found:    101880.85
    Message:  Sum of all Extended List Prices = 101880.85

[OK] Calculations/calc_grand_net_total:
    Expected: 77390.93
    Found:    77390.93
    Message:  Sum of all Extended Net Prices = 77390.93

[OK] Calculations/calc_discount_percent:
    Expected: 24.04
    Found:    24.04
    Message:  (List 101880.85 - Net 77390.93) / List × 100 = 24.04%
```

## How to Use

### Step 1: Convert JSON to Excel (Optional)

```bash
python json_to_excel.py --json response.json --output api_data.xlsx
```

This creates an Excel file from the API response so you can visually compare.

### Step 2: Validate Excel File

```bash
python validate_excel.py --excel "your_file.xls" --transaction-id 481931730
```

The validator will:
1. Parse the Excel file
2. Ask for username/password
3. Fetch API data (or use existing response.json)
4. **Perform comprehensive calculation validation**
5. Show detailed results

## What to Look For

### ✅ PASS Indicators:
- All calculation fields show `[OK]`
- Expected and Found values match (within tolerance)
- Grand totals match sum of line items
- Discount percentages are correct

### ❌ FAIL Indicators:
- Calculation mismatches (e.g., `Qty × Price ≠ Extended Price`)
- Grand total doesn't match sum of line items
- Discount calculation is wrong
- Any `[FAIL]` in the Calculations section

## Tolerance Settings

Calculations use numeric tolerance (default: 0.01) to account for rounding:
- Values within $0.01 are considered matching
- Percentage values within 0.01% are considered matching

You can adjust tolerance in `config.py` or via environment variables.

## Important Notes

1. **All calculations are verified** - Every line item calculation is checked
2. **Grand totals are verified** - Sum of line items must match grand totals
3. **Discounts are verified** - Both line-level and total discounts are validated
4. **Excel calculations are verified** - Excel's own totals are checked for correctness

This ensures **100% accuracy** of all financial calculations in your Excel files.

