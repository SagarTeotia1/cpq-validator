from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse, parse_qs

import requests
from getpass import getpass

from config import AppConfig
from excel_parser import extract_excel_data
from validator import validate_quote
from api_client import CPQClient, CPQNotFoundError, CPQAuthError, CPQConnectionError, CPQServerError


def extract_transaction_id_from_url(url: str) -> Optional[str]:
    """Extract transaction ID from the URL query parameters."""
    parsed = urlparse(url)
    params = parse_qs(parsed.query)
    return params.get('id', [None])[0]


def fetch_api_data_via_rest_api(transaction_id: str, config: AppConfig) -> Dict[str, Any]:
    """Fetch data using the REST API endpoint (preferred method)."""
    # Verify credentials are available
    if not config.api.bearer_token and not (config.api.username and config.api.password):
        raise CPQAuthError("No authentication credentials available")
    
    print(f"  Creating API client with base URL: {config.api.base_url}")
    print(f"  Auth method: {'Bearer Token' if config.api.bearer_token else 'Basic Auth'}")
    if config.api.username:
        print(f"  Username: {config.api.username}")
    
    # Create a new client instance to ensure fresh session
    client = CPQClient(config)
    
    # Verify the session has auth configured
    if not config.api.bearer_token:
        if not client.session.auth:
            raise CPQAuthError("Session authentication not configured properly")
        print(f"  ✓ Session auth configured: {client.session.auth[0]}")
    
    try:
        print(f"  Fetching transaction data for ID: {transaction_id}")
        api_data: Dict[str, Any] = client.fetch_transaction_data(transaction_id)
        print(f"  ✓ Successfully fetched transaction data")
        
        # Also fetch transaction lines
        try:
            print(f"  Fetching transaction lines...")
            lines = client.fetch_transaction_lines(transaction_id)
            api_data["transactionLine"] = lines
            print(f"  ✓ Successfully fetched transaction lines")
        except Exception as e:
            print(f"  ⚠ Could not fetch transaction lines: {e}")
            pass
        return api_data
    except CPQAuthError as e:
        print(f"  ✗ Authentication failed: {e}")
        print(f"  Response details: Check if username/password are correct")
        raise
    except (CPQNotFoundError, CPQConnectionError, CPQServerError) as e:
        print(f"  ✗ REST API error: {e}")
        raise


def authenticate_via_sso(base_url: str, username: str, password: str) -> requests.Session:
    """Authenticate via SSO and return a session with cookies."""
    session = requests.Session()
    
    # Set headers to mimic a browser
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    })
    
    # Try to access the login page first to get SSO redirect
    print("  Attempting SSO authentication...")
    print("  Note: SSO authentication may require browser-based login.")
    print("  Please ensure you are logged into the web UI in your browser.")
    
    # For SSO, we typically need to:
    # 1. Access the web UI URL (which redirects to SSO)
    # 2. Follow redirects to get authenticated
    # 3. Extract cookies from the authenticated session
    
    # Since SSO requires browser interaction, we'll try to use the web UI URL
    # and extract any session cookies that might be set
    return session


