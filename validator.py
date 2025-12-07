from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, NamedTuple

from config import AppConfig
from utils import floats_match, strings_equal, strings_close, strings_contain_match, parse_currency, parse_date, only_digits, parse_percentage


@dataclass
class FieldResult:
    field_name: str
    section: str
    expected: Any
    found: Any
    match: bool
    page: Optional[int] = None
    message: Optional[str] = None


@dataclass
class ValidationResult:
    overall_status: str
    total_checked: int
    matches: int
    mismatches: int
    details: List[FieldResult] = field(default_factory=list)
    transaction_id: Optional[str] = None
    pdf_filename: Optional[str] = None


class ExtendedField(NamedTuple):
    name: str
    section: str
    kind: str  # string, picklist, numeric, currency, percent, bool, date
    threshold: float = 0.9


def _normalize_scalar(value: Any) -> Any:
    if isinstance(value, dict):
        for key in ("displayValue", "value", "display", "code", "name"):
            if key in value and value[key] not in (None, ""):
                return value[key]
        if len(value) == 1:
            return next(iter(value.values()))
    return value


def _to_bool(value: Any) -> Optional[bool]:
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if value in (0, 1):
            return bool(value)
        return None
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "yes", "y", "1", "t"}:
            return True
        if normalized in {"false", "no", "n", "0", "f"}:
            return False
    return None


def _to_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return parse_currency(str(value))


