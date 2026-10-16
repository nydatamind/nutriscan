"""
category_classifier.py
======================
Extensible Smart Product Category Detection & Analysis Rule Engine
for NutriScan · NY.
DEVELOPED BY NITIN YADAV

Categories supported:
  1. Food and snacks
  2. Skincare
  3. Haircare and personal care
  4. Cosmetics and beauty products
  5. Beverages
  6. Household products
  7. Hardware and tools
  8. Electronics and accessories
  9. Medicines and medical products
 10. Other consumer products
 11. Unknown category (Strict Fallback)

Strict Rules:
  - Never assume a barcode is food.
  - Hardware, electronics, cleaners, and medicines must NEVER receive food nutrition scoring.
  - Never fabricate ingredients, chemical compositions, dosages, or safety conclusions.
  - If category is uncertain, classify as UNKNOWN and display only verified general details.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


class ProductCategory(str, enum.Enum):
    FOOD_AND_SNACKS = "Food and snacks"
    SKINCARE = "Skincare"
    HAIRCARE_AND_PERSONAL_CARE = "Haircare and personal care"
    COSMETICS_AND_BEAUTY = "Cosmetics and beauty products"
    BEVERAGES = "Beverages"
    HOUSEHOLD_PRODUCTS = "Household products"
    HARDWARE_AND_TOOLS = "Hardware and tools"
    ELECTRONICS_AND_ACCESSORIES = "Electronics and accessories"
    MEDICINES_AND_MEDICAL = "Medicines and medical products"
    OTHER_CONSUMER_PRODUCTS = "Other consumer products"
    UNKNOWN = "Unknown category"


@dataclass(frozen=True)
class CategoryAnalysisRules:
    category: ProductCategory
    display_title: str
    display_type: str
    supports_food_score: bool
    supports_ingredients: bool
    requires_handling_warnings: bool
    requires_medical_disclaimer: bool
    gauge_metric_label: str
    default_summary: str
    default_advice: str


CATEGORY_RULES: Dict[ProductCategory, CategoryAnalysisRules] = {
    ProductCategory.FOOD_AND_SNACKS: CategoryAnalysisRules(
        category=ProductCategory.FOOD_AND_SNACKS,
        display_title="Food & Snack Nutrition Audit",
        display_type="NUTRITIONAL_ANALYSIS",
        supports_food_score=True,
        supports_ingredients=True,
        requires_handling_warnings=False,
        requires_medical_disclaimer=False,
        gauge_metric_label="Nutri-Score",
        default_summary="Nutritional composition and dietary additive evaluation.",
        default_advice="Check serving size and balanced nutritional intake.",
    ),
    ProductCategory.BEVERAGES: CategoryAnalysisRules(
        category=ProductCategory.BEVERAGES,
        display_title="Beverage & Liquid Refreshment Audit",
        display_type="NUTRITIONAL_ANALYSIS",
        supports_food_score=True,
        supports_ingredients=True,
        requires_handling_warnings=False,
        requires_medical_disclaimer=False,
        gauge_metric_label="Nutri-Score",
        default_summary="Hydration, sugar concentration, and beverage additives.",
        default_advice="Monitor added sugar and caffeine content.",
    ),
    ProductCategory.SKINCARE: CategoryAnalysisRules(
        category=ProductCategory.SKINCARE,
        display_title="Dermatological & Skincare Formulation Audit",
        display_type="DERMATOLOGICAL_ANALYSIS",
        supports_food_score=False,
        supports_ingredients=True,
        requires_handling_warnings=False,
        requires_medical_disclaimer=False,
        gauge_metric_label="Formula Safety",
        default_summary="Topical ingredient safety, comedogenicity, and irritant profile.",
        default_advice="Perform patch test on inner forearm prior to full facial application.",
    ),
    ProductCategory.HAIRCARE_AND_PERSONAL_CARE: CategoryAnalysisRules(
        category=ProductCategory.HAIRCARE_AND_PERSONAL_CARE,
        display_title="Hair & Personal Care Formulation Audit",
        display_type="PERSONAL_CARE_AUDIT",
        supports_food_score=False,
        supports_ingredients=True,
        requires_handling_warnings=False,
        requires_medical_disclaimer=False,
        gauge_metric_label="Scalp & Skin Safety",
        default_summary="Surfactant, emollient, and personal hygiene ingredient profile.",
        default_advice="Avoid contact with eyes; rinse thoroughly with clean water.",
    ),
    ProductCategory.COSMETICS_AND_BEAUTY: CategoryAnalysisRules(
        category=ProductCategory.COSMETICS_AND_BEAUTY,
        display_title="Cosmetics & Beauty Product Formulation Audit",
        display_type="COSMETICS_AUDIT",
        supports_food_score=False,
        supports_ingredients=True,
        requires_handling_warnings=False,
        requires_medical_disclaimer=False,
        gauge_metric_label="Cosmetic Safety",
        default_summary="Pigment, preservative, and cosmetic tolerance profile.",
        default_advice="Check for personal contact allergens before use.",
    ),
    ProductCategory.HOUSEHOLD_PRODUCTS: CategoryAnalysisRules(
        category=ProductCategory.HOUSEHOLD_PRODUCTS,
        display_title="Household Chemical Safety & Handling Audit",
        display_type="CHEMICAL_COMPOSITION",
        supports_food_score=False,
        supports_ingredients=True,
        requires_handling_warnings=True,
        requires_medical_disclaimer=False,
        gauge_metric_label="Handling Safety",
        default_summary="Chemical composition, cleaning agents, and active surfactants.",
        default_advice="Keep out of reach of children. Use in well-ventilated areas. Do not ingest.",
    ),
    ProductCategory.HARDWARE_AND_TOOLS: CategoryAnalysisRules(
        category=ProductCategory.HARDWARE_AND_TOOLS,
        display_title="Hardware & Tools Verified Specifications",
        display_type="SPECIFICATION_AUDIT",
        supports_food_score=False,
        supports_ingredients=False,
        requires_handling_warnings=True,
        requires_medical_disclaimer=False,
        gauge_metric_label="Spec Verified",
        default_summary="Verified technical specifications, materials, and manufacturer data.",
        default_advice="Wear appropriate personal protective equipment (PPE) during operation.",
    ),
    ProductCategory.ELECTRONICS_AND_ACCESSORIES: CategoryAnalysisRules(
        category=ProductCategory.ELECTRONICS_AND_ACCESSORIES,
        display_title="Electronics & Accessories Verified Specifications",
        display_type="SPECIFICATION_AUDIT",
        supports_food_score=False,
        supports_ingredients=False,
        requires_handling_warnings=True,
        requires_medical_disclaimer=False,
        gauge_metric_label="Spec Verified",
        default_summary="Verified electrical ratings, connectivity specifications, and certifications.",
        default_advice="Use only certified chargers; avoid moisture, punctures, and extreme temperatures.",
    ),
    ProductCategory.MEDICINES_AND_MEDICAL: CategoryAnalysisRules(
        category=ProductCategory.MEDICINES_AND_MEDICAL,
        display_title="Pharmaceutical & Regulated Medical Product",
        display_type="THERAPEUTIC_PROFILE",
        supports_food_score=False,
        supports_ingredients=True,
        requires_handling_warnings=True,
        requires_medical_disclaimer=True,
        gauge_metric_label="Regulated",
        default_summary="Regulated therapeutic product. Ingredients reflect documented active compounds.",
        default_advice="Consult a licensed physician or pharmacist for medical advice, dosage, and usage instructions.",
    ),
    ProductCategory.OTHER_CONSUMER_PRODUCTS: CategoryAnalysisRules(
        category=ProductCategory.OTHER_CONSUMER_PRODUCTS,
        display_title="Consumer Product Verified Details",
        display_type="GENERAL_PRODUCT_INFO",
        supports_food_score=False,
        supports_ingredients=False,
        requires_handling_warnings=False,
        requires_medical_disclaimer=False,
        gauge_metric_label="Verified Item",
        default_summary="Verified general consumer product details and specifications.",
        default_advice="Follow manufacturer packaging guidelines.",
    ),
    ProductCategory.UNKNOWN: CategoryAnalysisRules(
        category=ProductCategory.UNKNOWN,
        display_title="General Product Information",
        display_type="GENERAL_PRODUCT_INFO",
        supports_food_score=False,
        supports_ingredients=False,
        requires_handling_warnings=False,
        requires_medical_disclaimer=False,
        gauge_metric_label="Verified Record",
        default_summary="Verified product record from catalog. Category unclassified.",
        default_advice="Verify packaging details directly on the physical product.",
    ),
}


# ─────────────────────────────────────────────────────────────────────────────
# Taxonomy Keyword Dictionaries for Multi-Tier Classification
# ─────────────────────────────────────────────────────────────────────────────

TAXONOMY_KEYWORDS: Dict[ProductCategory, Set[str]] = {
    ProductCategory.FOOD_AND_SNACKS: {
        "food", "snack", "snacks", "chips", "crisps", "kurkure", "biscuit", "biscuits",
        "cookie", "cookies", "chocolate", "chocolates", "wafer", "wafers", "namkeen",
        "noodle", "noodles", "instant noodles", "maggi", "pasta", "oats", "cereal",
        "corn flakes", "bread", "butter", "cheese", "sauce", "ketchup", "jam",
        "pickle", "spices", "masala", "flour", "atta", "rice", "dal", "lentil",
        "edible oil", "refined oil", "ghee", "curd", "yogurt", "snack food",
        "confectionery", "sweets", "mithai", "popcorn", "extrudate", "extruded corn snack",
    },
    ProductCategory.BEVERAGES: {
        "beverage", "beverages", "drink", "drinks", "soft drink", "soda", "carbonated",
        "juice", "packaged fruit juice", "energy drink", "tea", "coffee", "syrup",
        "squash", "mineral water", "packaged drinking water", "cola", "lemonade",
        "mango beverage", "fruit drink", "cold drink", "tonic water", "iced tea",
    },
    ProductCategory.SKINCARE: {
        "skincare", "skin care", "face serum", "serum", "moisturizer", "moisturiser",
        "face wash", "facewash", "face cleanser", "cleanser", "sunscreen", "sun screen",
        "sunscreen gel", "spf", "face cream", "night cream", "day cream", "eye cream",
        "toner", "face mask", "sheet mask", "face scrub", "exfoliator", "micellar water",
        "anti-aging", "salicylic acid serum", "niacinamide", "hyaluronic", "vitamin c serum",
        "antiseptic skin cream", "body lotion", "body butter", "lip balm",
    },
    ProductCategory.HAIRCARE_AND_PERSONAL_CARE: {
        "haircare", "hair care", "shampoo", "conditioner", "hair conditioner",
        "hair oil", "kesh tel", "hair mask", "hair serum", "hair gel", "hair wax",
        "bathing soap", "soap", "beauty bar", "body wash", "shower gel", "deodorant",
        "roll-on", "underarm roll-on", "antiperspirant", "body spray", "talcum powder",
        "toothpaste", "gel toothpaste", "ayurvedic toothpaste", "sensitivity toothpaste",
        "mouthwash", "shaving cream", "shaving foam", "aftershave",
    },
    ProductCategory.COSMETICS_AND_BEAUTY: {
        "cosmetics", "cosmetic", "beauty", "makeup", "make up", "lipstick", "lip gloss",
        "lip liner", "foundation", "concealer", "compact powder", "eyeliner", "eye liner",
        "mascara", "kajal", "eyeshadow", "blush", "highlighter", "nail polish",
        "primer", "setting spray", "bb cream", "cc cream",
    },
    ProductCategory.HOUSEHOLD_PRODUCTS: {
        "cleaner", "surface cleaner", "glass cleaner", "floor cleaner", "toilet cleaner",
        "detergent", "laundry detergent", "washing powder", "fabric conditioner",
        "dishwash", "dishwashing liquid", "dishwash bar", "disinfectant", "bleach",
        "air freshener", "room spray", "mosquito repellent", "insecticide", "drain cleaner",
        "harpic", "lizol", "colin", "vim", "surf excel", "ariel", "tide",
    },
    ProductCategory.HARDWARE_AND_TOOLS: {
        "hardware", "tool", "tools", "screw", "screws", "bolt", "bolts", "nut", "nuts",
        "nail", "nails", "fastener", "pipe", "pipes", "fitting", "fittings", "pvc pipe",
        "hammer", "screwdriver", "wrench", "pliers", "saw", "drill", "drill bit",
        "power tool", "measuring tape", "adhesive tape", "duct tape", "sandpaper",
        "cement", "construction supply", "wire mesh", "padlock", "lock",
    },
    ProductCategory.ELECTRONICS_AND_ACCESSORIES: {
        "electronics", "electronic", "accessory", "accessories", "charger", "fast charger",
        "adapter", "power adapter", "cable", "usb cable", "type-c", "lightning cable",
        "battery", "batteries", "power bank", "earphones", "headphones", "earbuds",
        "bluetooth speaker", "smartwatch", "mouse", "keyboard", "pendrive", "usb drive",
        "memory card", "plug", "socket", "extension cord", "led bulb",
    },
    ProductCategory.MEDICINES_AND_MEDICAL: {
        "medicine", "medicines", "medical", "pharmaceutical", "drug", "tablet", "tablets",
        "capsule", "capsules", "syrup", "ointment", "analgesic", "antipyretic",
        "paracetamol", "crocin", "paracetamol tablets", "ibuprofen", "antibiotic",
        "cough syrup", "antacid", "band-aid", "bandage", "thermometer",
        "surgical", "glucose monitor", "pulse oximeter", "inhaler", "antiseptic liquid",
    },
    ProductCategory.OTHER_CONSUMER_PRODUCTS: {
        "toy", "toys", "board game", "puzzle", "stationery", "notebook", "pen", "pencil",
        "eraser", "ruler", "stapler", "apparel", "clothing accessory", "socks", "wallet",
        "umbrella", "backpack", "bag", "keychain",
    },
}


def normalize_category_string(raw: Optional[str]) -> str:
    """Normalize category, brand, or name tokens for canonical classification."""
    if not raw:
        return ""
    clean = re.sub(r"[\W_]+", " ", str(raw).lower())
    return " ".join(clean.split())


def classify_product(
    name: Optional[str] = None,
    brand: Optional[str] = None,
    raw_category: Optional[str] = None,
    ingredients_text: Optional[str] = None,
    specifications: Optional[str] = None,
) -> Tuple[ProductCategory, float, str]:
    """
    Classify product category reliably using priority:
      1. Verified product record raw_category / categories_tags.
      2. Verified product name & brand keywords.
      3. Specifications / ingredient context (secondary).
      4. Fallback: UNKNOWN.

    Returns:
      (ProductCategory, confidence_score [0.0 - 1.0], rationale_str)
    """
    norm_cat = normalize_category_string(raw_category)
    norm_name = normalize_category_string(name)
    norm_brand = normalize_category_string(brand)
    norm_specs = normalize_category_string(specifications)
    norm_ing = normalize_category_string(ingredients_text)

    # ── Tier 1: Check verified raw_category metadata (Primary Source) ─────────
    if norm_cat:
        for cat_enum, keywords in TAXONOMY_KEYWORDS.items():
            for kw in keywords:
                # Exact or boundary match inside category string
                pattern = r"\b" + re.escape(kw) + r"\b"
                if re.search(pattern, norm_cat):
                    return (
                        cat_enum,
                        1.0,
                        f"Exact verified category match: '{kw}' in metadata '{raw_category}'",
                    )

    # ── Tier 2: Check verified product name & brand ───────────────────────────
    combined_name = f"{norm_brand} {norm_name}".strip()
    if combined_name:
        # Check specific multi-word matches first for precision
        sorted_categories = [
            ProductCategory.MEDICINES_AND_MEDICAL,
            ProductCategory.HARDWARE_AND_TOOLS,
            ProductCategory.ELECTRONICS_AND_ACCESSORIES,
            ProductCategory.HOUSEHOLD_PRODUCTS,
            ProductCategory.SKINCARE,
            ProductCategory.HAIRCARE_AND_PERSONAL_CARE,
            ProductCategory.COSMETICS_AND_BEAUTY,
            ProductCategory.BEVERAGES,
            ProductCategory.FOOD_AND_SNACKS,
            ProductCategory.OTHER_CONSUMER_PRODUCTS,
        ]

        for cat_enum in sorted_categories:
            keywords = TAXONOMY_KEYWORDS[cat_enum]
            # Match longest keywords first (e.g. 'face wash' before 'wash')
            sorted_kws = sorted(keywords, key=len, reverse=True)
            for kw in sorted_kws:
                pattern = r"\b" + re.escape(kw) + r"\b"
                if re.search(pattern, combined_name):
                    return (
                        cat_enum,
                        0.90,
                        f"Matched verified product identifier '{kw}' in name/brand '{name}'",
                    )

    # ── Tier 3: Check specifications / ingredient characteristics ─────────────
    if norm_specs:
        for cat_enum in [ProductCategory.HARDWARE_AND_TOOLS, ProductCategory.ELECTRONICS_AND_ACCESSORIES]:
            for kw in TAXONOMY_KEYWORDS[cat_enum]:
                pattern = r"\b" + re.escape(kw) + r"\b"
                if re.search(pattern, norm_specs):
                    return (
                        cat_enum,
                        0.80,
                        f"Matched hardware/technical specification keyword '{kw}'",
                    )

    # ── Tier 4: Fallback to UNKNOWN ──────────────────────────────────────────
    return (
        ProductCategory.UNKNOWN,
        0.0,
        "Category uncertain; fallback to UNKNOWN without speculative classification.",
    )


def get_category_analysis_rules(category: ProductCategory | str) -> CategoryAnalysisRules:
    """Retrieve rules and safety parameters for a given product category."""
    if isinstance(category, str):
        for cat_enum in ProductCategory:
            if cat_enum.value.lower() == category.lower() or cat_enum.name.lower() == category.lower():
                return CATEGORY_RULES[cat_enum]
        # Check if category name matches any key
        cat_match = ProductCategory.UNKNOWN
        for c in ProductCategory:
            if c.value.lower() in category.lower():
                cat_match = c
                break
        return CATEGORY_RULES.get(cat_match, CATEGORY_RULES[ProductCategory.UNKNOWN])

    return CATEGORY_RULES.get(category, CATEGORY_RULES[ProductCategory.UNKNOWN])
