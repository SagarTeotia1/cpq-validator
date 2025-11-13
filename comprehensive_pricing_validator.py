"""Comprehensive pricing validation with all attributes"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from config import AppConfig
from excel_parser import extract_excel_data
from validator import validate_quote, FieldResult
from utils import floats_match, parse_currency


def extract_all_pricing_attributes(api_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract ALL pricing-related attributes from API response."""
    pricing = {}
    
    # Header-level pricing attributes
    pricing_fields = [
        # Grand Totals
        "quoteListPrice_t_c",
        "quoteNetPrice_t_c", 
        "extNetPrice_t_c",
        "netPrice_t_c",
        "totalOneTimeListAmount_t",
        "totalOneTimeNetAmount_t",
        "totalOneTimeCostAmount_t",
        "totalOneTimeDiscount_t",
        "totalOneTimeMarginAmount_t",
        "totalContractListValue_t_c",
        "totalContractCostAmount_t",
        "totalListPrice_t_c",
        "totalNetPrice_t_c",
        
        # Discounts
        "quoteCurrentDiscount_t_c",
        "transactionTotalDiscountPercent_t",
        "quoteDesiredDiscount_t_c",
        "totalMonthlyDiscount_t",
        "discountAmount_t_c",
        "discountAmountUSD_t_c",
        
        # Desired/Adjusted Prices
        "quoteDesiredNetPrice_t_c",
        "quotedesiredNetPriceUSD_t_c",
        
        # Margins
        "standardProductMarginUSD_t_c",
        "standardProductMargin_t_c",
        "standardProductMarginPercentage_t_c",
        "fullStackMarginUSD_t_c",
        "fullStackMargin_t_c",
        "fullStackMarginPercent_t_c",
        "quoteSuggestedMargin_t_c",
        
        # Costs
        "stdProductCost_t_c",
        "fullStackStandardCostUSD_t_c",
        "fullStackOnlyCost_t_c",
        
        # Other Pricing
        "quoteFullStackOnlyNetPrice_t_c",
        "guidanceToGreenAmount_t_c",
        "guidanceToYellowAmount_t_c",
        "guidanceToOrangeAmount_t_c",
        "quoteTotalCapacityGB_t_c",
        "quoteDollarPerGBTotal_t_c",
        
        # Currency
        "currency_t",
    ]
    
    for field in pricing_fields:
        val = api_data.get(field)
        if val is not None:
            # Handle dict values (e.g., currency_t: {value: "USD", displayValue: "USD"})
            if isinstance(val, dict):
                pricing[field] = val.get("value") or val.get("displayValue") or val
            else:
                pricing[field] = val
    
    return pricing


