from __future__ import annotations

import io
import re
from typing import Any, Dict, Optional, List

import pandas as pd

from utils import parse_currency


HEADER_PATTERNS = {
    "quoteNumber_t_c": [
        re.compile(r"Solution\s+Quotation\s+(?P<val>\d{3,})", re.IGNORECASE),
        re.compile(r"Quote\s+(?P<val>\d{3,})", re.IGNORECASE),
        re.compile(r"quote\s*number\s*[:\-]?\s*(?P<val>\d{3,})", re.IGNORECASE),
        re.compile(r"Quotation\s+Number\s*[:\-]?\s*(?P<val>\d{3,})", re.IGNORECASE),
        re.compile(r"Quote\s+ID\s*[:\-]?\s*(?P<val>\d{3,})", re.IGNORECASE),
    ],
    "quoteNameTextArea_t_c": [
        re.compile(r"Quote\s+Name\s*:\s*(?P<val>[^<\n]+?)(?:</div>|</td>|$)", re.IGNORECASE | re.DOTALL),
        re.compile(r"Quote\s+(?P<val>\d{3,}[^<\n]+?)(?:</div>|</td>|$)", re.IGNORECASE | re.DOTALL),
        re.compile(r"<div[^>]*>Quote\s+(?P<val>\d{3,}[^<]+)</div>", re.IGNORECASE),
        re.compile(r"<td[^>]*>Quote\s+Name[^<]*</td>\s*<td[^>]*>(?P<val>[^<]+)</td>", re.IGNORECASE),
    ],
    "createdDate_t": [
        re.compile(r"Quote\s+Date\s*:\s*(?P<val>[\d\-A-Za-z/]+)", re.IGNORECASE),
        re.compile(r"Created\s+Date\s*:\s*(?P<val>[\d\-A-Za-z/]+)", re.IGNORECASE),
        re.compile(r"<div[^>]*>(\d{1,2}[-/]\w+[-/]\d{4})</div>", re.IGNORECASE),
        re.compile(r"(\d{1,2}[-/]\d{1,2}[-/]\d{4})", re.IGNORECASE),
        re.compile(r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})", re.IGNORECASE),
    ],
    "expiresOnDate_t_c": [
        re.compile(r"Quote\s+Valid\s+Until\s*:\s*(?P<val>[\d\-A-Za-z/]+)", re.IGNORECASE),
        re.compile(r"Valid\s+Until\s*:\s*(?P<val>[\d\-A-Za-z/]+)", re.IGNORECASE),
        re.compile(r"Expires?\s+On\s*:\s*(?P<val>[\d\-A-Za-z/]+)", re.IGNORECASE),
        re.compile(r"Expiration\s+Date\s*:\s*(?P<val>[\d\-A-Za-z/]+)", re.IGNORECASE),
    ],
    "status_t": [
        re.compile(r"Quote\s+Status\s*:\s*(?P<val>[A-Za-z ]+?)(?:</div>|</td>|$)", re.IGNORECASE),
        re.compile(r"Status\s*:\s*(?P<val>[A-Za-z ]+?)(?:</div>|</td>|$)", re.IGNORECASE),
        re.compile(r"<div[^>]*>(?P<val>[A-Za-z]+)</div>", re.IGNORECASE),
        re.compile(r"<td[^>]*>Status[^<]*</td>\s*<td[^>]*>(?P<val>[^<]+)</td>", re.IGNORECASE),
    ],
    "incoterm_t_c": [
        re.compile(r"Incoterm\s*:\s*(?P<val>[A-Z ]+[^<\n]*?)(?:</div>|</td>|$)", re.IGNORECASE),
        re.compile(r"<div[^>]*>(?P<val>[A-Z]{2,}[^<]+)</div>", re.IGNORECASE),
        re.compile(r"<td[^>]*>Incoterm[^<]*</td>\s*<td[^>]*>(?P<val>[^<]+)</td>", re.IGNORECASE),
    ],
    "orderType_t_c": [
        re.compile(r"Order\s+Type\s*:\s*(?P<val>[A-Za-z ]+?)(?:</div>|</td>|$)", re.IGNORECASE),
        re.compile(r"<td[^>]*>Order\s+Type[^<]*</td>\s*<td[^>]*>(?P<val>[^<]+)</td>", re.IGNORECASE),
    ],
    "paymentTerms_t_c": [
        re.compile(r"Payment\s+Terms\s*:\s*(?P<val>[A-Z0-9%., ]+?)(?:</div>|</td>|$)", re.IGNORECASE),
        re.compile(r"<td[^>]*>Payment\s+Terms[^<]*</td>\s*<td[^>]*>(?P<val>[^<]+)</td>", re.IGNORECASE),
    ],
    "priceList_t_c": [
        re.compile(r"Price\s+List\s*:\s*(?P<val>[A-Z0-9\-_/]+)", re.IGNORECASE),
        re.compile(r"Price\s+List:\s*(?P<val>[A-Z0-9\-_/]+)", re.IGNORECASE),
        re.compile(r"<td[^>]*>Price\s+List[^<]*</td>\s*<td[^>]*>(?P<val>[^<]+)</td>", re.IGNORECASE),
    ],
    "currency_t": [
        re.compile(r"Currency\s*:\s*(?P<val>[A-Z]{3})", re.IGNORECASE),
        re.compile(r"<td[^>]*>Currency[^<]*</td>\s*<td[^>]*>(?P<val>[A-Z]{3})</td>", re.IGNORECASE),
    ],
    "freightTerms_t_c": [
        re.compile(r"Freight\s+Terms\s*:\s*(?P<val>[A-Za-z ]+?)(?:</div>|</td>|$)", re.IGNORECASE),
        re.compile(r"<td[^>]*>Freight\s+Terms[^<]*</td>\s*<td[^>]*>(?P<val>[^<]+)</td>", re.IGNORECASE),
    ],
    "contractName_t": [
        re.compile(r"Contract\s+Name\s*:\s*(?P<val>[^<\n]+?)(?:</div>|</td>|$)", re.IGNORECASE | re.DOTALL),
        re.compile(r"<td[^>]*>Contract\s+Name[^<]*</td>\s*<td[^>]*>(?P<val>[^<]+)</td>", re.IGNORECASE),
    ],
    "contractStartDate_t": [
        re.compile(r"Contract\s+Start\s+Date\s*:\s*(?P<val>[\d\-A-Za-z/]+)", re.IGNORECASE),
        re.compile(r"<td[^>]*>Contract\s+Start[^<]*</td>\s*<td[^>]*>(?P<val>[^<]+)</td>", re.IGNORECASE),
    ],
    "contractEndDate_t": [
        re.compile(r"Contract\s+End\s+Date\s*:\s*(?P<val>[\d\-A-Za-z/]+)", re.IGNORECASE),
        re.compile(r"<td[^>]*>Contract\s+End[^<]*</td>\s*<td[^>]*>(?P<val>[^<]+)</td>", re.IGNORECASE),
    ],
    "lastUpdatedDate_t": [
        re.compile(r"Last\s+Updated\s*:\s*(?P<val>[\d\-A-Za-z/: ]+)", re.IGNORECASE),
        re.compile(r"<td[^>]*>Last\s+Updated[^<]*</td>\s*<td[^>]*>(?P<val>[^<]+)</td>", re.IGNORECASE),
    ],
    "lastUpdatedBy_t": [
        re.compile(r"Last\s+Updated\s+By\s*:\s*(?P<val>[^<\n]+?)(?:</div>|</td>|$)", re.IGNORECASE),
        re.compile(r"<td[^>]*>Last\s+Updated\s+By[^<]*</td>\s*<td[^>]*>(?P<val>[^<]+)</td>", re.IGNORECASE),
    ],
    "sellingMotion_t_c": [
        re.compile(r"Selling\s+Motion\s*:\s*(?P<val>[^<\n]+?)(?:</div>|</td>|$)", re.IGNORECASE),
        re.compile(r"<td[^>]*>Selling\s+Motion[^<]*</td>\s*<td[^>]*>(?P<val>[^<]+)</td>", re.IGNORECASE),
    ],
    "district_t_c": [
        re.compile(r"District\s*:\s*(?P<val>[^<\n]+?)(?:</div>|</td>|$)", re.IGNORECASE),
        re.compile(r"<td[^>]*>District[^<]*</td>\s*<td[^>]*>(?P<val>[^<]+)</td>", re.IGNORECASE),
    ],
}

