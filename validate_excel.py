"""Simple script to validate Excel file against API data"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict
from getpass import getpass

from config import AppConfig
from excel_parser import extract_excel_data
from validator import validate_quote
from api_client import CPQClient, CPQAuthError, CPQConnectionError, CPQNotFoundError, CPQServerError


def main():
    parser = argparse.ArgumentParser(description="Validate Excel file against CPQ API")
    parser.add_argument("--excel", required=True, help="Path to Excel file (.xls or .xlsx)")
    parser.add_argument("--transaction-id", help="Transaction ID (optional, will try to extract from Excel)")
    parser.add_argument("--base-url", default="https://netappinctest3.bigmachines.com/rest/v16", 
                       help="Base URL for API (default: https://netappinctest3.bigmachines.com/rest/v16)")
    args = parser.parse_args()
    
    # Check Excel file exists
    excel_path = Path(args.excel)
    if not excel_path.exists():
        print(f"ERROR: Excel file not found: {excel_path}")
        sys.exit(1)
    
    print("="*60)
    print("CPQ Excel Validator")
    print("="*60)
    
    # Step 1: Parse Excel file
    print("\n[STEP 1] Parsing Excel file...")
    try:
        with open(excel_path, "rb") as f:
            excel_bytes = f.read()
        excel_data = extract_excel_data(excel_bytes)
        excel_data["_filename"] = excel_path.name
        print(f"[OK] Parsed Excel file: {excel_path.name}")
        print(f"  - Quote Number: {excel_data.get('quoteNumber_t_c', 'N/A')}")
        print(f"  - Quote Name: {excel_data.get('quoteNameTextArea_t_c', 'N/A')}")
        print(f"  - Net Price: {excel_data.get('quoteNetPrice_t_c', 'N/A')}")
        print(f"  - Line Items: {len(excel_data.get('line_items', []))}")
    except Exception as e:
        print(f"[ERROR] Failed to parse Excel file: {e}")
        sys.exit(1)
    
    # Step 2: Get transaction ID
    transaction_id = args.transaction_id
    if not transaction_id:
        # Try to extract from Excel filename or data
        # Filename format: 174044_12-Nov-2025_... -> quote 174044
        # Or look for Config# in Excel data
        quote_num = excel_data.get('quoteNumber_t_c')
        if quote_num:
            print(f"\n[INFO] Found Quote Number in Excel: {quote_num}")
            print("[INFO] You may need to provide Transaction ID manually")
            print("[INFO] Transaction ID is usually different from Quote Number")
        transaction_id = input("\nEnter Transaction ID (or press Enter to skip API fetch): ").strip()
        if not transaction_id:
            print("\n[INFO] No Transaction ID provided. Will use existing response.json if available.")
    
    # Step 3: Fetch API data
    api_data = None
    
    if transaction_id:
        print(f"\n[STEP 2] Fetching API data for Transaction ID: {transaction_id}")
        
        # Get credentials
        print("\nEnter CPQ API credentials:")
        username = input("Username: ").strip()
        if not username:
            print("[WARNING] No username provided. Will try to use existing response.json")
        else:
            password = getpass("Password: ")
            
            # Configure API
            config = AppConfig.from_env_and_file()
            config.api.base_url = args.base_url
            config.api.username = username
            config.api.password = password
            
            # Try to fetch
            try:
                client = CPQClient(config)
                print(f"\n[INFO] Attempting to fetch from: {config.api.base_url}")
                api_data = client.fetch_transaction_data(transaction_id)
                
                # Also fetch transaction lines
                try:
                    lines = client.fetch_transaction_lines(transaction_id)
                    api_data["transactionLine"] = lines
                    print(f"[OK] Fetched transaction lines")
                except Exception:
                    pass
                
                print(f"[OK] Successfully fetched API data!")
                
                # Save for future use
                with open("response.json", "w", encoding="utf-8") as f:
                    json.dump(api_data, f, indent=2, ensure_ascii=False)
                print(f"[OK] Saved API response to: response.json")
                
            except CPQAuthError as e:
                print(f"[ERROR] Authentication failed: {e}")
                print("[INFO] This API requires SSO (Single Sign-On).")
                print("[INFO] Will try to use existing response.json if available...")
            except (CPQNotFoundError, CPQConnectionError, CPQServerError) as e:
                print(f"[ERROR] Failed to fetch API data: {e}")
                print("[INFO] Will try to use existing response.json if available...")
            except Exception as e:
                print(f"[ERROR] Unexpected error: {e}")
                print("[INFO] Will try to use existing response.json if available...")
    
    # Step 4: Try to use existing response.json
    if api_data is None:
        response_file = Path("response.json")
        if response_file.exists():
            print(f"\n[STEP 2] Using existing API response from: response.json")
            try:
                with open(response_file, "r", encoding="utf-8") as f:
                    api_data = json.load(f)
                print(f"[OK] Loaded existing API response")
                
                # Extract transaction ID from response if not provided
                if not transaction_id:
                    transaction_id = (
                        api_data.get("transactionID_t") or 
                        api_data.get("quoteTransactionID_t_c") or 
                        api_data.get("bs_id") or
                        "unknown"
                    )
                    print(f"[INFO] Using Transaction ID from response: {transaction_id}")
            except Exception as e:
                print(f"[ERROR] Failed to load response.json: {e}")
                sys.exit(1)
        else:
            print("\n[ERROR] No API data available and no response.json found.")
            print("[INFO] Please:")
            print("  1. Provide Transaction ID and credentials to fetch new data, OR")
            print("  2. Save API response as response.json in the current directory")
            sys.exit(1)
    
    # Step 5: Validate
    print("\n[STEP 3] Validating Excel against API data...")
    print("="*60)
    
    config = AppConfig.from_env_and_file()
    
    try:
        result = validate_quote(
            config,
            api_data,
            excel_data,
            transaction_id=str(transaction_id) if transaction_id else None,
            pdf_filename=excel_path.name
        )
        
        # Print results
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
        
        # Save results
        output_file = f"{excel_path.stem}_validation_results.json"
        serializable = {
            "overall_status": result.overall_status,
            "total_checked": result.total_checked,
            "matches": result.matches,
            "mismatches": result.mismatches,
            "transaction_id": result.transaction_id,
            "excel_filename": excel_path.name,
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
        }
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(serializable, f, indent=2, ensure_ascii=False)
        
        print(f"\n[OK] Validation results saved to: {output_file}")
        print("\n" + "="*60)
        print("COMPLETE!")
        print("="*60)
        
    except Exception as e:
        print(f"[ERROR] Validation failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

