from __future__ import annotations

import argparse
import json
import os
from getpass import getpass
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from api_client import CPQClient, CPQAuthError, CPQConnectionError, CPQNotFoundError, CPQServerError
from config import AppConfig
from pdf_parser import extract_pdf_data
from excel_parser import extract_excel_data
from report_generator import generate_report
from validator import validate_quote


def main() -> None:
    parser = argparse.ArgumentParser(description="CPQ Quote Validation System")
    parser.add_argument("--pdf", required=True, help="Path to quote PDF file")
    parser.add_argument("--transaction-id", required=True, help="CPQ Transaction ID")
    parser.add_argument("--config", required=False, help="Optional JSON config path")
    parser.add_argument("--out", required=False, help="Output PDF path (default: auto)")
    parser.add_argument("--xlsx", required=False, help="Output XLSX path (optional)")
    parser.add_argument("--json", required=False, help="Output JSON result path (optional)")
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

    # Optional XLSX report
    if args.xlsx:
        from report_generator import generate_xlsx
        xlsx_bytes = generate_xlsx(result)
        # Handle Windows lock when the file is open: write to a new name if needed
        target_xlsx = args.xlsx
        try:
            with open(target_xlsx, "wb") as xf:
                xf.write(xlsx_bytes)
        except PermissionError:
            base, ext = os.path.splitext(target_xlsx)
            alt_written = False
            for i in range(1, 10):
                alt = f"{base} ({i}){ext}"
                try:
                    with open(alt, "wb") as xf:
                        xf.write(xlsx_bytes)
                    target_xlsx = alt
                    alt_written = True
                    break
                except PermissionError:
                    continue
            if not alt_written:
                raise SystemExit(
                    f"Unable to write XLSX to {args.xlsx}. Close the file if open and try again."
                )

    # Optional JSON output
    if args.json:
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
        with open(args.json, "w", encoding="utf-8") as jf:
            json.dump(serializable, jf, indent=2)

    print(f"Validation {result.overall_status}. Matches: {result.matches}, Mismatches: {result.mismatches}.")
    print(f"Report written to: {out_path}")
    if args.xlsx:
        print(f"XLSX written to: {args.xlsx}")


if __name__ == "__main__":
    main()


