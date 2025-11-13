"""Comprehensive attribute extraction from API response"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def extract_all_attributes(api_data: Dict[str, Any]) -> Dict[str, Any]:
    """Extract ALL possible attributes from API response, organized by category."""
    attributes = {
        "header": {},
        "pricing": {},
        "dates": {},
        "accounting": {},
        "approval": {},
        "metadata": {},
        "line_item_attributes": [],
    }
    
    # HEADER ATTRIBUTES
    header_fields = [
        "quoteNumber_t_c",
        "quoteNameTextArea_t_c",
        "transactionID_t",
        "quoteTransactionID_t_c",
        "bs_id",
        "_id",
        "_document_number",
        "status_t",
        "quoteStatus_t_c",
        "currency_t",
        "priceList_t_c",
        "quotePricelist_t_c",
        "incoterm_t_c",
        "orderType_t_c",
        "paymentTerms_t_c",
        "freightTerms_t_c",
        "sellingMotion_t_c",
        "district_t_c",
        "contractName_t",
        "legalEntities_t_c",
        "contractEntityCompanyCMATName_t_c",
        "endCustomer_t_c",
        "endCustomerCMR_t_c",
        "endCustomerCmrId_t_c",
        "dealRegID_t_c",
        "quoteType_t_c",
        "internalOrderType_t_c",
        "opptyTerritoryId_t_c",
        "salesRepEmailId_t_c",
        "lastUpdatedBy_t",
        "submittedBy_t_c",
        "oMUser_t_c",
        "projectCode_t_c",
        "multiQuoteName_t_c",
        "multiQuoteDeal_t_c",
        "addOnQuoteNumbers_t_c",
        "lineItemNumbers_t_c",
        "quoteIDsOnMQ_t_c",
    ]
    
    for field in header_fields:
        val = api_data.get(field)
        if val is not None:
            if isinstance(val, dict):
                attributes["header"][field] = val.get("value") or val.get("displayValue") or val
            else:
                attributes["header"][field] = val
    
    # PRICING ATTRIBUTES
    pricing_fields = [
        # Grand Totals
        "quoteListPrice_t_c",
        "quoteNetPrice_t_c",
        "extNetPrice_t_c",
        "netPrice_t_c",
        "totalOneTimeListAmount_t",
        "totalOneTimeNetAmount_t",
        "totalOneTimeCostAmount_t",
        "totalOneTimeDiscount_t",
        "totalOneTimeMarginAmount_t",
        "totalContractListValue_t_c",
        "totalContractCostAmount_t",
        "totalListPrice_t_c",
        "totalNetPrice_t_c",
        "totalMonthlyNetAmount_t",
        "totalMonthlyCostAmount_t",
        "totalMonthlyUsageRev_t",
        "totalARR_t_c",
        "totalAnnualValue_t",
        "totalRecurRevenue_t",
        # Discounts
        "quoteCurrentDiscount_t_c",
        "transactionTotalDiscountPercent_t",
        "quoteDesiredDiscount_t_c",
        "totalMonthlyDiscount_t",
        "discountAmount_t_c",
        "discountAmountUSD_t_c",
        # Desired/Adjusted Prices
        "quoteDesiredNetPrice_t_c",
        "quotedesiredNetPriceUSD_t_c",
        # Margins
        "standardProductMarginUSD_t_c",
        "standardProductMargin_t_c",
        "standardProductMarginPercentage_t_c",
        "fullStackMarginUSD_t_c",
        "fullStackMargin_t_c",
        "fullStackMarginPercent_t_c",
        "quoteSuggestedMargin_t_c",
        # Costs
        "stdProductCost_t_c",
        "fullStackStandardCostUSD_t_c",
        "fullStackOnlyCost_t_c",
        "standardProductCost_t_c",
        # Other Pricing
        "quoteFullStackOnlyNetPrice_t_c",
        "guidanceToGreenAmount_t_c",
        "guidanceToYellowAmount_t_c",
        "guidanceToOrangeAmount_t_c",
        "quoteTotalCapacityGB_t_c",
        "quoteDollarPerGBTotal_t_c",
        "quoteGuidanceToGreen_t_c",
        "quoteMinMarginViolation_t_c",
        "priceWithinPolicy_t",
        "freezePriceFlag_t",
        "_freezePrice",
        "priceExpirationDate_t",
        "priceJustification_t_c",
        "justification_t_c",
        "quoteAdjustmentMethod_t_c",
        "quoteDiscountPolicyViolation_t_c",
        "customDiscountPresent_t_c",
        "discountByCategory_t_c",
        "priceScore_t",
        "priceType_t",
        "quoteDesiredValuesJSON_t_c",
        "previousQuoteDesiredValuesJSON_t_c",
    ]
    
    for field in pricing_fields:
        val = api_data.get(field)
        if val is not None:
            if isinstance(val, dict):
                attributes["pricing"][field] = val.get("value") or val.get("displayValue") or val
            else:
                attributes["pricing"][field] = val
    
    # DATE ATTRIBUTES
    date_fields = [
        "createdDate_t",
        "expiresOnDate_t_c",
        "contractStartDate_t",
        "contractEndDate_t",
        "lastUpdatedDate_t",
        "lastConfigEditDate_t_c",
        "lastPricedDate_t",
        "evaluationStartDate_t_c",
        "evalDuration_t_c",
        "requested_shipping_date_prebuild_t_c",
        "editServiceDate_t_c",
        "priceExpirationDate_t",
    ]
    
    for field in date_fields:
        val = api_data.get(field)
        if val is not None:
            attributes["dates"][field] = val
    
    # ACCOUNTING/BILLING ATTRIBUTES
    accounting_fields = [
        "oRCL_ERP_OrderID_t",
        "oRCL_ERP_OrderNumber_l",
        "pOFromResellerHeader_t_c",
        "pOFromDistributorHeader_t_c",
        "costCenter_t_c",
        "costCentreDescription_t_c",
        "accountStrategyCustomerPosition_t_c",
    ]
    
    for field in accounting_fields:
        val = api_data.get(field)
        if val is not None:
            attributes["accounting"][field] = val
    
    # APPROVAL ATTRIBUTES
    approval_fields = [
        "approval_status_submittest_c",
        "internalRepApprovalPending_t_c",
        "bDApproverPending_t_c",
        "partnerInvokedApproval_t_c",
        "rejectionComments_t_c",
        "approvalCommentsEmailNew_t_c",
        "changeRequestStatus_t_c",
        "presentedToCustomer_t_c",
        "proposalExists_t",
        "previousReviewReasons_t_c",
    ]
    
    for field in approval_fields:
        val = api_data.get(field)
        if val is not None:
            attributes["approval"][field] = val
    
    # METADATA ATTRIBUTES
    metadata_fields = [
        "_url",
        "_timestamp",
        "_transaction_id",
        "version_number_createUSDQuote_c",
        "quoteadvisorHTML_t_c",
        "accountArrayHTML_t_c",
        "pricingTargetAttributeLookup_c",
        "lineLockDiscountMessagesJSON_t_c",
        "lSCProgramDiscountInfo_t_c",
        "gTCRiskMessageString_t_c",
        "priceListWarningMessages_t_c",
        "discountingDisplayMessages_t_c",
        "discountingDisplayMessagesHTML_t_c",
        "quoteDesiredValuesJSON_t_c",
        "previousQuoteDesiredValuesJSON_t_c",
    ]
    
    for field in metadata_fields:
        val = api_data.get(field)
        if val is not None:
            attributes["metadata"][field] = val
    
    # LINE ITEM ATTRIBUTES (extract from transactionLine)
    line_items = api_data.get("transactionLine", {})
    if isinstance(line_items, dict) and "items" in line_items:
        for item in line_items.get("items", []):
            line_attrs = extract_line_item_attributes(item)
            if line_attrs:
                attributes["line_item_attributes"].append(line_attrs)
    
    return attributes


def extract_line_item_attributes(line: Dict[str, Any]) -> Dict[str, Any]:
    """Extract ALL attributes from a single line item."""
    attrs = {}
    
    # Basic identifiers
    identifier_fields = [
        "_part_number",
        "_part_display_number",
        "_line_display_name",
        "_line_bom_part_number",
        "originalPartNumber_l_c",
        "partDescription_l_c",
        "_document_number",
        "_id",
        "_bs_id",
        "virtualLineID_l_c",
        "virtualConfigName_l_c",
        "originalVirtualConfigName_l_c",
        "lineSequenceNumber_l_c",
        "_sequence_number",
        "_group_sequence_number",
    ]
    
    for field in identifier_fields:
        val = line.get(field)
        if val is not None:
            attrs[field] = val
    
    # Quantity
    qty_fields = ["_price_quantity", "_line_bom_item_quantity", "quantity", "desiredQuantity_l_c", "addedQuantity_l_c", "assetOriginalQuantity_l_c", "assetAmendedQty_l_c"]
    for field in qty_fields:
        val = line.get(field)
        if val is not None:
            attrs[field] = val
            break
    
    # Pricing - Unit List
    unit_list_fields = ["_price_item_price_each", "_price_unit_price_each", "_price_list_price_each", "_pricing_rule_price_each"]
    for field in unit_list_fields:
        val = line.get(field)
        if val is not None:
            if isinstance(val, dict):
                attrs[field] = val.get("value")
                attrs[f"{field}_currency"] = val.get("currency")
            else:
                attrs[field] = val
            break
    
    # Pricing - Unit Net
    unit_net_fields = ["netPrice_l", "netPrice_l_c", "rollUpResUnitNetPrice_l_c", "resellerUnitNetPricefloat_l_c", "endCustomerUnitNetPricefloat_l_c"]
    for field in unit_net_fields:
        val = line.get(field)
        if val is not None and val != 0:
            attrs[field] = val
            break
    
    # Pricing - Extended List
    ext_list_fields = ["_price_extended_price", "extListPrice_l_c", "listAmount_l", "listPriceRollup_l", "listPrice_l_c"]
    for field in ext_list_fields:
        val = line.get(field)
        if val is not None and val != 0:
            attrs[field] = val
            break
    
    # Pricing - Extended Net
    ext_net_fields = ["netAmount_l", "netAmountRollup_l", "netPriceRollup_l", "extendedNetPriceUSD_l_c", "rollUpNetPrice_l_c", "extNetPriceWOMarkupPriceDefinition_l_c"]
    for field in ext_net_fields:
        val = line.get(field)
        if val is not None and val != 0:
            attrs[field] = val
            break
    
    # Discounts
    discount_fields = ["discountPercent_l", "currentDiscount_l_c", "currentDiscountEndCustomer_l_c", "discountPercentRollup_l", "discountAmount_l", "promoDiscount_l_c", "directDiscount_l_c", "annualDiscount_l", "contractDiscount_l"]
    for field in discount_fields:
        val = line.get(field)
        if val is not None:
            attrs[field] = val
    
    # Totals by category
    total_fields = ["hardwareTotal_l_c", "serviceTotal_l_c", "storageTotal_l_c", "oSCapacityTotal_l_c", "contractValue_l", "contractValueRollup_l", "annualListValue_l"]
    for field in total_fields:
        val = line.get(field)
        if val is not None and val != 0:
            attrs[field] = val
    
    # Costs
    cost_fields = ["unitCost_l", "unitCost_l_c", "contractCost_l"]
    for field in cost_fields:
        val = line.get(field)
        if val is not None and val != 0:
            attrs[field] = val
    
    # Dates
    date_fields = ["contractStartDate_l", "contractEndDate_l", "requestShipDate_l", "renewDate_l", "resumeDate_l", "lastUpdatedDate_l", "activationDate_l_c", "softwareStartDate_l_c", "eLAESAStartDate_l_c", "eLAESAEndDate_l_c", "eOSLDate_l_c", "renewalStartDate_l_c", "renewalServiceEndDate_l_c"]
    for field in date_fields:
        val = line.get(field)
        if val is not None:
            attrs[field] = val
    
    # Status and flags
    status_fields = ["status_l", "fulfillmentStatus_l", "configStatus_l_c", "lineOrderableFlag_l_c", "bundleChild_l_c", "fullStackOnly_l_c", "hasChildren_l_c", "priceWithinPolicy_l", "pricesCalculated__l_c", "lineDefaultsSet_l_c", "readOnlyDiscount_l_c", "tierThreeDiscountLock_l_c", "unsavedChanges_l_c", "doNotPrintFlag_l_c", "serviceStartDateFlag_l_c"]
    for field in status_fields:
        val = line.get(field)
        if val is not None:
            attrs[field] = val
    
    # Descriptions and metadata
    desc_fields = ["partDescription_l_c", "_line_description", "_part_extended_desc_1", "_part_extended_desc_2", "_line_item_comment", "summaryPrintLabel_l_c", "attributeMirror_l_c"]
    for field in desc_fields:
        val = line.get(field)
        if val is not None and val:
            attrs[field] = val
    
    # Model/Product info
    model_fields = ["_model_name", "_model_bom", "_model_product_line_name", "_model_product_line_id", "_model_is_valid", "_line_bom_id", "_line_bom_parent_id", "productType_l_c", "partType_l_c", "catalogGroup_l_c", "productGroup_l_c", "productGroupingNetapp_l_c"]
    for field in model_fields:
        val = line.get(field)
        if val is not None:
            attrs[field] = val
    
    return attrs

