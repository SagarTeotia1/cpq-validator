from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from getpass import getpass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from api_client import (
    CPQAuthError,
    CPQClient,
    CPQConnectionError,
    CPQNotFoundError,
    CPQServerError,
)
from config import AppConfig
from excel_parser import extract_excel_data
from pdf_parser import extract_pdf_data
from report_generator import generate_report
from validator import validate_quote


def _maybe_unwrap_value(value: Any) -> Any:
    if isinstance(value, dict) and "value" in value:
        return value.get("value")
    return value


def build_structured_api_payload(
    api_data: dict[str, Any],
    transaction_id: str,
    base_url: str,
) -> dict[str, Any]:
    """Shape the API response into an easy-to-read structure."""
    quote_number = (
        api_data.get("quoteNumber_t_c")
        or api_data.get("_document_number")
        or api_data.get("_id")
    )
    quote_name = api_data.get("quoteNameTextArea_t_c") or api_data.get("transactionName_t")
    status = api_data.get("quoteStatus_t_c") or api_data.get("status_t")

    list_price = _maybe_unwrap_value(
        api_data.get("quoteListPrice_t_c") or api_data.get("totalOneTimeListAmount_t")
    )
    net_price = _maybe_unwrap_value(
        api_data.get("quoteNetPrice_t_c")
        or api_data.get("totalOneTimeNetAmount_t")
        or api_data.get("_transaction_total")
    )
    discount = _maybe_unwrap_value(
        api_data.get("quoteCurrentDiscount_t_c")
        or api_data.get("transactionTotalDiscountPercent_t")
    )

    line_items: list[Any] = []
    line_container = api_data.get("transactionLine")
    if isinstance(line_container, dict):
        items = line_container.get("items")
        if isinstance(items, list):
            line_items = items
    elif isinstance(line_container, list):
        line_items = line_container
    elif isinstance(api_data.get("items"), list):
        line_items = api_data["items"]  # type: ignore[assignment]

    payload: dict[str, Any] = {
        "metadata": {
            "source": "CPQ REST API",
            "base_url": base_url,
            "transaction_id": transaction_id,
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        },
        "quote_data": {
            "quote_number": quote_number,
            "transaction_id": (
                api_data.get("transactionID_t")
                or api_data.get("quoteTransactionID_t_c")
                or api_data.get("bs_id")
            ),
            "quote_name": quote_name,
            "status": status,
            "created_date": api_data.get("createdDate_t"),
            "expires_date": api_data.get("expiresOnDate_t_c"),
            "currency": api_data.get("currency_t"),
            "price_list": api_data.get("priceList_t_c"),
            "incoterm": api_data.get("incoterm_t_c"),
            "payment_terms": api_data.get("paymentTerms_t_c"),
            "order_type": api_data.get("orderType_t_c"),
            "list_price": list_price,
            "net_price": net_price,
            "discount": discount,
        },
        "line_items": line_items,
        "raw_response": api_data,
    }
    return payload


def build_document_payload(
    doc_data: dict[str, Any],
    source_file: str,
    source_kind: str,
) -> dict[str, Any]:
    """Wrap parsed document fields with metadata for easier inspection."""
    line_items = doc_data.get("line_items")
    if isinstance(line_items, list):
        items = line_items
    else:
        items = []

    header_fields = {k: v for k, v in doc_data.items() if k != "line_items"}

    return {
        "metadata": {
            "source_file": source_file,
            "source_type": source_kind,
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "field_count": len(header_fields),
            "line_item_count": len(items),
        },
        "header_fields": header_fields,
        "line_items": items,
    }


