from __future__ import annotations

import html as html_lib
import io
import math
import re
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from utils import parse_currency, parse_int, parse_percentage

CONFIDENCE_THRESHOLD = 0.78
PATTERN_CONFIDENCE = 0.65
LINE_HEADER_KEYWORDS = {"part", "description", "unit", "ext", "qty"}

FIELD_MAPPING: Dict[str, Dict[str, Any]] = {
    "quoteNumber_t_c": {
        "labels": ["quote number", "quotation number", "solution quotation", "quote #", "quoteid", "quote id"],
        "patterns": [
            r"(?:quote|quotation)\s*(?:number|#)\s*[:\-]?\s*(\d{5,})",
            r"solution\s+quotation\s+(\d{5,})",
        ],
        "field_type": "string",
        "adjacent_search": True,
        "multi_cell": False,
    },
    "transactionID_t": {
        "labels": ["transaction id", "transaction number", "quote transaction id"],
        "patterns": [
            r"transaction\s*id\s*[:\-]?\s*([A-Z0-9\-]+)",
            r"quote\s*transaction\s*id\s*[:\-]?\s*([A-Z0-9\-]+)",
        ],
        "field_type": "string",
        "adjacent_search": True,
        "multi_cell": False,
    },
    "quoteNameTextArea_t_c": {
        "labels": ["quote name", "quote description", "name", "quote"],
        "patterns": [
            r"(quote\s+\d{5,}\s+for\s+[A-Za-z0-9 ,.\-&]+)",
            r"quote\s*name\s*[:\-]?\s*([A-Za-z0-9 ,.\-&/]+)",
        ],
        "field_type": "string",
        "adjacent_search": True,
        "multi_cell": True,
    },
    "createdDate_t": {
        "labels": ["quote date", "created date", "date", "pricing date"],
        "patterns": [
            r"(?:created|quote|pricing)\s*date\s*[:\-]?\s*([\d]{1,2}[-/][A-Za-z]{3}[-/][\d]{4})",
            r"(?:created|quote|pricing)\s*date\s*[:\-]?\s*([\d]{1,2}[-/][\d]{1,2}[-/][\d]{4})",
        ],
        "field_type": "string",
        "adjacent_search": True,
    },
    "expiresOnDate_t_c": {
        "labels": ["expires on", "valid until", "expiration date", "quote valid until"],
        "patterns": [
            r"(?:valid\s*until|expires\s*on|expiration\s*date)\s*[:\-]?\s*([\d]{1,2}[-/][A-Za-z]{3}[-/][\d]{4})",
            r"(?:valid\s*until|expires\s*on|expiration\s*date)\s*[:\-]?\s*([\d]{1,2}[-/][\d]{1,2}[-/][\d]{4})",
        ],
        "field_type": "string",
        "adjacent_search": True,
    },
    "status_t": {
        "labels": ["status", "quote status"],
        "patterns": [],
        "field_type": "string",
        "adjacent_search": True,
    },
    "incoterm_t_c": {
        "labels": ["incoterm", "incoterms"],
        "patterns": [],
        "field_type": "string",
        "adjacent_search": True,
    },
    "paymentTerms_t_c": {
        "labels": ["payment terms"],
        "patterns": [],
        "field_type": "string",
        "adjacent_search": True,
        "multi_cell": True,
    },
    "orderType_t_c": {
        "labels": ["order type"],
        "patterns": [],
        "field_type": "string",
        "adjacent_search": True,
    },
    "priceList_t_c": {
        "labels": ["price list", "pricelist"],
        "patterns": [],
        "field_type": "string",
        "adjacent_search": True,
    },
    "currency_t": {
        "labels": ["currency"],
        "patterns": [r"all\s+amounts\s+are\s+in\s+([A-Z]{3})"],
        "field_type": "string",
        "adjacent_search": True,
    },
    "freightTerms_t_c": {
        "labels": ["freight terms"],
        "patterns": [],
        "field_type": "string",
        "adjacent_search": True,
    },
    "contractName_t": {
        "labels": ["contract name", "contract", "agreement name", "agreement"],
        "patterns": [
            r"contract\s*name\s*[:\-]?\s*(.+?)(?:\s*(?:contract|agreement|end|start|date|number|payment|incoterm))",
            r"agreement\s*(?:name|for)\s*[:\-]?\s*(.+?)(?:\s*(?:contract|agreement|end|start|date|number|payment|incoterm))",
            r"(?:contract|agreement)\s*name\s*[:\-]?\s*(.+?)(?:\n|$)",
            r"agreement\s+for\s+([\d/]+\s+[A-Za-z0-9\s.,\-]+?)(?:\s*(?:contract|agreement|end|start|date|number|payment|incoterm|quote\s+information))",
        ],
        "field_type": "string",
        "adjacent_search": True,
        "multi_cell": True,
        "match_threshold": 0.75,
    },
    "contractStartDate_t": {
        "labels": ["contract start date"],
        "patterns": [r"contract\s*start\s*date\s*[:\-]?\s*([\dA-Za-z\-\/]+)"],
        "field_type": "string",
        "adjacent_search": True,
    },
    "contractEndDate_t": {
        "labels": ["contract end date"],
        "patterns": [r"contract\s*end\s*date\s*[:\-]?\s*([\dA-Za-z\-\/]+)"],
        "field_type": "string",
        "adjacent_search": True,
    },
    "lastUpdatedDate_t": {
        "labels": ["last updated date", "last updated"],
        "patterns": [r"last\s+updated\s*[:\-]?\s*([\dA-Za-z:\-\/ ]+)"],
        "field_type": "string",
        "adjacent_search": True,
    },
    "lastUpdatedBy_t": {
        "labels": ["last updated by"],
        "patterns": [],
        "field_type": "string",
        "adjacent_search": True,
    },
    "sellingMotion_t_c": {
        "labels": ["selling motion"],
        "patterns": [],
        "field_type": "string",
        "adjacent_search": True,
    },
    "district_t_c": {
        "labels": ["district"],
        "patterns": [],
        "field_type": "string",
        "adjacent_search": True,
    },
    "quoteColorRating_t_c": {
        "labels": ["quote color rating", "color rating"],
        "patterns": [],
        "field_type": "string",
        "adjacent_search": True,
    },
    "freezePriceFlag_t": {
        "labels": ["freeze price", "freeze price flag"],
        "patterns": [],
        "field_type": "bool",
        "adjacent_search": True,
    },
    "partialShipAllowedFlag_t": {
        "labels": ["partial ship allowed", "partial shipments allowed"],
        "patterns": [],
        "field_type": "bool",
        "adjacent_search": True,
    },
    "priceWithinPolicy_t": {
        "labels": ["price within policy"],
        "patterns": [],
        "field_type": "bool",
        "adjacent_search": True,
    },
    "presentedToCustomer_t_c": {
        "labels": ["presented to customer"],
        "patterns": [],
        "field_type": "bool",
        "adjacent_search": True,
    },
    "salesRepEmailId_t_c": {
        "labels": ["sales rep email", "sales rep email id"],
        "patterns": [r"sales\s*rep\s*email\s*[:\-]?\s*([A-Za-z0-9_.+-]+@[A-Za-z0-9_.\-]+)"],
        "field_type": "string",
        "adjacent_search": True,
    },
    "buySellAvailableOptions_t_c": {
        "labels": ["buy/sell available options"],
        "patterns": [],
        "field_type": "string",
        "adjacent_search": True,
    },
    "previousUsersLogin_t_c": {
        "labels": ["previous users login", "previous user"],
        "patterns": [],
        "field_type": "string",
        "adjacent_search": True,
    },
    "opptyTerritoryId_t_c": {
        "labels": ["oppty territory id", "opportunity territory id"],
        "patterns": [],
        "field_type": "string",
        "adjacent_search": True,
    },
    "quoteListPrice_t_c": {
        "labels": ["list grand total", "total list price", "list total"],
        "patterns": [
            r"list\s+grand\s+total\s*[:\-]?\s*([$€₹Rs.,\d ]+)",
            r"total\s+list\s+price\s*[:\-]?\s*([$€₹Rs.,\d ]+)",
        ],
        "field_type": "currency",
        "adjacent_search": True,
    },
    "quoteCurrentDiscount_t_c": {
        "labels": ["total discount", "discount %"],
        "patterns": [
            r"total\s+discount\s*[:\-]?\s*([\d\.,]+)",
            r"discount\s*%\s*[:\-]?\s*([\d\.,]+)",
        ],
        "field_type": "numeric",
        "adjacent_search": True,
    },
    "quoteNetPrice_t_c": {
        "labels": ["net grand total", "net total", "grand total (net)"],
        "patterns": [
            r"net\s+grand\s+total\s*[:\-]?\s*([$€₹Rs.,\d ]+)",
            r"grand\s+total\s*\(net\)\s*[:\-]?\s*([$€₹Rs.,\d ]+)",
        ],
        "field_type": "currency",
        "adjacent_search": True,
    },
    "extNetPrice_t_c": {
        "labels": ["extended net price"],
        "patterns": [
            r"extended\s+net\s+price\s*[:\-]?\s*([$€₹Rs.,\d ]+)",
        ],
        "field_type": "currency",
        "adjacent_search": True,
    },
    "quoteDesiredNetPrice_t_c": {
        "labels": ["desired net price"],
        "patterns": [
            r"desired\s+net\s+price\s*[:\-]?\s*([$€₹Rs.,\d ]+)",
        ],
        "field_type": "currency",
        "adjacent_search": True,
    },
    "quoteDesiredDiscount_t_c": {
        "labels": ["desired discount"],
        "patterns": [
            r"desired\s+discount\s*[:\-]?\s*([\d\.,]+)",
        ],
        "field_type": "numeric",
        "adjacent_search": True,
    },
    "standardProductMargin_t_c": {
        "labels": ["standard product margin"],
        "patterns": [],
        "field_type": "currency",
        "adjacent_search": True,
    },
    "standardProductMarginUSD_t_c": {
        "labels": ["standard product margin usd"],
        "patterns": [],
        "field_type": "currency",
        "adjacent_search": True,
    },
    "fullStackMarginUSD_t_c": {
        "labels": ["full stack margin usd"],
        "patterns": [],
        "field_type": "currency",
        "adjacent_search": True,
    },
    "quoteFullStackOnlyNetPrice_t_c": {
        "labels": ["quote full stack only net price"],
        "patterns": [],
        "field_type": "currency",
        "adjacent_search": True,
    },
    "quoteTotalCapacityGB_t_c": {
        "labels": ["quote total capacity", "total capacity"],
        "patterns": [],
        "field_type": "numeric",
        "adjacent_search": True,
    },
    "guidanceToGreenAmount_t_c": {
        "labels": ["guidance to green amount"],
        "patterns": [],
        "field_type": "currency",
        "adjacent_search": True,
    },
    "guidanceToYellowAmount_t_c": {
        "labels": ["guidance to yellow amount"],
        "patterns": [],
        "field_type": "currency",
        "adjacent_search": True,
    },
    "quoteGuidanceToGreen_t_c": {
        "labels": ["guidance to green %", "guidance to green percent"],
        "patterns": [],
        "field_type": "numeric",
        "adjacent_search": True,
    },
    "gTCRiskMessageString_t_c": {
        "labels": ["gtc risk message", "gtc risk"],
        "patterns": [],
        "field_type": "string",
        "adjacent_search": True,
        "multi_cell": True,
    },
    "contractNumber_t": {
        "labels": ["contract number", "contract #"],
        "patterns": [
            r"contract\s*(?:number|#)\s*[:\-]?\s*([A-Z0-9\-]+)",
        ],
        "field_type": "string",
        "adjacent_search": True,
        "multi_cell": False,
    },
    "endCustomer_t_c": {
        "labels": ["end customer", "customer", "quote to"],
        "patterns": [
            r"end\s+customer\s*[:\-]?\s*(.+?)(?:\n|quote|from|contract)",
            r"quote\s+to\s*[:\-]?\s*(.+?)(?:\n|quote|from|contract)",
        ],
        "field_type": "string",
        "adjacent_search": True,
        "multi_cell": True,
    },
    "quoteFrom_t_c": {
        "labels": ["quote from", "from"],
        "patterns": [
            r"quote\s+from\s*[:\-]?\s*(.+?)(?:\n|quote|to|contract)",
        ],
        "field_type": "string",
        "adjacent_search": True,
        "multi_cell": True,
    },
    "contactName_t_c": {
        "labels": ["contact name", "contact"],
        "patterns": [
            r"contact\s+name\s*[:\-]?\s*(.+?)(?:\n|email|phone|address)",
        ],
        "field_type": "string",
        "adjacent_search": True,
        "multi_cell": False,
    },
    "contactEmail_t_c": {
        "labels": ["contact email", "email"],
        "patterns": [
            r"email\s*[:\-]?\s*([A-Za-z0-9_.+-]+@[A-Za-z0-9_.\-]+\.[A-Za-z]{2,})",
            r"contact\s+email\s*[:\-]?\s*([A-Za-z0-9_.+-]+@[A-Za-z0-9_.\-]+\.[A-Za-z]{2,})",
        ],
        "field_type": "string",
        "adjacent_search": True,
        "multi_cell": False,
    },
    "contingency_t_c": {
        "labels": ["contingency"],
        "patterns": [],
        "field_type": "string",
        "adjacent_search": True,
        "multi_cell": False,
    },
    "quoteType_t_c": {
        "labels": ["quote type", "type"],
        "patterns": [],
        "field_type": "string",
        "adjacent_search": True,
        "multi_cell": False,
    },
    "dealRegID_t_c": {
        "labels": ["deal reg id", "deal registration id", "deal reg"],
        "patterns": [
            r"deal\s*(?:reg|registration)\s*(?:id|#)?\s*[:\-]?\s*([A-Z0-9\-]+)",
        ],
        "field_type": "string",
        "adjacent_search": True,
        "multi_cell": False,
    },
    "projectCode_t_c": {
        "labels": ["project code", "project"],
        "patterns": [
            r"project\s+code\s*[:\-]?\s*([A-Z0-9\-]+)",
        ],
        "field_type": "string",
        "adjacent_search": True,
        "multi_cell": False,
    },
    "sCSoldToContractName_t_c": {
        "labels": ["sold to contract name", "sold to contract"],
        "patterns": [],
        "field_type": "string",
        "adjacent_search": True,
        "multi_cell": True,
    },
    "sCEndCustomerContractName_t_c": {
        "labels": ["end customer contract name", "end customer contract"],
        "patterns": [],
        "field_type": "string",
        "adjacent_search": True,
        "multi_cell": True,
    },
}


