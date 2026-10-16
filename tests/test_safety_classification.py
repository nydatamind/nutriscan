"""
tests/test_safety_classification.py
===================================
Safety classification and ingredient risk engine tests using known, documented examples.
"""

import pytest
from ai_handler import (
    calculate_deterministic_safety,
    generate_deterministic_summary,
    match_ingredient_against_kb,
    parse_raw_ingredients_text,
)


class TestSafetyClassification:
    def test_pure_natural_product_graded_a_safe(self):
        """Pure coconut oil without additives is graded A (Excellent / Safe)."""
        raw = "100% Pure Coconut Oil (Cold Pressed / Pure Edible & Hair Oil)"
        tokens = parse_raw_ingredients_text(raw)
        matched = [match_ingredient_against_kb(t) for t in tokens]
        score_data = calculate_deterministic_safety(matched)

        assert score_data["overall_grade"] == "A"
        assert score_data["overall_score"] >= 85
        assert score_data["concerning_ingredients_count"] == 0
        assert score_data["has_high_risk"] is False

    def test_hazardous_additive_graded_d_hazardous(self):
        """Potassium Bromate (INS 924a) or BHA triggers high penalty and low grade."""
        raw = "Refined Wheat Flour, Water, Sugar, Potassium Bromate (INS 924a), Butylated Hydroxyanisole (BHA / INS 320)"
        tokens = parse_raw_ingredients_text(raw)
        matched = [match_ingredient_against_kb(t) for t in tokens]
        score_data = calculate_deterministic_safety(matched)

        assert score_data["overall_grade"] in ("C", "D")
        assert score_data["has_high_risk"] is True
        assert score_data["concerning_ingredients_count"] >= 2
        # Verify potassium bromate penalty applied
        assert any(i["risk_level"] == "High Risk" for i in score_data["ingredients"])

    def test_moderate_additives_caution_grade_c(self):
        """Artificial colors and mineral oil trigger Caution / Grade C."""
        raw = "Mineral Oil (73.4% v/v), Fragrance, Sunset Yellow FCF (INS 110)"
        tokens = parse_raw_ingredients_text(raw)
        matched = [match_ingredient_against_kb(t) for t in tokens]
        score_data = calculate_deterministic_safety(matched)

        assert score_data["overall_grade"] in ("B", "C")
        assert score_data["concerning_ingredients_count"] >= 1

    def test_allergen_detection_sulfites_and_milk(self):
        """Sulfites and milk solids identified as declared allergens."""
        raw = "Wheat Flour, Milk Solids, Sugar, Sodium Metabisulphite (INS 223)"
        tokens = parse_raw_ingredients_text(raw)
        matched = [match_ingredient_against_kb(t) for t in tokens]
        score_data = calculate_deterministic_safety(matched)

        assert "Sulfites" in score_data["allergens_detected"]

    def test_empty_ingredients_marked_insufficient(self):
        """Empty ingredients list must be treated as insufficient evidence, not Grade A."""
        score_data = calculate_deterministic_safety([])
        assert score_data["overall_grade"] == "N/A"
        assert score_data["overall_score"] == 0
        assert score_data["insufficient_data"] is True

    def test_multilanguage_summary_generation(self):
        """Summary and recommendations generated deterministically in English, Hindi, and Hinglish."""
        score_data = {
            "overall_grade": "A",
            "overall_score": 95,
            "concerning_ingredients_count": 0,
            "allergens_detected": [],
        }

        sum_en, rec_en = generate_deterministic_summary(score_data, language="English")
        sum_hi, rec_hi = generate_deterministic_summary(score_data, language="Hindi")
        sum_hl, rec_hl = generate_deterministic_summary(score_data, language="Hinglish")

        assert "safe" in sum_en.lower() or "score" in sum_en.lower()
        assert "सुरक्षित" in sum_hi or "स्कोर" in sum_hi
        assert "safe" in sum_hl.lower() or "product" in sum_hl.lower()
