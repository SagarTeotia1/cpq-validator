from __future__ import annotations

import io
import re
from typing import Any, Dict, Optional

import pdfplumber

from utils import parse_currency


HEADER_QUOTE_NUMBER_PATTERNS = [
    # Common explicit labels
    re.compile(r"\bquote\s*number\s*[:\-]\s*(?P<val>[\w\-\/]+)", re.IGNORECASE),
    re.compile(r"\bquotation\s*#\s*(?P<val>[\w\-\/]+)", re.IGNORECASE),
    re.compile(r"\bquote\s*(no\.|number|#)\s*[:\-]?\s*(?P<val>[\w\-\/]+)", re.IGNORECASE),
    # Headers like: "Quote 173670 for Arrow Technologies ..."
    re.compile(r"\bquote\s+(?P<val>\d{3,})\b", re.IGNORECASE),
]

TRANSACTION_ID_PATTERNS = [
    re.compile(r"\btransaction\s*id\b\s*[:\-]?\s*(?P<val>[A-Z]*-?\d{3,})", re.IGNORECASE),
    re.compile(r"\bquote\s*transaction\s*id\b\s*[:\-]?\s*(?P<val>\d{3,})", re.IGNORECASE),
]

SUMMARY_NET_PRICE_PATTERNS = [
    re.compile(r"\bnet\s*(price|amount)\b\s*[:\-]?\s*(?P<val>[-$€₹,\d\.]+)", re.IGNORECASE),
    re.compile(r"\btotal\s*net\b\s*[:\-]?\s*(?P<val>[-$€₹,\d\.]+)", re.IGNORECASE),
    re.compile(r"\bgrand\s*total\b\s*[:\-]?\s*(?P<val>[-$€₹,\d\.]+)", re.IGNORECASE),
    re.compile(r"\bnet\s*amount\s*\(in\s*[A-Z]{3}\)\b\s*[:\-]?\s*(?P<val>[-$€₹,\d\.]+)", re.IGNORECASE),
    re.compile(r"\bnet\s*grand\s*total\b\s*[:\-]?\s*(?P<val>[-$€₹,Rs\.,\d ]+)", re.IGNORECASE),
    re.compile(r"\brenewals\s*grand\s*total\b\s*[:\-]?\s*(?P<val>[-$€₹,Rs\.,\d ]+)", re.IGNORECASE),
]

SUMMARY_LIST_PRICE_PATTERNS = [
    re.compile(r"\blist\s*grand\s*total\b\s*[:\-]?\s*(?P<val>[-$€₹,Rs\.,\d ]+)", re.IGNORECASE),
    re.compile(r"\bext\.?\s*list\s*price\b\s*[:\-]?\s*(?P<val>[-$€₹,Rs\.,\d ]+)", re.IGNORECASE),
]

SUMMARY_DISCOUNT_PATTERNS = [
    re.compile(r"\btotal\s*discount\b\s*[:\-]?\s*(?P<val>[-\d\.,]+)", re.IGNORECASE),
    re.compile(r"\bdiscount\s*:\s*(?P<val>[-\d\.,]+)\b", re.IGNORECASE),
]

# Additional header field patterns
CURRENCY_PATTERNS = [
    re.compile(r"\bcurrency\b\s*[:\-]?\s*(?P<val>[A-Z]{3})", re.IGNORECASE),
    re.compile(r"\ball\s*amounts\s*are\s*in\s*(?P<val>[A-Z]{3})", re.IGNORECASE),
    re.compile(r"\bRs\b", re.IGNORECASE),
]

PRICELIST_PATTERNS = [
    re.compile(r"\bprice\s*list\b\s*[:\-]?\s*(?P<val>[A-Z0-9\-_/]+)", re.IGNORECASE),
]

STATUS_PATTERNS = [
    re.compile(r"\bstatus\b\s*[:\-]?\s*(?P<val>[A-Za-z ]+)", re.IGNORECASE),
]

DATE_PATTERNS = {
    "createdDate_t": [
        re.compile(r"\bcreated\s*date\b\s*[:\-]?\s*(?P<val>[\w\-/: ]{8,})", re.IGNORECASE),
        re.compile(r"\bpricing\s*date\b\s*[:\-]?\s*(?P<val>[\w\-/: ]{8,})", re.IGNORECASE),
    ],
    "expiresOnDate_t_c": [
        re.compile(r"\bexpiry\s*date\b\s*[:\-]?\s*(?P<val>[\w\-/: ]{8,})", re.IGNORECASE),
        re.compile(r"\bexpiration\s*date\b\s*[:\-]?\s*(?P<val>[\w\-/: ]{8,})", re.IGNORECASE),
        re.compile(r"\bquote\s*valid\s*until\b\s*[:\-]?\s*(?P<val>[\w\-/: ]{8,})", re.IGNORECASE),
    ],
}