def extract_excel_data(xls_bytes: bytes) -> Dict[str, Any]:
    metadata: Dict[str, Any] = {
        "fields_found": 0,
        "fields_missing": [],
        "confidence_scores": {},
        "events": [],
        "warnings": [],
    }

    result: Dict[str, Any] = {key: None for key in FIELD_MAPPING}
    result["line_items"] = []

    html_text: Optional[str] = None
    try:
        html_text = xls_bytes.decode("utf-8", errors="ignore")
    except Exception:
        html_text = None

    text_flat = _strip_html(html_text) if html_text else ""
    tables = _load_tables(xls_bytes, html_text)

    for field_name, config in FIELD_MAPPING.items():
        raw_value, reference, method, confidence = _extract_field(
            tables, text_flat, config, field_name
        )
        if raw_value is None:
            metadata["fields_missing"].append(field_name)
            metadata["confidence_scores"][field_name] = 0.0
            continue

        value = extract_value_intelligently(raw_value, config.get("field_type", "string"))
        if value is None:
            metadata["fields_missing"].append(field_name)
            metadata["confidence_scores"][field_name] = 0.0
            continue

        result[field_name] = value
        metadata["confidence_scores"][field_name] = round(confidence, 3)
        log_extraction_details(
            metadata,
            field_name=field_name,
            found_at=reference or "unknown",
            method=method,
            confidence=confidence,
            raw_value=raw_value,
        )

    result["line_items"] = parse_line_items_advanced(tables, metadata)
    validate_and_correct_parsed_data(result, metadata)

    metadata["fields_missing"] = sorted(set(metadata["fields_missing"]))
    metadata["fields_found"] = len(
        [f for f in FIELD_MAPPING if result.get(f) not in (None, "")]
    )
    result["_extraction_metadata"] = metadata
    return result