TOTAL_PATTERNS = {
    "quoteListPrice_t_c": [
        re.compile(r"List\s+Grand\s+Total\s*:\s*(?P<val>[$€₹,Rs\.,\d ]+)", re.IGNORECASE),
        re.compile(r"Grand\s+Total\s+\(List\)\s*:\s*(?P<val>[$€₹,Rs\.,\d ]+)", re.IGNORECASE),
        re.compile(r"Total\s+List\s+Price\s*:\s*(?P<val>[$€₹,Rs\.,\d ]+)", re.IGNORECASE),
        re.compile(r"\$(?P<val>[\d,]+\.?\d*)", re.IGNORECASE),
        re.compile(r"<td[^>]*>List\s+Grand\s+Total[^<]*</td>\s*<td[^>]*>(?P<val>[$€₹,Rs\.,\d ]+)</td>", re.IGNORECASE),
    ],
    "quoteCurrentDiscount_t_c": [
        re.compile(r"Total\s+Discount\s*:\s*(?P<val>[\d\.,]+)", re.IGNORECASE),
        re.compile(r"Discount\s*:\s*(?P<val>[\d\.,]+)", re.IGNORECASE),
        re.compile(r"Discount\s+%\s*:\s*(?P<val>[\d\.,]+)", re.IGNORECASE),
        re.compile(r"<td[^>]*>Total\s+Discount[^<]*</td>\s*<td[^>]*>(?P<val>[\d\.,]+)</td>", re.IGNORECASE),
    ],
    "quoteNetPrice_t_c": [
        re.compile(r"Net\s+Grand\s+Total\s*:\s*(?P<val>[$€₹,Rs\.,\d ]+)", re.IGNORECASE),
        re.compile(r"Grand\s+Total\s+\(Net\)\s*:\s*(?P<val>[$€₹,Rs\.,\d ]+)", re.IGNORECASE),
        re.compile(r"Renewals\s+Grand\s+Total\s*:\s*(?P<val>[$€₹,Rs\.,\d ]+)", re.IGNORECASE),
        re.compile(r"Total\s+Net\s+Price\s*:\s*(?P<val>[$€₹,Rs\.,\d ]+)", re.IGNORECASE),
        re.compile(r"<td[^>]*>Net\s+Grand\s+Total[^<]*</td>\s*<td[^>]*>(?P<val>[$€₹,Rs\.,\d ]+)</td>", re.IGNORECASE),
    ],
    "extNetPrice_t_c": [
        re.compile(r"Extended\s+Net\s+Price\s*:\s*(?P<val>[$€₹,Rs\.,\d ]+)", re.IGNORECASE),
        re.compile(r"<td[^>]*>Extended\s+Net[^<]*</td>\s*<td[^>]*>(?P<val>[$€₹,Rs\.,\d ]+)</td>", re.IGNORECASE),
    ],
    "quoteDesiredNetPrice_t_c": [
        re.compile(r"Desired\s+Net\s+Price\s*:\s*(?P<val>[$€₹,Rs\.,\d ]+)", re.IGNORECASE),
        re.compile(r"<td[^>]*>Desired\s+Net[^<]*</td>\s*<td[^>]*>(?P<val>[$€₹,Rs\.,\d ]+)</td>", re.IGNORECASE),
    ],
    "quoteDesiredDiscount_t_c": [
        re.compile(r"Desired\s+Discount\s*:\s*(?P<val>[\d\.,]+)", re.IGNORECASE),
        re.compile(r"<td[^>]*>Desired\s+Discount[^<]*</td>\s*<td[^>]*>(?P<val>[\d\.,]+)</td>", re.IGNORECASE),
    ],
}


