from __future__ import annotations

import re
from datetime import datetime
from typing import Optional
from difflib import SequenceMatcher


def normalize_text(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return re.sub(r"\s+", " ", value).strip().lower()


def parse_currency(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    text = str(value)
    # Remove currency symbols and spaces
    # Normalize Rs patterns like "Rs 1,23,456.78" or "Rs.1,23,456.78"
    text = re.sub(r"\bRs\.?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[\s$,€₹]|USD|INR", "", text, flags=re.IGNORECASE)
    # Remove thousand separators
    text = text.replace(",", "")
    if text == "" or text == "-":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_percentage(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip().replace("%", "")
    text = text.replace(",", "")
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    text = str(value).strip().replace(",", "")
    if text == "":
        return None
    try:
        return int(text)
    except ValueError:
        return None


def parse_date(value: Optional[str]) -> Optional[datetime.date]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    # Try multiple common formats
    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%m-%d-%Y",
        "%m/%d/%Y",
        "%d-%b-%Y",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def floats_match(a: Optional[float], b: Optional[float], tolerance: float) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    # Round to 2 decimals to minimize OCR rounding drift
    a_ = round(float(a), 2)
    b_ = round(float(b), 2)
    if abs(a_ - b_) <= tolerance:
        return True
    # Relative tolerance backup
    denom = max(abs(a_), abs(b_), 1.0)
    return abs(a_ - b_) / denom <= max(tolerance, 1e-6)


def strings_equal(a: Optional[str], b: Optional[str]) -> bool:
    return normalize_text(a) == normalize_text(b)


def strings_close(a: Optional[str], b: Optional[str], *, threshold: float = 0.9) -> bool:
    na = normalize_text(a)
    nb = normalize_text(b)
    if na == nb:
        return True
    if not na or not nb:
        return False
    ratio = SequenceMatcher(None, na, nb).ratio()
    return ratio >= threshold


def strings_contain_match(a: Optional[str], b: Optional[str], *, extract_numbers: bool = False) -> bool:
    """Check if strings match by containment or by extracted numeric identifiers.
    
    This is useful for cases like:
    - API: "174044" vs PDF: "174044 Quote 174044 for Arrow Electronics Inc." -> Match
    - API: "CPQ-174044" vs PDF: "174044" -> Match (extract numbers)
    - API: "Quote 174044" vs PDF: "174044" -> Match (extract numbers)
    
    Args:
        a: First string (typically API value)
        b: Second string (typically PDF value)
        extract_numbers: If True, extract numeric identifiers and compare them
    
    Returns:
        True if strings match by containment or extracted numbers match
    """
    if a is None or b is None:
        return False
    
    na = str(a).strip()
    nb = str(b).strip()
    
    if not na or not nb:
        return False
    
    # Exact match (case-insensitive)
    if na.lower() == nb.lower():
        return True
    
    # Check if one contains the other (case-insensitive)
    na_lower = na.lower()
    nb_lower = nb.lower()
    if na_lower in nb_lower or nb_lower in na_lower:
        return True
    
    # If extract_numbers is True, extract numeric identifiers and compare
    if extract_numbers:
        # Extract all numeric sequences from both strings
        a_numbers = re.findall(r'\d+', na)
        b_numbers = re.findall(r'\d+', nb)
        
        # If both have numbers, check if any match
        if a_numbers and b_numbers:
            # Check if any number from a is in b, or vice versa
            for num_a in a_numbers:
                if num_a in b_numbers:
                    return True
            # Also check if the number appears in the other string
            for num_a in a_numbers:
                if num_a in nb:
                    return True
            for num_b in b_numbers:
                if num_b in na:
                    return True
    
    return False


def only_digits(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    digits = re.sub(r"\D", "", str(text))
    return digits or None


def normalize_address(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).lower()
    # Expand common abbreviations
    repl = {
        " st ": " street ",
        " rd ": " road ",
        " ave ": " avenue ",
        " blvd ": " boulevard ",
        " ln ": " lane ",
        " hwy ": " highway ",
    }
    text = f" {re.sub(r'[^a-z0-9 ]+', ' ', text)} "
    for k, v in repl.items():
        text = text.replace(k, v)
    text = re.sub(r"\s+", " ", text).strip()
    return text