def write_binary_file(target_path: str, content: bytes) -> str:
    """Write binary content to disk. On Windows, fall back to suffixed name if locked."""
    try:
        with open(target_path, "wb") as fh:
            fh.write(content)
        return target_path
    except PermissionError:
        base, ext = os.path.splitext(target_path)
        for i in range(1, 10):
            alt = f"{base} ({i}){ext}"
            try:
                with open(alt, "wb") as fh:
                    fh.write(content)
                return alt
            except PermissionError:
                continue
        raise SystemExit(
            f"Unable to write file to {target_path}. Close the file if it is open and try again."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="CPQ Quote Validation System")
    parser.add_argument("--pdf", required=True, help="Path to quote document (PDF or Excel)")
    parser.add_argument("--transaction-id", required=True, help="CPQ Transaction ID")
    parser.add_argument("--config", required=False, help="Optional JSON config path")
    parser.add_argument("--out", required=False, help="Output PDF path (default: auto)")
    parser.add_argument("--xlsx", required=False, help="Output XLSX path (optional)")
    parser.add_argument("--json", required=False, help="Output JSON result path (optional)")
    parser.add_argument(
        "--api-json",
        required=False,
        help="Optional path to write structured API data snapshot",
    )
    parser.add_argument(
        "--doc-json",
        required=False,
        help="Optional path to write parsed document snapshot",
    )
    parser.add_argument(
        "--all-artifacts",
        action="store_true",
        help="Generate PDF, XLSX, validation JSON, structured API JSON, and parsed document JSON together",
    )
    args = parser.parse_args()

    load_dotenv()

    # Input validation
    pdf_path = Path(args.pdf)
    if not pdf_path.exists() or not pdf_path.is_file():
        raise SystemExit("PDF file is missing or not a file")
    if pdf_path.stat().st_size == 0:
        raise SystemExit("PDF file is empty")
    if pdf_path.stat().st_size > 10 * 1024 * 1024:
        raise SystemExit("PDF exceeds 10MB limit")
    if not args.transaction_id.isdigit():
        # Some environments use non-numeric IDs; allow but warn. Here we enforce numeric as requested.
        raise SystemExit("Invalid Transaction ID format: must be numeric")

    cfg = AppConfig.from_env_and_file(args.config)

    # Prompt for Basic Auth if neither Bearer nor Basic provided
    if not cfg.api.bearer_token and not (cfg.api.username and cfg.api.password):
        print("Enter CPQ API credentials (Basic Auth). Leave blank to skip.")
        username = input("Username: ").strip()
        if username:
            password = getpass("Password: ")
            cfg.api.username = username
            cfg.api.password = password

    client = CPQClient(cfg)

    try:
        api_data: dict[str, Any] = client.fetch_transaction_data(args.transaction_id)
        # Also fetch transaction lines and attach for validation if accessible
        try:
            lines = client.fetch_transaction_lines(args.transaction_id)
            api_data["transactionLine"] = lines
        except Exception:
            pass
    except CPQNotFoundError as e:
        raise SystemExit(str(e))
    except CPQAuthError as e:
        raise SystemExit(str(e))
    except CPQConnectionError as e:
        raise SystemExit(str(e))
    except CPQServerError as e:
        raise SystemExit(str(e))

    # Read document bytes
    with open(pdf_path, "rb") as f:
        doc_bytes = f.read()

    # Choose parser by extension
    suffix = pdf_path.suffix.lower()
    if suffix in [".xls", ".xlsx"]:
        pdf_data = extract_excel_data(doc_bytes)
    else:
        pdf_data = extract_pdf_data(doc_bytes)

    # Validate minimal fields
    result = validate_quote(cfg, api_data, pdf_data, transaction_id=args.transaction_id, pdf_filename=pdf_path.name)

    # Generate report PDF
    pdf_report_bytes = generate_report(result)
    out_path = args.out or f"{pdf_path.stem}_validated_{args.transaction_id}.pdf"
    with open(out_path, "wb") as f:
        f.write(pdf_report_bytes)

    # Determine artifact outputs
    suffix = pdf_path.suffix.lower()
    derived_json_path = args.json
    derived_xlsx_path = args.xlsx
    derived_api_json_path = args.api_json
    derived_doc_json_path = args.doc_json

    if args.all_artifacts:
        if not derived_json_path:
            derived_json_path = f"{pdf_path.stem}_validation_results.json"
        if not derived_xlsx_path:
            derived_xlsx_path = f"{pdf_path.stem}_validation_results.xlsx"
        if not derived_api_json_path:
            derived_api_json_path = f"{args.transaction_id}_api_snapshot.json"
        if not derived_doc_json_path:
            source_kind = "excel" if suffix in {".xls", ".xlsx"} else "pdf"
            derived_doc_json_path = f"{pdf_path.stem}_{source_kind}_parsed.json"

    # Optional XLSX report
    final_xlsx_path: str | None = None
    if derived_xlsx_path:
        from report_generator import generate_xlsx

        xlsx_bytes = generate_xlsx(result)
        final_xlsx_path = write_binary_file(derived_xlsx_path, xlsx_bytes)

    # Optional JSON output
    if derived_json_path:
        serializable = {
            "overall_status": result.overall_status,
            "total_checked": result.total_checked,
            "matches": result.matches,
            "mismatches": result.mismatches,
            "transaction_id": result.transaction_id,
            "pdf_filename": result.pdf_filename,
            "details": [
                {
                    "field_name": d.field_name,
                    "section": d.section,
                    "expected": d.expected,
                    "found": d.found,
                    "match": d.match,
                    "page": d.page,
                    "message": d.message,
                }
                for d in result.details
            ],
        }
        with open(derived_json_path, "w", encoding="utf-8") as jf:
            json.dump(serializable, jf, indent=2)

    # Structured API snapshot
    if derived_api_json_path:
        structured_api = build_structured_api_payload(api_data, args.transaction_id, cfg.api.base_url)
        with open(derived_api_json_path, "w", encoding="utf-8") as jf:
            json.dump(structured_api, jf, indent=2)

    # Parsed document snapshot
    if derived_doc_json_path:
        source_kind = "excel" if suffix in {".xls", ".xlsx"} else "pdf"
        structured_doc = build_document_payload(pdf_data, pdf_path.name, source_kind)
        with open(derived_doc_json_path, "w", encoding="utf-8") as jf:
            json.dump(structured_doc, jf, indent=2)

    print(f"Validation {result.overall_status}. Matches: {result.matches}, Mismatches: {result.mismatches}.")
    print(f"Report written to: {out_path}")
    if final_xlsx_path:
        print(f"Excel summary written to: {final_xlsx_path}")
    if derived_json_path:
        print(f"JSON summary written to: {derived_json_path}")
    if derived_api_json_path:
        print(f"API snapshot written to: {derived_api_json_path}")
    if derived_doc_json_path:
        print(f"Parsed document JSON written to: {derived_doc_json_path}")


if __name__ == "__main__":
    main()