def _load_tables(xls_bytes: bytes, html_text: Optional[str]) -> List[pd.DataFrame]:
    tables: List[pd.DataFrame] = []
    for source in (
        (io.BytesIO(xls_bytes), {"keep_default_na": False, "header": None}),
        (io.StringIO(html_text) if html_text else None, {"keep_default_na": False, "header": None}),
    ):
        buffer, kwargs = source
        if buffer is None:
            continue
        buffer.seek(0)
        try:
            frames = pd.read_html(buffer, **kwargs)
        except ValueError:
            continue
        for df in frames:
            if not isinstance(df, pd.DataFrame) or df.empty:
                continue
            tables.append(df.fillna(""))
    return tables


def _extract_field(
    tables: List[pd.DataFrame],
    text_flat: str,
    config: Dict[str, Any],
    field_name: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str], str, float]:
    labels = config.get("labels") or []
    patterns = config.get("patterns") or []
    match_threshold = config.get("match_threshold", CONFIDENCE_THRESHOLD)

    if tables and labels:
        value, reference, score = locate_field_value(
            tables,
            labels,
            config.get("adjacent_search", True),
            config.get("multi_cell", False),
            match_threshold,
        )
        if value:
            return value, reference, "label", score

    if text_flat and patterns:
        for pattern in patterns:
            compiled = re.compile(pattern, re.IGNORECASE | re.DOTALL)
            match = compiled.search(text_flat)
            if match:
                extracted_value = None
                if match.groups():
                    extracted_value = match.group(1).strip()
                else:
                    extracted_value = match.group(0).strip()
                
                if extracted_value:
                    # Clean up the extracted value for contract names
                    if field_name == "contractName_t":
                        extracted_value = _clean_contract_name(extracted_value)
                    return extracted_value, "pattern", "pattern", PATTERN_CONFIDENCE

    return None, None, "not_found", 0.0


