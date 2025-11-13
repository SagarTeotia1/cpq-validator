"""Test script to debug authentication issues"""
import requests
from requests.auth import HTTPBasicAuth

# Test credentials
username = "km87158"
password = "g$^E1y_S71"
base_url = "https://netappinctest8.bigmachines.com/rest/v16"
transaction_id = "166233956"

url = f"{base_url}/commerceDocumentsUcpqStandardCommerceProcessTransaction/{transaction_id}"

print("="*60)
print("Testing Basic Auth with requests library")
print("="*60)
print(f"URL: {url}")
print(f"Username: {username}")
print(f"Password: {'*' * len(password)}")

# Method 1: Using session.auth
print("\n--- Method 1: Using session.auth ---")
session = requests.Session()
session.auth = (username, password)
session.headers.update({"Accept": "application/json"})

try:
    resp = session.get(url, timeout=30)
    print(f"Status Code: {resp.status_code}")
    print(f"Response Headers: {dict(resp.headers)}")
    if resp.status_code == 200:
        print("✓ SUCCESS!")
        print(f"Response keys: {list(resp.json().keys())[:10]}")
    else:
        print(f"Response Text (first 500 chars): {resp.text[:500]}")
except Exception as e:
    print(f"Error: {e}")

# Method 2: Using HTTPBasicAuth
print("\n--- Method 2: Using HTTPBasicAuth ---")
try:
    resp = requests.get(
        url,
        auth=HTTPBasicAuth(username, password),
        headers={"Accept": "application/json"},
        timeout=30
    )
    print(f"Status Code: {resp.status_code}")
    print(f"Response Headers: {dict(resp.headers)}")
    if resp.status_code == 200:
        print("✓ SUCCESS!")
        print(f"Response keys: {list(resp.json().keys())[:10]}")
    else:
        print(f"Response Text (first 500 chars): {resp.text[:500]}")
except Exception as e:
    print(f"Error: {e}")

# Method 3: Manual Basic Auth header
print("\n--- Method 3: Manual Basic Auth header ---")
import base64
auth_str = f"{username}:{password}"
auth_bytes = auth_str.encode('utf-8')
auth_b64 = base64.b64encode(auth_bytes).decode('utf-8')

try:
    resp = requests.get(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Basic {auth_b64}"
        },
        timeout=30
    )
    print(f"Status Code: {resp.status_code}")
    print(f"Response Headers: {dict(resp.headers)}")
    if resp.status_code == 200:
        print("✓ SUCCESS!")
        print(f"Response keys: {list(resp.json().keys())[:10]}")
    else:
        print(f"Response Text (first 500 chars): {resp.text[:500]}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "="*60)
print("Test Complete")
print("="*60)