def extract_line_item_pricing(line: Dict[str, Any]) -> Dict[str, Any]:
    """Extract ALL pricing attributes from a line item."""
    line_pricing = {}
    
    # Quantity
    qty = line.get("_price_quantity") or line.get("_line_bom_item_quantity") or line.get("quantity")
    line_pricing["quantity"] = qty
    
    # Unit Prices - List
    unit_list_price_keys = [
        "_price_item_price_each",
        "_price_unit_price_each", 
        "_price_list_price_each",
        "unitListPrice",
    ]
    for key in unit_list_price_keys:
        val = line.get(key)
        if val is not None:
            if isinstance(val, dict) and val.get("value") is not None:
                line_pricing["unitListPrice"] = val.get("value")
                line_pricing["unitListPrice_currency"] = val.get("currency")
                break
            elif isinstance(val, (int, float)) and val != 0:
                line_pricing["unitListPrice"] = val
                break
    
    # Unit Prices - Net
    unit_net_price_keys = [
        "netPrice_l",
        "netPrice_l_c",
        "unitNetPrice",
        "resellerUnitNetPricefloat_l_c",
        "endCustomerUnitNetPricefloat_l_c",
    ]
    for key in unit_net_price_keys:
        val = line.get(key)
        if val is not None:
            if isinstance(val, dict) and val.get("value") is not None:
                line_pricing["unitNetPrice"] = val.get("value")
                line_pricing["unitNetPrice_currency"] = val.get("currency")
                break
            elif isinstance(val, (int, float)) and val != 0:
                line_pricing["unitNetPrice"] = val
                break
    
    # Extended Prices - List
    ext_list_price_keys = [
        "_price_extended_price",
        "extendedListPrice",
        "extListPrice_l_c",
        "listAmount_l",
        "listPriceRollup_l",
    ]
    for key in ext_list_price_keys:
        val = line.get(key)
        if val is not None:
            if isinstance(val, dict) and val.get("value") is not None:
                line_pricing["extendedListPrice"] = val.get("value")
                break
            elif isinstance(val, (int, float)) and val != 0:
                line_pricing["extendedListPrice"] = val
                break
    
    # Extended Prices - Net
    ext_net_price_keys = [
        "netAmount_l",
        "netAmountRollup_l",
        "netPriceRollup_l",
        "extendedNetPrice",
        "extendedNetPriceUSD_l_c",
        "rollUpNetPrice_l_c",
    ]
    for key in ext_net_price_keys:
        val = line.get(key)
        if val is not None:
            if isinstance(val, dict) and val.get("value") is not None:
                line_pricing["extendedNetPrice"] = val.get("value")
                break
            elif isinstance(val, (int, float)) and val != 0:
                line_pricing["extendedNetPrice"] = val
                break
    
    # Discounts
    discount_keys = [
        "discountPercent_l",
        "currentDiscount_l_c",
        "currentDiscountEndCustomer_l_c",
        "discountPercent",
    ]
    for key in discount_keys:
        val = line.get(key)
        if val is not None:
            if isinstance(val, dict) and val.get("value") is not None:
                line_pricing["discountPercent"] = val.get("value")
                break
            elif isinstance(val, (int, float)):
                line_pricing["discountPercent"] = val
                break
    
    # Discount Amount
    discount_amount = line.get("discountAmount_l")
    if discount_amount is not None:
        if isinstance(discount_amount, dict) and discount_amount.get("value") is not None:
            line_pricing["discountAmount"] = discount_amount.get("value")
        elif isinstance(discount_amount, (int, float)):
            line_pricing["discountAmount"] = discount_amount
    
    # Totals by category
    line_pricing["hardwareTotal"] = line.get("hardwareTotal_l_c")
    line_pricing["serviceTotal"] = line.get("serviceTotal_l_c")
    line_pricing["storageTotal"] = line.get("storageTotal_l_c")
    line_pricing["rollUpResUnitNetPrice"] = line.get("rollUpResUnitNetPrice_l_c")
    
    # Calculate if missing
    if line_pricing.get("unitListPrice") and qty and not line_pricing.get("extendedListPrice"):
        line_pricing["extendedListPrice_calculated"] = float(line_pricing["unitListPrice"]) * float(qty)
    
    if line_pricing.get("unitNetPrice") and qty and not line_pricing.get("extendedNetPrice"):
        line_pricing["extendedNetPrice_calculated"] = float(line_pricing["unitNetPrice"]) * float(qty)
    
    # Calculate discount if missing
    if line_pricing.get("unitListPrice") and line_pricing.get("unitNetPrice") and not line_pricing.get("discountPercent"):
        try:
            ulp = float(line_pricing["unitListPrice"])
            unp = float(line_pricing["unitNetPrice"])
            if ulp > 0:
                line_pricing["discountPercent_calculated"] = ((ulp - unp) / ulp) * 100
        except (ValueError, TypeError, ZeroDivisionError):
            pass
    
    return line_pricing