def locate_field_value(
    tables: List[pd.DataFrame],
    labels: List[str],
    adjacent_search: bool,
    multi_cell: bool,
    threshold: float,
) -> Tuple[Optional[str], Optional[str], float]:
    best_value: Optional[str] = None
    best_reference: Optional[str] = None
    best_score = 0.0
    contract_name_candidates: List[Tuple[str, str, float]] = []  # Store contract name candidates
    is_contract_name_field = any("contract" in label.lower() for label in labels)

    for table_idx, df in enumerate(tables):
        rows, cols = df.shape
        for row_idx in range(rows):
            for col_idx in range(cols):
                cell_raw = df.iat[row_idx, col_idx]
                cell_text = _normalize_cell_text(cell_raw)
                if not cell_text:
                    continue
                score, matched_label = _match_label(cell_text, labels)
                if score < threshold:
                    continue

                # Special handling for contract name to avoid false matches
                is_contract_name = "contract" in matched_label.lower() if matched_label else False
                if is_contract_name:
                    # Skip if this looks like contract start/end date or contract number
                    if any(keyword in cell_text.lower() for keyword in ["contract start", "contract end", "contract number", "contract #"]):
                        continue
                    # Skip if it's just "Quote Information" without actual contract name
                    if cell_text.lower().strip() in ["quote information", "contract name", "agreement name"]:
                        continue
                    # Require higher score for contract name to avoid false matches
                    if score < 0.85:
                        continue
                    
                    # Check if the adjacent cell value looks like a contact name (simple name pattern)
                    # Contact names are typically 1-3 words, all capitalized, no special characters
                    # Contract names typically have "Agreement", "Contract", company names with Ltd/Inc, etc.
                    if row_idx < df.shape[0] and col_idx + 1 < df.shape[1]:
                        next_cell = _normalize_cell_text(df.iat[row_idx, col_idx + 1])
                        if next_cell and _is_likely_contact_name(next_cell):
                            # This looks like a contact name, skip this match and continue searching
                            continue
                    
                    # Also check cells further away for actual contract names
                    # Look for patterns like "CompanyName_Region Agreement" in nearby cells
                    # Search in the same row first (most common case)
                    for check_offset in range(1, min(10, cols - col_idx)):
                        if col_idx + check_offset < cols:
                            check_cell = _normalize_cell_text(df.iat[row_idx, col_idx + check_offset])
                            if check_cell and not _is_likely_contact_name(check_cell):
                                # Check if it contains contract name patterns
                                contract_patterns = [
                                    r"[A-Z][a-zA-Z\s]+(?:Ltd|Inc|Corp|LLC)\s*_\s*[A-Z]+\s+[A-Z][a-zA-Z\s]+(?:Agreement|Agreem|Contract|Supplier|Distribution|Master)",
                                    r"[A-Z][a-zA-Z\s]+Technology\s+(?:Ltd|Inc|Corp|LLC)\s*_\s*[A-Z]+\s+[A-Z][a-zA-Z\s]+(?:Agreement|Agreem|Contract)",
                                ]
                                for pattern in contract_patterns:
                                    if re.search(pattern, check_cell, re.IGNORECASE):
                                        # Found a likely contract name, use this instead
                                        contract_name_candidates.append((check_cell, _cell_reference(table_idx, row_idx, col_idx + check_offset), score + 0.2))
                                        break
                    
                    # Also check rows above and below (contract name might be in a different row)
                    for row_offset in [-1, 1]:
                        check_row_idx = row_idx + row_offset
                        if 0 <= check_row_idx < rows:
                            # Check a few cells in the same column or nearby
                            for col_offset in range(-2, 3):
                                check_col_idx = col_idx + col_offset
                                if 0 <= check_col_idx < cols:
                                    check_cell = _normalize_cell_text(df.iat[check_row_idx, check_col_idx])
                                    if check_cell and not _is_likely_contact_name(check_cell):
                                        contract_patterns = [
                                            r"[A-Z][a-zA-Z\s]+(?:Ltd|Inc|Corp|LLC)\s*_\s*[A-Z]+\s+[A-Z][a-zA-Z\s]+(?:Agreement|Agreem|Contract|Supplier|Distribution|Master)",
                                            r"[A-Z][a-zA-Z\s]+Technology\s+(?:Ltd|Inc|Corp|LLC)\s*_\s*[A-Z]+\s+[A-Z][a-zA-Z\s]+(?:Agreement|Agreem|Contract)",
                                        ]
                                        for pattern in contract_patterns:
                                            if re.search(pattern, check_cell, re.IGNORECASE):
                                                contract_name_candidates.append((check_cell, _cell_reference(table_idx, check_row_idx, check_col_idx), score + 0.15))
                                                break

                value = None
                if ":" in str(cell_raw):
                    inline_parts = str(cell_raw).split(":", 1)
                    if _looks_like_label(inline_parts[0]):
                        inline_value = _normalize_cell_text(inline_parts[1])
                        if inline_value:
                            value = inline_value
                            # Clean up contract name - remove common suffixes
                            if is_contract_name:
                                value = _clean_contract_name(value)

                if adjacent_search and not value:
                    # For contract name, use more cells to capture full name
                    max_cells = 10 if multi_cell and is_contract_name else 5
                    value = _collect_horizontal(df, row_idx, col_idx, multi_cell, max_cells, is_contract_name)
                    if is_contract_name and value:
                        # Validate that this looks like a contract name, not a contact name
                        if _is_likely_contact_name(value):
                            # This looks like a contact name, skip it
                            continue
                        value = _clean_contract_name(value)
                if adjacent_search and not value:
                    value = _collect_vertical(df, row_idx, col_idx, multi_cell)
                    if is_contract_name and value:
                        # Validate that this looks like a contract name, not a contact name
                        if _is_likely_contact_name(value):
                            # This looks like a contact name, skip it
                            continue
                        value = _clean_contract_name(value)

                if not value:
                    continue

                reference = _cell_reference(table_idx, row_idx, col_idx)
                if score > best_score:
                    best_score = score
                    best_value = value
                    best_reference = reference

    # For contract names, prioritize candidates that look like actual contract names
    if contract_name_candidates:
        # Sort by score (highest first)
        contract_name_candidates.sort(key=lambda x: x[2], reverse=True)
        # Use the best contract name candidate
        best_contract_value, best_contract_ref, best_contract_score = contract_name_candidates[0]
        if best_contract_score > best_score or (best_value and _is_likely_contact_name(best_value)):
            # Use the contract name candidate if it's better or if current value is a contact name
            best_value = _clean_contract_name(best_contract_value)
            best_reference = best_contract_ref
            best_score = best_contract_score

    return best_value, best_reference, best_score


