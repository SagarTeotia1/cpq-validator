from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class APIConfig:
    base_url: str = "https://netappinctest3.bigmachines.com/rest/v16"
    timeout: int = 30
    retry_attempts: int = 3
    # Auth
    bearer_token: Optional[str] = None  # Preferred
    username: Optional[str] = None
    password: Optional[str] = None


@dataclass
class ValidationRules:
    numeric_tolerance: float = 0.01
    percentage_tolerance: float = 0.01  # percentage points
    date_formats: List[str] = field(default_factory=lambda: [
        "YYYY-MM-DD",
        "DD/MM/YYYY",
        "MM-DD-YYYY",
        "YYYY/MM/DD",
    ])
    currency_symbols: List[str] = field(default_factory=lambda: [
        "$",
        "€",
        "₹",
        "INR",
        "USD",
    ])


@dataclass
class PDFParsing:
    line_item_table_header: List[str] = field(default_factory=lambda: [
        "Part Number",
        "Description",
        "Qty",
        "Unit Price",
    ])
    summary_keywords: List[str] = field(default_factory=lambda: [
        "Total",
        "Grand Total",
        "Net Amount",
        "Net Price",
    ])


@dataclass
class AppConfig:
    api: APIConfig = field(default_factory=APIConfig)
    validation_rules: ValidationRules = field(default_factory=ValidationRules)
    pdf_parsing: PDFParsing = field(default_factory=PDFParsing)

    @staticmethod
    def from_env_and_file(config_path: Optional[str] = None) -> "AppConfig":
        cfg = AppConfig()

        # Environment variables override defaults
        cfg.api.base_url = os.getenv("CPQ_BASE_URL", cfg.api.base_url)
        cfg.api.timeout = int(os.getenv("CPQ_TIMEOUT", str(cfg.api.timeout)))
        cfg.api.retry_attempts = int(
            os.getenv("CPQ_RETRY_ATTEMPTS", str(cfg.api.retry_attempts))
        )
        cfg.api.bearer_token = os.getenv("CPQ_BEARER_TOKEN") or cfg.api.bearer_token
        cfg.api.username = os.getenv("CPQ_USERNAME") or cfg.api.username
        cfg.api.password = os.getenv("CPQ_PASSWORD") or cfg.api.password

        # Optional JSON config file to override
        if config_path and os.path.isfile(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            api = data.get("api", {})
            vr = data.get("validation_rules", {})
            pp = data.get("pdf_parsing", {})

            cfg.api.base_url = api.get("base_url", cfg.api.base_url)
            cfg.api.timeout = int(api.get("timeout", cfg.api.timeout))
            cfg.api.retry_attempts = int(api.get("retry_attempts", cfg.api.retry_attempts))

            if "bearer_token" in api:
                cfg.api.bearer_token = api["bearer_token"]
            if "username" in api:
                cfg.api.username = api["username"]
            if "password" in api:
                cfg.api.password = api["password"]

            if "numeric_tolerance" in vr:
                cfg.validation_rules.numeric_tolerance = float(vr["numeric_tolerance"])
            if "percentage_tolerance" in vr:
                cfg.validation_rules.percentage_tolerance = float(
                    vr["percentage_tolerance"]
                )
            if "date_formats" in vr:
                cfg.validation_rules.date_formats = list(vr["date_formats"])
            if "currency_symbols" in vr:
                cfg.validation_rules.currency_symbols = list(vr["currency_symbols"])

            if "line_item_table_header" in pp:
                cfg.pdf_parsing.line_item_table_header = list(pp["line_item_table_header"])
            if "summary_keywords" in pp:
                cfg.pdf_parsing.summary_keywords = list(pp["summary_keywords"])

        return cfg


