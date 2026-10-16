"""
tests/test_regression.py
========================
Mandatory regression test suite covering the 8 specific scenarios from MASTER DEVELOPMENT PROMPT:
  1. A valid barcode with a correct product record.
  2. A barcode mapped to the wrong product.
  3. An unknown barcode.
  4. Two conflicting records.
  5. A product with missing ingredients.
  6. A network/API failure.
  7. Two consecutive scans of different products.
  8. A barcode containing leading zeros.
"""

from unittest.mock import MagicMock, patch
import pytest

from ai_handler import (
    IngredientSafetyAI,
    _BARCODE_CACHE,
    calculate_deterministic_safety,
    match_ingredient_against_kb,
)
from barcode_validator import normalize_barcode_string, validate_barcode
from product_database import get_product_database
from product_resolver import fetch_and_verify_external_product, resolve_scanned_barcode


@pytest.fixture(autouse=True)
def clean_barcode_cache():
    """Ensure in-memory barcode cache is clean before and after each test."""
    _BARCODE_CACHE.clear()
    yield
    _BARCODE_CACHE.clear()


class TestMandatoryRegressionSuite:
    # ── Scenario 1: A valid barcode with a correct product record ────────────
    def test_scenario_1_valid_barcode_correct_product(self):
        """A valid barcode must accurately return its verified product and ingredients."""
        code = "8901030013003"  # Parachute Pure Coconut Oil
        res = resolve_scanned_barcode(code)
        assert res["found"] is True
        assert res["barcode"] == code
        assert "Parachute" in res["product_info"]["name"]
        assert "Coconut Oil" in res["product_info"]["name"]
        assert res["has_ingredients"] is True
        assert res["verification_status"] == "VERIFIED"

    # ── Scenario 2: A barcode mapped to the wrong product ────────────────────
    def test_scenario_2_barcode_mapped_to_wrong_product_prevented(self):
        """External API returning product with mismatched barcode must be discarded."""
        clean = "8901088770507"  # Nihar Naturals
        wrong_code = "8901030383793"  # Dabur Amla

        with patch("product_resolver.query_external_api_with_backoff") as mock_api:
            # External source returns wrong code
            mock_api.return_value = {
                "status": 1,
                "code": wrong_code,
                "product": {
                    "code": wrong_code,
                    "product_name": "Wrong Product Attached",
                    "brands": "Wrong Brand",
                },
            }
            # Attempt to verify external product
            prod = fetch_and_verify_external_product(clean)
            assert prod is None  # Mismatch rejected!

    # ── Scenario 3: An unknown barcode ───────────────────────────────────────
    def test_scenario_3_unknown_barcode(self):
        """An unknown barcode returns an honest unverified status without hallucinating."""
        unknown_code = "8901233024998"  # Valid checksum EAN-13, not in database
        with patch("product_resolver.fetch_and_verify_external_product", return_value=None):
            res = resolve_scanned_barcode(unknown_code)
            assert res["found"] is False
            assert res["verification_status"] == "UNVERIFIED"
            assert "Product not verified" in res["message"]
            # Must not contain fabricated ingredients
            assert "ingredients_text" not in res or not res["ingredients_text"]

    # ── Scenario 4: Two conflicting records ──────────────────────────────────
    def test_scenario_4_two_conflicting_records(self):
        """When an incoming unverified record conflicts with a verified local record, verified is preserved."""
        db = get_product_database()
        barcode = "8901058852394"  # Maggi in database

        # Existing verified record
        verified = db.get_product_by_barcode(barcode)
        assert verified is not None
        assert verified["verification_status"] == "VERIFIED"

        # Attempt to insert lower-quality/unverified conflicting record
        updated = db.upsert_product(
            barcode=barcode,
            name="Conflicting Fabricated Fake Product",
            brand="Fake Brand",
            verification_status="UNVERIFIED",
            confidence_score=0.1,
            reason="Attempted conflicting overwrite",
        )
        # Verified record must be protected
        assert updated["name"] == verified["name"]
        assert updated["verification_status"] == "VERIFIED"

    # ── Scenario 5: A product with missing ingredients ───────────────────────
    def test_scenario_5_product_with_missing_ingredients(self):
        """A product found without ingredients must be flagged has_ingredients=False without fabricating."""
        clean = "8901030013997"
        with patch("product_resolver.query_external_api_with_backoff") as mock_api:
            mock_api.return_value = {
                "status": 1,
                "code": clean,
                "product": {
                    "code": clean,
                    "product_name": "Test Snack Without Ingredients",
                    "brands": "Brand X",
                    "ingredients_text": "",
                },
            }
            res = resolve_scanned_barcode(clean)
            assert res["found"] is True
            assert res["has_ingredients"] is False
            assert res["verification_status"] == "PARTIALLY_VERIFIED"
            assert res["ingredients_text"] == ""

    # ── Scenario 6: A network/API failure ────────────────────────────────────
    def test_scenario_6_network_api_failure(self):
        """When network or external API fails/times out, app handles it gracefully without crash."""
        with patch("product_resolver.query_external_api_with_backoff", return_value=None):
            # Unknown barcode requiring external lookup that is not in database
            clean = "8901030099991"
            res = resolve_scanned_barcode(clean)
            assert res["found"] is False
            assert res["verification_status"] == "UNVERIFIED"
            assert "Product not verified" in res["message"]

    # ── Scenario 7: Two consecutive scans of different products ──────────────
    def test_scenario_7_consecutive_scans_cache_isolation(self):
        """Consecutive scans of two different products must remain completely isolated."""
        code1 = "8901058852394"  # Maggi Noodles
        code2 = "8901030013003"  # Parachute Coconut Oil

        res1 = resolve_scanned_barcode(code1)
        res2 = resolve_scanned_barcode(code2)

        assert res1["barcode"] == code1
        assert "Maggi" in res1["product_info"]["name"]

        assert res2["barcode"] == code2
        assert "Parachute" in res2["product_info"]["name"]
        assert "Maggi" not in res2["product_info"]["name"]

        # Re-check scan 1 to ensure scan 2 did not pollute state
        res1_recheck = resolve_scanned_barcode(code1)
        assert res1_recheck["barcode"] == code1
        assert "Maggi" in res1_recheck["product_info"]["name"]
        assert "Parachute" not in res1_recheck["product_info"]["name"]

    # ── Scenario 8: A barcode containing leading zeros ───────────────────────
    def test_scenario_8_barcode_with_leading_zeros(self):
        """A barcode starting with '0' must preserve the leading zero through the entire pipeline."""
        upc_zero = "012345678905"
        val = validate_barcode(upc_zero)
        assert val.is_valid is True
        assert val.normalized_barcode == "012345678905"
        assert val.normalized_barcode.startswith("0")
        assert len(val.normalized_barcode) == 12

        # Save to database and query back
        db = get_product_database()
        db.upsert_product(
            barcode=upc_zero,
            name="Leading Zero Cereal",
            brand="General Mills",
            ingredients_text="Whole Grain Oats, Sugar",
            verification_status="VERIFIED",
        )

        res = resolve_scanned_barcode(upc_zero)
        assert res["found"] is True
        assert res["barcode"] == "012345678905"
        assert res["barcode"].startswith("0")
        assert res["product_info"]["name"] == "Leading Zero Cereal"