def _is_likely_contact_name(value: str) -> bool:
    """Check if a value looks like a contact name rather than a contract name."""
    if not value:
        return False
    
    value_clean = value.strip()
    
    # Contact names are typically:
    # - 1-4 words
    # - Each word starts with capital letter
    # - No special characters like underscores, dashes (except hyphens in names)
    # - No contract-related keywords
    
    words = value_clean.split()
    if len(words) > 4:
        # Contract names are usually longer
        return False
    
    # Check for contract-related keywords
    contract_keywords = ["agreement", "contract", "ltd", "inc", "corp", "llc", "technology", 
                        "solutions", "distribution", "supplier", "master", "prc", "opp-"]
    if any(keyword in value_clean.lower() for keyword in contract_keywords):
        return False
    
    # Check for patterns that indicate contract names
    # Pattern: CompanyName_Region or CompanyName Ltd_Region
    if re.search(r"[A-Z][a-zA-Z\s]+(?:Ltd|Inc|Corp|LLC)\s*_\s*[A-Z]+", value_clean):
        return False
    
    # Check if it's just a simple name pattern (First Last or First Middle Last)
    # Simple names: 2-3 words, all title case, no special chars except hyphens
    name_pattern = r"^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2}$"
    if re.match(name_pattern, value_clean):
        # Check if it's repeated (like "Kerry Cheng Kerry Cheng Kerry Cheng")
        words_list = words
        if len(set(words_list)) <= 3 and len(words_list) > 3:
            # Repeated name pattern - definitely a contact name
            return True
        # Simple name without contract keywords - likely contact name
        return True
    
    return False


def _clean_contract_name(value: str) -> str:
    """Clean up contract name by removing common suffixes and artifacts."""
    if not value:
        return value
    
    # Remove checkmarks and special characters at the end
    value = value.rstrip("✓✓✓✓")
    
    # Remove leading section headers that shouldn't be part of contract name
    leading_phrases_to_remove = [
        r"^quote\s+information\s+",
        r"^contract\s+name\s*[:\-]?\s*",
        r"^agreement\s+name\s*[:\-]?\s*",
    ]
    for pattern in leading_phrases_to_remove:
        value = re.sub(pattern, "", value, flags=re.IGNORECASE).strip()
    
    # Split on common delimiters that indicate end of contract name
    # Stop at phrases that indicate a new field
    stop_phrases = [
        "contract start date",
        "contract end date", 
        "contract number",
        "payment terms",
        "incoterm",
        "quote information",
        "quote from",
        "quote to",
        "end customer",
    ]
    
    # Find the earliest occurrence of any stop phrase
    earliest_stop = len(value)
    for phrase in stop_phrases:
        idx = value.lower().find(phrase.lower())
        if idx != -1 and idx < earliest_stop:
            earliest_stop = idx
    
    # Also check for patterns that indicate a second contract name
    # Look for patterns like "CompanyName_Agreement" that might be a second contract
    # Pattern: CompanyName Ltd_Region Master Distribution Supplier Agreement
    # This pattern matches: "Lenovo NetApp Technology Ltd_PRC Master Distribution Supplier Agreem"
    second_contract_patterns = [
        # Pattern: CompanyName Technology Ltd_Region Agreement
        r"\s+([A-Z][a-zA-Z\s]+Technology\s+(?:Ltd|Inc|Corp|LLC)\s*_\s*[A-Z]+\s+[A-Z][a-zA-Z\s]+(?:Agreement|Agreem|Contract|Supplier|Distribution))",
        # Pattern: CompanyName Ltd_Region Agreement  
        r"\s+([A-Z][a-zA-Z\s]+(?:Ltd|Inc|Corp|LLC)\s*_\s*[A-Z]{2,}\s+[A-Z][a-zA-Z\s]+(?:Agreement|Agreem|Contract|Supplier|Distribution|Master))",
        # Pattern: CompanyName Ltd Region Agreement (with space instead of underscore)
        r"\s+([A-Z][a-zA-Z\s]+(?:Ltd|Inc|Corp|LLC)\s+[A-Z]{2,}\s+[A-Z][a-zA-Z\s]+(?:Agreement|Agreem|Contract|Supplier|Distribution|Master))",
    ]
    
    for pattern in second_contract_patterns:
        match = re.search(pattern, value, re.IGNORECASE)
        if match:
            # Take only the part before the second contract
            # Make sure we don't cut off in the middle of a word
            stop_pos = match.start()
            # If there's a period or other punctuation before, include it
            if stop_pos > 0 and value[stop_pos-1] in ['.', '!', '?']:
                stop_pos -= 1
            value = value[:stop_pos].strip()
            # Remove trailing period if it's just a period
            if value.endswith('.'):
                value = value[:-1].strip()
            break
    
    # Also check for common patterns where a company name followed by underscore indicates a new contract
    # Pattern: "CompanyName Ltd_Region Agreement"
    company_underscore_pattern = r"([A-Z][a-zA-Z\s]+(?:Ltd|Inc|Corp|LLC)\s*_\s*[A-Z]{2,}\s+[A-Z][a-zA-Z\s]+(?:Agreement|Agreem|Contract|Supplier|Distribution))"
    matches = list(re.finditer(company_underscore_pattern, value, re.IGNORECASE))
    if len(matches) > 1:
        # If we find multiple such patterns, take only the first contract name
        # Find where the second pattern starts
        if len(matches) >= 2:
            # Check if the first match is part of the actual contract name or if it's a second contract
            first_match_end = matches[0].end()
            # If there's a second match and it's clearly a separate contract, stop before it
            if matches[1].start() > first_match_end:
                # Check if the text between matches looks like it ends the first contract
                text_between = value[first_match_end:matches[1].start()].strip()
                if len(text_between) < 20 or any(word in text_between.lower() for word in [".", "testing", "opp-"]):
                    # This looks like the end of the first contract, stop here
                    value = value[:matches[1].start()].strip()
    
    # If we found a stop phrase, truncate there
    if earliest_stop < len(value):
        value = value[:earliest_stop].strip()
    
    # Remove common trailing phrases that might be from adjacent cells
    trailing_phrases = [
        "contract start date",
        "contract end date", 
        "contract number",
        "payment terms",
        "incoterm",
        "quote information",
    ]
    for phrase in trailing_phrases:
        if value.lower().endswith(phrase.lower()):
            value = value[:-(len(phrase))].strip()
    
    # Remove extra whitespace
    value = re.sub(r"\s+", " ", value).strip()
    
    return value


