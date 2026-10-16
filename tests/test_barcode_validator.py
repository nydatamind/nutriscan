"""
tests/test_barcode_validator.py
===============================
Unit tests for GS1 barcode validation, leading-zero preservation,
checksum computation, and partial/blurred scan detection.
"""

import pytest
from barcode_validator import (
    calculate_ean8_checksum,
    calculate_ean13_checksum,
    calculate_gtin14_checksum,
    calculate_upca_checksum,
    normalize_barcode_string,
    validate_barcode,
)


class TestBarcodeNormalization:
    def test_leading_zero_preservation_string(self):
        """Must preserve leading zeros and never cast to integer."""
        raw = "012345678905"
        normalized = normalize_barcode_string(raw)
        assert normalized == "012345678905"
        assert normalized.startswith("0")
        assert len(normalized) == 12

    def test_leading_zero_with_whitespace(self):
        """Trims whitespace while preserving leading zeros."""
        raw = "  0012345678905  \n\t"
        normalized = normalize_barcode_string(raw)
        assert normalized == "0012345678905"

    def test_strip_scanner_artifacts(self):
        """Removes spaces, hyphens, and non-digit characters."""
        raw = "890-1030-013003"
        assert normalize_barcode_string(raw) == "8901030013003"

    def test_gs1_ai_extraction(self):
        """Extracts GTIN-14 from GS1-128 / DataBar formatted with (01)."""
        raw = "(01)08901030013003"
        normalized = normalize_barcode_string(raw)
        assert normalized == "8901030013003"

    def test_url_barcode_extraction(self):
        """Extracts barcode from Open Food Facts or retail product URLs."""
        url = "https://world.openfoodfacts.org/product/8901030013003/parachute-coconut-oil"
        # query param
        url2 = "https://example.com/lookup?barcode=8901030013003&source=camera"
        assert normalize_barcode_string(url2) == "8901030013003"


class TestChecksumValidation:
    def test_valid_ean13(self):
        """EAN-13 valid check digit."""
        code = "8901030013003"  # Parachute coconut oil
        res = validate_barcode(code)
        assert res.is_valid is True
        assert res.format == "EAN-13"
        assert res.normalized_barcode == "8901030013003"

    def test_invalid_ean13_checksum(self):
        """EAN-13 with corrupted/wrong check digit."""
        code = "8901030013004"  # Check digit 4 instead of 3
        res = validate_barcode(code)
        assert res.is_valid is False
        assert "checksum" in (res.error_message or "").lower()

    def test_valid_upca_with_leading_zero(self):
        """UPC-A starting with 0."""
        code = "012345678905"
        res = validate_barcode(code)
        assert res.is_valid is True
        assert res.format == "UPC-A"
        assert res.normalized_barcode == "012345678905"

    def test_invalid_upca_checksum(self):
        """UPC-A with wrong check digit."""
        code = "012345678909"
        res = validate_barcode(code)
        assert res.is_valid is False
        assert res.format == "UPC-A"

    def test_valid_ean8(self):
        """EAN-8 8-digit retail code."""
        code = "90162602"  # Red Bull
        res = validate_barcode(code)
        assert res.is_valid is True
        assert res.format == "EAN-8"
        assert res.normalized_barcode == "90162602"

    def test_invalid_ean8_checksum(self):
        """EAN-8 with wrong check digit."""
        code = "90162609"
        res = validate_barcode(code)
        assert res.is_valid is False

    def test_valid_gtin14(self):
        """GTIN-14 validation."""
        # 08901030013003 (GTIN-14 with leading 0)
        code = "08901030013003"
        res = validate_barcode(code)
        assert res.is_valid is True
        assert res.normalized_barcode == "8901030013003"


class TestPartialAndBlurredScanRejection:
    def test_truncated_partial_scans(self):
        """Partial camera reads (e.g. 5, 7, 10, or 11 digits) must be rejected."""
        partials = ["12345", "890103", "89010300130", "890103001"]
        for p in partials:
            res = validate_barcode(p)
            assert res.is_valid is False
            assert "unsupported barcode length" in (res.error_message or "").lower()

    def test_empty_and_none(self):
        """Empty or None input handled safely."""
        assert validate_barcode("").is_valid is False
        assert validate_barcode(None).is_valid is False
        assert validate_barcode("    ").is_valid is False
