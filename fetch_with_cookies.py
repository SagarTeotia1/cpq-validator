"""Helper script to fetch API data using browser cookies for SSO authentication"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse, parse_qs

import requests

from config import AppConfig
from excel_parser import extract_excel_data
from validator import validate_quote


def extract_transaction_id_from_url(url: str) -> Optional[str]:
    """Extract transaction ID from the URL query parameters."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    return params.get('id', [None])[0]


def fetch_with_cookies(transaction_id: str, base_url: str, cookies: Dict[str, str]) -> Dict[str, Any]:
    """Fetch API data using provided cookies."""
    session = requests.Session()
    
    # Set cookies
    for name, value in cookies.items():
        session.cookies.set(name, value)
    
    # Set headers
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    })
    
    # Fetch transaction data
    api_url = f"{base_url}/commerceDocumentsUcpqStandardCommerceProcessTransaction/{transaction_id}"
    print(f"Fetching: {api_url}")
    
    response = session.get(api_url, timeout=30)
    
    if response.status_code == 200:
        api_data = response.json()
        
        # Also fetch transaction lines
        try:
            lines_url = f"{base_url}/commerceDocumentsUcpqStandardCommerceProcessTransaction/{transaction_id}/transactionLine"
            lines_response = session.get(lines_url, timeout=30)
            if lines_response.status_code == 200:
                api_data["transactionLine"] = lines_response.json()
        except Exception:
            pass
        
        return api_data
    else:
        print(f"Error: Status {response.status_code}")
        print(f"Response: {response.text[:500]}")
        raise Exception(f"API call failed: {response.status_code}")


def main():
    print("="*60)
    print("CPQ API Data Fetcher with Browser Cookies")
    print("="*60)
    print("\nThis script uses cookies from your browser to authenticate.")
    print("\nTo get cookies:")
    print("1. Open the web UI URL in your browser and log in")
    print("2. Open Developer Tools (F12)")
    print("3. Go to Network tab")
    print("4. Refresh the page or navigate to the quote")
    print("5. Find any API request (look for 'rest/v16' in URL)")
    print("6. Click on it, then go to 'Headers' tab")
    print("7. Find 'Cookie:' header and copy all cookie values")
    print("\nOr use a browser extension to export cookies")
    print("="*60)
    
    # Direct REST API URL
    url = "https://netappinctest3.bigmachines.com/rest/v16/commerceDocumentsUcpqStandardCommerceProcessTransaction/481931730"
    
    # Extract transaction ID from REST API URL
    if "/commerceDocumentsUcpqStandardCommerceProcessTransaction/" in url:
        parts = url.split("/commerceDocumentsUcpqStandardCommerceProcessTransaction/")
        transaction_id = parts[1].split("?")[0].split("/")[0] if len(parts) > 1 else "481931730"
    else:
        transaction_id = extract_transaction_id_from_url(url) or "481931730"
    
    parsed = urlparse(url)
    base_url = f"{parsed.scheme}://{parsed.netloc}/rest/v16"
    
    print(f"\nTransaction ID: {transaction_id}")
    print(f"Base URL: {base_url}")
    
    # Option 1: Get cookies from user input
    print("\n" + "-"*60)
    print("Option 1: Enter cookies manually")
    print("-"*60)
    cookie_string = input("\nPaste the Cookie header value (or press Enter to skip): ").strip()
    
    cookies = {}
    if cookie_string:
        # Parse cookie string (format: "name1=value1; name2=value2")
        for cookie_pair in cookie_string.split(';'):
            if '=' in cookie_pair:
                name, value = cookie_pair.strip().split('=', 1)
                cookies[name] = value
        print(f"Parsed {len(cookies)} cookies")
    
    # Option 2: Load from file
    if not cookies:
        print("\n" + "-"*60)
        print("Option 2: Load cookies from file")
        print("-"*60)
        cookie_file = input("Enter path to cookies JSON file (or press Enter to skip): ").strip()
        if cookie_file and Path(cookie_file).exists():
            with open(cookie_file, 'r') as f:
                cookies = json.load(f)
            print(f"Loaded {len(cookies)} cookies from file")
    
    if not cookies:
        print("\nNo cookies provided. Cannot proceed.")
        print("\nExample cookie format (JSON file):")
        print('{"JSESSIONID": "ABC123...", "X-Oracle-OCI-LBCookie": "xyz..."}')
        sys.exit(1)
    
    # Fetch data
    print("\n" + "="*60)
    print("Fetching API Data")
    print("="*60)
    try:
        api_data = fetch_with_cookies(transaction_id, base_url, cookies)
        
        # Add metadata
        api_data["_url"] = url
        api_data["_timestamp"] = __import__("datetime").datetime.now().isoformat()
        api_data["_transaction_id"] = transaction_id
        
        # Save response
        print("\nSaving API response...")
        with open("api_response_structured.json", "w", encoding="utf-8") as f:
            structured = {
                "metadata": {
                    "source_url": url,
                    "timestamp": api_data["_timestamp"],
                    "transaction_id": transaction_id
                },
                "quote_data": {
                    "quote_number": api_data.get("quoteNumber_t_c"),
                    "transaction_id": api_data.get("transactionID_t"),
                    "quote_name": api_data.get("quoteNameTextArea_t_c"),
                    "status": api_data.get("quoteStatus_t_c"),
                    "net_price": api_data.get("quoteNetPrice_t_c"),
                },
                "line_items": api_data.get("transactionLine", {}).get("items", []),
                "raw_response": api_data
            }
            json.dump(structured, f, indent=2, ensure_ascii=False)
        print("✓ Saved to: api_response_structured.json")
        
        # Parse Excel files
        print("\n" + "="*60)
        print("Parsing Excel Files")
        print("="*60)
        
        excel_files = list(Path(".").glob("*.xls*"))
        excel_files = [f for f in excel_files if not f.name.startswith("Validated_") and not f.name.startswith("Unknown")]
        
        if excel_files:
            excel_data_list = []
            for excel_file in excel_files:
                print(f"\nParsing: {excel_file.name}")
                try:
                    with open(excel_file, "rb") as f:
                        excel_bytes = f.read()
                    excel_data = extract_excel_data(excel_bytes)
                    excel_data["_filename"] = excel_file.name
                    excel_data_list.append(excel_data)
                    print(f"  ✓ Extracted {len(excel_data.get('line_items', []))} line items")
                except Exception as e:
                    print(f"  ✗ Error: {e}")
            
            if excel_data_list:
                # Save Excel data
                with open("excel_data_parsed.json", "w", encoding="utf-8") as f:
                    json.dump(excel_data_list, f, indent=2, ensure_ascii=False)
                print(f"\n✓ Excel data saved to: excel_data_parsed.json")
                
                # Validate
                print("\n" + "="*60)
                print("Validating")
                print("="*60)
                
                config = AppConfig.from_env_and_file()
                from validator import validate_quote
                
                for excel_data in excel_data_list:
                    print(f"\nValidating: {excel_data['_filename']}")
                    result = validate_quote(
                        config,
                        api_data,
                        excel_data,
                        transaction_id=transaction_id,
                        pdf_filename=excel_data["_filename"]
                    )
                    print(f"Status: {result.overall_status}")
                    print(f"Matches: {result.matches}/{result.total_checked}")
        else:
            print("No Excel files found")
        
        print("\n" + "="*60)
        print("COMPLETE!")
        print("="*60)
        
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