def _match_label(text: str, labels: List[str]) -> Tuple[float, Optional[str]]:
    text_norm = re.sub(r"[:\s]+$", "", text.lower().replace("_", " ").strip())
    best_ratio = 0.0
    best_label = None
    for label in labels:
        label_norm = label.lower().replace(":", "").strip()
        if not label_norm:
            continue
        if text_norm == label_norm:
            return 1.0, label
        ratio = SequenceMatcher(None, text_norm, label_norm).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_label = label
    return best_ratio, best_label


def _collect_horizontal(
    df: pd.DataFrame,
    row_idx: int,
    col_idx: int,
    multi_cell: bool,
    max_cells: int = 5,
    is_contract_name: bool = False,
) -> Optional[str]:
    values: List[str] = []
    cols = df.shape[1]
    cells_collected = 0
    for offset in range(1, cols - col_idx):
        if cells_collected >= max_cells:
            break
        candidate = _normalize_cell_text(df.iat[row_idx, col_idx + offset])
        if not candidate:
            if multi_cell:
                continue
            break
        
        # For contract names, check for patterns that indicate a second contract name
        if is_contract_name:
            # Check if this cell contains a pattern like "CompanyName_Agreement" which might be a second contract
            second_contract_pattern = r"^[A-Z][a-zA-Z\s]+(?:Ltd|Inc|Corp|LLC)[_\s]+[A-Z]+\s+[A-Z][a-zA-Z\s]+(?:Agreement|Agreem|Contract)"
            if re.match(second_contract_pattern, candidate):
                # Stop before this second contract name
                break
        
        # Stop if we hit another label (but allow for multi-cell fields like contract names)
        if _looks_like_label(candidate) and not multi_cell:
            break
        # For contract names, stop if we hit certain keywords that indicate end of field
        stop_keywords = ["contract start date", "contract end date", "contract number", "payment terms", "incoterm", "quote from", "quote to", "end customer"]
        if multi_cell and candidate.lower() in stop_keywords:
            break
        # Also stop if we see a pattern that looks like a new section
        if is_contract_name and re.match(r"^[A-Z][a-zA-Z\s]+\s+[A-Z][a-zA-Z\s]+$", candidate) and len(candidate.split()) >= 2:
            # Check if it might be a company name starting a new contract
            if any(word in candidate.lower() for word in ["ltd", "inc", "corp", "llc", "technology", "solutions"]):
                # This might be a second contract, stop here
                break
        
        values.append(candidate)
        cells_collected += 1
        if not multi_cell:
            break
    joined = " ".join(values).strip()
    return joined or None


def _collect_vertical(
    df: pd.DataFrame,
    row_idx: int,
    col_idx: int,
    multi_cell: bool,
) -> Optional[str]:
    values: List[str] = []
    rows = df.shape[0]
    max_offset = 3 if multi_cell else 1
    for offset in range(1, max_offset + 1):
        if row_idx + offset >= rows:
            break
        candidate = _normalize_cell_text(df.iat[row_idx + offset, col_idx])
        if not candidate:
            if multi_cell:
                continue
            break
        if _looks_like_label(candidate) and not multi_cell:
            break
        values.append(candidate)
        if not multi_cell:
            break
    joined = " ".join(values).strip()
    return joined or None


def _looks_like_label(text: str) -> bool:
    lowered = text.lower().strip()
    return lowered.endswith(":") or lowered in {"yes", "no"}


def _cell_reference(table_idx: int, row_idx: int, col_idx: int) -> str:
    column = col_idx + 1
    letters = ""
    while column > 0:
        column, remainder = divmod(column - 1, 26)
        letters = chr(65 + remainder) + letters
    return f"T{table_idx + 1}!{letters}{row_idx + 1}"


def _normalize_cell_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_lib.unescape(text)
    text = text.replace("\xa0", " ")
    # Preserve currency symbols and numbers for price columns
    text = re.sub(r"\s+", " ", text).strip()
    if text.lower() in {"nan", "none"}:
        return ""
    return text


def _strip_html(html_text: Optional[str]) -> str:
    if not html_text:
        return ""
    text = re.sub(r"<[^>]+>", " ", html_text)
    text = html_lib.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_value_intelligently(raw_value: Any, field_type: str) -> Any:
    if raw_value is None:
        return None
    text = _normalize_cell_text(raw_value)
    if not text:
        return None
    if field_type == "currency":
        return parse_currency(text)
    if field_type == "numeric":
        value = parse_currency(text)
        if value is None:
            value = parse_percentage(text)
        if value is None:
            value = parse_int(text)
        return value
    if field_type == "bool":
        lowered = text.lower()
        if lowered in {"yes", "true", "y", "1", "✓"}:
            return True
        if lowered in {"no", "false", "n", "0", "✗"}:
            return False
        return None
    return text