def validate_all_pricing_attributes(config: AppConfig, api_data: Dict[str, Any], excel_data: Dict[str, Any], results: List[FieldResult]) -> None:
    """Validate ALL pricing attributes with extreme accuracy."""
    
    # Extract all pricing from API
    api_pricing = extract_all_pricing_attributes(api_data)
    
    # Extract pricing from Excel
    excel_pricing = {
        "quoteListPrice_t_c": excel_data.get("quoteListPrice_t_c"),
        "quoteNetPrice_t_c": excel_data.get("quoteNetPrice_t_c"),
        "quoteCurrentDiscount_t_c": excel_data.get("quoteCurrentDiscount_t_c"),
    }
    
    # Validate each pricing attribute
    pricing_attributes = [
        ("quoteListPrice_t_c", "List Grand Total", True),
        ("quoteNetPrice_t_c", "Net Grand Total", True),
        ("quoteCurrentDiscount_t_c", "Total Discount %", False),
        ("extNetPrice_t_c", "Extended Net Price", True),
        ("netPrice_t_c", "Net Price", True),
        ("quoteDesiredNetPrice_t_c", "Desired Net Price", True),
        ("quoteDesiredDiscount_t_c", "Desired Discount %", False),
    ]
    
    for attr, label, is_currency in pricing_attributes:
        api_val = api_pricing.get(attr)
        excel_val = excel_pricing.get(attr)
        
        if api_val is not None:
            # Parse values
            if is_currency:
                api_parsed = parse_currency(str(api_val) if not isinstance(api_val, (int, float)) else api_val)
                excel_parsed = excel_val
            else:
                try:
                    api_parsed = float(api_val) if api_val is not None else None
                    excel_parsed = float(excel_val) if excel_val is not None else None
                except (ValueError, TypeError):
                    api_parsed = None
                    excel_parsed = None
            
            if api_parsed is not None:
                tolerance = config.validation_rules.numeric_tolerance if is_currency else config.validation_rules.percentage_tolerance
                match = floats_match(api_parsed, excel_parsed, tolerance) if excel_parsed is not None else False
                
                results.append(
                    FieldResult(
                        field_name=attr,
                        section="Pricing",
                        expected=round(api_parsed, 2) if api_parsed else None,
                        found=round(excel_parsed, 2) if excel_parsed else None,
                        match=match,
                        message=f"API: {api_parsed}, Excel: {excel_parsed}" if not match else None,
                    )
                )


