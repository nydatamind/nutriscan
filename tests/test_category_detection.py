"""
tests/test_category_detection.py
================================
Regression and validation suite for Smart Product Category Detection:
  Scenario 1: Kurkure packet categorized as food, not skincare or hardware.
  Scenario 2: Face serum categorized as skincare without food nutrition score.
  Scenario 3: Face wash categorized as skincare or personal care.
  Scenario 4: Hardware item displays specifications rather than fabricated ingredients.
  Scenario 5: Electronic accessory does not receive food safety analysis.
  Scenario 6: Product with an unknown category does not receive fabricated analysis.
  Scenario 7: Known product retrieved correctly from the verified cache.
  Scenario 8: Different barcode never displays previous product.
  Scenario 9: API timeout never results in an unrelated product being displayed.
  Scenario 10: Missing ingredient data remains missing.
  Scenario 11: Existing UI contracts and visual structure remain unchanged.
"""

from unittest.mock import patch
import pytest

from barcode_validator import normalize_barcode_string, validate_barcode
from category_classifier import (
    ProductCategory,
    classify_product,
    get_category_analysis_rules,
)
from product_database import get_product_database
from product_resolver import (
    clear_resolver_cache,
    get_resolver_cache_stats,
    resolve_scanned_barcode,
)
from ai_handler import IngredientSafetyAI