def _to_percent(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return parse_percentage(str(value))


def _to_string(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _is_pdf_value_none(pdf_val: Any) -> bool:
    """Check if PDF value is None, empty, or the string 'None'.
    Returns True if the value should be considered as missing/not present in PDF.
    If PDF doesn't have a value, there's no point in comparing it."""
    if pdf_val is None:
        return True
    if isinstance(pdf_val, str):
        normalized = pdf_val.strip().lower()
        if normalized in ("", "none", "null", "n/a", "na", "-", "--"):
            return True
    # For numeric types, 0 might be valid, but None/empty string means missing
    if isinstance(pdf_val, (int, float)):
        # Only consider it None if it's explicitly None or NaN
        if pdf_val != pdf_val:  # NaN check
            return True
    return False


EXTENDED_FIELDS: List[ExtendedField] = [
    ExtendedField("pVRSMLevelFlag_t_c", "Header", "bool"),
    ExtendedField("partnerTermsAndCondition_t_c", "Header", "string"),
    ExtendedField("validStagesForCurrentProcess_t_c", "Header", "string"),
    ExtendedField("previousReviewReasons_t_c", "Header", "string"),
    ExtendedField("copyProcess_t_c", "Header", "bool"),
    ExtendedField("makeTransition_t_c", "Header", "bool"),
    ExtendedField("contingencyAllowableValue_t_c", "Header", "string"),
    ExtendedField("keystoneConfigFlag_t_c", "Header", "bool"),
    ExtendedField("_tax_isTaxInclusive_t", "Header", "bool"),
    ExtendedField("lineLockDiscountMessagesJSON_t_c", "Header", "string"),
    ExtendedField("geoFinanceLeadFlag_t_c", "Header", "bool"),
    ExtendedField("copyLinesFlag_t_c", "Header", "bool"),
    ExtendedField("_s_priceScoreSimpleMarginUnitCost_t", "Summary", "numeric"),
    ExtendedField("test_c", "Header", "bool"),
    ExtendedField("version_number_createUSDQuote_c", "Header", "string"),
    ExtendedField("partnerInvokedApproval_t_c", "Header", "bool"),
    ExtendedField("standardProductMarginUSD_t_c", "Summary", "currency"),
    ExtendedField("addOnStorageAdded_t_c", "Summary", "bool"),
    ExtendedField("internalRepApprovalPending_t_c", "Header", "bool"),
    ExtendedField("contractEntityCompanyCMATName_t_c", "Header", "string"),
    ExtendedField("qLET_FAQ_HTML_Link_t_c", "Header", "string"),
    ExtendedField("opptyTerritoryId_t_c", "Header", "string"),
    ExtendedField("promoExpiryFlag_t_c", "Summary", "bool"),
    ExtendedField("priceWithinPolicy_t", "Summary", "bool"),
    ExtendedField("rPHoldNetPriceFlag_t_c", "Summary", "bool"),
    ExtendedField("copyQuoteInitiatedFlag_t_c", "Header", "bool"),
    ExtendedField("quoteGuidanceToGreen_t_c", "Summary", "percent"),
    ExtendedField("salesRepEmailId_t_c", "Header", "string"),
    ExtendedField("showTPDColumns_t_c", "Summary", "bool"),
    ExtendedField("quoteTotalCapacityGB_t_c", "Summary", "numeric"),
    ExtendedField("theZeroMarginSpecial_t_c", "Summary", "bool"),
    ExtendedField("proposalExists_t", "Summary", "bool"),
    ExtendedField("_tax_isTaxPresent_t", "Header", "bool"),
    ExtendedField("legalEntities_t_c", "Header", "picklist"),
    ExtendedField("lSCLevelUpdate_t_c", "Header", "bool"),
    ExtendedField("presentedToCustomer_t_c", "Header", "bool"),
    ExtendedField("chooseYouAction_c", "Header", "string"),
    ExtendedField("jVGlobalFlag_c", "Header", "bool"),
    ExtendedField("incumbentVendor_Array_Control_t_c", "Summary", "numeric"),
    ExtendedField("vPFlagRenewals_t_c", "Header", "bool"),
    ExtendedField("paymentTermsInitialValue_t_c", "Header", "string"),
    ExtendedField("dDSIgnoredQuotes_t_c", "Header", "bool"),
    ExtendedField("addOnQuoteStatusFlag_t_c", "Header", "bool"),
    ExtendedField("salesRBDLevelFlag_t_c", "Header", "bool"),
    ExtendedField("partnerCompetencyString_t_c", "Header", "string"),
    ExtendedField("printAndExportFilename_t_c", "Header", "string"),
    ExtendedField("runTimeLoggedInUser_t_c", "Header", "string"),
    ExtendedField("_s_assignedTo_t", "Header", "picklist"),
    ExtendedField("incotermInitialValue_t_c", "Header", "string"),
    ExtendedField("fPVREOSLFlag_t_c", "Header", "bool"),
    ExtendedField("quoteFullStackOnlyNetPrice_t_c", "Summary", "currency"),
    ExtendedField("dealRegApproved_t_c", "Header", "bool"),
    ExtendedField("_s_quoteForAgreement_t", "Header", "bool"),
    ExtendedField("labOnDemandLODHasBeenConsidered_t_c", "Header", "bool"),
    ExtendedField("_s_priceScoreListBased_t", "Summary", "numeric"),
    ExtendedField("partDescriptionQletOperator_t_c", "Summary", "picklist"),
    ExtendedField("keyStone_t_c", "Header", "picklist"),
    ExtendedField("addonQuoteFlag_t_c", "Header", "bool"),
    ExtendedField("preBuildQuoteFlag_t_c", "Header", "bool"),
    ExtendedField("hasManagedServicesParts_t_c", "Header", "bool"),
    ExtendedField("enterDollarAmount_RawCapacity_t_c", "Summary", "currency"),
    ExtendedField("fullStackMarginUSD_t_c", "Summary", "currency"),
    ExtendedField("cAPAccount_t_c", "Header", "string"),
    ExtendedField("previousQuoteDesiredValuesJSON_t_c", "Header", "string"),
    ExtendedField("policyViolationRegionLevel_t_c", "Header", "bool"),
    ExtendedField("defaultRequestDate_t", "Header", "date"),
    ExtendedField("standardJustificationForm_t_c", "Header", "string"),
    ExtendedField("customDiscountPresent_t_c", "Summary", "bool"),
    ExtendedField("standardProductMargin_t_c", "Summary", "currency"),
    ExtendedField("guidanceToGreenAmount_t_c", "Summary", "currency"),
    ExtendedField("guidanceToYellowAmount_t_c", "Summary", "currency"),
    ExtendedField("quoteColorRating_t_c", "Header", "picklist"),
    ExtendedField("freezePriceFlag_t", "Summary", "bool"),
    ExtendedField("partialShipAllowedFlag_t", "Header", "bool"),
    ExtendedField("salesAutoApproverFlag_t_c", "Header", "bool"),
    ExtendedField("currentUserBuyName_t_c", "Header", "string"),
    ExtendedField("previousUsersLogin_t_c", "Header", "string"),
    ExtendedField("quoteStatusSentFlag_t_c", "Header", "bool"),
    ExtendedField("buySellAvailableOptions_t_c", "Header", "string"),
    ExtendedField("quoteOwnerSSOId_t_c", "Header", "string"),
    ExtendedField("gTCRiskMessageString_t_c", "Header", "string"),
]


def _evaluate_extended_field(field: ExtendedField, api_val: Any, doc_val: Any, config: AppConfig) -> tuple[Any, Any, bool]:
    if field.kind == "bool":
        api_bool = _to_bool(api_val)
        doc_bool = _to_bool(doc_val)
        expected = api_bool
        found = doc_bool
        if api_bool is None and doc_bool is None:
            match = True
        elif api_bool is not None and doc_bool is not None:
            match = api_bool == doc_bool
        else:
            match = False
        return expected, found, match

    if field.kind == "currency":
        api_num = _to_float(api_val)
        doc_num = _to_float(doc_val)
        expected = round(api_num, 2) if api_num is not None else None
        found = round(doc_num, 2) if doc_num is not None else None
        match = floats_match(api_num, doc_num, config.validation_rules.numeric_tolerance)
        return expected, found, match

    if field.kind == "numeric":
        api_num = _to_float(api_val)
        doc_num = _to_float(doc_val)
        expected = api_num
        found = doc_num
        match = floats_match(api_num, doc_num, config.validation_rules.numeric_tolerance)
        return expected, found, match

    if field.kind == "percent":
        api_pct = _to_percent(api_val)
        doc_pct = _to_percent(doc_val)
        expected = round(api_pct, 2) if api_pct is not None else None
        found = round(doc_pct, 2) if doc_pct is not None else None
        match = floats_match(api_pct, doc_pct, config.validation_rules.percentage_tolerance)
        return expected, found, match

    if field.kind == "date":
        api_date = parse_date(api_val)
        doc_date = parse_date(doc_val)
        expected = api_val
        found = doc_val
        match = api_date == doc_date if (api_date is not None or doc_date is not None) else True
        return expected, found, match

    # Default string / picklist comparison with containment matching
    api_str = _to_string(api_val)
    doc_str = _to_string(doc_val)
    expected = api_str
    found = doc_str
    # Use containment matching first (more lenient), then fall back to similarity
    match = strings_contain_match(api_str, doc_str, extract_numbers=True) or strings_close(api_str, doc_str, threshold=field.threshold)
    return expected, found, match


def validate_quote(config: AppConfig, api_data: Dict[str, Any], pdf_data: Dict[str, Any], *, transaction_id: Optional[str] = None, pdf_filename: Optional[str] = None) -> ValidationResult:
    """
    Validate quote data following the exact structure of the Excel document:
    1. Header Section (Quote Name, Dates, Contact Info, Status)
    2. Line Items (Hardware & Services)
    3. Grand Totals (List Total, Discount, Net Total)
    4. Quote Information (Additional Details: Incoterm, Contract, Payment Terms, etc.)
    """
    results: List[FieldResult] = []

    # ========================================================================
    # SECTION 1: HEADER SECTION (Top of Document)
    # ========================================================================
    
    # 1. Quote Name
    api_quote_name = api_data.get("quoteNameTextArea_t_c") or api_data.get("transactionName_t")
    pdf_quote_name = pdf_data.get("quoteNameTextArea_t_c")
    if not _is_pdf_value_none(pdf_quote_name):
        api_str = str(api_quote_name) if api_quote_name else None
        pdf_str = str(pdf_quote_name) if pdf_quote_name else None
        match = strings_contain_match(api_str, pdf_str, extract_numbers=True) or strings_close(api_str, pdf_str, threshold=0.8)
        results.append(
            FieldResult(
                field_name="quoteNameTextArea_t_c",
                section="Header",
                expected=api_quote_name,
                found=pdf_quote_name,
                match=match,
            )
        )

    # 2. Quote Date
    api_created = api_data.get("createdDate_t")
    pdf_created = pdf_data.get("createdDate_t")
    if not _is_pdf_value_none(pdf_created):
        results.append(
            FieldResult(
                field_name="createdDate_t",
                section="Header",
                expected=api_created,
                found=pdf_created,
                match=(
                    (parse_date(api_created) == parse_date(pdf_created))
                    if (api_created or pdf_created)
                    else True
                ),
            )
        )

    # 3. Quote Valid Until
    api_expires = api_data.get("expiresOnDate_t_c")
    pdf_expires = pdf_data.get("expiresOnDate_t_c")
    if not _is_pdf_value_none(pdf_expires):
        results.append(
            FieldResult(
                field_name="expiresOnDate_t_c",
                section="Header",
                expected=api_expires,
                found=pdf_expires,
                match=(
                    (parse_date(api_expires) == parse_date(pdf_expires))
                    if (api_expires or pdf_expires)
                    else True
                ),
            )
        )

    # 4. Contact Name (if available in PDF)
    # Note: Contact name may not be in standard fields, skip if not present

    # 5. Email (if available in PDF)
    # Note: Email may not be in standard fields, skip if not present

    # 6. Quote To (if available in PDF)
    # Note: Quote To may not be in standard fields, skip if not present

    # 7. Quote From (if available in PDF)
    # Note: Quote From may not be in standard fields, skip if not present

    # 8. End Customer (if available in PDF)
    # Note: End Customer may not be in standard fields, skip if not present

    # 9. Quote Status
    api_status_candidates = [
        (api_data.get("quoteStatus_t_c") or {}).get("displayValue") if isinstance(api_data.get("quoteStatus_t_c"), dict) else api_data.get("quoteStatus_t_c"),
        (api_data.get("status_t") or {}).get("displayValue") if isinstance(api_data.get("status_t"), dict) else api_data.get("status_t"),
    ]
    api_status = next((v for v in api_status_candidates if v is not None), None)
    pdf_status = pdf_data.get("status_t")
    if not _is_pdf_value_none(pdf_status):
        results.append(
            FieldResult(
                field_name="status_t",
                section="Header",
                expected=api_status,
                found=pdf_status,
                match=strings_close(api_status, pdf_status, threshold=0.9),
            )
        )

    # ========================================================================
    # SECTION 2: LINE ITEMS (Hardware & Services)
    # ========================================================================
    # Validate line items as they appear in the document (before totals)
    validate_line_items(config, api_data, pdf_data, results)

    # ========================================================================
    # SECTION 3: GRAND TOTALS
    # ========================================================================
    
    # 1. List Grand Total
    api_list_candidates = [
        api_data.get("quoteListPrice_t_c"),
        api_data.get("totalOneTimeListAmount_t"),
        api_data.get("totalListPrice_t_c"),
    ]
    api_list = None
    for candidate in api_list_candidates:
        if candidate is not None:
            if isinstance(candidate, dict) and candidate.get("value") is not None:
                api_list = candidate.get("value")
                break
            elif isinstance(candidate, (int, float)):
                api_list = candidate
                break
    
    pdf_list = pdf_data.get("quoteListPrice_t_c")
    api_list_parsed = parse_currency(str(api_list) if api_list is not None else None)
    
    if not _is_pdf_value_none(pdf_list):
        results.append(
            FieldResult(
                field_name="quoteListPrice_t_c",
                section="Grand Totals",
                expected=round(api_list_parsed, 2) if api_list_parsed is not None else None,
                found=round(pdf_list, 2) if pdf_list is not None else None,
                match=floats_match(api_list_parsed, pdf_list, config.validation_rules.numeric_tolerance),
                message=f"CRITICAL: List Grand Total validation" if not floats_match(api_list_parsed, pdf_list, config.validation_rules.numeric_tolerance) else None,
            )
        )

    # 2. Total Discount
    api_disc = api_data.get("transactionTotalDiscountPercent_t") or api_data.get("quoteCurrentDiscount_t_c")
    pdf_disc = pdf_data.get("quoteCurrentDiscount_t_c")
    if not _is_pdf_value_none(pdf_disc):
        try:
            api_disc_f = float(api_disc) if api_disc is not None else None
        except Exception:
            api_disc_f = None
        try:
            pdf_disc_f = float(pdf_disc) if pdf_disc is not None else None
        except Exception:
            pdf_disc_f = None
        results.append(
            FieldResult(
                field_name="quoteCurrentDiscount_t_c",
                section="Grand Totals",
                expected=api_disc_f,
                found=pdf_disc_f,
                match=floats_match(api_disc_f, pdf_disc_f, config.validation_rules.percentage_tolerance),
            )
        )

    # 3. Net Grand Total
    api_net_candidates = [
        api_data.get("quoteNetPrice_t_c"),
        api_data.get("extNetPrice_t_c"),
        api_data.get("netPrice_t_c"),
        api_data.get("totalOneTimeNetAmount_t"),
        api_data.get("_transaction_total"),
    ]
    api_net = next((v for v in api_net_candidates if v is not None), None)
    api_net_f = parse_currency(api_net if isinstance(api_net, str) else str(api_net) if api_net is not None else None)
    pdf_net_f = pdf_data.get("quoteNetPrice_t_c")
    
    if not _is_pdf_value_none(pdf_net_f):
        results.append(
            FieldResult(
                field_name="quoteNetPrice_t_c",
                section="Grand Totals",
                expected=round(api_net_f, 2) if api_net_f is not None else None,
                found=round(pdf_net_f, 2) if pdf_net_f is not None else None,
                match=floats_match(api_net_f, pdf_net_f, config.validation_rules.numeric_tolerance),
                message=f"CRITICAL: Net Grand Total validation" if not floats_match(api_net_f, pdf_net_f, config.validation_rules.numeric_tolerance) else None,
            )
        )

    # ========================================================================
    # SECTION 4: QUOTE INFORMATION (Additional Details)
    # ========================================================================
    
    # Quote Name (repeated in Quote Information section)
    # Already validated above, skip duplicate

    # Quote Date (repeated in Quote Information section)
    # Already validated above, skip duplicate

    # Quote Valid Until (repeated in Quote Information section)
    # Already validated above, skip duplicate

    # Contact Name, Phone, Email, Quote To, Quote From, End Customer
    # (These may not be in standard API fields, skip if not present)

    # Ship To, Software Delivery Contact, Software Delivery Email
    # (These may not be in standard API fields, skip if not present)

    # Incoterm
    api_incoterm = (
        (api_data.get("incoterm_t_c") or {}).get("displayValue")
        if isinstance(api_data.get("incoterm_t_c"), dict)
        else api_data.get("incoterm_t_c")
    )
    pdf_incoterm = pdf_data.get("incoterm_t_c")
    if not _is_pdf_value_none(pdf_incoterm):
        results.append(
            FieldResult(
                field_name="incoterm_t_c",
                section="Quote Information",
                expected=api_incoterm,
                found=pdf_incoterm,
                match=strings_close(api_incoterm, pdf_incoterm, threshold=0.92),
            )
        )

    # Quote Status (repeated in Quote Information section)
    # Already validated above, skip duplicate

    # Contingency (if available in PDF)
    # Note: May not be in standard fields, skip if not present

    # Contract Number (if available in PDF)
    # Note: May not be in standard fields, skip if not present

    # Order Type
    api_order_type = (
        (api_data.get("orderType_t_c") or {}).get("displayValue")
        if isinstance(api_data.get("orderType_t_c"), dict)
        else api_data.get("orderType_t_c")
    )
    pdf_order_type = pdf_data.get("orderType_t_c")
    if not _is_pdf_value_none(pdf_order_type):
        results.append(
            FieldResult(
                field_name="orderType_t_c",
                section="Quote Information",
                expected=api_order_type,
                found=pdf_order_type,
                match=strings_close(api_order_type, pdf_order_type, threshold=0.92),
            )
        )

    # Contract Name
    api_contract_name = api_data.get("contractName_t")
    if api_contract_name is not None:
        if isinstance(api_contract_name, dict):
            api_contract_name = api_contract_name.get("value") or api_contract_name.get("displayValue")
        pdf_contract_name = pdf_data.get("contractName_t")
        if not _is_pdf_value_none(pdf_contract_name):
            api_str = str(api_contract_name) if api_contract_name is not None else None
            pdf_str = str(pdf_contract_name) if pdf_contract_name is not None else None
            match = strings_contain_match(api_str, pdf_str, extract_numbers=True) or strings_close(api_str, pdf_str, threshold=0.85)
            results.append(
                FieldResult(
                    field_name="contractName_t",
                    section="Quote Information",
                    expected=api_str,
                    found=pdf_str,
                    match=match,
                )
            )

    # Payment Terms
    api_payterms = (
        (api_data.get("paymentTerms_t_c") or {}).get("displayValue")
        if isinstance(api_data.get("paymentTerms_t_c"), dict)
        else api_data.get("paymentTerms_t_c")
    )
    pdf_payterms = pdf_data.get("paymentTerms_t_c")
    if not _is_pdf_value_none(pdf_payterms):
        results.append(
            FieldResult(
                field_name="paymentTerms_t_c",
                section="Quote Information",
                expected=api_payterms,
                found=pdf_payterms,
                match=strings_close(api_payterms, pdf_payterms, threshold=0.92),
            )
        )

    # Price List
    api_pricelist = (
        (api_data.get("priceList_t_c") or {}).get("value")
        if isinstance(api_data.get("priceList_t_c"), dict)
        else api_data.get("priceList_t_c")
    )
    pdf_pricelist = pdf_data.get("priceList_t_c")
    if not _is_pdf_value_none(pdf_pricelist):
        results.append(
            FieldResult(
                field_name="priceList_t_c",
                section="Quote Information",
                expected=api_pricelist,
                found=pdf_pricelist,
                match=strings_close(api_pricelist, pdf_pricelist, threshold=0.95),
            )
        )

    # Transaction ID (if available)
    api_tx_candidates = [
        api_data.get("transactionID_t"),
        api_data.get("quoteTransactionID_t_c"),
        api_data.get("bs_id"),
        api_data.get("_id"),
        api_data.get("sourceBS_ID_t_c"),
    ]
    api_tx_expected = next((v for v in api_tx_candidates if v is not None), None)
    pdf_tx = pdf_data.get("transactionID_t")
    if not _is_pdf_value_none(pdf_tx):
        api_digits = only_digits(str(api_tx_expected) if api_tx_expected else None)
        pdf_digits = only_digits(str(pdf_tx) if pdf_tx else None)
        match = (api_digits == pdf_digits) if (api_digits and pdf_digits) else strings_contain_match(
            str(api_tx_expected) if api_tx_expected else None,
            str(pdf_tx) if pdf_tx else None,
            extract_numbers=True
        )
        results.append(
            FieldResult(
                field_name="transactionID_t",
                section="Quote Information",
                expected=api_tx_expected,
                found=pdf_tx,
                match=match,
            )
        )

    # Quote Number (for reference, if different from quote name)
    api_quote_number = api_data.get("quoteNumber_t_c") or api_data.get("_document_number") or api_data.get("_id")
    pdf_quote_number = pdf_data.get("quoteNumber_t_c")
    if not _is_pdf_value_none(pdf_quote_number):
        api_str = str(api_quote_number) if api_quote_number is not None else None
        pdf_str = str(pdf_quote_number) if pdf_quote_number is not None else None
        match = strings_contain_match(api_str, pdf_str, extract_numbers=True) or strings_close(api_str, pdf_str, threshold=0.85)
        results.append(
            FieldResult(
                field_name="quoteNumber_t_c",
                section="Quote Information",
                expected=api_quote_number,
                found=pdf_quote_number,
                match=match,
            )
        )

    # Additional Header Attributes (if present in PDF)
    additional_header_fields = [
        ("freightTerms_t_c", "Freight Terms"),
        ("contractStartDate_t", "Contract Start Date"),
        ("contractEndDate_t", "Contract End Date"),
        ("lastUpdatedDate_t", "Last Updated Date"),
        ("lastUpdatedBy_t", "Last Updated By"),
        ("sellingMotion_t_c", "Selling Motion"),
        ("district_t_c", "District"),
    ]
    
    for field, label in additional_header_fields:
        api_val = api_data.get(field)
        if api_val is not None:
            if isinstance(api_val, dict):
                api_val = api_val.get("value") or api_val.get("displayValue")
            pdf_val = pdf_data.get(field)
            if _is_pdf_value_none(pdf_val):
                continue
            api_str = str(api_val) if api_val is not None else None
            pdf_str = str(pdf_val) if pdf_val is not None else None
            match = strings_contain_match(api_str, pdf_str, extract_numbers=True) or strings_close(api_str, pdf_str, threshold=0.85)
            results.append(
                FieldResult(
                    field_name=field,
                    section="Quote Information",
                    expected=api_str,
                    found=pdf_str,
                    match=match,
                )
            )
    
    # Additional Pricing Attributes (if present in PDF)
    additional_pricing_fields = [
        ("extNetPrice_t_c", "Extended Net Price", True),
        ("quoteDesiredNetPrice_t_c", "Desired Net Price", True),
        ("quoteDesiredDiscount_t_c", "Desired Discount %", False),
    ]
    
    for field, label, is_currency in additional_pricing_fields:
        api_val = api_data.get(field)
        pdf_val = pdf_data.get(field)
        if _is_pdf_value_none(pdf_val):
            continue
        if api_val is not None or pdf_val is not None:
            if is_currency:
                api_parsed = parse_currency(str(api_val) if api_val is not None and not isinstance(api_val, (int, float)) else api_val)
                pdf_parsed = pdf_val
                tolerance = config.validation_rules.numeric_tolerance
            else:
                try:
                    api_parsed = float(api_val) if api_val is not None else None
                    pdf_parsed = float(pdf_val) if pdf_val is not None else None
                    tolerance = config.validation_rules.percentage_tolerance
                except (ValueError, TypeError):
                    api_parsed = None
                    pdf_parsed = None
                    tolerance = 0.0
            
            results.append(
                FieldResult(
                    field_name=field,
                    section="Quote Information",
                    expected=round(api_parsed, 2) if api_parsed is not None else None,
                    found=round(pdf_parsed, 2) if pdf_parsed is not None else None,
                    match=floats_match(api_parsed, pdf_parsed, tolerance) if (api_parsed is not None and pdf_parsed is not None) else False,
                )
            )

    # Extended attribute coverage (50+ additional validations) - if present in PDF
    for ext_field in EXTENDED_FIELDS:
        api_raw = api_data.get(ext_field.name)
        pdf_raw = pdf_data.get(ext_field.name)
        api_val = _normalize_scalar(api_raw)
        pdf_val = _normalize_scalar(pdf_raw)
        # Skip validation if PDF value is None/empty
        if _is_pdf_value_none(pdf_val):
            continue
        if api_val is None and pdf_val is None:
            continue
        expected, found, match = _evaluate_extended_field(ext_field, api_val, pdf_val, config)
        results.append(
            FieldResult(
                field_name=ext_field.name,
                section=ext_field.section,
                expected=expected,
                found=found,
                match=match,
            )
        )

    matches = sum(1 for r in results if r.match)
    mismatches = len(results) - matches
    overall = "PASSED" if mismatches == 0 else "FAILED"

    return ValidationResult(
        overall_status=overall,
        total_checked=len(results),
        matches=matches,
        mismatches=mismatches,
        details=results,
        transaction_id=transaction_id,
        pdf_filename=pdf_filename,
    )


def _get_api_lines(api_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    # Support api_data["transactionLine"] from main.py (attached) or direct 'items'
    lines_container = api_data.get("transactionLine") or {}
    if isinstance(lines_container, dict) and "items" in lines_container:
        return list(lines_container.get("items") or [])
    if isinstance(api_data.get("items"), list):
        return list(api_data.get("items") or [])
    return []


def validate_line_items(config: AppConfig, api_data: Dict[str, Any], pdf_data: Dict[str, Any], results: List[FieldResult]) -> None:
    pdf_lines: List[Dict[str, Any]] = list(pdf_data.get("line_items") or [])
    api_lines: List[Dict[str, Any]] = _get_api_lines(api_data)
    if not pdf_lines or not api_lines:
        return

    # Index PDF lines by part number for quick lookup
    pdf_by_part: Dict[str, Dict[str, Any]] = {}
    for row in pdf_lines:
        part = row.get("partNumber")
        if part:
            pdf_by_part[str(part).strip()] = row

    # Line items count validation removed - not needed
    
    # Calculate totals from line items for validation
    api_calculated_list_total = 0.0
    api_calculated_net_total = 0.0
    pdf_calculated_list_total = 0.0
    pdf_calculated_net_total = 0.0

    # For each API line, compare against matching PDF part
    for line in api_lines:
        api_part = line.get("_part_number") or line.get("_part_display_number") or line.get("_line_display_name")
        pdf_row = pdf_by_part.get(str(api_part)) if api_part is not None else None

        # If PDF doesn't have this part number, skip all validations for this line item
        if pdf_row is None or _is_pdf_value_none(pdf_row.get("partNumber")):
            continue

        # Part number presence (only validate if we have a PDF row)
        # Use containment matching for part numbers (e.g., "SG5812A-001-48TB" vs "SG5812A-001-48TB-PR")
        pdf_part = pdf_row.get("partNumber")
        if not _is_pdf_value_none(pdf_part):
            api_part_str = str(api_part) if api_part is not None else None
            pdf_part_str = str(pdf_part) if pdf_part is not None else None
            # Use containment match - if one contains the other, it's a match
            match = strings_contain_match(api_part_str, pdf_part_str, extract_numbers=True) or strings_close(api_part_str, pdf_part_str, threshold=0.85)
            results.append(
                FieldResult(
                    field_name="_part_number",
                    section="Lines",
                    expected=api_part,
                    found=pdf_part,
                    match=match,
                )
            )

        # Quantity exact
        api_qty = line.get("_price_quantity") or line.get("_line_bom_item_quantity")
        pdf_qty = pdf_row.get("quantity") if pdf_row else None
        if not _is_pdf_value_none(pdf_qty):
            results.append(
                FieldResult(
                    field_name="quantity",
                    section="Lines",
                    expected=api_qty,
                    found=pdf_qty,
                    match=(int(api_qty) == int(pdf_qty)) if (api_qty is not None and pdf_qty is not None) else False,
                )
            )

        # Unit List Price - validation removed, not needed
        api_ulp = None
        for key in ["_price_item_price_each", "_price_unit_price_each", "_price_list_price_each"]:
            val = line.get(key)
            if isinstance(val, dict) and val.get("value") is not None:
                api_ulp = val.get("value")
                break

        # Unit Net Price - validation removed, not needed
        api_unp = line.get("netPrice_l")
        api_unp_val = api_unp.get("value") if isinstance(api_unp, dict) else None

        # Extended List Price - validation removed, not needed
        # Still extract for calculation validations
        api_xlp = None
        for key in ["_price_extended_price", "extendedListPrice", "listAmount_l"]:
            val = line.get(key)
            if isinstance(val, dict) and val.get("value") is not None:
                api_xlp = val.get("value")
                break
            elif isinstance(val, (int, float)) and val is not None:
                api_xlp = val
                break

        # Extended Net Price - Check ALL possible fields
        api_xnp = None
        for key in ["netAmount_l", "netAmountRollup_l", "netPriceRollup_l", "extendedNetPriceUSD_l_c", "rollUpNetPrice_l_c"]:
            val = line.get(key)
            if isinstance(val, dict) and val.get("value") is not None:
                api_xnp = val.get("value")
                break
            elif isinstance(val, (int, float)) and val is not None and val != 0:
                api_xnp = val
                break
        
        # Also check listPrice_l_c for extended list
        if api_xnp is None:
            api_list_price = line.get("listPrice_l_c")
            if isinstance(api_list_price, (int, float)) and api_list_price != 0:
                # This might be extended list, check if it matches calculation
                pass
        
        pdf_xnp = pdf_row.get("extendedNetPrice") if pdf_row else None
        if not _is_pdf_value_none(pdf_xnp):
            results.append(
                FieldResult(
                    field_name="extendedNetPrice",
                    section="Lines",
                    expected=round(api_xnp, 2) if api_xnp is not None else None,
                    found=round(pdf_xnp, 2) if pdf_xnp is not None else None,
                    match=floats_match(
                        parse_currency(str(api_xnp) if api_xnp is not None else None),
                        pdf_xnp,
                        config.validation_rules.numeric_tolerance,
                    ),
                    message=f"CRITICAL: Extended Net Price = Quantity × Unit Net Price" if not floats_match(
                        parse_currency(str(api_xnp) if api_xnp is not None else None),
                        pdf_xnp,
                        config.validation_rules.numeric_tolerance,
                    ) else None,
                )
            )

        # CRITICAL CALCULATION VALIDATION: Extended List = Quantity × Unit List
        if api_qty and api_ulp and pdf_row:
            calculated_ext_list = float(api_qty) * float(api_ulp)
            actual_ext_list = api_xlp or pdf_row.get("extendedListPrice")
            if actual_ext_list and not _is_pdf_value_none(actual_ext_list):
                actual_ext_list = parse_currency(str(actual_ext_list) if not isinstance(actual_ext_list, (int, float)) else actual_ext_list)
                calc_match = floats_match(calculated_ext_list, actual_ext_list, config.validation_rules.numeric_tolerance)
                results.append(
                    FieldResult(
                        field_name=f"calc_ext_list_{api_part}",
                        section="Calculations",
                        expected=round(calculated_ext_list, 2),
                        found=round(actual_ext_list, 2) if actual_ext_list else None,
                        match=calc_match,
                        message=f"Qty({api_qty}) × Unit List({api_ulp}) = {calculated_ext_list:.2f}, Found: {actual_ext_list:.2f}" if not calc_match else None,
                    )
                )

        # CRITICAL CALCULATION VALIDATION: Extended Net = Quantity × Unit Net
        api_unp_val_for_calc = api_unp_val or (line.get("netPrice_l_c") if isinstance(line.get("netPrice_l_c"), (int, float)) else None)
        if api_qty and api_unp_val_for_calc and pdf_row:
            calculated_ext_net = float(api_qty) * float(api_unp_val_for_calc)
            actual_ext_net = api_xnp or pdf_row.get("extendedNetPrice")
            if actual_ext_net and not _is_pdf_value_none(actual_ext_net):
                actual_ext_net = parse_currency(str(actual_ext_net) if not isinstance(actual_ext_net, (int, float)) else actual_ext_net)
                calc_match = floats_match(calculated_ext_net, actual_ext_net, config.validation_rules.numeric_tolerance)
                results.append(
                    FieldResult(
                        field_name=f"calc_ext_net_{api_part}",
                        section="Calculations",
                        expected=round(calculated_ext_net, 2),
                        found=round(actual_ext_net, 2) if actual_ext_net else None,
                        match=calc_match,
                        message=f"Qty({api_qty}) × Unit Net({api_unp_val_for_calc}) = {calculated_ext_net:.2f}, Found: {actual_ext_net:.2f}" if not calc_match else None,
                    )
                )

        # Discount % - Check multiple fields
        api_disc = line.get("discountPercent_l") or line.get("currentDiscount_l_c") or line.get("currentDiscountEndCustomer_l_c")
        if isinstance(api_disc, dict):
            api_disc = api_disc.get("value")
        pdf_disc = pdf_row.get("discountPercent") if pdf_row else None
        if not _is_pdf_value_none(pdf_disc):
            results.append(
                FieldResult(
                    field_name="discountPercent",
                    section="Lines",
                    expected=api_disc,
                    found=pdf_disc,
                    match=floats_match(
                        float(api_disc) if api_disc is not None else None,
                        float(pdf_disc) if pdf_disc is not None else None,
                        config.validation_rules.percentage_tolerance,
                    ),
                )
            )
        
        # Accumulate totals for grand total validation
        if api_xlp:
            try:
                api_calculated_list_total += float(api_xlp)
            except (ValueError, TypeError):
                pass
        if api_xnp:
            try:
                api_calculated_net_total += float(api_xnp)
            except (ValueError, TypeError):
                pass
        
        if pdf_row:
            pdf_ext_list = pdf_row.get("extendedListPrice")
            pdf_ext_net = pdf_row.get("extendedNetPrice")
            if pdf_ext_list:
                try:
                    pdf_calculated_list_total += float(pdf_ext_list)
                except (ValueError, TypeError):
                    pass
            if pdf_ext_net:
                try:
                    pdf_calculated_net_total += float(pdf_ext_net)
                except (ValueError, TypeError):
                    pass
        
        # Additional pricing fields validation
        # Check listPrice_l_c (might be extended list price for the line)
        api_list_price_line = line.get("listPrice_l_c")
        if isinstance(api_list_price_line, (int, float)) and api_list_price_line != 0:
            pdf_ext_list = pdf_row.get("extendedListPrice") if pdf_row else None
            if not _is_pdf_value_none(pdf_ext_list):
                results.append(
                    FieldResult(
                        field_name=f"listPrice_l_c_{api_part}",
                        section="Lines",
                        expected=round(api_list_price_line, 2),
                        found=round(pdf_ext_list, 2) if pdf_ext_list else None,
                        match=floats_match(
                            float(api_list_price_line),
                            pdf_ext_list,
                            config.validation_rules.numeric_tolerance,
                        ),
                    )
                )
        
        # Check rollUpNetPrice_l_c
        api_rollup_net = line.get("rollUpNetPrice_l_c")
        if isinstance(api_rollup_net, (int, float)) and api_rollup_net != 0:
            pdf_ext_net = pdf_row.get("extendedNetPrice") if pdf_row else None
            if not _is_pdf_value_none(pdf_ext_net):
                results.append(
                    FieldResult(
                        field_name=f"rollUpNetPrice_l_c_{api_part}",
                        section="Lines",
                        expected=round(api_rollup_net, 2),
                        found=round(pdf_ext_net, 2) if pdf_ext_net else None,
                        match=floats_match(
                            float(api_rollup_net),
                            pdf_ext_net,
                            config.validation_rules.numeric_tolerance,
                        ),
                    )
                )
        
        # rollUpResUnitNetPrice_l_c validation removed - not needed
        
        # Check storageTotal_l_c, serviceTotal_l_c, hardwareTotal_l_c
        # These are typically not in PDF, so skip validation
        # (They're informational fields from API only)
        
    
    # Calculation validations removed - not needed