def parse_line_items_advanced(
    tables: List[pd.DataFrame],
    metadata: Dict[str, Any],
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []

    for table_idx, df in enumerate(tables):
        header_info = _locate_header_row(df)
        if not header_info:
            continue

        header_row_idx, header_labels, header_rows_used = header_info
        data_start = header_row_idx + header_rows_used
        data_df = df.iloc[data_start:].reset_index(drop=True)

        column_map = _build_column_map(header_labels)
        if column_map.get("part") is None:
            continue
        
        # Check if we have at least one price column (unit or extended)
        has_price_column = (
            column_map.get("unit_list") is not None or
            column_map.get("unit_net") is not None or
            column_map.get("ext_list") is not None or
            column_map.get("ext_net") is not None
        )
        if not has_price_column:
            continue

        # Track current section (Hardware or Services)
        current_section = None

        for row_idx, row in data_df.iterrows():
            part = (
                _normalize_cell_text(row.iloc[column_map["part"]])
                if column_map.get("part") is not None
                else ""
            )
            description = (
                _normalize_cell_text(row.iloc[column_map["description"]])
                if column_map.get("description") is not None
                else ""
            )

            # Check for section headers
            part_lower = part.lower()
            desc_lower = description.lower()
            if "hardware" in part_lower or "hardware" in desc_lower:
                current_section = "Hardware"
                continue
            elif "service" in part_lower or "service" in desc_lower:
                if "part number" not in part_lower:  # Skip header rows
                    current_section = "Services"
                continue

            # Skip header rows and totals
            if not part and not description:
                continue
            if "total" in part_lower or "total" in desc_lower:
                continue
            if part_lower in ("part number", "part", "description", "product description"):
                continue
            if desc_lower in ("part number", "part", "description", "product description"):
                continue

            quantity = parse_int(
                row.iloc[column_map["quantity"]] if column_map.get("quantity") is not None else None
            )
            
            # Extract price values - convert to string first to handle formatted currency values
            unit_list_raw = row.iloc[column_map["unit_list"]] if column_map.get("unit_list") is not None else None
            unit_list = parse_currency(str(unit_list_raw) if unit_list_raw is not None else None)
            
            unit_net_raw = row.iloc[column_map["unit_net"]] if column_map.get("unit_net") is not None else None
            unit_net = parse_currency(str(unit_net_raw) if unit_net_raw is not None else None)
            
            ext_list_raw = row.iloc[column_map["ext_list"]] if column_map.get("ext_list") is not None else None
            ext_list = parse_currency(str(ext_list_raw) if ext_list_raw is not None else None)
            
            ext_net_raw = row.iloc[column_map["ext_net"]] if column_map.get("ext_net") is not None else None
            ext_net = parse_currency(str(ext_net_raw) if ext_net_raw is not None else None)
            discount_percent = parse_percentage(
                row.iloc[column_map["discount_percent"]] if column_map.get("discount_percent") is not None else None
            )
            discount_amount = parse_currency(
                row.iloc[column_map["discount_amount"]] if column_map.get("discount_amount") is not None else None
            )
            line_total = parse_currency(
                row.iloc[column_map["line_total"]] if column_map.get("line_total") is not None else None
            )

            # Determine item type based on part number patterns or section
            item_type = current_section
            if item_type is None:
                # Try to infer from part number
                if part and any(prefix in part.upper() for prefix in ["CS-", "PS-", "SS-", "TS-"]):
                    item_type = "Services"
                elif part and any(prefix in part.upper() for prefix in ["SG", "FA", "AFF", "E-SERIES"]):
                    item_type = "Hardware"
                else:
                    # Default based on description
                    if description and any(keyword in description.lower() for keyword in ["service", "support", "deployment", "advisory"]):
                        item_type = "Services"
                    else:
                        item_type = "Hardware"  # Default assumption

            item = {
                "partNumber": part or None,
                "description": description or None,
                "quantity": quantity,
                "unitListPrice": unit_list,
                "unitNetPrice": unit_net,
                "extendedListPrice": ext_list,
                "extendedNetPrice": ext_net,
                "discountPercent": discount_percent,
                "discountAmount": discount_amount,
                "lineTotal": line_total,
                "itemType": item_type,
            }

            # Only skip if ALL meaningful fields are None (allow items with just part number)
            meaningful_fields = {
                "partNumber", "description", "quantity", "unitListPrice", 
                "unitNetPrice", "extendedListPrice", "extendedNetPrice"
            }
            if all(item.get(key) is None for key in meaningful_fields):
                continue

            items.append(item)

    return items


def _locate_header_row(df: pd.DataFrame) -> Optional[Tuple[int, List[str], int]]:
    rows, cols = df.shape
    for row_idx in range(rows):
        primary = [_normalize_cell_text(df.iat[row_idx, col_idx]) for col_idx in range(cols)]
        primary_lower = [label.lower() for label in primary]
        if not _row_matches_header(primary_lower):
            continue

        header_rows_used = 1
        header_labels = primary

        if row_idx + 1 < rows:
            secondary = [_normalize_cell_text(df.iat[row_idx + 1, col_idx]) for col_idx in range(cols)]
            if _row_contains_subheaders(secondary):
                header_rows_used = 2
                header_labels = [
                    " ".join(filter(None, [primary[col_idx], secondary[col_idx]])).strip()
                    for col_idx in range(cols)
                ]

        return row_idx, header_labels, header_rows_used
    return None


def _row_matches_header(row_lower: List[str]) -> bool:
    tokens_present = set()
    for cell in row_lower:
        words = cell.replace("/", " ").split()
        for word in words:
            if word in LINE_HEADER_KEYWORDS:
                tokens_present.add(word)
    return bool(tokens_present.intersection({"part", "unit", "ext"}))


def _row_contains_subheaders(row: List[str]) -> bool:
    return any(word.lower() in {"price", "each", "net", "list"} for word in row if word)


def _build_column_map(header_labels: List[str]) -> Dict[str, Optional[int]]:
    mapping: Dict[str, Optional[int]] = {
        "part": None,
        "description": None,
        "quantity": None,
        "unit_list": None,
        "unit_net": None,
        "ext_list": None,
        "ext_net": None,
        "discount_percent": None,
        "discount_amount": None,
        "line_total": None,
    }
    
    # First pass: identify extended columns explicitly (to avoid confusion with unit columns)
    for idx, label in enumerate(header_labels):
        lowered = label.lower()
        # Extended columns must explicitly contain "ext" or "extended"
        # Also handle "Estimated Ext." format
        if mapping["ext_list"] is None:
            if (("ext" in lowered or "extended" in lowered) and "list" in lowered and "unit" not in lowered) or \
               ("estimated" in lowered and ("ext" in lowered or "ext." in lowered) and "list" in lowered):
                mapping["ext_list"] = idx
        if mapping["ext_net"] is None:
            if (("ext" in lowered or "extended" in lowered) and "net" in lowered and "unit" not in lowered) or \
               ("estimated" in lowered and ("ext" in lowered or "ext." in lowered) and "net" in lowered):
                mapping["ext_net"] = idx
    
    # Second pass: identify other columns, being careful to avoid extended columns
    for idx, label in enumerate(header_labels):
        lowered = label.lower()
        
        # Skip if already mapped
        if idx in mapping.values():
            continue
            
        if mapping["part"] is None and "part" in lowered and "number" in lowered:
            mapping["part"] = idx
        elif mapping["description"] is None and any(keyword in lowered for keyword in ("description", "product")):
            mapping["description"] = idx
        elif mapping["quantity"] is None and any(keyword in lowered for keyword in ("qty", "quantity")):
            mapping["quantity"] = idx
        # Unit columns: must contain "unit" and NOT be extended
        # Also check for alternative column names like "Estimated Unit List Price", "Unit List Price", etc.
        elif mapping["unit_list"] is None:
            # Check for various unit list price column name patterns
            if ("unit" in lowered and "list" in lowered) or \
               ("estimated" in lowered and "unit" in lowered and "list" in lowered) or \
               (lowered.startswith("unit") and "list" in lowered) or \
               ("list" in lowered and "price" in lowered and "each" in lowered) or \
               ("list" in lowered and "price" in lowered and "unit" in lowered):
                # Make sure it's not an extended column
                if "ext" not in lowered and "extended" not in lowered:
                    mapping["unit_list"] = idx
        elif mapping["unit_net"] is None:
            # Check for various unit net price column name patterns
            if ("unit" in lowered and "net" in lowered) or \
               ("estimated" in lowered and "unit" in lowered and "net" in lowered) or \
               (lowered.startswith("unit") and "net" in lowered) or \
               ("net" in lowered and "price" in lowered and "each" in lowered) or \
               ("net" in lowered and "price" in lowered and "unit" in lowered):
                # Make sure it's not an extended column
                if "ext" not in lowered and "extended" not in lowered:
                    mapping["unit_net"] = idx
        # Extended columns (if not already found in first pass)
        # Also check for alternative column names like "Estimated Ext. List Price", "Extended List Price", etc.
        elif mapping["ext_list"] is None:
            if (("ext" in lowered or "extended" in lowered) and "list" in lowered) or \
               ("estimated" in lowered and ("ext" in lowered or "extended" in lowered) and "list" in lowered):
                mapping["ext_list"] = idx
        elif mapping["ext_net"] is None:
            if (("ext" in lowered or "extended" in lowered) and "net" in lowered) or \
               ("estimated" in lowered and ("ext" in lowered or "extended" in lowered) and "net" in lowered):
                mapping["ext_net"] = idx
        elif mapping["discount_percent"] is None and "%" in lowered and "discount" in lowered:
            mapping["discount_percent"] = idx
        elif mapping["discount_amount"] is None and "discount" in lowered and "%" not in lowered:
            mapping["discount_amount"] = idx
        elif mapping["line_total"] is None and "line" in lowered and "total" in lowered:
            mapping["line_total"] = idx
    
    # Fallback: If we still don't have unit prices but have extended prices, try to infer unit columns
    # by looking for columns that contain "price" and "each" or just "price" without "extended"
    if mapping["unit_list"] is None and mapping["ext_list"] is not None:
        for idx, label in enumerate(header_labels):
            lowered = label.lower()
            if idx not in mapping.values():
                # Look for columns with "list" and "price" that aren't extended
                if "list" in lowered and "price" in lowered and "ext" not in lowered and "extended" not in lowered:
                    mapping["unit_list"] = idx
                    break
    
    if mapping["unit_net"] is None and mapping["ext_net"] is not None:
        for idx, label in enumerate(header_labels):
            lowered = label.lower()
            if idx not in mapping.values():
                # Look for columns with "net" and "price" that aren't extended
                if "net" in lowered and "price" in lowered and "ext" not in lowered and "extended" not in lowered:
                    mapping["unit_net"] = idx
                    break
    
    return mapping


def validate_and_correct_parsed_data(result: Dict[str, Any], metadata: Dict[str, Any]) -> None:
    tolerance = 0.01
    list_total = 0.0
    net_total = 0.0

    for item in result.get("line_items", []):
        qty = item.get("quantity")
        unit_list = item.get("unitListPrice")
        unit_net = item.get("unitNetPrice")
        ext_list = item.get("extendedListPrice")
        ext_net = item.get("extendedNetPrice")

        if ext_list is None and qty is not None and unit_list is not None:
            item["extendedListPrice"] = round(float(qty) * float(unit_list), 2)
            metadata["warnings"].append(
                f"Calculated extended list price for part {item.get('partNumber')}"
            )

        if ext_net is None and qty is not None and unit_net is not None:
            item["extendedNetPrice"] = round(float(qty) * float(unit_net), 2)
            metadata["warnings"].append(
                f"Calculated extended net price for part {item.get('partNumber')}"
            )

        ext_list = item.get("extendedListPrice")
        ext_net = item.get("extendedNetPrice")

        if qty is not None and unit_list is not None and ext_list is not None:
            expected_list = round(float(qty) * float(unit_list), 2)
            if not math.isclose(expected_list, float(ext_list), abs_tol=tolerance):
                metadata["warnings"].append(
                    f"Extended list price mismatch for part {item.get('partNumber')}: expected {expected_list:.2f}, found {ext_list}"
                )

        if qty is not None and unit_net is not None and ext_net is not None:
            expected_net = round(float(qty) * float(unit_net), 2)
            if not math.isclose(expected_net, float(ext_net), abs_tol=tolerance):
                metadata["warnings"].append(
                    f"Extended net price mismatch for part {item.get('partNumber')}: expected {expected_net:.2f}, found {ext_net}"
                )

        if ext_list is not None:
            list_total += float(ext_list)
        if ext_net is not None:
            net_total += float(ext_net)

    if result.get("quoteListPrice_t_c") is None and list_total:
        result["quoteListPrice_t_c"] = round(list_total, 2)
        metadata["warnings"].append("Inferred quoteListPrice_t_c from line item totals.")

    if result.get("quoteNetPrice_t_c") is None and net_total:
        result["quoteNetPrice_t_c"] = round(net_total, 2)
        metadata["warnings"].append("Inferred quoteNetPrice_t_c from line item totals.")

    if result.get("quoteListPrice_t_c") and not math.isclose(
        float(result["quoteListPrice_t_c"]), list_total, abs_tol=tolerance
    ):
        metadata["warnings"].append(
            f"Line item list total {list_total:.2f} differs from header list total {result['quoteListPrice_t_c']:.2f}"
        )

    if result.get("quoteNetPrice_t_c") and not math.isclose(
        float(result["quoteNetPrice_t_c"]), net_total, abs_tol=tolerance
    ):
        metadata["warnings"].append(
            f"Line item net total {net_total:.2f} differs from header net total {result['quoteNetPrice_t_c']:.2f}"
        )


def log_extraction_details(
    metadata: Dict[str, Any],
    *,
    field_name: str,
    found_at: str,
    method: str,
    confidence: float,
    raw_value: Any,
) -> None:
    metadata.setdefault("events", []).append(
        {
            "field": field_name,
            "method": method,
            "location": found_at,
            "confidence": round(confidence, 3),
            "raw_value": raw_value,
        }
    )

