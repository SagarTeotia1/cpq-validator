# Comprehensive Pricing Validation Enhancements

## Overview
The pricing validation has been significantly enhanced to ensure **extreme accuracy** in validating all pricing attributes, with special attention to the difference between **unit prices** and **grand totals**.

## Key Enhancements

### 1. **Comprehensive Pricing Attribute Extraction**
- **Header-Level Pricing**: Extracts ALL pricing fields from API response including:
  - Grand Totals: `quoteListPrice_t_c`, `quoteNetPrice_t_c`, `extNetPrice_t_c`, `netPrice_t_c`
  - Discounts: `quoteCurrentDiscount_t_c`, `transactionTotalDiscountPercent_t`, `quoteDesiredDiscount_t_c`
  - Margins: `standardProductMarginUSD_t_c`, `fullStackMarginUSD_t_c`, `standardProductMarginPercentage_t_c`
  - Costs: `stdProductCost_t_c`, `fullStackStandardCostUSD_t_c`
  - And many more...

### 2. **Line Item Pricing Validation**
For each line item, the validator now checks:
- **Unit List Price** (`_price_item_price_each`, `_price_unit_price_each`, `_price_list_price_each`)
- **Unit Net Price** (`netPrice_l`, `netPrice_l_c`, `resellerUnitNetPricefloat_l_c`)
- **Extended List Price** (`_price_extended_price`, `extendedListPrice`, `listAmount_l`, `listPrice_l_c`)
- **Extended Net Price** (`netAmount_l`, `netAmountRollup_l`, `netPriceRollup_l`, `extendedNetPriceUSD_l_c`, `rollUpNetPrice_l_c`)
- **Discount Percent** (`discountPercent_l`, `currentDiscount_l_c`, `currentDiscountEndCustomer_l_c`)
- **Additional Fields**: `rollUpResUnitNetPrice_l_c`, `storageTotal_l_c`, `serviceTotal_l_c`, `hardwareTotal_l_c`

### 3. **CRITICAL Calculation Validations**

#### Unit Price × Quantity = Extended Price
For each line item, the validator verifies:
- **Extended List Price = Quantity × Unit List Price**
- **Extended Net Price = Quantity × Unit Net Price**

If these calculations don't match, a **CRITICAL** error is flagged with detailed information.

#### Grand Totals = Sum of Line Items
The validator ensures:
- **List Grand Total = Sum of all Extended List Prices**
- **Net Grand Total = Sum of all Extended Net Prices**

This is critical because:
- **Unit List Price** is the price per unit
- **Extended List Price** = Unit List Price × Quantity (for that line)
- **List Grand Total** = Sum of all Extended List Prices (across all lines)

### 4. **Multiple Field Fallbacks**
The validator checks multiple possible field names for each pricing attribute to handle variations in API responses:
- For Net Price: `quoteNetPrice_t_c`, `extNetPrice_t_c`, `netPrice_t_c`, `totalOneTimeNetAmount_t`, `_transaction_total`
- For List Price: `quoteListPrice_t_c`, `totalOneTimeListAmount_t`, `totalListPrice_t_c`

### 5. **Enhanced Error Messages**
All pricing mismatches now include:
- Clear indication if it's a **CRITICAL** pricing error
- Expected vs Found values (rounded to 2 decimal places)
- Calculation details (e.g., "Qty(1) × Unit List(101880.85) = 101880.85")

## Usage

### Standard Validation (via `validate_excel.py`)
```bash
python validate_excel.py --excel "174044_12-Nov-2025_13-47-19_Quote174044forArrowElectronicsInc..xls" --transaction-id 481931730
```

### Comprehensive Validation (via `comprehensive_pricing_validator.py`)
```bash
python comprehensive_pricing_validator.py --excel "your_file.xls" --json response.json
```

## Validation Sections

The validator now organizes results into sections:
- **Header**: Quote number, transaction ID, dates, etc.
- **Summary**: Grand totals (List Grand Total, Net Grand Total, Discount %)
- **Lines**: Individual line item pricing
- **Line Totals**: Storage, Service, Hardware totals per line
- **Calculations**: Critical calculation validations
  - Unit × Quantity = Extended (per line)
  - Sum of Extended = Grand Total

## Accuracy Requirements

- **Numeric Tolerance**: Default 0.01 (configurable in `config.py`)
- **Percentage Tolerance**: Default 0.1% (configurable)
- **Currency Parsing**: Handles $, €, ₹, Rs., commas, etc.
- **Rounding**: All values displayed rounded to 2 decimal places

## Important Notes

1. **Unit vs Extended vs Grand Total**:
   - **Unit Price**: Price for ONE unit
   - **Extended Price**: Unit Price × Quantity (for that line item)
   - **Grand Total**: Sum of ALL Extended Prices (for all line items)

2. **Multiple Pricing Fields**: The API may expose pricing in different fields. The validator checks all possible fields with priority order.

3. **Calculation Validation**: The validator not only compares API vs Excel values but also validates that calculations are correct internally.

4. **Critical Errors**: Any mismatch in pricing calculations is flagged as **CRITICAL** to ensure accuracy.

## Example Output

```
[FAIL] Calculations/calc_ext_list_SGA-TOP-LEVEL:
  Expected: 101880.85
  Found:    101880.85
  Message:  Qty(1) × Unit List(101880.85) = 101880.85, Found: 101880.85

[FAIL] Calculations/calc_grand_list_total:
  Expected: 101880.85
  Found:    101880.85
  Message:  CRITICAL: List Grand Total (101880.85) should equal sum of all Extended List Prices (101880.85)
```

