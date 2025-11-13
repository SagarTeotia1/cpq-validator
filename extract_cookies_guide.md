# How to Extract Browser Cookies for CPQ API

Since the CPQ API requires Single Sign-On (SSO), you need to use cookies from your browser session.

## Method 1: Using Browser Developer Tools (Chrome/Edge)

1. **Open the CPQ web UI** in your browser:
   ```
   https://netappinctest8.bigmachines.com/redwood/vp/cx-cpq/application/container/quotes/quotes-detail?id=166233956&mode=live&processVariableName=ucpqStandardCommerceProcess
   ```

2. **Open Developer Tools**:
   - Press `F12` or `Ctrl+Shift+I` (Windows) / `Cmd+Option+I` (Mac)
   - Or right-click → "Inspect"

3. **Go to Network tab**

4. **Refresh the page** (F5) or navigate to the quote page

5. **Find an API request**:
   - Look for requests containing `rest/v16` in the URL
   - Or look for requests with type "xhr" or "fetch"
   - Example: `commerceDocumentsUcpqStandardCommerceProcessTransaction/166233956`

6. **Click on the request** → Go to **Headers** tab

7. **Find the Cookie header**:
   - Scroll down to "Request Headers"
   - Find the line: `Cookie: ...`
   - Copy the entire value (it will be long, something like: `JSESSIONID=...; X-Oracle-OCI-LBCookie=...; ...`)

8. **Use the cookie**:
   - Run: `python fetch_with_cookies.py`
   - Paste the cookie string when prompted

## Method 2: Using Browser Extension

1. **Install a cookie export extension**:
   - Chrome: "Cookie-Editor" or "EditThisCookie"
   - Edge: Same extensions work

2. **Export cookies**:
   - Click the extension icon
   - Select "Export" → "JSON"
   - Save to a file (e.g., `cookies.json`)

3. **Use the file**:
   - Run: `python fetch_with_cookies.py`
   - Provide the path to the JSON file

## Method 3: Copy Cookies from Application Tab

1. **Open Developer Tools** (F12)

2. **Go to Application tab** (Chrome) or **Storage tab** (Firefox)

3. **Click on Cookies** → Select `https://netappinctest8.bigmachines.com`

4. **Copy cookie values**:
   - You'll see a list of cookies
   - Important ones: `JSESSIONID`, `X-Oracle-OCI-LBCookie`, etc.
   - Create a JSON file with format:
     ```json
     {
       "JSESSIONID": "value_here",
       "X-Oracle-OCI-LBCookie": "value_here",
       "other_cookie": "value_here"
     }
     ```

5. **Use the file** with `fetch_with_cookies.py`

## Quick Test

After getting cookies, test if they work:
```bash
python fetch_with_cookies.py
```

Then paste your cookie string or provide the JSON file path.

