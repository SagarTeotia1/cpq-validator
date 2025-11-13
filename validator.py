from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from config import AppConfig
from utils import floats_match, strings_equal, strings_close, parse_currency, parse_date, only_digits


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


def validate_quote(config: AppConfig, api_data: Dict[str, Any], pdf_data: Dict[str, Any], *, transaction_id: Optional[str] = None, pdf_filename: Optional[str] = None) -> ValidationResult:
    results: List[FieldResult] = []

    # Quote Number (text exact, case-insensitive)
    api_quote_number = api_data.get("quoteNumber_t_c") or api_data.get("_document_number") or api_data.get("_id")
    pdf_quote_number = pdf_data.get("quoteNumber_t_c")
    results.append(
        FieldResult(
            field_name="quoteNumber_t_c",
            section="Header",
            expected=api_quote_number,
            found=pdf_quote_number,
            match=strings_close(str(api_quote_number) if api_quote_number is not None else None, str(pdf_quote_number) if pdf_quote_number is not None else None, threshold=0.92),
        )
    )

    # Transaction ID (text exact across multiple API fallbacks)
    # API often exposes: transactionID_t (e.g., CPQ-173670), quoteTransactionID_t_c, bs_id, _id
    api_tx_candidates = [
        api_data.get("transactionID_t"),
        api_data.get("quoteTransactionID_t_c"),
        api_data.get("bs_id"),
        api_data.get("_id"),
        api_data.get("sourceBS_ID_t_c"),
    ]
    api_tx_expected = next((v for v in api_tx_candidates if v is not None), None)
    pdf_tx = pdf_data.get("transactionID_t")
    results.append(
        FieldResult(
            field_name="transactionID_t",
            section="Header",
            expected=api_tx_expected,
            found=pdf_tx,
            match=(only_digits(api_tx_expected) == only_digits(pdf_tx)),
        )
    )

    # Net Price - Check ALL possible fields with priority
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

    results.append(
        FieldResult(
            field_name="quoteNetPrice_t_c",
            section="Summary",
            expected=round(api_net_f, 2) if api_net_f is not None else None,
            found=round(pdf_net_f, 2) if pdf_net_f is not None else None,
            match=floats_match(api_net_f, pdf_net_f, config.validation_rules.numeric_tolerance),
            message=f"CRITICAL: Net Grand Total validation" if not floats_match(api_net_f, pdf_net_f, config.validation_rules.numeric_tolerance) else None,
        )
    )

    # List Total - Check ALL possible fields with priority
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
    
    results.append(
        FieldResult(
            field_name="quoteListPrice_t_c",
            section="Summary",
            expected=round(api_list_parsed, 2) if api_list_parsed is not None else None,
            found=round(pdf_list, 2) if pdf_list is not None else None,
            match=floats_match(api_list_parsed, pdf_list, config.validation_rules.numeric_tolerance),
            message=f"CRITICAL: List Grand Total validation (Unit prices sum to this)" if not floats_match(api_list_parsed, pdf_list, config.validation_rules.numeric_tolerance) else None,
        )
    )
    
    # Additional pricing validations
    # Extended Net Price
    api_ext_net = api_data.get("extNetPrice_t_c")
    if api_ext_net is not None:
        api_ext_net_f = parse_currency(str(api_ext_net) if not isinstance(api_ext_net, (int, float)) else api_ext_net)
        results.append(
            FieldResult(
                field_name="extNetPrice_t_c",
                section="Summary",
                expected=round(api_ext_net_f, 2) if api_ext_net_f is not None else None,
                found=round(pdf_net_f, 2) if pdf_net_f is not None else None,
                match=floats_match(api_ext_net_f, pdf_net_f, config.validation_rules.numeric_tolerance),
            )
        )
    
    # Desired Net Price
    api_desired_net = api_data.get("quoteDesiredNetPrice_t_c")
    if api_desired_net is not None:
        api_desired_net_f = parse_currency(str(api_desired_net) if not isinstance(api_desired_net, (int, float)) else api_desired_net)
        results.append(
            FieldResult(
                field_name="quoteDesiredNetPrice_t_c",
                section="Summary",
                expected=round(api_desired_net_f, 2) if api_desired_net_f is not None else None,
                found=round(pdf_net_f, 2) if pdf_net_f is not None else None,
                match=floats_match(api_desired_net_f, pdf_net_f, config.validation_rules.numeric_tolerance),
            )
        )

    # Discount % (percentage tolerance)
    api_disc = api_data.get("transactionTotalDiscountPercent_t") or api_data.get("quoteCurrentDiscount_t_c")
    pdf_disc = pdf_data.get("quoteCurrentDiscount_t_c")
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
            section="Summary",
            expected=api_disc_f,
            found=pdf_disc_f,
            match=floats_match(api_disc_f, pdf_disc_f, config.validation_rules.percentage_tolerance),
        )
    )

    # Currency (exact string)
    api_currency = (
        (api_data.get("currency_t") or {}).get("value")
        if isinstance(api_data.get("currency_t"), dict)
        else api_data.get("currency_t")
    )
    results.append(
        FieldResult(
            field_name="currency_t",
            section="Header",
            expected=api_currency,
            found=pdf_data.get("currency_t"),
            match=strings_equal(api_currency, pdf_data.get("currency_t")),
        )
    )

    # Price List (exact string)
    api_pricelist = (
        (api_data.get("priceList_t_c") or {}).get("value")
        if isinstance(api_data.get("priceList_t_c"), dict)
        else api_data.get("priceList_t_c")
    )
    results.append(
        FieldResult(
            field_name="priceList_t_c",
            section="Header",
            expected=api_pricelist,
            found=pdf_data.get("priceList_t_c"),
            match=strings_close(api_pricelist, pdf_data.get("priceList_t_c"), threshold=0.95),
        )
    )

    # Status (exact string)
    api_status_candidates = [
        (api_data.get("quoteStatus_t_c") or {}).get("displayValue") if isinstance(api_data.get("quoteStatus_t_c"), dict) else api_data.get("quoteStatus_t_c"),
        (api_data.get("status_t") or {}).get("displayValue") if isinstance(api_data.get("status_t"), dict) else api_data.get("status_t"),
    ]
    api_status = next((v for v in api_status_candidates if v is not None), None)
    results.append(
        FieldResult(
            field_name="status_t",
            section="Header",
            expected=api_status,
            found=pdf_data.get("status_t"),
            match=strings_close(api_status, pdf_data.get("status_t"), threshold=0.9),
        )
    )

    # Dates (format-agnostic)
    api_created = api_data.get("createdDate_t")
    api_expires = api_data.get("expiresOnDate_t_c")
    results.append(
        FieldResult(
            field_name="createdDate_t",
            section="Header",
            expected=api_created,
            found=pdf_data.get("createdDate_t"),
            match=(
                (parse_date(api_created) == parse_date(pdf_data.get("createdDate_t")))
                if (api_created or pdf_data.get("createdDate_t"))
                else True
            ),
        )
    )
    results.append(
        FieldResult(
            field_name="expiresOnDate_t_c",
            section="Header",
            expected=api_expires,
            found=pdf_data.get("expiresOnDate_t_c"),
            match=(
                (parse_date(api_expires) == parse_date(pdf_data.get("expiresOnDate_t_c")))
                if (api_expires or pdf_data.get("expiresOnDate_t_c"))
                else True
            ),
        )
    )

    # Incoterm (exact string, case-insensitive)
    api_incoterm = (
        (api_data.get("incoterm_t_c") or {}).get("displayValue")
        if isinstance(api_data.get("incoterm_t_c"), dict)
        else api_data.get("incoterm_t_c")
    )
    results.append(
        FieldResult(
            field_name="incoterm_t_c",
            section="Header",
            expected=api_incoterm,
            found=pdf_data.get("incoterm_t_c"),
            match=strings_close(api_incoterm, pdf_data.get("incoterm_t_c"), threshold=0.92),
        )
    )

    # Payment Terms (exact)
    api_payterms = (
        (api_data.get("paymentTerms_t_c") or {}).get("displayValue")
        if isinstance(api_data.get("paymentTerms_t_c"), dict)
        else api_data.get("paymentTerms_t_c")
    )
    results.append(
        FieldResult(
            field_name="paymentTerms_t_c",
            section="Header",
            expected=api_payterms,
            found=pdf_data.get("paymentTerms_t_c"),
            match=strings_close(api_payterms, pdf_data.get("paymentTerms_t_c"), threshold=0.92),
        )
    )

    # Order Type (exact)
    api_order_type = (
        (api_data.get("orderType_t_c") or {}).get("displayValue")
        if isinstance(api_data.get("orderType_t_c"), dict)
        else api_data.get("orderType_t_c")
    )
    results.append(
        FieldResult(
            field_name="orderType_t_c",
            section="Header",
            expected=api_order_type,
            found=pdf_data.get("orderType_t_c"),
            match=strings_close(api_order_type, pdf_data.get("orderType_t_c"), threshold=0.92),
        )
    )

    # Quote Name (exact)
    api_quote_name = api_data.get("quoteNameTextArea_t_c") or api_data.get("transactionName_t")
    results.append(
        FieldResult(
            field_name="quoteNameTextArea_t_c",
            section="Header",
            expected=api_quote_name,
            found=pdf_data.get("quoteNameTextArea_t_c"),
            match=strings_close(api_quote_name, pdf_data.get("quoteNameTextArea_t_c"), threshold=0.9),
        )
    )
    
    # Additional Header Attributes
    additional_header_fields = [
        ("currency_t", "Currency"),
        ("freightTerms_t_c", "Freight Terms"),
        ("contractName_t", "Contract Name"),
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
            results.append(
                FieldResult(
                    field_name=field,
                    section="Header",
                    expected=str(api_val) if api_val is not None else None,
                    found=str(pdf_val) if pdf_val is not None else None,
                    match=strings_close(str(api_val) if api_val else None, str(pdf_val) if pdf_val else None, threshold=0.9),
                )
            )
    
    # Additional Pricing Attributes
    additional_pricing_fields = [
        ("extNetPrice_t_c", "Extended Net Price", True),
        ("quoteDesiredNetPrice_t_c", "Desired Net Price", True),
        ("quoteDesiredDiscount_t_c", "Desired Discount %", False),
    ]
    
    for field, label, is_currency in additional_pricing_fields:
        api_val = api_data.get(field)
        pdf_val = pdf_data.get(field)
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
                    section="Summary",
                    expected=round(api_parsed, 2) if api_parsed is not None else None,
                    found=round(pdf_parsed, 2) if pdf_parsed is not None else None,
                    match=floats_match(api_parsed, pdf_parsed, tolerance) if (api_parsed is not None and pdf_parsed is not None) else False,
                )
            )

    # Line items (optional)
    validate_line_items(config, api_data, pdf_data, results)

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

    # Validate count (optional informational)
    results.append(
        FieldResult(
            field_name="line_items_count",
            section="Lines",
            expected=len(api_lines),
            found=len(pdf_lines),
            match=len(api_lines) == len(pdf_lines),
        )
    )
    
    # Calculate totals from line items for validation
    api_calculated_list_total = 0.0
    api_calculated_net_total = 0.0
    pdf_calculated_list_total = 0.0
    pdf_calculated_net_total = 0.0

    # For each API line, compare against matching PDF part
    for line in api_lines:
        api_part = line.get("_part_number") or line.get("_part_display_number") or line.get("_line_display_name")
        pdf_row = pdf_by_part.get(str(api_part)) if api_part is not None else None

        # Part number presence
        results.append(
            FieldResult(
                field_name="_part_number",
                section="Lines",
                expected=api_part,
                found=pdf_row.get("partNumber") if pdf_row else None,
                match=strings_equal(str(api_part) if api_part is not None else None, pdf_row.get("partNumber") if pdf_row else None),
            )
        )

        # Quantity exact
        api_qty = line.get("_price_quantity") or line.get("_line_bom_item_quantity")
        results.append(
            FieldResult(
                field_name="quantity",
                section="Lines",
                expected=api_qty,
                found=pdf_row.get("quantity") if pdf_row else None,
                match=(int(api_qty) == int(pdf_row.get("quantity"))) if (api_qty is not None and pdf_row and pdf_row.get("quantity") is not None) else False,
            )
        )

        # Unit List Price
        api_ulp = None
        for key in ["_price_item_price_each", "_price_unit_price_each", "_price_list_price_each"]:
            val = line.get(key)
            if isinstance(val, dict) and val.get("value") is not None:
                api_ulp = val.get("value")
                break
        results.append(
            FieldResult(
                field_name="unitListPrice",
                section="Lines",
                expected=api_ulp,
                found=pdf_row.get("unitListPrice") if pdf_row else None,
                match=floats_match(
                    parse_currency(api_ulp if isinstance(api_ulp, str) else str(api_ulp) if api_ulp is not None else None),
                    pdf_row.get("unitListPrice") if pdf_row else None,
                    config.validation_rules.numeric_tolerance,
                ),
            )
        )

        # Unit Net Price
        api_unp = line.get("netPrice_l")
        api_unp_val = api_unp.get("value") if isinstance(api_unp, dict) else None
        results.append(
            FieldResult(
                field_name="unitNetPrice",
                section="Lines",
                expected=api_unp_val,
                found=pdf_row.get("unitNetPrice") if pdf_row else None,
                match=floats_match(
                    parse_currency(str(api_unp_val) if api_unp_val is not None else None),
                    pdf_row.get("unitNetPrice") if pdf_row else None,
                    config.validation_rules.numeric_tolerance,
                ),
            )
        )

        # Extended List Price
        api_xlp = None
        for key in ["_price_extended_price", "extendedListPrice", "listAmount_l"]:
            val = line.get(key)
            if isinstance(val, dict) and val.get("value") is not None:
                api_xlp = val.get("value")
                break
            elif isinstance(val, (int, float)) and val is not None:
                api_xlp = val
                break
        results.append(
            FieldResult(
                field_name="extendedListPrice",
                section="Lines",
                expected=api_xlp,
                found=pdf_row.get("extendedListPrice") if pdf_row else None,
                match=floats_match(
                    parse_currency(str(api_xlp) if api_xlp is not None else None),
                    pdf_row.get("extendedListPrice") if pdf_row else None,
                    config.validation_rules.numeric_tolerance,
                ),
            )
        )

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
        
        results.append(
            FieldResult(
                field_name="extendedNetPrice",
                section="Lines",
                expected=round(api_xnp, 2) if api_xnp is not None else None,
                found=round(pdf_row.get("extendedNetPrice"), 2) if pdf_row and pdf_row.get("extendedNetPrice") is not None else None,
                match=floats_match(
                    parse_currency(str(api_xnp) if api_xnp is not None else None),
                    pdf_row.get("extendedNetPrice") if pdf_row else None,
                    config.validation_rules.numeric_tolerance,
                ),
                message=f"CRITICAL: Extended Net Price = Quantity × Unit Net Price" if not floats_match(
                    parse_currency(str(api_xnp) if api_xnp is not None else None),
                    pdf_row.get("extendedNetPrice") if pdf_row else None,
                    config.validation_rules.numeric_tolerance,
                ) else None,
            )
        )

        # CRITICAL CALCULATION VALIDATION: Extended List = Quantity × Unit List
        if api_qty and api_ulp and pdf_row:
            calculated_ext_list = float(api_qty) * float(api_ulp)
            actual_ext_list = api_xlp or pdf_row.get("extendedListPrice")
            if actual_ext_list:
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
            if actual_ext_net:
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
        results.append(
            FieldResult(
                field_name="discountPercent",
                section="Lines",
                expected=api_disc,
                found=pdf_row.get("discountPercent") if pdf_row else None,
                match=floats_match(
                    float(api_disc) if api_disc is not None else None,
                    float(pdf_row.get("discountPercent")) if (pdf_row and pdf_row.get("discountPercent") is not None) else None,
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
            results.append(
                FieldResult(
                    field_name=f"listPrice_l_c_{api_part}",
                    section="Lines",
                    expected=round(api_list_price_line, 2),
                    found=round(pdf_row.get("extendedListPrice"), 2) if pdf_row and pdf_row.get("extendedListPrice") else None,
                    match=floats_match(
                        float(api_list_price_line),
                        pdf_row.get("extendedListPrice") if pdf_row else None,
                        config.validation_rules.numeric_tolerance,
                    ),
                )
            )
        
        # Check rollUpNetPrice_l_c
        api_rollup_net = line.get("rollUpNetPrice_l_c")
        if isinstance(api_rollup_net, (int, float)) and api_rollup_net != 0:
            results.append(
                FieldResult(
                    field_name=f"rollUpNetPrice_l_c_{api_part}",
                    section="Lines",
                    expected=round(api_rollup_net, 2),
                    found=round(pdf_row.get("extendedNetPrice"), 2) if pdf_row and pdf_row.get("extendedNetPrice") else None,
                    match=floats_match(
                        float(api_rollup_net),
                        pdf_row.get("extendedNetPrice") if pdf_row else None,
                        config.validation_rules.numeric_tolerance,
                    ),
                )
            )
        
        # Check rollUpResUnitNetPrice_l_c (reseller unit net)
        api_res_unit_net = line.get("rollUpResUnitNetPrice_l_c")
        if isinstance(api_res_unit_net, (int, float)) and api_res_unit_net != 0:
            results.append(
                FieldResult(
                    field_name=f"rollUpResUnitNetPrice_l_c_{api_part}",
                    section="Lines",
                    expected=round(api_res_unit_net, 2),
                    found=round(pdf_row.get("unitNetPrice"), 2) if pdf_row and pdf_row.get("unitNetPrice") else None,
                    match=floats_match(
                        float(api_res_unit_net),
                        pdf_row.get("unitNetPrice") if pdf_row else None,
                        config.validation_rules.numeric_tolerance,
                    ),
                )
            )
        
        # Check storageTotal_l_c, serviceTotal_l_c, hardwareTotal_l_c
        for field, label in [
            ("storageTotal_l_c", "Storage Total"),
            ("serviceTotal_l_c", "Service Total"),
            ("hardwareTotal_l_c", "Hardware Total"),
        ]:
            api_total = line.get(field)
            if isinstance(api_total, (int, float)) and api_total != 0:
                results.append(
                    FieldResult(
                        field_name=f"{field}_{api_part}",
                        section="Line Totals",
                        expected=round(api_total, 2),
                        found=None,  # Excel may not have these breakdowns
                        match=True,  # Informational only
                    )
                )
        
    
    # VALIDATE GRAND TOTALS: Sum of all line items should match grand totals
    # Get API grand totals
    api_list_total = api_data.get("quoteListPrice_t_c") or api_data.get("totalOneTimeListAmount_t")
    if isinstance(api_list_total, dict):
        api_list_total = api_list_total.get("value")
    api_net_total = api_data.get("quoteNetPrice_t_c") or api_data.get("totalOneTimeNetAmount_t") or api_data.get("_transaction_total")
    if isinstance(api_net_total, dict):
        api_net_total = api_net_total.get("value")
    
    # Get PDF grand totals
    pdf_list_total = pdf_data.get("quoteListPrice_t_c")
    pdf_net_total = pdf_data.get("quoteNetPrice_t_c")
    
    # CRITICAL: Validate calculated totals match grand totals
    # This ensures that sum of all line item extended prices = grand total
    if api_calculated_list_total > 0 and api_list_total:
        api_list_total_parsed = parse_currency(str(api_list_total) if not isinstance(api_list_total, (int, float)) else api_list_total)
        match = floats_match(api_list_total_parsed, api_calculated_list_total, config.validation_rules.numeric_tolerance)
        results.append(
            FieldResult(
                field_name="calc_grand_list_total",
                section="Calculations",
                expected=round(api_list_total_parsed, 2) if api_list_total_parsed else None,
                found=round(api_calculated_list_total, 2),
                match=match,
                message=f"CRITICAL: List Grand Total ({api_list_total_parsed:.2f}) should equal sum of all Extended List Prices ({api_calculated_list_total:.2f})" if not match else f"Sum of Extended List Prices = {api_calculated_list_total:.2f}",
            )
        )
    
    if api_calculated_net_total > 0 and api_net_total:
        api_net_total_parsed = parse_currency(str(api_net_total) if not isinstance(api_net_total, (int, float)) else api_net_total)
        match = floats_match(api_net_total_parsed, api_calculated_net_total, config.validation_rules.numeric_tolerance)
        results.append(
            FieldResult(
                field_name="calc_grand_net_total",
                section="Calculations",
                expected=round(api_net_total_parsed, 2) if api_net_total_parsed else None,
                found=round(api_calculated_net_total, 2),
                match=match,
                message=f"CRITICAL: Net Grand Total ({api_net_total_parsed:.2f}) should equal sum of all Extended Net Prices ({api_calculated_net_total:.2f})" if not match else f"Sum of Extended Net Prices = {api_calculated_net_total:.2f}",
            )
        )
    
    # Validate PDF calculated totals
    if pdf_calculated_list_total > 0 and pdf_list_total:
        results.append(
            FieldResult(
                field_name="calc_pdf_list_total",
                section="Calculations",
                expected=round(float(pdf_list_total), 2),
                found=round(pdf_calculated_list_total, 2),
                match=floats_match(float(pdf_list_total), pdf_calculated_list_total, config.validation_rules.numeric_tolerance),
                message=f"Excel: Sum of Extended List Prices = {pdf_calculated_list_total:.2f}",
            )
        )
    
    if pdf_calculated_net_total > 0 and pdf_net_total:
        results.append(
            FieldResult(
                field_name="calc_pdf_net_total",
                section="Calculations",
                expected=round(float(pdf_net_total), 2),
                found=round(pdf_calculated_net_total, 2),
                match=floats_match(float(pdf_net_total), pdf_calculated_net_total, config.validation_rules.numeric_tolerance),
                message=f"Excel: Sum of Extended Net Prices = {pdf_calculated_net_total:.2f}",
            )
        )
    
    # Validate discount calculation
    if api_list_total and api_net_total:
        api_calc_discount = ((float(api_list_total) - float(api_net_total)) / float(api_list_total)) * 100
        api_discount = api_data.get("transactionTotalDiscountPercent_t") or api_data.get("quoteCurrentDiscount_t_c")
        if isinstance(api_discount, dict):
            api_discount = api_discount.get("value")
        if api_discount:
            results.append(
                FieldResult(
                    field_name="calc_discount_percent",
                    section="Calculations",
                    expected=round(float(api_discount), 2),
                    found=round(api_calc_discount, 2),
                    match=floats_match(float(api_discount), api_calc_discount, config.validation_rules.percentage_tolerance),
                    message=f"(List {api_list_total} - Net {api_net_total}) / List × 100 = {api_calc_discount:.2f}%",
                )
            )