QUOTE_NAME_PATTERNS = [
    re.compile(r"\bquote\s*name\b\s*[:\-]?\s*(?P<val>.+)", re.IGNORECASE),
    re.compile(r"\bquote\s+(?P<val>\d{3,}.*?)(?:\n|$)", re.IGNORECASE),
]

INCOTERM_PATTERNS = [
    re.compile(r"\bincoterm\b\s*[:\-]?\s*(?P<val>[A-Z ]+)", re.IGNORECASE),
]

PAYMENT_TERMS_PATTERNS = [
    re.compile(r"\bpayment\s*terms\b\s*[:\-]?\s*(?P<val>[A-Z0-9 ]+)", re.IGNORECASE),
]

ORDER_TYPE_PATTERNS = [
    re.compile(r"\border\s*type\b\s*[:\-]?\s*(?P<val>[A-Za-z ]+)", re.IGNORECASE),
]


def extract_pdf_data(pdf_bytes: bytes) -> Dict[str, Any]:
    """Extract minimal fields from PDF required for phase 1.

    Returns structure with keys mirroring API fields where possible.
    Currently extracts:
      - quoteNumber_t_c (from header)
      - quoteNetPrice_t_c (from summary)
    """
    result: Dict[str, Any] = {
        "quoteNumber_t_c": None,
        "transactionID_t": None,
        "quoteNetPrice_t_c": None,
        "quoteListPrice_t_c": None,
        "quoteCurrentDiscount_t_c": None,
        "currency_t": None,
        "priceList_t_c": None,
        "status_t": None,
        "createdDate_t": None,
        "expiresOnDate_t_c": None,
        "quoteNameTextArea_t_c": None,
        "incoterm_t_c": None,
        "paymentTerms_t_c": None,
        "orderType_t_c": None,
        "line_items": [],  # list of rows
    }

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        # Page 1 header: quote number and transaction id
        if len(pdf.pages) > 0:
            text_p1 = pdf.pages[0].extract_text(x_tolerance=2, y_tolerance=2) or ""
            header_val = _find_first_match(text_p1, HEADER_QUOTE_NUMBER_PATTERNS)
            if header_val:
                result["quoteNumber_t_c"] = header_val
            txid_val = _find_first_match(text_p1, TRANSACTION_ID_PATTERNS)
            if txid_val:
                result["transactionID_t"] = txid_val

        # All pages: net price in summary sections
        net_candidates: list[float] = []
        all_text_parts: list[str] = []
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=3, y_tolerance=3) or ""
            if text:
                all_text_parts.append(text)
            # Match on-page (allow cross-line via merged later)
            val_str = _find_first_match(text, SUMMARY_NET_PRICE_PATTERNS)
            if val_str:
                val = parse_currency(val_str)
                if val is not None:
                    net_candidates.append(val)
            # list price on page
            lval_str = _find_first_match(text, SUMMARY_LIST_PRICE_PATTERNS)
            if lval_str and result["quoteListPrice_t_c"] is None:
                lval = parse_currency(lval_str)
                if lval is not None:
                    result["quoteListPrice_t_c"] = lval

        if net_candidates:
            # Prefer the last occurrence in reading order
            result["quoteNetPrice_t_c"] = net_candidates[-1]

        # If not found on per-page scan, try merged text with broader context
        merged = "\n".join(all_text_parts)
        if result["quoteNetPrice_t_c"] is None and merged:
            val_str = _find_first_match(merged, SUMMARY_NET_PRICE_PATTERNS)
            if val_str:
                val = parse_currency(val_str)
                if val is not None:
                    result["quoteNetPrice_t_c"] = val

        # Derive list total and discount from merged
        if merged and result.get("quoteListPrice_t_c") is None:
            lval_str = _find_first_match(merged, SUMMARY_LIST_PRICE_PATTERNS)
            if lval_str:
                lval = parse_currency(lval_str)
                if lval is not None:
                    result["quoteListPrice_t_c"] = lval
        if merged:
            dval_str = _find_first_match(merged, SUMMARY_DISCOUNT_PATTERNS)
            if dval_str:
                try:
                    result["quoteCurrentDiscount_t_c"] = float(dval_str.replace(",",""))
                except Exception:
                    pass

        # Other header fields from merged text
        if merged:
            currency = _find_first_match(merged, CURRENCY_PATTERNS)
            if currency:
                # If we matched a plain Rs token, normalize to INR
                result["currency_t"] = "INR" if currency.lower() == "rs" else currency

            pricelist = _find_first_match(merged, PRICELIST_PATTERNS)
            if pricelist:
                result["priceList_t_c"] = pricelist

            status = _find_first_match(merged, STATUS_PATTERNS)
            if status:
                result["status_t"] = status

            for k, pats in DATE_PATTERNS.items():
                d = _find_first_match(merged, pats)
                if d:
                    result[k] = d

            qn = _find_first_match(merged, QUOTE_NAME_PATTERNS)
            if qn:
                result["quoteNameTextArea_t_c"] = qn

            inc = _find_first_match(merged, INCOTERM_PATTERNS)
            if inc:
                result["incoterm_t_c"] = inc

            pt = _find_first_match(merged, PAYMENT_TERMS_PATTERNS)
            if pt:
                result["paymentTerms_t_c"] = pt

            ot = _find_first_match(merged, ORDER_TYPE_PATTERNS)
            if ot:
                result["orderType_t_c"] = ot

        # Try to extract line item tables by header detection
        try:
            tables_rows: list[dict] = []
            for page in pdf.pages:
                # Use pdfplumber's table extraction; heuristic header detection
                table_settings = {
                    "vertical_strategy": "text",
                    "horizontal_strategy": "text",
                    "intersection_tolerance": 5,
                }
                tables = page.extract_tables(table_settings)
                for tbl in tables or []:
                    # Normalize header row
                    if not tbl or len(tbl) < 2:
                        continue
                    header = [ (c or "").strip().lower() for c in tbl[0] ]
                    # Look for key columns commonly present in quotes
                    header_text = "|".join(header)
                    if (
                        "part number" in header_text
                        or "unit list price" in header_text
                        or "ext. net price" in header_text
                        or "ext. list price" in header_text
                        or "disc%" in header_text
                    ):
                        idx = {name: None for name in [
                            "part number","product description","ext. qty","unit list price","disc%","unit net price","ext. net price","ext. list price","qty","unit price","discount","unit net","extended net"
                        ]}
                        for i, col in enumerate(header):
                            for key in list(idx.keys()):
                                if col.startswith(key):
                                    idx[key] = i
                        # Iterate body rows
                        for row in tbl[1:]:
                            def col(i: Optional[int]) -> Optional[str]:
                                if i is None:
                                    return None
                                if i < 0 or i >= len(row):
                                    return None
                                return (row[i] or "").strip()

                            part = col(idx.get("part number"))
                            desc = col(idx.get("product description"))
                            qty_s = col(idx.get("ext. qty")) or col(idx.get("qty"))
                            ulp_s = col(idx.get("unit list price")) or col(idx.get("unit price"))
                            disc_s = col(idx.get("disc%")) or col(idx.get("discount"))
                            unp_s = col(idx.get("unit net price")) or col(idx.get("unit net"))
                            xnp_s = col(idx.get("ext. net price")) or col(idx.get("extended net"))
                            xlp_s = col(idx.get("ext. list price"))

                            # Filter out obvious non-data rows
                            numeric_present = any(v and any(ch.isdigit() for ch in v) for v in [ulp_s, unp_s, xnp_s, xlp_s])
                            if not part and not numeric_present:
                                continue

                            row_obj = {
                                "partNumber": part or None,
                                "description": desc or None,
                                "quantity": int(qty_s.replace(",","")) if (qty_s and qty_s.replace(",","" ).isdigit()) else None,
                                "unitListPrice": parse_currency(ulp_s),
                                "unitNetPrice": parse_currency(unp_s),
                                "extendedNetPrice": parse_currency(xnp_s),
                                "extendedListPrice": parse_currency(xlp_s),
                                "discountPercent": None,
                            }
                            # Parse discount percent if present like 24.52
                            if disc_s:
                                try:
                                    row_obj["discountPercent"] = float(disc_s.replace("%",""))
                                except Exception:
                                    row_obj["discountPercent"] = None
                            tables_rows.append(row_obj)
            if tables_rows:
                result["line_items"] = tables_rows
        except Exception:
            # Silent fallback; line items optional in phase
            pass

    return result


def _find_first_match(text: str, patterns: list[re.Pattern]) -> Optional[str]:
    for pat in patterns:
        m = pat.search(text)
        if m and m.group("val"):
            return m.group("val").strip()
    return None


