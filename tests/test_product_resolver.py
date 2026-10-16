"""
tests/test_product_resolver.py
==============================
Unit tests for product_resolver.py:
  - Exact barcode matching
  - Mocked external API queries with barcode verification
  - Mismatched barcode discard
  - Missing ingredients handling
  - Image cross-verification
  - Network timeout and rate limit resilience
"""

from unittest.mock import MagicMock, patch
import pytest

from product_resolver import (
    cross_verify_image_identity,
    fetch_and_verify_external_product,
    resolve_scanned_barcode,
)


class TestProductResolver:
    def test_local_database_exact_match(self):
        """Known valid barcode is resolved directly from database."""
        # 8901058852394 is Maggi in seed database
        res = resolve_scanned_barcode("8901058852394")
        assert res["found"] is True
        assert res["barcode"] == "8901058852394"
        assert "Maggi" in res["product_info"]["name"]
        assert res["has_ingredients"] is True
        assert res["verification_status"] == "VERIFIED"

    def test_unknown_barcode_returns_unverified_not_hallucinated(self):
        """Unknown barcode returns UNVERIFIED error state and never fabricates product."""
        # 8901030099991 is a valid checksum EAN-13, but not in database
        with patch("product_resolver.fetch_and_verify_external_product", return_value=None):
            res = resolve_scanned_barcode("8901030099991")
            assert res["found"] is False
            assert res["verification_status"] == "UNVERIFIED"
            assert "Product not verified" in res["message"]
            assert res["confidence_score"] == 0.0

    def test_invalid_barcode_rejected_immediately(self):
        """Invalid checksum or partial scan rejected without database or API query."""
        res = resolve_scanned_barcode("12345")
        assert res["found"] is False
        assert res["is_valid_barcode"] is False
        assert "unsupported barcode length" in res["message"].lower()

    @patch("product_resolver.query_external_api_with_backoff")
    def test_external_api_matching_barcode_accepted(self, mock_query):
        """External API returning the exact requested barcode is accepted and verified."""
        clean = "8901030013997"
        mock_query.return_value = {
            "status": 1,
            "code": clean,
            "product": {
                "code": clean,
                "product_name": "Verified Cloud Snack",
                "brands": "Cloud Brand",
                "categories": "Snacks",
                "ingredients_text": "Wheat Flour, Salt, Palm Oil",
            },
        }

        prod = fetch_and_verify_external_product(clean)
        assert prod is not None
        assert prod["barcode"] == clean
        assert prod["name"] == "Verified Cloud Snack"
        assert prod["verification_status"] == "VERIFIED"

    @patch("product_resolver.query_external_api_with_backoff")
    def test_external_api_mismatched_barcode_discarded(self, mock_query):
        """External API returning a DIFFERENT barcode must be rejected as unverified."""
        scanned = "8901030013997"
        different = "8901030013003"
        mock_query.return_value = {
            "status": 1,
            "code": different,  # Mismatched barcode!
            "product": {
                "code": different,
                "product_name": "Unrelated Product",
                "brands": "Wrong Brand",
                "ingredients_text": "Wrong Ingredients",
            },
        }

        prod = fetch_and_verify_external_product(scanned)
        assert prod is None  # Must discard mismatch!

    @patch("product_resolver.query_external_api_with_backoff")
    def test_external_api_missing_ingredients(self, mock_query):
        """External API product with missing ingredients marked as PARTIALLY_VERIFIED."""
        clean = "8901030013997"
        mock_query.return_value = {
            "status": 1,
            "code": clean,
            "product": {
                "code": clean,
                "product_name": "No Ingredients Item",
                "brands": "Some Brand",
                "ingredients_text": "",  # Empty
            },
        }

        prod = fetch_and_verify_external_product(clean)
        assert prod is not None
        assert prod["name"] == "No Ingredients Item"
        assert prod["ingredients_text"] == ""
        assert prod["verification_status"] == "PARTIALLY_VERIFIED"

    @patch("product_resolver.query_external_api_with_backoff")
    def test_external_api_timeout_fallback(self, mock_query):
        """Network timeout or connection failure returns None gracefully."""
        mock_query.return_value = None
        prod = fetch_and_verify_external_product("8901030013997")
        assert prod is None

    def test_image_cross_verification_matching(self):
        """Image OCR text matching product name / brand keywords."""
        match, note = cross_verify_image_identity(
            product_name="Parachute Pure Coconut Oil",
            brand="Parachute",
            ocr_text="100% Pure Coconut Oil Parachute 500ml",
        )
        assert match is True
        assert "confirmed keywords" in note.lower()

    def test_image_cross_verification_conflicting(self):
        """Image OCR text completely disagreeing with product metadata."""
        match, note = cross_verify_image_identity(
            product_name="Parachute Pure Coconut Oil",
            brand="Parachute",
            ocr_text="Dettol Original Germ Protection Bathing Bar Soap",
        )
        assert match is False
        assert "do not strongly match" in note.lower()