def validate_line_item_pricing_comprehensive(config: AppConfig, api_data: Dict[str, Any], excel_data: Dict[str, Any], results: List[FieldResult]) -> None:
    """Comprehensive line item pricing validation with ALL attributes."""
    from validator import _get_api_lines
    
    excel_lines = excel_data.get("line_items", [])
    api_lines = _get_api_lines(api_data)
    
    if not excel_lines or not api_lines:
        return
    
    # Index Excel lines by part number
    excel_by_part: Dict[str, Dict[str, Any]] = {}
    for line in excel_lines:
        part = line.get("partNumber")
        if part:
            excel_by_part[str(part).strip()] = line
    
    # Validate each API line item
    for api_line in api_lines:
        api_part = (
            api_line.get("_part_number") or 
            api_line.get("_part_display_number") or 
            api_line.get("_line_display_name") or
            ""
        )
        excel_line = excel_by_part.get(str(api_part)) if api_part else None
        
        if not excel_line:
            continue
        
        # Extract all pricing from both
        api_pricing = extract_line_item_pricing(api_line)
        excel_pricing = {
            "quantity": excel_line.get("quantity"),
            "unitListPrice": excel_line.get("unitListPrice"),
            "unitNetPrice": excel_line.get("unitNetPrice"),
            "extendedListPrice": excel_line.get("extendedListPrice"),
            "extendedNetPrice": excel_line.get("extendedNetPrice"),
            "discountPercent": excel_line.get("discountPercent"),
        }
        
        # Validate each pricing attribute
        pricing_checks = [
            ("quantity", "Quantity", False),
            ("unitListPrice", "Unit List Price", True),
            ("unitNetPrice", "Unit Net Price", True),
            ("extendedListPrice", "Extended List Price", True),
            ("extendedNetPrice", "Extended Net Price", True),
            ("discountPercent", "Discount %", False),
        ]
        
        for attr, label, is_currency in pricing_checks:
            api_val = api_pricing.get(attr)
            excel_val = excel_pricing.get(attr)
            
            if api_val is not None or excel_val is not None:
                if is_currency:
                    api_parsed = parse_currency(str(api_val) if api_val is not None and not isinstance(api_val, (int, float)) else api_val)
                    excel_parsed = excel_val
                    tolerance = config.validation_rules.numeric_tolerance
                else:
                    try:
                        api_parsed = float(api_val) if api_val is not None else None
                        excel_parsed = float(excel_val) if excel_val is not None else None
                        tolerance = config.validation_rules.percentage_tolerance if attr == "discountPercent" else 0.0
                    except (ValueError, TypeError):
                        api_parsed = None
                        excel_parsed = None
                        tolerance = 0.0
                
                match = floats_match(api_parsed, excel_parsed, tolerance) if (api_parsed is not None and excel_parsed is not None) else False
                
                results.append(
                    FieldResult(
                        field_name=f"{attr}_{api_part}",
                        section="Line Pricing",
                        expected=round(api_parsed, 2) if api_parsed is not None else None,
                        found=round(excel_parsed, 2) if excel_parsed is not None else None,
                        match=match,
                    )
                )
        
        # CRITICAL: Validate calculations
        # Extended List = Quantity × Unit List
        if api_pricing.get("quantity") and api_pricing.get("unitListPrice"):
            qty = float(api_pricing["quantity"])
            ulp = float(api_pricing["unitListPrice"])
            calculated_ext_list = qty * ulp
            actual_ext_list = api_pricing.get("extendedListPrice") or excel_pricing.get("extendedListPrice")
            
            if actual_ext_list:
                actual_ext_list = parse_currency(actual_ext_list) if isinstance(actual_ext_list, str) else float(actual_ext_list)
                match = floats_match(calculated_ext_list, actual_ext_list, config.validation_rules.numeric_tolerance)
                
                results.append(
                    FieldResult(
                        field_name=f"calc_ext_list_{api_part}",
                        section="Calculations",
                        expected=round(calculated_ext_list, 2),
                        found=round(actual_ext_list, 2) if actual_ext_list else None,
                        match=match,
                        message=f"Qty({qty}) × Unit List({ulp}) = {calculated_ext_list:.2f}" if not match else None,
                    )
                )
        
        # Extended Net = Quantity × Unit Net
        if api_pricing.get("quantity") and api_pricing.get("unitNetPrice"):
            qty = float(api_pricing["quantity"])
            unp = float(api_pricing["unitNetPrice"])
            calculated_ext_net = qty * unp
            actual_ext_net = api_pricing.get("extendedNetPrice") or excel_pricing.get("extendedNetPrice")
            
            if actual_ext_net:
                actual_ext_net = parse_currency(actual_ext_net) if isinstance(actual_ext_net, str) else float(actual_ext_net)
                match = floats_match(calculated_ext_net, actual_ext_net, config.validation_rules.numeric_tolerance)
                
                results.append(
                    FieldResult(
                        field_name=f"calc_ext_net_{api_part}",
                        section="Calculations",
                        expected=round(calculated_ext_net, 2),
                        found=round(actual_ext_net, 2) if actual_ext_net else None,
                        match=match,
                        message=f"Qty({qty}) × Unit Net({unp}) = {calculated_ext_net:.2f}" if not match else None,
                    )
                )


