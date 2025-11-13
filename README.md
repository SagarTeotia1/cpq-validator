# CPQ Quote Validation System

Validate customer quotes by comparing document values (PDF or Excel export) against CPQ API data, then generate a concise report (PDF and optional XLSX/JSON).

This README explains what the tool does, our approach, how to set it up, how to run it, and how the internals work so you can maintain or extend it easily.

## What this tool does

- Fetches CPQ transaction data from a REST API using a Transaction ID
- Extracts key fields from a quote document (PDF or CPQ-exported XLS/XLSX)
- Compares document values with authoritative API values using lenient, well-defined rules
- Outputs a validation report as PDF, plus optional XLSX and JSON

## Our approach (how we achieved the solution)

- API-first truth: Treat CPQ API as the source of truth. Fetch the transaction via `GET /commerceDocumentsUcpqStandardCommerceProcessTransaction/{transactionId}` and, when available, the child `transactionLine` collection.
- Targeted parsing: Extract only fields needed for validation from the quote PDF/XLS. We use pattern-based text extraction for robustness and table heuristics for line items.
- Pragmatic matching: Use exact or fuzzy matching depending on field type:
  - Text: case-insensitive equality or similarity (`strings_close`) for fields like status, price list, quote name
  - Numbers: tolerant float comparison (`floats_match`) to account for rounding/OCR noise
  - Dates: multiple-format parsing so formatting differences don’t cause false negatives
  - IDs: digit-only normalization for transaction IDs
- Clear reporting: Summarize all checked fields with expected vs found values and a pass/fail indicator. Provide a clean PDF report and optional XLSX for spreadsheet workflows.
- Secure, flexible auth: Prefer Bearer tokens; fall back to Basic Auth. Prompt for credentials if needed.

## Features

- PDF parsing via `pdfplumber` with regex patterns for headers, totals, currency, and dates
- Excel/HTML (.xls/.xlsx) parsing using `pandas.read_html` to detect line item tables
- Line-item validation when both sides provide data (by part number)
- Configurable numeric and percentage tolerances
- Retries and timeouts for API calls
- Report outputs: PDF (always), XLSX/JSON (optional)

## Project structure

- `main.py`: CLI entrypoint (parses args, loads config, runs validation, writes outputs)
- `config.py`: App configuration (API settings, validation rules, parsing hints) + loaders
- `api_client.py`: Authenticated CPQ API client with retry/error handling
- `pdf_parser.py`: Extracts fields and tables from PDFs
- `excel_parser.py`: Extracts fields and tables from CPQ-exported XLS/XLSX
- `validator.py`: Field-by-field comparison logic and line item checks
- `report_generator.py`: PDF and XLSX report builders
- `utils.py`: Helpers for parsing, normalization, tolerant comparisons

## Requirements

- Python 3.9+
- Install dependencies:

```bash
pip install -r requirements.txt
```

On Windows PowerShell, run inside the project directory:

```powershell
python -m pip install -r requirements.txt
```

## Configuration

You can configure via environment variables, a JSON config file, or both (env overrides file). We also load `.env` if present (via `python-dotenv`).

### Environment variables

```bash
CPQ_BASE_URL=https://netappinctest3.bigmachines.com/rest/v16
CPQ_BEARER_TOKEN=<your_token>       # preferred
# or Basic Auth
CPQ_USERNAME=<username>
CPQ_PASSWORD=<password>

# Optional tuning
CPQ_TIMEOUT=30
CPQ_RETRY_ATTEMPTS=3
```

You may create a `.env` file with the same keys for local development.

### JSON config file

Pass `--config path/to/config.json` to override defaults. Example:

```json
{
  "api": {
    "base_url": "https://netappinctest3.bigmachines.com/rest/v16",
    "timeout": 30,
    "retry_attempts": 3,
    "bearer_token": null,
    "username": null,
    "password": null
  },
  "validation_rules": {
    "numeric_tolerance": 0.01,
    "percentage_tolerance": 0.01,
    "date_formats": ["YYYY-MM-DD", "DD/MM/YYYY", "MM-DD-YYYY", "YYYY/MM/DD"],
    "currency_symbols": ["$", "€", "₹", "INR", "USD"]
  },
  "pdf_parsing": {
    "line_item_table_header": ["Part Number", "Description", "Qty", "Unit Price"],
    "summary_keywords": ["Total", "Grand Total", "Net Amount", "Net Price"]
  }
}
```