class TestCategoryDetectionAndRegression:
    def setup_method(self):
        clear_resolver_cache()
        self.ai = IngredientSafetyAI()

    def test_scenario_1_kurkure_categorized_as_food(self):
        """Scenario 1: A Kurkure packet is categorized as food, not skincare or hardware."""
        cat_enum, conf, reason = classify_product(
            name="Kurkure Masala Munch Crispy Snack",
            brand="Kurkure (PepsiCo)",
            raw_category="Extruded Corn Snack",
        )
        assert cat_enum == ProductCategory.FOOD_AND_SNACKS
        assert cat_enum != ProductCategory.SKINCARE
        assert cat_enum != ProductCategory.HARDWARE_AND_TOOLS

        rules = get_category_analysis_rules(cat_enum)
        assert rules.supports_food_score is True
        assert rules.supports_ingredients is True

        # End-to-end resolution of Kurkure
        res = resolve_scanned_barcode("8901491101837")
        assert res["found"] is True
        assert res["category"] == ProductCategory.FOOD_AND_SNACKS.value
        assert res["category_type"] == "FOOD_AND_SNACKS"
        assert res["product_info"]["supports_food_score"] is True

    def test_scenario_2_face_serum_categorized_as_skincare_no_food_score(self):
        """Scenario 2: A face serum is categorized as skincare and does not receive a food nutrition score."""
        cat_enum, conf, reason = classify_product(
            name="The Derma Co 2% Salicylic Acid Face Serum",
            brand="The Derma Co",
            raw_category="Skincare",
        )
        assert cat_enum == ProductCategory.SKINCARE
        rules = get_category_analysis_rules(cat_enum)
        assert rules.supports_food_score is False
        assert rules.supports_ingredients is True
        assert rules.display_type == "DERMATOLOGICAL_ANALYSIS"

        # End-to-end resolution
        res = resolve_scanned_barcode("8906107792478")
        assert res["found"] is True
        assert res["category"] == ProductCategory.SKINCARE.value
        assert res["product_info"]["nutriscore"] == ""
        assert res["product_info"]["supports_food_score"] is False

        # AI analysis pipeline check
        analysis = self.ai.fetch_and_analyze_barcode("8906107792478")
        assert analysis["found"] is True
        assert analysis["category"] == ProductCategory.SKINCARE.value
        assert "food" not in analysis["summary"].lower()
        assert "patch test" in analysis["recommendation"].lower()

    def test_scenario_3_face_wash_categorized_as_skincare_or_personal_care(self):
        """Scenario 3: A face wash is categorized as skincare or personal care."""
        cat_enum, conf, reason = classify_product(
            name="Pond's Bright Beauty Spot-less Glow Face Wash",
            brand="Pond's",
            raw_category="Face Wash",
        )
        assert cat_enum in (ProductCategory.SKINCARE, ProductCategory.HAIRCARE_AND_PERSONAL_CARE)
        rules = get_category_analysis_rules(cat_enum)
        assert rules.supports_food_score is False

        res = resolve_scanned_barcode("8901030752001")
        assert res["found"] is True
        assert res["category"] in (ProductCategory.SKINCARE.value, ProductCategory.HAIRCARE_AND_PERSONAL_CARE.value)

    def test_scenario_4_hardware_item_displays_specs_not_fabricated_ingredients(self):
        """Scenario 4: A hardware item displays product specifications rather than fabricated ingredients."""
        res = resolve_scanned_barcode("4059952514000")
        assert res["found"] is True
        assert res["category"] == ProductCategory.HARDWARE_AND_TOOLS.value
        assert res["category_type"] == "HARDWARE_AND_TOOLS"
        assert res["has_ingredients"] is False
        assert res["ingredients_text"] == ""
        assert "carbide" in res["specifications"].lower()
        assert res["analysis_rules"]["supports_ingredients"] is False
        assert res["analysis_rules"]["supports_food_score"] is False

        # Ensure AI pipeline does not fabricate ingredients
        analysis = self.ai.fetch_and_analyze_barcode("4059952514000")
        assert analysis["found"] is True
        assert analysis["has_ingredients"] is False
        assert analysis["ingredients"] == []
        assert analysis["overall_grade"] == "SPEC VERIFIED"
        assert "carbide" in analysis["specifications"].lower()
        assert "ppe" in analysis["recommendation"].lower() or "safety" in analysis["recommendation"].lower()

    def test_scenario_5_electronic_accessory_does_not_receive_food_safety_analysis(self):
        """Scenario 5: An electronic accessory does not receive food safety analysis."""
        res = resolve_scanned_barcode("0194252157008")
        assert res["found"] is True
        assert res["category"] == ProductCategory.ELECTRONICS_AND_ACCESSORIES.value
        assert res["category_type"] == "ELECTRONICS_AND_ACCESSORIES"
        assert res["product_info"]["nutriscore"] == ""
        assert res["product_info"]["supports_food_score"] is False

        analysis = self.ai.fetch_and_analyze_barcode("0194252157008")
        assert analysis["overall_grade"] == "SPEC VERIFIED"
        assert analysis["allergens_detected"] == []
        assert analysis["total_ingredients_found"] == 0
        assert "food" not in analysis["summary"].lower()
        assert "voltage" in analysis["recommendation"].lower() or "charger" in analysis["recommendation"].lower()

    def test_scenario_6_unknown_product_does_not_receive_fabricated_analysis(self):
        """Scenario 6: A product with an unknown category does not receive fabricated analysis."""
        cat_enum, conf, reason = classify_product(
            name="Generic Unlabeled Item XYZ",
            brand="Anonymous Corp",
            raw_category="",
        )
        assert cat_enum == ProductCategory.UNKNOWN
        assert conf == 0.0

        rules = get_category_analysis_rules(cat_enum)
        assert rules.supports_food_score is False
        assert rules.supports_ingredients is False

        with patch("product_resolver.fetch_and_verify_external_product", return_value=None):
            res = resolve_scanned_barcode("8901030099991")
            assert res["found"] is False
            assert res["verification_status"] == "UNVERIFIED"
            assert "not verified" in res["message"].lower()

    def test_scenario_7_known_product_retrieved_correctly_from_verified_cache(self):
        """Scenario 7: A known product is retrieved correctly from the verified cache."""
        clear_resolver_cache()
        assert get_resolver_cache_stats()["size"] == 0

        # First lookup (populates cache)
        first = resolve_scanned_barcode("8901058852394")
        assert first["found"] is True
        assert get_resolver_cache_stats()["size"] == 1
        assert "8901058852394" in get_resolver_cache_stats()["cached_barcodes"]

        # Second lookup (served from cache)
        second = resolve_scanned_barcode("8901058852394")
        assert second["found"] is True
        assert second["barcode"] == first["barcode"]
        assert second["product_info"]["name"] == first["product_info"]["name"]
        assert second["category"] == first["category"]

    def test_scenario_8_different_barcode_never_displays_previous_product(self):
        """Scenario 8: A different barcode never displays the previous product."""
        code1 = "8901058852394"  # Maggi
        code2 = "4059952514000"  # Bosch Drill Bits

        res1 = resolve_scanned_barcode(code1)
        res2 = resolve_scanned_barcode(code2)

        assert res1["barcode"] == code1
        assert "Maggi" in res1["product_info"]["name"]
        assert res1["category"] == ProductCategory.FOOD_AND_SNACKS.value

        assert res2["barcode"] == code2
        assert "Bosch" in res2["product_info"]["name"]
        assert res2["category"] == ProductCategory.HARDWARE_AND_TOOLS.value
        assert res2["product_info"]["name"] != res1["product_info"]["name"]

        # Interleaved re-check
        res1_recheck = resolve_scanned_barcode(code1)
        assert res1_recheck["barcode"] == code1
        assert "Maggi" in res1_recheck["product_info"]["name"]

    def test_scenario_9_api_timeout_never_results_in_unrelated_product_displayed(self):
        """Scenario 9: An API timeout never results in an unrelated product being displayed."""
        unknown_code = "8901030099991"
        with patch("product_resolver.query_external_api_with_backoff", side_effect=TimeoutError("Network timed out")):
            clear_resolver_cache()
            res = resolve_scanned_barcode(unknown_code)
            assert res["found"] is False
            assert res["barcode"] == unknown_code
            assert res["verification_status"] == "UNVERIFIED"
            assert "not verified" in res["message"].lower()

    def test_scenario_10_missing_ingredient_data_remains_missing(self):
        """Scenario 10: Missing ingredient data remains missing; never fabricated."""
        clean = "8901030013997"  # In DB with empty ingredients
        res = resolve_scanned_barcode(clean)
        assert res["found"] is True
        assert res["has_ingredients"] is False
        assert res["ingredients_text"] == ""
        assert res["verification_status"] == "PARTIALLY_VERIFIED"

        analysis = self.ai.fetch_and_analyze_barcode(clean)
        assert analysis["has_ingredients"] is False
        assert "missing from the database" in analysis["message"].lower()

    def test_scenario_11_ui_contract_and_structure_integrity(self):
        """Scenario 11: The existing UI still works and its visual structure is unchanged."""
        from pathlib import Path
        frontend_html = Path("d:/My_Projects/Nutriscan/frontend/index.html").read_text(encoding="utf-8")

        # Verify essential DOM elements remain intact
        assert 'id="results-area"' in frontend_html
        assert 'id="score-ring-fill"' in frontend_html
        assert 'class="grade-card"' in frontend_html
        assert 'class="stats-row"' in frontend_html
        assert 'class="verdict-box"' in frontend_html
        assert 'class="action-box"' in frontend_html
        assert 'class="ing-card"' in frontend_html
        assert 'class="alt-choice-box"' in frontend_html
        assert 'id="splash-screen"' in frontend_html

        # Verify client-side category classifier exists
        assert "function classifyProductCategoryClient" in frontend_html
        assert "CLIENT_VERIFIED_CACHE" in frontend_html