def fetch_api_with_sso_session(transaction_id: str, base_url: str, web_ui_url: str, config: AppConfig) -> Dict[str, Any]:
    """Fetch API data using SSO session cookies."""
    session = requests.Session()
    
    # Set headers to mimic a browser
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/html, */*",
        "Referer": web_ui_url,
    })
    
    # Check if web_ui_url is already a REST API URL
    api_url = f"{base_url}/commerceDocumentsUcpqStandardCommerceProcessTransaction/{transaction_id}"
    
    if "/rest/v16/commerceDocumentsUcpqStandardCommerceProcessTransaction/" in web_ui_url:
        # It's already a REST API URL, try accessing it directly
        print("  Accessing REST API URL directly to establish session...")
        try:
            api_response = session.get(web_ui_url, timeout=config.api.timeout, allow_redirects=True)
            print(f"  API response status: {api_response.status_code}")
            print(f"  Cookies received: {len(session.cookies)} cookies")
            
            if api_response.status_code == 200:
                print("  [OK] Successfully fetched data using SSO session!")
                api_data = api_response.json()
                
                # Also fetch transaction lines
                try:
                    lines_url = f"{base_url}/commerceDocumentsUcpqStandardCommerceProcessTransaction/{transaction_id}/transactionLine"
                    lines_response = session.get(lines_url, timeout=config.api.timeout)
                    if lines_response.status_code == 200:
                        api_data["transactionLine"] = lines_response.json()
                except Exception:
                    pass
                
                return api_data
        except Exception as e:
            print(f"  Direct access failed: {e}")
            print("  Will try accessing web UI first...")
    
    # First, try to get session by accessing the web UI or a login page
    print("  Accessing web UI/login page to establish session...")
    try:
        # Try accessing a base URL first to get cookies
        base_domain = web_ui_url.split("/rest/")[0] if "/rest/" in web_ui_url else web_ui_url.rsplit("/", 1)[0]
        web_response = session.get(base_domain, timeout=config.api.timeout, allow_redirects=True)
        print(f"  Base URL response status: {web_response.status_code}")
        print(f"  Cookies received: {len(session.cookies)} cookies")
        
        # Now try to use these cookies for the API call
        print(f"  Attempting API call with session cookies...")
        
        api_response = session.get(api_url, timeout=config.api.timeout)
        
        if api_response.status_code == 200:
            print("  [OK] Successfully fetched data using SSO session!")
            api_data = api_response.json()
            
            # Also fetch transaction lines
            try:
                lines_url = f"{base_url}/commerceDocumentsUcpqStandardCommerceProcessTransaction/{transaction_id}/transactionLine"
                lines_response = session.get(lines_url, timeout=config.api.timeout)
                if lines_response.status_code == 200:
                    api_data["transactionLine"] = lines_response.json()
            except Exception:
                pass
            
            return api_data
        else:
            print(f"  API call failed with status: {api_response.status_code}")
            if api_response.status_code == 401:
                error_data = api_response.json() if api_response.headers.get('content-type', '').startswith('application/json') else {}
                error_msg = error_data.get('error_description', error_data.get('error', 'Authentication failed'))
                print(f"  Error: {error_msg}")
                raise CPQAuthError(f"SSO authentication required: {error_msg}")
            api_response.raise_for_status()
            
    except requests.exceptions.RequestException as e:
        print(f"  Error: {e}")
        raise CPQConnectionError(f"Failed to establish SSO session: {e}")


def fetch_web_ui_data(url: str, config: AppConfig) -> Dict[str, Any]:
    """Fetch data from the REST API URL.
    
    Since the API requires SSO, we'll:
    1. Try to access the API directly with session cookies
    2. Use those cookies for API calls
    """
    # Check if this is a direct REST API URL
    if "/rest/v16/commerceDocumentsUcpqStandardCommerceProcessTransaction/" in url:
        # Extract transaction ID from REST API URL
        parts = url.split("/commerceDocumentsUcpqStandardCommerceProcessTransaction/")
        if len(parts) > 1:
            transaction_id = parts[1].split("?")[0].split("/")[0]
        else:
            raise ValueError("Could not extract transaction ID from REST API URL")
        
        # Extract base URL
        parsed = urlparse(url)
        base_domain = f"{parsed.scheme}://{parsed.netloc}"
        rest_api_base = f"{base_domain}/rest/v16"
        
        print(f"Using direct REST API URL")
        print(f"Transaction ID: {transaction_id}")
        print(f"Base URL: {rest_api_base}")
        print("API requires SSO authentication (Single Sign-On)")
        print("Attempting to use session cookies for API access...")
        
        try:
            # Try to fetch using SSO session
            return fetch_api_with_sso_session(transaction_id, rest_api_base, url, config)
        except CPQAuthError as e:
            raise
    else:
        # Old web UI URL handling
        transaction_id = extract_transaction_id_from_url(url)
        
        if not transaction_id:
            raise ValueError("Could not extract transaction ID from URL")
        
        print(f"Extracted transaction ID: {transaction_id}")
        
        # Extract base URL
        parsed = urlparse(url)
        base_domain = f"{parsed.scheme}://{parsed.netloc}"
        rest_api_base = f"{base_domain}/rest/v16"
        
        print("API requires SSO authentication (Single Sign-On)")
        print("Attempting to use web UI session for API access...")
        
        try:
            # Try to fetch using SSO session
            return fetch_api_with_sso_session(transaction_id, rest_api_base, url, config)
        except CPQAuthError as e:
            print(f"\nSSO Authentication Error: {e}")
            print("\nSOLUTION:")
            print("="*60)
            print("This API requires Single Sign-On (SSO) authentication.")
            print("You need to:")
            print("1. Open the REST API URL in your browser and log in")
            print("2. Extract the session cookies from your browser")
            print("3. Use those cookies for API calls")
            print("\nAlternative: Use browser developer tools to:")
            print("- Open Network tab")
            print("- Access the REST API URL")
            print("- Find the API call in Network tab")
            print("- Copy the 'Cookie' header from that request")
            print("="*60)
            raise


def save_api_response(data: Dict[str, Any], output_path: str) -> None:
    """Save API response in a well-structured JSON format."""
    output_file = Path(output_path)
    
    # Create a well-structured format
    structured_data = {
        "metadata": {
            "source_url": data.get("_url", "N/A"),
            "response_type": data.get("_response_type", "json"),
            "timestamp": data.get("_timestamp", "N/A")
        },
        "quote_data": {
            # Header fields
            "quote_number": data.get("quoteNumber_t_c") or data.get("_document_number") or data.get("_id"),
            "transaction_id": data.get("transactionID_t") or data.get("quoteTransactionID_t_c") or data.get("bs_id"),
            "quote_name": data.get("quoteNameTextArea_t_c") or data.get("transactionName_t"),
            "status": data.get("quoteStatus_t_c") or data.get("status_t"),
            "created_date": data.get("createdDate_t"),
            "expires_date": data.get("expiresOnDate_t_c"),
            
            # Pricing fields
            "currency": data.get("currency_t"),
            "price_list": data.get("priceList_t_c"),
            "list_price": data.get("quoteListPrice_t_c") or data.get("totalOneTimeListAmount_t"),
            "net_price": data.get("quoteNetPrice_t_c") or data.get("totalOneTimeNetAmount_t") or data.get("_transaction_total"),
            "discount": data.get("quoteCurrentDiscount_t_c") or data.get("transactionTotalDiscountPercent_t"),
            
            # Additional fields
            "incoterm": data.get("incoterm_t_c"),
            "payment_terms": data.get("paymentTerms_t_c"),
            "order_type": data.get("orderType_t_c"),
        },
        "line_items": [],
        "raw_response": data  # Include full raw response for reference
    }
    
    # Extract line items if available
    lines_container = data.get("transactionLine") or {}
    if isinstance(lines_container, dict) and "items" in lines_container:
        structured_data["line_items"] = lines_container.get("items", [])
    elif isinstance(data.get("items"), list):
        structured_data["line_items"] = data.get("items", [])
    
    # Add timestamp
    from datetime import datetime
    structured_data["metadata"]["timestamp"] = datetime.now().isoformat()
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(structured_data, f, indent=2, ensure_ascii=False)
    
    print(f"API response saved to: {output_file}")


def main() -> None:
    # Direct REST API URL
    url = "https://netappinctest3.bigmachines.com/rest/v16/commerceDocumentsUcpqStandardCommerceProcessTransaction/481931730"
    
    # Load configuration
    config = AppConfig.from_env_and_file()
    
    # Prompt for credentials if needed
    if not config.api.bearer_token and not (config.api.username and config.api.password):
        print("Enter CPQ API credentials (Basic Auth). Leave blank to skip.")
        username = input("Username: ").strip()
        if username:
            password = getpass("Password: ")
            config.api.username = username
            config.api.password = password
    
    # Verify credentials are set
    if not config.api.bearer_token and not (config.api.username and config.api.password):
        print("ERROR: No authentication credentials provided!")
        print("Please set CPQ_USERNAME and CPQ_PASSWORD environment variables, or enter them when prompted.")
        sys.exit(1)
    
    print(f"Using authentication: {'Bearer Token' if config.api.bearer_token else f'Basic Auth (user: {config.api.username})'}")
    
    # Step 1: Fetch API data
    print("\n" + "="*60)
    print("STEP 1: Fetching API Response")
    print("="*60)
    
    # Extract transaction ID from URL (it's in the path for REST API URLs)
    transaction_id = "481931730"  # Direct from URL path
    if "/commerceDocumentsUcpqStandardCommerceProcessTransaction/" in url:
        # Extract from REST API URL
        parts = url.split("/commerceDocumentsUcpqStandardCommerceProcessTransaction/")
        if len(parts) > 1:
            transaction_id = parts[1].split("?")[0].split("/")[0]
    else:
        transaction_id = extract_transaction_id_from_url(url) or "166233956"
    print(f"Transaction ID: {transaction_id}")
    
    try:
        api_data = fetch_web_ui_data(url, config)
        
        # Add metadata
        api_data["_url"] = url
        api_data["_timestamp"] = __import__("datetime").datetime.now().isoformat()
        api_data["_transaction_id"] = transaction_id
        
    except Exception as e:
        print(f"Failed to fetch API data: {e}")
        print("\nTrying alternative: Direct REST API call...")
        # Try direct REST API call as last resort
        try:
            parsed = urlparse(url)
            base_domain = f"{parsed.scheme}://{parsed.netloc}"
            original_base = config.api.base_url
            config.api.base_url = f"{base_domain}/rest/v16"
            print(f"Retry with base URL: {config.api.base_url}")
            print(f"Credentials: username={config.api.username}, password={'***' if config.api.password else 'None'}")
            api_data = fetch_api_data_via_rest_api(transaction_id, config)
            api_data["_url"] = url
            api_data["_timestamp"] = __import__("datetime").datetime.now().isoformat()
            api_data["_transaction_id"] = transaction_id
            config.api.base_url = original_base
        except Exception as e2:
            print(f"Alternative method also failed: {e2}")
            print("\nTroubleshooting:")
            print(f"  - Base URL: {config.api.base_url}")
            print(f"  - Username: {config.api.username}")
            print(f"  - Password set: {config.api.password is not None}")
            print(f"  - Transaction ID: {transaction_id}")
            print("\nPlease verify:")
            print("  1. Credentials are correct")
            print("  2. You have access to this transaction ID")
            print("  3. The base URL is correct for your environment")
            sys.exit(1)
    
    # Step 2: Save API response
    print("\n" + "="*60)
    print("STEP 2: Saving API Response")
    print("="*60)
    save_api_response(api_data, "api_response_structured.json")
    
    # Step 3: Parse Excel files
    print("\n" + "="*60)
    print("STEP 3: Parsing Excel Files")
    print("="*60)
    
    excel_files = list(Path(".").glob("*.xls*"))
    excel_files = [f for f in excel_files if not f.name.startswith("Validated_") and not f.name.startswith("Unknown")]
    
    if not excel_files:
        print("No Excel files found in current directory")
        sys.exit(1)
    
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
            print(f"  ✗ Error parsing {excel_file.name}: {e}")
    
    if not excel_data_list:
        print("No Excel files could be parsed successfully")
        sys.exit(1)
    
    # Step 4: Compare and Validate
    print("\n" + "="*60)
    print("STEP 4: Comparing and Validating")
    print("="*60)
    
    # Save Excel data for reference
    with open("excel_data_parsed.json", "w", encoding="utf-8") as f:
        json.dump(excel_data_list, f, indent=2, ensure_ascii=False)
    print(f"Excel data saved to: excel_data_parsed.json")
    
    # Compare each Excel file with API data
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
                transaction_id=transaction_id,
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
                status = "✓" if detail.match else "✗"
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
    
    # Step 5: Save comparison results
    print("\n" + "="*60)
    print("STEP 5: Saving Comparison Results")
    print("="*60)
    
    # Create serializable results
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
    
    print(f"Comparison results saved to: comparison_results.json")
    print("\n" + "="*60)
    print("COMPLETE!")
    print("="*60)
    print("\nGenerated files:")
    print("  1. api_response_structured.json - Well-structured API response")
    print("  2. excel_data_parsed.json - Parsed Excel data")
    print("  3. comparison_results.json - Validation comparison results")


if __name__ == "__main__":
    main()