def main():
    parser = argparse.ArgumentParser(description="Comprehensive Pricing Validation")
    parser.add_argument("--excel", required=True, help="Excel file path")
    parser.add_argument("--json", default="response.json", help="API JSON response file")
    args = parser.parse_args()
    
    # Load data
    excel_path = Path(args.excel)
    json_path = Path(args.json)
    
    if not excel_path.exists():
        print(f"ERROR: Excel file not found: {excel_path}")
        sys.exit(1)
    
    if not json_path.exists():
        print(f"ERROR: JSON file not found: {json_path}")
        sys.exit(1)
    
    print("="*60)
    print("COMPREHENSIVE PRICING VALIDATION")
    print("="*60)
    
    # Parse Excel
    print("\n[STEP 1] Parsing Excel...")
    with open(excel_path, "rb") as f:
        excel_bytes = f.read()
    excel_data = extract_excel_data(excel_bytes)
    excel_data["_filename"] = excel_path.name
    print(f"[OK] Parsed Excel: {excel_path.name}")
    
    # Load API data
    print("\n[STEP 2] Loading API data...")
    with open(json_path, "r", encoding="utf-8") as f:
        api_data = json.load(f)
    print(f"[OK] Loaded API data from: {json_path}")
    
    # Extract and display all pricing attributes
    print("\n[STEP 3] Extracting ALL pricing attributes...")
    api_pricing = extract_all_pricing_attributes(api_data)
    print(f"\nAPI Pricing Attributes Found ({len(api_pricing)}):")
    for key, val in sorted(api_pricing.items()):
        if val is not None:
            print(f"  {key}: {val}")
    
    # Run comprehensive validation
    print("\n[STEP 4] Running comprehensive validation...")
    config = AppConfig.from_env_and_file()
    results: List[FieldResult] = []
    
    # Standard validation
    standard_result = validate_quote(config, api_data, excel_data, transaction_id=None, pdf_filename=excel_path.name)
    results.extend(standard_result.details)
    
    # Additional comprehensive pricing validation
    validate_all_pricing_attributes(config, api_data, excel_data, results)
    validate_line_item_pricing_comprehensive(config, api_data, excel_data, results)
    
    # Summary
    matches = sum(1 for r in results if r.match)
    mismatches = len(results) - matches
    overall = "PASSED" if mismatches == 0 else "FAILED"
    
    print(f"\n{'='*60}")
    print(f"VALIDATION RESULTS")
    print(f"{'='*60}")
    print(f"Overall Status: {overall}")
    print(f"Total Checks: {len(results)}")
    print(f"Matches: {matches}")
    print(f"Mismatches: {mismatches}")
    
    # Group by section
    by_section = {}
    for r in results:
        section = r.section
        if section not in by_section:
            by_section[section] = []
        by_section[section].append(r)
    
    print(f"\nResults by Section:")
    for section, section_results in sorted(by_section.items()):
        section_matches = sum(1 for r in section_results if r.match)
        print(f"  {section}: {section_matches}/{len(section_results)} passed")
    
    # Show critical pricing failures
    pricing_failures = [r for r in results if not r.match and r.section in ["Pricing", "Calculations", "Summary"]]
    if pricing_failures:
        print(f"\n{'='*60}")
        print("CRITICAL PRICING MISMATCHES:")
        print(f"{'='*60}")
        for r in pricing_failures:
            print(f"\n[FAIL] {r.section}/{r.field_name}:")
            print(f"  Expected: {r.expected}")
            print(f"  Found:    {r.found}")
            if r.message:
                print(f"  {r.message}")
    
    # Save results
    output_file = f"{excel_path.stem}_comprehensive_validation.json"
    serializable = {
        "overall_status": overall,
        "total_checked": len(results),
        "matches": matches,
        "mismatches": mismatches,
        "excel_filename": excel_path.name,
        "api_pricing_attributes": api_pricing,
        "details": [
            {
                "field_name": d.field_name,
                "section": d.section,
                "expected": d.expected,
                "found": d.found,
                "match": d.match,
                "message": d.message,
            }
            for d in results
        ]
    }
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2, ensure_ascii=False)
    
    print(f"\n[OK] Comprehensive validation results saved to: {output_file}")
    print("\n" + "="*60)
    print("COMPLETE!")
    print("="*60)


if __name__ == "__main__":
    import argparse
    main()

