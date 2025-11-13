"""Script to use existing response.json file and compare with Excel files"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

from config import AppConfig
from excel_parser import extract_excel_data
from validator import validate_quote


def main():
    print("="*60)
    print("Using Existing API Response")
    print("="*60)
    
    # Check if response.json exists
    response_file = Path("response.json")
    if not response_file.exists():
        print("ERROR: response.json not found!")
        print("Please ensure response.json exists in the current directory.")
        sys.exit(1)
    
    print(f"Loading API response from: {response_file}")
    
    # Load API data
    try:
        with open(response_file, "r", encoding="utf-8") as f:
            api_data = json.load(f)
        print(f"[OK] Loaded API response successfully")
        print(f"  Keys in response: {len(api_data)} fields")
    except Exception as e:
        print(f"ERROR loading response.json: {e}")
        sys.exit(1)
    
    # Extract transaction ID
    transaction_id = (
        api_data.get("transactionID_t") or 
        api_data.get("quoteTransactionID_t_c") or 
        api_data.get("bs_id") or
        api_data.get("_id") or
        "unknown"
    )
    print(f"Transaction ID: {transaction_id}")
    
    # Try to load transaction lines if available
    if "transactionLine" not in api_data:
        # Try to load from a separate file
        lines_file = Path("response_lines.json")
        if lines_file.exists():
            try:
                with open(lines_file, "r", encoding="utf-8") as f:
                    lines_data = json.load(f)
                    api_data["transactionLine"] = lines_data
                    print(f"[OK] Loaded transaction lines from: {lines_file}")
            except Exception:
                pass
    
    # Save structured response
    print("\n" + "="*60)
    print("Saving Structured API Response")
    print("="*60)
    
    structured_data = {
        "metadata": {
            "source": "response.json (existing file)",
            "timestamp": __import__("datetime").datetime.now().isoformat(),
            "transaction_id": str(transaction_id)
        },
        "quote_data": {
            "quote_number": api_data.get("quoteNumber_t_c") or api_data.get("_document_number"),
            "transaction_id": transaction_id,
            "quote_name": api_data.get("quoteNameTextArea_t_c") or api_data.get("transactionName_t"),
            "status": api_data.get("quoteStatus_t_c") or api_data.get("status_t"),
            "created_date": api_data.get("createdDate_t"),
            "expires_date": api_data.get("expiresOnDate_t_c"),
            "currency": api_data.get("currency_t"),
            "price_list": api_data.get("priceList_t_c"),
            "list_price": api_data.get("quoteListPrice_t_c") or api_data.get("totalOneTimeListAmount_t"),
            "net_price": api_data.get("quoteNetPrice_t_c") or api_data.get("totalOneTimeNetAmount_t"),
            "discount": api_data.get("quoteCurrentDiscount_t_c") or api_data.get("transactionTotalDiscountPercent_t"),
            "incoterm": api_data.get("incoterm_t_c"),
            "payment_terms": api_data.get("paymentTerms_t_c"),
            "order_type": api_data.get("orderType_t_c"),
        },
        "line_items": [],
        "raw_response": api_data
    }
    
    # Extract line items
    lines_container = api_data.get("transactionLine") or {}
    if isinstance(lines_container, dict) and "items" in lines_container:
        structured_data["line_items"] = lines_container.get("items", [])
        print(f"  Found {len(structured_data['line_items'])} line items")
    elif isinstance(api_data.get("items"), list):
        structured_data["line_items"] = api_data.get("items", [])
        print(f"  Found {len(structured_data['line_items'])} line items")
    
    with open("api_response_structured.json", "w", encoding="utf-8") as f:
        json.dump(structured_data, f, indent=2, ensure_ascii=False)
    print(f"[OK] Saved structured response to: api_response_structured.json")
    
    # Parse Excel files
    print("\n" + "="*60)
    print("Parsing Excel Files")
    print("="*60)
    
    excel_files = list(Path(".").glob("*.xls*"))
    excel_files = [f for f in excel_files if not f.name.startswith("Validated_") and not f.name.startswith("Unknown")]
    
    if not excel_files:
        print("No Excel files found in current directory")
        print("\nAvailable files:")
        for f in Path(".").glob("*"):
            if f.is_file():
                print(f"  - {f.name}")
        sys.exit(0)
    
    excel_data_list = []
    for excel_file in excel_files:
        print(f"\nParsing: {excel_file.name}")
        try:
            with open(excel_file, "rb") as f:
                excel_bytes = f.read()
            excel_data = extract_excel_data(excel_bytes)
            excel_data["_filename"] = excel_file.name
            excel_data_list.append(excel_data)
            print(f"  [OK] Extracted {len(excel_data.get('line_items', []))} line items")
        except Exception as e:
            print(f"  [ERROR] Error parsing {excel_file.name}: {e}")
            import traceback
            traceback.print_exc()
    
    if not excel_data_list:
        print("No Excel files could be parsed successfully")
        sys.exit(1)
    
    # Save Excel data
    with open("excel_data_parsed.json", "w", encoding="utf-8") as f:
        json.dump(excel_data_list, f, indent=2, ensure_ascii=False)
    print(f"\n[OK] Excel data saved to: excel_data_parsed.json")
    
    # Compare and Validate
    print("\n" + "="*60)
    print("Comparing and Validating")
    print("="*60)
    
    config = AppConfig.from_env_and_file()
    comparison_results = []
    
    for excel_data in excel_data_list:
        print(f"\n{'='*60}")
        print(f"Validating: {excel_data['_filename']}")
        print(f"{'='*60}")
        
        try:
            result = validate_quote(
                config,
                api_data,
                excel_data,
                transaction_id=str(transaction_id),
                pdf_filename=excel_data["_filename"]
            )
            
            comparison_results.append({
                "filename": excel_data["_filename"],
                "result": result
            })
            
            # Print summary
            print(f"\nValidation Status: {result.overall_status}")
            print(f"Total Fields Checked: {result.total_checked}")
            print(f"Matches: {result.matches}")
            print(f"Mismatches: {result.mismatches}")
            
            # Print details
            print("\nDetailed Results:")
            print("-" * 60)
            for detail in result.details:
                status = "[OK]" if detail.match else "[FAIL]"
                print(f"{status} {detail.section}/{detail.field_name}:")
                print(f"    Expected: {detail.expected}")
                print(f"    Found:    {detail.found}")
                if detail.message:
                    print(f"    Message:  {detail.message}")
                print()
                
        except Exception as e:
            print(f"Error during validation: {e}")
            import traceback
            traceback.print_exc()
    
    # Save comparison results
    print("\n" + "="*60)
    print("Saving Comparison Results")
    print("="*60)
    
    serializable_results = []
    for comp in comparison_results:
        result = comp["result"]
        serializable_results.append({
            "filename": comp["filename"],
            "overall_status": result.overall_status,
            "total_checked": result.total_checked,
            "matches": result.matches,
            "mismatches": result.mismatches,
            "transaction_id": result.transaction_id,
            "details": [
                {
                    "field_name": d.field_name,
                    "section": d.section,
                    "expected": d.expected,
                    "found": d.found,
                    "match": d.match,
                    "message": d.message,
                }
                for d in result.details
            ]
        })
    
    with open("comparison_results.json", "w", encoding="utf-8") as f:
        json.dump(serializable_results, f, indent=2, ensure_ascii=False)
    
    print(f"[OK] Comparison results saved to: comparison_results.json")
    print("\n" + "="*60)
    print("COMPLETE!")
    print("="*60)
    print("\nGenerated files:")
    print("  1. api_response_structured.json - Well-structured API response")
    print("  2. excel_data_parsed.json - Parsed Excel data")
    print("  3. comparison_results.json - Validation comparison results")


if __name__ == "__main__":
    main()