def extract_excel_data(xls_bytes: bytes) -> Dict[str, Any]:
    """Extracts key fields and line items from HTML-based .xls or .xlsx.

    Strategy:
    - Treat as UTF-8 HTML when possible and regex search for header/totals.
    - Use pandas.read_html to pull tables; locate line item tables by headers.
    """
    result: Dict[str, Any] = {
        # Header fields
        "quoteNumber_t_c": None,
        "quoteNameTextArea_t_c": None,
        "createdDate_t": None,
        "expiresOnDate_t_c": None,
        "status_t": None,
        "incoterm_t_c": None,
        "orderType_t_c": None,
        "paymentTerms_t_c": None,
        "priceList_t_c": None,
        "currency_t": None,
        "freightTerms_t_c": None,
        "contractName_t": None,
        "contractStartDate_t": None,
        "contractEndDate_t": None,
        "lastUpdatedDate_t": None,
        "lastUpdatedBy_t": None,
        "sellingMotion_t_c": None,
        "district_t_c": None,
        # Pricing fields
        "quoteListPrice_t_c": None,
        "quoteCurrentDiscount_t_c": None,
        "quoteNetPrice_t_c": None,
        "extNetPrice_t_c": None,
        "quoteDesiredNetPrice_t_c": None,
        "quoteDesiredDiscount_t_c": None,
        # Line items
        "line_items": [],
    }

    # Try decode as text (HTML inside .xls is common in CPQ exports)
    text = None
    try:
        text = xls_bytes.decode("utf-8", errors="ignore")
    except Exception:
        pass

    if text:
        # Clean up HTML tags for better pattern matching
        import html
        # Try to extract text content from HTML
        text_clean = re.sub(r'<[^>]+>', ' ', text)  # Remove HTML tags
        text_clean = html.unescape(text_clean)  # Decode HTML entities
        text_clean = re.sub(r'\s+', ' ', text_clean)  # Normalize whitespace
        
        # Use both original and cleaned text for pattern matching
        for key, pats in HEADER_PATTERNS.items():
            val = _find_first(text, pats)
            if not val:
                val = _find_first(text_clean, pats)
            if val:
                # Clean up extracted value
                val = val.strip()
                val = re.sub(r'\s+', ' ', val)
                result[key] = val
        
        for key, pats in TOTAL_PATTERNS.items():
            raw = _find_first(text, pats)
            if not raw:
                raw = _find_first(text_clean, pats)
            if raw:
                if key == "quoteCurrentDiscount_t_c":
                    try:
                        # Extract just the number
                        num_match = re.search(r'([\d\.,]+)', str(raw))
                        if num_match:
                            result[key] = float(num_match.group(1).replace(",", ""))
                    except Exception:
                        pass
                else:
                    result[key] = parse_currency(raw)

    # Parse tables for line items using pandas
    try:
        tables = pd.read_html(io.BytesIO(xls_bytes))
        for df in tables:
            cols = [str(c).strip().lower() for c in df.columns]
            header_text = "|".join(cols)
            if (
                "part number" in header_text
                and ("unit list price" in header_text or "unit net price" in header_text or "ext. net price" in header_text)
            ):
                def get_col(name_variants: List[str]) -> Optional[int]:
                    for i, c in enumerate(cols):
                        for v in name_variants:
                            if c.startswith(v):
                                return i
                    return None

                idx_part = get_col(["part number", "part#", "part no", "item number"])
                idx_desc = get_col(["product description", "description", "item description", "product name"])
                idx_qty = get_col(["ext. qty", "qty", "quantity", "qty.", "ext qty"])
                idx_ulp = get_col(["unit list price", "unit price", "list price", "unit list", "list price each"])
                idx_disc = get_col(["disc%", "discount", "discount %", "disc", "discount percent", "disc %"])
                idx_unp = get_col(["unit net price", "unit net", "net price", "unit net price each", "net price each"])
                idx_xnp = get_col(["ext. net price", "extended net", "ext net price", "extended net price", "net amount"])
                idx_xlp = get_col(["ext. list price", "extended list", "ext list price", "extended list price", "list amount"])
                idx_disc_amt = get_col(["discount amount", "disc amt", "discount amt"])
                idx_line_total = get_col(["line total", "total", "amount"]) 

                for _, row in df.iterrows():
                    part = _safe_row(row, idx_part)
                    # Skip header-like or empty rows
                    if not part and not any(_safe_row(row, i) for i in [idx_ulp, idx_unp, idx_xnp, idx_xlp] if i is not None):
                        continue
                    # Extract all possible fields
                    item = {
                        "partNumber": part or None,
                        "description": _safe_row(row, idx_desc),
                        "quantity": _to_int(_safe_row(row, idx_qty)),
                        "unitListPrice": parse_currency(_safe_row(row, idx_ulp)),
                        "unitNetPrice": parse_currency(_safe_row(row, idx_unp)),
                        "extendedNetPrice": parse_currency(_safe_row(row, idx_xnp)),
                        "extendedListPrice": parse_currency(_safe_row(row, idx_xlp)),
                        "discountPercent": _to_float(_safe_row(row, idx_disc)),
                        "discountAmount": parse_currency(_safe_row(row, idx_disc_amt)),
                        "lineTotal": parse_currency(_safe_row(row, idx_line_total)),
                    }
                    # Only add if we have at least part number or pricing info
                    if item["partNumber"] or item["unitListPrice"] or item["unitNetPrice"] or item["extendedNetPrice"]:
                        result["line_items"].append(item)
    except ValueError:
        # no tables found; ignore
        pass

    return result


def _find_first(text: str, patterns: List[re.Pattern]) -> Optional[str]:
    for pat in patterns:
        m = pat.search(text)
        if m:
            try:
                val = m.group("val")
                if val:
                    return val.strip()
            except IndexError:
                # Pattern doesn't have a "val" group, try group(0) or group(1)
                try:
                    val = m.group(1) if m.lastindex and m.lastindex >= 1 else m.group(0)
                    if val:
                        return val.strip()
                except (IndexError, AttributeError):
                    pass
    return None


def _safe_row(row: pd.Series, idx: Optional[int]) -> Optional[str]:
    if idx is None:
        return None
    try:
        val = row.iloc[idx]
    except Exception:
        return None
    if pd.isna(val):
        return None
    return str(val).strip()


def _to_int(val: Optional[str]) -> Optional[int]:
    if val is None:
        return None
    s = str(val).replace(",", "").strip()
    return int(s) if s.isdigit() else None


def _to_float(val: Optional[str]) -> Optional[float]:
    if val is None:
        return None
    s = str(val).replace("%", "").replace(",", "").strip()
    try:
        return float(s)
    except Exception:
        return None