## Usage

CLI requires a document and a Transaction ID. The document can be a PDF or an Excel export (`.xls`/`.xlsx`) even though the flag is named `--pdf`.

```bash
python main.py --pdf "./Quote173670.pdf" --transaction-id 481320048
```

Optional outputs and config:

```bash
python main.py \
  --pdf "./Quote173670.pdf" \
  --transaction-id 481320048 \
  --config ./config.json \
  --out ./Validated_173670.pdf \
  --xlsx ./Validated_173670.xlsx \
  --json ./result.json \
  --api-json ./api_snapshot.json \
  --doc-json ./quote_parsed.json
```

Behavior:

- Always writes a validation PDF (default name: `<input_stem>_validated_<txid>.pdf`)
- If `--xlsx` is provided, writes an XLSX details report
- If `--json` is provided, writes a machine-readable summary
- `--api-json` writes a structured snapshot of the fetched CPQ API payload
- `--doc-json` writes the parsed fields and line items extracted from the quote document
- `--all-artifacts` generates every optional output automatically with sensible default filenames

On first run, if neither Bearer token nor Basic Auth are set, you’ll be prompted for username/password.

## What gets validated

Header-level fields (when present):

- `quoteNumber_t_c`: fuzzy text match (handles case and minor differences)
- `transactionID_t`: digit-only exact match across several CPQ API candidate fields
- `quoteNetPrice_t_c`, `quoteListPrice_t_c`: tolerant numeric match with currency parsing
- `quoteCurrentDiscount_t_c`: tolerant percentage match
- `currency_t`, `priceList_t_c`, `status_t`, `createdDate_t`, `expiresOnDate_t_c`, `quoteNameTextArea_t_c`, `incoterm_t_c`, `paymentTerms_t_c`, `orderType_t_c`: exact, fuzzy, or format-agnostic comparisons as appropriate

Line items (when available on both sides):

- Match rows by `partNumber`
- Validate quantity, unit list/net prices, extended prices, discount percent with numeric tolerances
- Include an informational check of line count parity

## API endpoints used

- `GET {BASE_URL}/commerceDocumentsUcpqStandardCommerceProcessTransaction/{transactionId}`
- `GET {BASE_URL}/commerceDocumentsUcpqStandardCommerceProcessTransaction/{transactionId}/transactionLine`

Auth:

- Prefer `Authorization: Bearer <token>`
- Fallback: HTTP Basic Auth (username/password)

## Error handling

- 404 → clean "Transaction ID not found"
- 401 → authentication error guidance
- 5xx → surfaced as server error
- Network timeouts and connection errors → limited retries with backoff
- Input validation: missing/empty/oversize files, Transaction ID format check

## Output formats

- PDF: Summary table of all fields with ✓/✗, plus metadata (transaction ID, file name, counts)
- XLSX (optional): Summary sheet + detailed sheet with conditional formatting (green/red)
- JSON (optional): Machine-readable summary with all field details

## Troubleshooting

- Authentication:
  - Prefer setting `CPQ_BEARER_TOKEN`. If unavailable, set `CPQ_USERNAME`/`CPQ_PASSWORD` or enter when prompted.
- Cannot write XLSX:
  - If the target file is open on Windows, the tool writes `(<n>)` suffixed alternatives automatically. Close the file and rerun if needed.
- PDF text not detected:
  - Some PDFs are image-based; OCR is out of scope for now. If values aren’t detected, try the Excel export path.
- Different field names:
  - The validator already checks multiple candidate API keys for many fields; extend `validator.py` if your CPQ has custom names.

## Extending the validator

- Add new header fields: update `pdf_parser.py`/`excel_parser.py` to extract them, then add comparison logic in `validator.py`.
- Adjust tolerances: change `numeric_tolerance` or `percentage_tolerance` in config.
- Change output layout: edit `report_generator.py` for PDF/XLSX formatting.

## License

Proprietary/Internal use unless stated otherwise.

