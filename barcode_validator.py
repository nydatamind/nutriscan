"""
barcode_validator.py
====================
Robust, deterministic barcode normalization and checksum validation pipeline
for NutriScan · NY.
DEVELOPED BY NITIN YADAV

Supports:
  - EAN-13 (International Article Number)
  - UPC-A (Universal Product Code - 12 digits, leading zero safe)
  - EAN-8 (Compact 8-digit retail code)
  - GTIN-14 (14-digit Global Trade Item Number)

Key features:
  1. Preserves leading zeros (never casts to int).
  2. Strips whitespace, control characters, and scanner artifacts.
  3. Rejects partial, blurred, truncated, or corrupted scan results via GS1 mod-10 checksums.
  4. Detects GS1 Application Identifiers ((01), etc.).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class BarcodeValidationResult:
    is_valid: bool
    normalized_barcode: str
    format: str
    error_message: Optional[str] = None
    warning: Optional[str] = None

    @property
    def clean_code(self) -> str:
        return self.normalized_barcode


def normalize_barcode_string(raw: str | int | None) -> str:
    """
    Safely clean and normalize raw barcode input.
    Preserves leading zeros and never converts to integer.
    """
    if raw is None:
        return ""
    if isinstance(raw, int):
        # Convert integer to string without losing whatever digits are present
        raw = str(raw)
    else:
        raw = str(raw)

    # Trim whitespace and control characters
    cleaned = raw.strip()

    # Extract GS1 (01) GTIN-14 if embedded with Application Identifier
    gs1_match = re.search(r"(?:/01/|\(01\)|^01)(\d{14})", cleaned)
    if gs1_match:
        gtin14 = gs1_match.group(1)
        if gtin14.startswith("0"):
            return gtin14[1:]
        return gtin14

    # Check if this is an Open Food Facts or retail URL containing barcode query param
    url_match = re.search(r"[?&](?:barcode|gtin|ean|upc)=(\d{8,14})", cleaned, re.IGNORECASE)
    if url_match:
        return url_match.group(1)

    # Remove non-digits for standard retail numeric barcodes
    digits_only = re.sub(r"[^\d]", "", cleaned)
    return digits_only


def calculate_ean13_checksum(digits12: str) -> int:
    """Calculate the 13th check digit for a 12-digit prefix."""
    if len(digits12) != 12 or not digits12.isdigit():
        return -1
    total = sum(
        int(d) * (1 if i % 2 == 0 else 3)
        for i, d in enumerate(digits12)
    )
    return (10 - (total % 10)) % 10


def calculate_upca_checksum(digits11: str) -> int:
    """Calculate the 12th check digit for an 11-digit prefix."""
    if len(digits11) != 11 or not digits11.isdigit():
        return -1
    total = sum(
        int(d) * (3 if i % 2 == 0 else 1)
        for i, d in enumerate(digits11)
    )
    return (10 - (total % 10)) % 10


def calculate_ean8_checksum(digits7: str) -> int:
    """Calculate the 8th check digit for a 7-digit prefix."""
    if len(digits7) != 7 or not digits7.isdigit():
        return -1
    total = sum(
        int(d) * (3 if i % 2 == 0 else 1)
        for i, d in enumerate(digits7)
    )
    return (10 - (total % 10)) % 10


def calculate_gtin14_checksum(digits13: str) -> int:
    """Calculate the 14th check digit for a 13-digit prefix."""
    if len(digits13) != 13 or not digits13.isdigit():
        return -1
    total = sum(
        int(d) * (3 if i % 2 == 0 else 1)
        for i, d in enumerate(digits13)
    )
    return (10 - (total % 10)) % 10


def validate_barcode(raw_barcode: str | int | None) -> BarcodeValidationResult:
    """
    Complete validation pipeline:
      1. Normalize string safely (preserving leading zeros).
      2. Verify length against standard symbologies.
      3. Verify mod-10 checksum according to GS1 specifications.
      4. Detect truncated/partial scans.
    """
    clean = normalize_barcode_string(raw_barcode)

    if not clean:
        return BarcodeValidationResult(
            is_valid=False,
            normalized_barcode="",
            format="UNKNOWN",
            error_message="Empty or missing barcode value.",
        )

    # ── EAN-13 (13 digits) ──────────────────────────────────────────────────
    if len(clean) == 13:
        expected = calculate_ean13_checksum(clean[:12])
        actual = int(clean[12])
        if expected == actual:
            return BarcodeValidationResult(
                is_valid=True,
                normalized_barcode=clean,
                format="EAN-13",
            )
        return BarcodeValidationResult(
            is_valid=False,
            normalized_barcode=clean,
            format="EAN-13",
            error_message=(
                f"Invalid EAN-13 barcode checksum (scanned check digit {actual}, "
                f"expected {expected}). Scanned code may be blurred or truncated."
            ),
        )

    # ── UPC-A (12 digits, often with leading zeros in US/Canada) ─────────────
    if len(clean) == 12:
        expected = calculate_upca_checksum(clean[:11])
        actual = int(clean[11])
        if expected == actual:
            return BarcodeValidationResult(
                is_valid=True,
                normalized_barcode=clean,
                format="UPC-A",
            )
        return BarcodeValidationResult(
            is_valid=False,
            normalized_barcode=clean,
            format="UPC-A",
            error_message=(
                f"Invalid UPC-A barcode checksum (scanned check digit {actual}, "
                f"expected {expected}). Possible partial scan."
            ),
        )

    # ── EAN-8 (8 digits) ────────────────────────────────────────────────────
    if len(clean) == 8:
        expected = calculate_ean8_checksum(clean[:7])
        actual = int(clean[7])
        if expected == actual:
            return BarcodeValidationResult(
                is_valid=True,
                normalized_barcode=clean,
                format="EAN-8",
            )
        return BarcodeValidationResult(
            is_valid=False,
            normalized_barcode=clean,
            format="EAN-8",
            error_message=(
                f"Invalid EAN-8 barcode checksum (scanned check digit {actual}, "
                f"expected {expected})."
            ),
        )

    # ── GTIN-14 (14 digits) ─────────────────────────────────────────────────
    if len(clean) == 14:
        expected = calculate_gtin14_checksum(clean[:13])
        actual = int(clean[13])
        if expected == actual:
            # If leading digit is 0, normalizes to EAN-13
            normalized = clean[1:] if clean.startswith("0") else clean
            return BarcodeValidationResult(
                is_valid=True,
                normalized_barcode=normalized,
                format="GTIN-14" if normalized == clean else "EAN-13",
            )
        return BarcodeValidationResult(
            is_valid=False,
            normalized_barcode=clean,
            format="GTIN-14",
            error_message=(
                f"Invalid GTIN-14 barcode checksum (scanned check digit {actual}, "
                f"expected {expected})."
            ),
        )

    # ── Invalid length (partial or corrupted scan) ───────────────────────────
    return BarcodeValidationResult(
        is_valid=False,
        normalized_barcode=clean,
        format="INVALID_LENGTH",
        error_message=(
            f"Unsupported barcode length ({len(clean)} digits). "
            f"Standard barcodes must be 8 (EAN-8), 12 (UPC-A), 13 (EAN-13), or 14 (GTIN-14) digits. "
            f"Please hold the camera steady to capture the complete barcode."
        ),
    )
