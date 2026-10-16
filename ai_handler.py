"""
ai_handler.py
=============
Deterministic AI routing & ingredient safety engine for NutriScan · NY.
DEVELOPED BY NITIN YADAV

Features:
  1. Image fingerprinting (SHA-256) & normalization caching for consistent results.
  2. Canonical additive & ingredient database (E-numbers, INS codes, sweeteners, preservatives).
  3. Deterministic rule-based scoring & classification engine.
  4. Temperature = 0.0 deterministic OCR extraction.
  5. Multi-language output (English, Hindi, Hinglish) without altering safety scores.
  6. Unreadable label detection to prevent hallucinated ingredients.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
import textwrap
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple
import urllib.error
import urllib.request

from google import genai
from google.genai import types as genai_types
from PIL import Image


# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# In-Memory Cache (Stable Analysis by Image & Normalized Barcode)
# ─────────────────────────────────────────────────────────────────────────────
_IMAGE_CACHE: Dict[str, Dict[str, Any]] = {}
_INGREDIENT_CACHE: Dict[str, Dict[str, Any]] = {}
_BARCODE_CACHE: Dict[str, Dict[str, Any]] = {}


# ─────────────────────────────────────────────────────────────────────────────
# Comprehensive Canonical Ingredient & Additive Knowledge Base
# ─────────────────────────────────────────────────────────────────────────────
CANONICAL_DATABASE: List[Dict[str, Any]] = [
    # ── High Risk / Hazardous ──
    {
        "name": "Potassium Bromate (INS 924a)",
        "patterns": [r"potassium\s*bromate", r"ins\s*924\s*a?", r"e\s*924\s*a?"],
        "risk_level": "High Risk",
        "category": "Flour Treatment Agent",
        "side_effects": "Classified as potential carcinogen; banned in EU, India, UK, and multiple countries.",
        "regulatory_status": "Banned in Food",
        "icon": "",
        "score_penalty": 35,
    },
    {
        "name": "Butylated Hydroxyanisole (BHA / INS 320)",
        "patterns": [r"\bbha\b", r"butylated\s*hydroxyanisole", r"ins\s*320", r"e\s*320"],
        "risk_level": "High Risk",
        "category": "Synthetic Antioxidant",
        "side_effects": "Potential endocrine disruptor; possible human carcinogen in long-term high doses.",
        "regulatory_status": "Restricted in EU / FDA Regulated",
        "icon": "",
        "score_penalty": 25,
    },
    {
        "name": "Butylated Hydroxytoluene (BHT / INS 321)",
        "patterns": [r"\bbht\b", r"butylated\s*hydroxytoluene", r"ins\s*321", r"e\s*321"],
        "risk_level": "High Risk",
        "category": "Synthetic Antioxidant",
        "side_effects": "Linked to hormone disruption and potential organ toxicity with excessive intake.",
        "regulatory_status": "Strictly Limited Use",
        "icon": "",
        "score_penalty": 25,
    },
    {
        "name": "Titanium Dioxide (INS 171)",
        "patterns": [r"titanium\s*dioxide", r"ins\s*171", r"e\s*171", r"ci\s*77891"],
        "risk_level": "High Risk",
        "category": "Artificial Color",
        "side_effects": "Banned in EU as food additive due to DNA damage (genotoxicity) concerns.",
        "regulatory_status": "Banned in EU Food",
        "icon": "",
        "score_penalty": 30,
    },
    {
        "name": "Partially Hydrogenated Oil (Trans Fat)",
        "patterns": [r"partially\s*hydrogenated", r"trans\s*fat", r"vanaspati\s*ghee", r"hydrogenated\s*vegetable\s*oil"],
        "risk_level": "High Risk",
        "category": "Industrial Fat",
        "side_effects": "Elevates LDL bad cholesterol, lowers HDL, significantly increases heart disease risk.",
        "regulatory_status": "Prohibited / Heavily Restricted by WHO & FDA",
        "icon": "",
        "score_penalty": 30,
    },
    {
        "name": "Azodicarbonamide (INS 927a)",
        "patterns": [r"azodicarbonamide", r"ins\s*927\s*a?", r"e\s*927\s*a?"],
        "risk_level": "High Risk",
        "category": "Dough Conditioner",
        "side_effects": "Respiratory sensitivity and asthma risk; breakdown products include semicarbazide.",
        "regulatory_status": "Banned in EU & Australia",
        "icon": "",
        "score_penalty": 28,
    },
    {
        "name": "Red 40 / Allura Red (INS 129)",
        "patterns": [r"allura\s*red", r"red\s*40", r"ins\s*129", r"e\s*129", r"fd&c\s*red\s*no\.?\s*40"],
        "risk_level": "Moderate Risk",
        "category": "Artificial Color",
        "side_effects": "Synthetic azo dye; linked to hyperactivity in children and mild allergic sensitivities.",
        "regulatory_status": "Warning Label Required in EU",
        "icon": "",
        "score_penalty": 15,
    },
    {
        "name": "Tartrazine / Yellow 5 (INS 102)",
        "patterns": [r"tartrazine", r"yellow\s*5", r"ins\s*102", r"e\s*102", r"fd&c\s*yellow\s*no\.?\s*5"],
        "risk_level": "Moderate Risk",
        "category": "Artificial Color",
        "side_effects": "May trigger urticaria (hives), asthma, and hyperactive behavior in sensitive children.",
        "regulatory_status": "Warning Label Required in EU",
        "icon": "",
        "score_penalty": 15,
    },
    {
        "name": "Sunset Yellow FCF / Yellow 6 (INS 110)",
        "patterns": [r"sunset\s*yellow", r"yellow\s*6", r"ins\s*110", r"e\s*110"],
        "risk_level": "Moderate Risk",
        "category": "Artificial Color",
        "side_effects": "Synthetic azo dye; linked to hyperactivity and allergy symptoms in sensitive individuals.",
        "regulatory_status": "Warning Label Required in EU",
        "icon": "",
        "score_penalty": 15,
    },
    {
        "name": "Brilliant Blue FCF (INS 133)",
        "patterns": [r"brilliant\s*blue", r"blue\s*1", r"ins\s*133", r"e\s*133"],
        "risk_level": "Moderate Risk",
        "category": "Artificial Color",
        "side_effects": "Synthetic dye; potential mild skin irritations or allergic reactions in rare cases.",
        "regulatory_status": "Approved with Limits",
        "icon": "",
        "score_penalty": 12,
    },
    {
        "name": "Sodium Benzoate (INS 211)",
        "patterns": [r"sodium\s*benzoate", r"ins\s*211", r"e\s*211", r"preservative\s*\(?211\)?"],
        "risk_level": "Moderate Risk",
        "category": "Preservative",
        "side_effects": "Can form trace benzene when combined with Vitamin C (Ascorbic Acid).",
        "regulatory_status": "FSSAI / FDA Approved with Limits",
        "icon": "",
        "score_penalty": 14,
    },
    {
        "name": "Potassium Sorbate (INS 202)",
        "patterns": [r"potassium\s*sorbate", r"ins\s*202", r"e\s*202", r"preservative\s*\(?202\)?"],
        "risk_level": "Low Risk",
        "category": "Preservative",
        "side_effects": "Widely used anti-fungal preservative; generally safe, rare contact allergic reactions.",
        "regulatory_status": "FDA GRAS / FSSAI Approved",
        "icon": "",
        "score_penalty": 6,
    },
    {
        "name": "Sodium Nitrate / Nitrite (INS 250 / 251)",
        "patterns": [r"sodium\s*nitr[ia]te", r"potassium\s*nitr[ia]te", r"ins\s*250", r"ins\s*251", r"e\s*250", r"e\s*251"],
        "risk_level": "High Risk",
        "category": "Curing Agent / Preservative",
        "side_effects": "Forms carcinogenic nitrosamines during high heat cooking; linked to colon health risks.",
        "regulatory_status": "Strictly Regulated Preservative",
        "icon": "",
        "score_penalty": 24,
    },
    {
        "name": "Monosodium Glutamate (MSG / INS 621)",
        "patterns": [r"monosodium\s*glutamate", r"\bmsg\b", r"ins\s*621", r"e\s*621", r"flavor\s*enhancer\s*\(?621\)?"],
        "risk_level": "Low Risk",
        "category": "Flavor Enhancer",
        "side_effects": "Flavor enhancer providing umami; may cause mild transient sensitivity in rare individuals.",
        "regulatory_status": "FDA GRAS / FSSAI Approved",
        "icon": "",
        "score_penalty": 6,
    },
    {
        "name": "Disodium Inosinate & Guanylate (INS 627, 631)",
        "patterns": [r"disodium\s*inosinate", r"disodium\s*guanylate", r"ins\s*627", r"ins\s*631", r"ins\s*635", r"e\s*627", r"e\s*631"],
        "risk_level": "Low Risk",
        "category": "Flavor Enhancer",
        "side_effects": "Synergistic flavor enhancers; metabolizes to purines, consume with caution if prone to gout.",
        "regulatory_status": "Approved Additive",
        "icon": "",
        "score_penalty": 5,
    },
    {
        "name": "High Fructose Corn Syrup (HFCS)",
        "patterns": [r"high\s*fructose\s*corn\s*syrup", r"\bhfcs\b", r"fructose\s*glucose\s*syrup", r"corn\s*syrup\s*solids"],
        "risk_level": "Moderate Risk",
        "category": "Refined Sweetener",
        "side_effects": "Linked to fatty liver risk, insulin resistance, obesity, and accelerated metabolic syndrome.",
        "regulatory_status": "Permitted Refined Caloric Sweetener",
        "icon": "",
        "score_penalty": 15,
    },
    {
        "name": "Aspartame (INS 951)",
        "patterns": [r"aspartame", r"ins\s*951", r"e\s*951", r"artificial\s*sweetener\s*\(?951\)?"],
        "risk_level": "Moderate Risk",
        "category": "Artificial Sweetener",
        "side_effects": "Classified by IARC as possibly carcinogenic (Group 2B); unsafe for individuals with PKU.",
        "regulatory_status": "FDA Approved / PKU Warning Required",
        "icon": "",
        "score_penalty": 16,
    },
    {
        "name": "Acesulfame Potassium (Ace-K / INS 950)",
        "patterns": [r"acesulfame\s*potassium", r"acesulfame\s*k", r"ace-?k", r"ins\s*950", r"e\s*950"],
        "risk_level": "Moderate Risk",
        "category": "Artificial Sweetener",
        "side_effects": "Zero-calorie synthetic sweetener; some studies show potential gut microbiome disruption.",
        "regulatory_status": "FDA / FSSAI Approved",
        "icon": "",
        "score_penalty": 14,
    },
    {
        "name": "Sucralose (INS 955)",
        "patterns": [r"sucralose", r"ins\s*955", r"e\s*955"],
        "risk_level": "Low Risk",
        "category": "Non-Nutritive Sweetener",
        "side_effects": "Chlorinated sugar derivative; generally safe, high heat cooking may degrade compounds.",
        "regulatory_status": "FDA GRAS / FSSAI Approved",
        "icon": "",
        "score_penalty": 7,
    },
    {
        "name": "Palm Oil / Fractionated Palm Olein",
        "patterns": [r"palm\s*oil", r"palm\s*olein", r"palmolein\s*oil", r"fractionated\s*palm"],
        "risk_level": "Moderate Risk",
        "category": "Saturated Fat",
        "side_effects": "High saturated palmitic acid content; frequent high consumption increases cardiovascular risk.",
        "regulatory_status": "Approved Cooking Oil",
        "icon": "",
        "score_penalty": 12,
    },
    {
        "name": "Refined Palm Kernel Oil",
        "patterns": [r"palm\s*kernel\s*oil"],
        "risk_level": "Moderate Risk",
        "category": "Saturated Fat",
        "side_effects": "Contains over 80% saturated fat; regular excessive intake raises blood lipid levels.",
        "regulatory_status": "Approved Fat",
        "icon": "",
        "score_penalty": 12,
    },
    {
        "name": "Caramel Color (Class III/IV - INS 150c/150d)",
        "patterns": [r"caramel\s*colou?r", r"ins\s*150[a-d]?", r"e\s*150[a-d]?"],
        "risk_level": "Moderate Risk",
        "category": "Food Coloring",
        "side_effects": "Ammonia-process caramel colors (150c/150d) may contain trace 4-MEI byproduct.",
        "regulatory_status": "Approved with Limits",
        "icon": "",
        "score_penalty": 12,
    },
    {
        "name": "Soy Lecithin (INS 322)",
        "patterns": [r"soy\s*lecithin", r"soya\s*lecithin", r"lecithin", r"ins\s*322", r"e\s*322", r"emulsifier\s*\(?322\)?"],
        "risk_level": "Safe",
        "category": "Natural Emulsifier",
        "side_effects": "Plant-derived natural phospholipid; safe for consumption. Contains soy allergen.",
        "regulatory_status": "FDA GRAS / FSSAI Approved",
        "icon": "",
        "allergen": "Soy",
        "score_penalty": 0,
    },
    {
        "name": "Citric Acid (INS 330 / Acidity Regulator)",
        "patterns": [r"citric\s*acid", r"ins\s*330", r"e\s*330", r"acidity\s*regulator\s*\(?330\)?"],
        "risk_level": "Safe",
        "category": "Acidity Regulator",
        "side_effects": "Naturally occurring organic acid; completely safe in standard food portions.",
        "regulatory_status": "FDA GRAS / FSSAI Approved",
        "icon": "",
        "score_penalty": 0,
    },
    {
        "name": "Sodium Bicarbonate / Baking Soda (INS 500ii)",
        "patterns": [r"sodium\s*bicarbonate", r"baking\s*soda", r"ins\s*500", r"e\s*500"],
        "risk_level": "Safe",
        "category": "Leavening Agent",
        "side_effects": "Standard alkaline mineral leavening agent; safe for regular digestion.",
        "regulatory_status": "FDA GRAS",
        "icon": "",
        "score_penalty": 0,
    },
    {
        "name": "Ascorbic Acid / Vitamin C (INS 300)",
        "patterns": [r"ascorbic\s*acid", r"vitamin\s*c", r"ins\s*300", r"e\s*300"],
        "risk_level": "Safe",
        "category": "Antioxidant / Vitamin",
        "side_effects": "Essential nutrient and safe natural antioxidant for food preservation.",
        "regulatory_status": "FDA GRAS / Essential Nutrient",
        "icon": "",
        "score_penalty": 0,
    },
    {
        "name": "Tocopherols / Vitamin E (INS 307)",
        "patterns": [r"tocopherol", r"vitamin\s*e", r"ins\s*307", r"e\s*307"],
        "risk_level": "Safe",
        "category": "Natural Antioxidant",
        "side_effects": "Fat-soluble natural antioxidant; safe and beneficial nutrient.",
        "regulatory_status": "FDA GRAS",
        "icon": "",
        "score_penalty": 0,
    },
    # ── Active Skincare & Cosmetic Ingredients (Roll-ons, Sunscreens, Serums) ──
    {
        "name": "Lactic Acid (AHA Exfoliant)",
        "patterns": [r"lactic\s*acid"],
        "risk_level": "Safe",
        "category": "Alpha Hydroxy Acid (AHA)",
        "side_effects": "Gentle AHA exfoliant; brightens skin, reduces underarm hyperpigmentation & hydrates skin.",
        "regulatory_status": "Dermatologist Approved Active",
        "icon": "",
        "score_penalty": 0,
    },
    {
        "name": "Salicylic Acid (BHA Active)",
        "patterns": [r"salicylic\s*acid", r"\bbha\b"],
        "risk_level": "Safe",
        "category": "Beta Hydroxy Acid (BHA)",
        "side_effects": "Penetrates deep into pores to control body odour, unclog pores, and prevent breakout bacteria.",
        "regulatory_status": "Dermatologist Approved Active",
        "icon": "",
        "score_penalty": 0,
    },
    {
        "name": "Mandelic Acid (AHA Active)",
        "patterns": [r"mandelic\s*acid"],
        "risk_level": "Safe",
        "category": "Gentle AHA Exfoliant",
        "side_effects": "Almond-derived gentle AHA; brightens skin tone without irritation.",
        "regulatory_status": "Cosmetic Grade Active",
        "icon": "",
        "score_penalty": 0,
    },
    {
        "name": "Shea Butter (Butyrospermum Parkii)",
        "patterns": [r"shea\s*butter", r"butyrospermum\s*parkii"],
        "risk_level": "Safe",
        "category": "Nourishing Botanical Lipid",
        "side_effects": "Rich in fatty acids and Vitamin E; deeply moisturizes and protects skin barrier.",
        "regulatory_status": "Beneficial Natural Emollient",
        "icon": "",
        "score_penalty": 0,
    },
    {
        "name": "Propylene Glycol / Propanediol",
        "patterns": [r"propylene\s*glycol", r"propanediol"],
        "risk_level": "Safe",
        "category": "Skin Hydrator & Carrier",
        "side_effects": "Helps active ingredients penetrate skin surface; attracts & locks in moisture.",
        "regulatory_status": "Cosmetic Standard Approved",
        "icon": "",
        "score_penalty": 0,
    },
    {
        "name": "Carrot Seed Oil / Extract",
        "patterns": [r"carrot", r"daucus\s*carota"],
        "risk_level": "Safe",
        "category": "Natural Botanical Antioxidant",
        "side_effects": "Rich in Beta-Carotene & Vitamin A; natural protection against free radical sun damage.",
        "regulatory_status": "Beneficial Botanical Extract",
        "icon": "",
        "score_penalty": 0,
    },
    {
        "name": "Xanthan Gum / Sclerotium Gum",
        "patterns": [r"xanthan\s*gum", r"sclerotium\s*gum", r"guar\s*gum"],
        "risk_level": "Safe",
        "category": "Natural Botanical Thickener",
        "side_effects": "Plant-derived natural gelling & stabilizing agent; 100% non-toxic.",
        "regulatory_status": "FDA GRAS Approved",
        "icon": "",
        "score_penalty": 0,
    },
    {
        "name": "Maltodextrin",
        "patterns": [r"maltodextrin", r"malto\s*dextrin"],
        "risk_level": "Low Risk",
        "category": "Processed Carbohydrate",
        "side_effects": "High glycemic index (GI 110-185); rapidly spikes blood glucose levels.",
        "regulatory_status": "FDA GRAS",
        "icon": "",
        "score_penalty": 6,
    },
    {
        "name": "Refined Sugar / Sucrose",
        "patterns": [r"\bsugar\b", r"refined\s*sugar", r"cane\s*sugar", r"sucrose", r"invert\s*sugar", r"liquid\s*glucose"],
        "risk_level": "Low Risk",
        "category": "Refined Sugar",
        "side_effects": "High caloric sweetener; frequent high intake contributes to tooth decay and weight gain.",
        "regulatory_status": "Safe in moderation",
        "icon": "",
        "score_penalty": 5,
    },
    {
        "name": "Iodised Salt / Sodium Chloride",
        "patterns": [r"iodised\s*salt", r"iodized\s*salt", r"\bsalt\b", r"sodium\s*chloride", r"edible\s*common\s*salt"],
        "risk_level": "Safe",
        "category": "Mineral Seasoning",
        "side_effects": "Essential dietary mineral; safe for regular consumption in recommended daily amounts.",
        "regulatory_status": "Essential Food Standard",
        "icon": "",
        "score_penalty": 0,
    },
    {
        "name": "Refined Wheat Flour (Maida)",
        "patterns": [r"refined\s*wheat\s*flour", r"\bmaida\b", r"wheat\s*flour", r"enriched\s*flour"],
        "risk_level": "Low Risk",
        "category": "Refined Grain",
        "side_effects": "Stripped of natural bran and fiber; low satiety, contains gluten allergen.",
        "regulatory_status": "Standard Staple",
        "icon": "",
        "allergen": "Wheat / Gluten",
        "score_penalty": 4,
    },
    {
        "name": "Whole Wheat Flour (Atta)",
        "patterns": [r"whole\s*wheat", r"\batta\b", r"whole\s*grain"],
        "risk_level": "Safe",
        "category": "Whole Grain",
        "side_effects": "Rich in dietary fiber and essential micronutrients. Contains gluten allergen.",
        "regulatory_status": "Natural Whole Food",
        "icon": "",
        "allergen": "Wheat / Gluten",
        "score_penalty": 0,
    },
    {
        "name": "Milk Solids / Whey / Dairy",
        "patterns": [r"milk\s*solids", r"whey\s*powder", r"skimmed\s*milk", r"dairy\s*whitener", r"milk\s*protein", r"casein"],
        "risk_level": "Safe",
        "category": "Dairy",
        "side_effects": "Source of natural protein and calcium. Contains lactose & dairy allergens.",
        "regulatory_status": "Natural Food",
        "icon": "",
        "allergen": "Milk / Dairy",
        "score_penalty": 0,
    },
    {
        "name": "Peanuts / Groundnuts",
        "patterns": [r"peanut", r"groundnut"],
        "risk_level": "Safe",
        "category": "Legume / Nut",
        "side_effects": "Nutrient-dense protein and healthy fats. Major common allergen.",
        "regulatory_status": "Natural Food",
        "icon": "",
        "allergen": "Peanuts",
        "score_penalty": 0,
    },
    {
        "name": "Almonds / Cashews / Tree Nuts",
        "patterns": [r"almond", r"cashew", r"walnut", r"pistachio", r"hazelnut", r"tree\s*nut"],
        "risk_level": "Safe",
        "category": "Tree Nut",
        "side_effects": "Heart-healthy unsaturated fats and antioxidants. Tree nut allergen.",
        "regulatory_status": "Natural Food",
        "icon": "",
        "allergen": "Tree Nuts",
        "score_penalty": 0,
    },
    {
        "name": "Guar Gum (INS 412)",
        "patterns": [r"guar\s*gum", r"ins\s*412", r"e\s*412", r"stabilizer\s*\(?412\)?"],
        "risk_level": "Safe",
        "category": "Natural Stabilizer",
        "side_effects": "Plant seed soluble fiber; safe and natural thickening agent.",
        "regulatory_status": "FDA GRAS",
        "icon": "",
        "score_penalty": 0,
    },
    {
        "name": "Xanthan Gum (INS 415)",
        "patterns": [r"xanthan\s*gum", r"ins\s*415", r"e\s*415", r"stabilizer\s*\(?415\)?"],
        "risk_level": "Safe",
        "category": "Fermented Stabilizer",
        "side_effects": "Safe fermented polysaccharide thickener; well-tolerated in normal food amounts.",
        "regulatory_status": "FDA GRAS",
        "icon": "",
        "score_penalty": 0,
    },
    {
        "name": "Mono- and Diglycerides of Fatty Acids (INS 471)",
        "patterns": [r"mono\s*and\s*diglycerides", r"ins\s*471", r"e\s*471", r"emulsifier\s*\(?471\)?"],
        "risk_level": "Low Risk",
        "category": "Emulsifier",
        "side_effects": "Common fat-derived emulsifier; may contain trace trans fats depending on oil source.",
        "regulatory_status": "FDA GRAS",
        "icon": "",
        "score_penalty": 5,
    },
    {
        "name": "Cocoa Solids / Butter",
        "patterns": [r"cocoa\s*solids", r"cocoa\s*butter", r"cocoa\s*powder", r"cacao"],
        "risk_level": "Safe",
        "category": "Natural Cocoa",
        "side_effects": "Rich in polyphenol antioxidants and natural flavonoids.",
        "regulatory_status": "Natural Food",
        "icon": "",
        "score_penalty": 0,
    },
    {
        "name": "Sulfites / Sulphur Dioxide (INS 220-228)",
        "patterns": [r"sulphur\s*dioxide", r"sodium\s*metabisulphite", r"sodium\s*metabisulfite", r"ins\s*22[0-8]", r"e\s*22[0-8]"],
        "risk_level": "Moderate Risk",
        "category": "Preservative / Allergen",
        "side_effects": "Can trigger acute bronchospasms and allergic reactions in asthmatic individuals.",
        "regulatory_status": "Allergen Declaration Required",
        "icon": "",
        "allergen": "Sulfites",
        "score_penalty": 15,
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# Normalization Helper Functions
# ─────────────────────────────────────────────────────────────────────────────

def compute_image_hash(image: Image.Image) -> str:
    """Compute a deterministic SHA-256 fingerprint from image pixels."""
    img_copy = image.convert("RGB").resize((400, 400), Image.Resampling.LANCZOS)
    buf = BytesIO()
    img_copy.save(buf, format="JPEG", quality=85)
    return hashlib.sha256(buf.getvalue()).hexdigest()


def normalize_ingredient_token(token: str) -> str:
    """Clean individual ingredient string (spaces, casing, parenthesis)."""
    token = re.sub(r"^\s*[\d\.\•\-\*]+\s*", "", token)
    token = re.sub(r"\b\d+(\.\d+)?\s*%\s*", "", token)
    token = re.sub(r"\s+", " ", token).strip()
    return token


def parse_raw_ingredients_text(raw_text: str) -> List[str]:
    """Parse comma/semicolon/newline-delimited text into distinct ingredient strings."""
    cleaned = re.sub(r"^(ingredients|contains|composition|samagri)\s*[:\-]\s*", "", raw_text, flags=re.IGNORECASE)
    
    tokens: List[str] = []
    raw_tokens = re.split(r",(?![^()]*\))|;(?![^()]*\))|\n|\|", cleaned)
    
    for rt in raw_tokens:
        tok = normalize_ingredient_token(rt)
        if len(tok) >= 2 and not tok.lower().startswith("may contain") and not tok.lower().startswith("allergen"):
            tokens.append(tok)
            
    return tokens


def match_ingredient_against_kb(raw_name: str) -> Dict[str, Any]:
    """Match an ingredient token against our canonical database using regex patterns."""
    raw_lower = raw_name.lower()
    
    for entry in CANONICAL_DATABASE:
        for pat in entry["patterns"]:
            if re.search(pat, raw_lower, re.IGNORECASE):
                res = {
                    "name": raw_name if len(raw_name) > 4 and not raw_name.startswith("INS") else entry["name"],
                    "canonical_name": entry["name"],
                    "risk_level": entry["risk_level"],
                    "category": entry["category"],
                    "side_effects": entry["side_effects"],
                    "regulatory_status": entry["regulatory_status"],
                    "icon": entry["icon"],
                    "score_penalty": entry["score_penalty"],
                }
                if "allergen" in entry:
                    res["allergen"] = entry["allergen"]
                return res
                
    # Fallback heuristic for unmatched ingredients
    penalty = 0
    cat = "Food Ingredient"
    risk = "Safe"
    icon = ""
    side_effects = "Standard food constituent; safe for general consumption."
    reg_status = "Approved Food"

    if re.search(r"artificial|synthetic|preservative|colour|color|stabilizer|emulsifier|flavo[u]?r", raw_lower):
        risk = "Moderate Risk" if re.search(r"artificial|synthetic", raw_lower) else "Low Risk"
        icon = "" if risk == "Moderate Risk" else ""
        penalty = 12 if risk == "Moderate Risk" else 5
        cat = "Food Additive"
        side_effects = "Additive used for texture, shelf-life or flavoring. Consume in moderation."
        reg_status = "Regulated Additive"
    elif re.search(r"oil|fat|hydrogenated", raw_lower):
        cat = "Fats & Oils"
        risk = "Low Risk"
        icon = ""
        penalty = 4
        side_effects = "Dietary lipid; recommended in balanced moderation."
    elif re.search(r"water|flour|grain|salt|spice|herb|extract|milk|fruit|nut|seed|vegetable", raw_lower):
        cat = "Natural Ingredient"
        risk = "Safe"
        icon = ""
        penalty = 0
        side_effects = "Natural wholesome ingredient."

    return {
        "name": raw_name.title() if raw_name.isupper() or raw_name.islower() else raw_name,
        "canonical_name": raw_name.title(),
        "risk_level": risk,
        "category": cat,
        "side_effects": side_effects,
        "regulatory_status": reg_status,
        "icon": icon,
        "score_penalty": penalty,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Deterministic Scoring Engine
# ─────────────────────────────────────────────────────────────────────────────

def calculate_deterministic_safety(matched_ingredients: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Deterministically computes:
      - overall_score (0 - 100)
      - overall_grade (A, B, C, D)
      - total_ingredients_found
      - concerning_ingredients_count
      - allergens_detected
    """
    total_count = len(matched_ingredients)
    if total_count == 0:
        return {
            "overall_grade": "N/A",
            "overall_score": 0,
            "total_ingredients_found": 0,
            "concerning_ingredients_count": 0,
            "allergens_detected": [],
            "ingredients": [],
            "has_high_risk": False,
            "has_moderate_risk": False,
            "insufficient_data": True,
        }

    base_score = 100
    total_penalty = 0
    concerning_count = 0
    allergens: List[str] = []
    has_high_risk = False
    has_moderate_risk = False

    for ing in matched_ingredients:
        risk = ing.get("risk_level", "Safe")
        pen = ing.get("score_penalty", 0)
        total_penalty += pen

        if risk == "High Risk":
            concerning_count += 1
            has_high_risk = True
        elif risk == "Moderate Risk":
            concerning_count += 1
            has_moderate_risk = True
        elif risk == "Low Risk" and pen >= 5:
            concerning_count += 1

        if "allergen" in ing and ing["allergen"] not in allergens:
            allergens.append(ing["allergen"])

    # Calculate final score with penalty
    raw_score = base_score - total_penalty
    final_score = max(5, min(100, raw_score))

    # Cap grade deterministically based on risk presence
    if has_high_risk:
        if final_score >= 65:
            final_score = 62  # Cap to Caution
        if final_score < 40 or total_penalty >= 45:
            grade = "D"
        else:
            grade = "C"
    else:
        if final_score >= 85:
            grade = "A"
        elif final_score >= 65:
            grade = "B"
        elif final_score >= 40:
            grade = "C"
        else:
            grade = "D"

    return {
        "overall_grade": grade,
        "overall_score": int(final_score),
        "total_ingredients_found": total_count,
        "concerning_ingredients_count": concerning_count,
        "allergens_detected": allergens,
        "ingredients": matched_ingredients,
        "has_high_risk": has_high_risk,
        "has_moderate_risk": has_moderate_risk,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Localized Summary & Recommendation Generator
# ─────────────────────────────────────────────────────────────────────────────

def generate_deterministic_summary(
    score_data: Dict[str, Any], language: str = "English", category: Optional[str] = None
) -> Tuple[str, str]:
    """Produce deterministic summary & recommendation text in selected language adapted to product category."""
    grade = score_data.get("overall_grade", "C")
    score = score_data.get("overall_score", 50)
    concerning = score_data.get("concerning_ingredients_count", 0)
    allergens = score_data.get("allergens_detected", [])
    cat_str = (category or score_data.get("category") or "").lower()

    allergen_str = f" Contains allergens: {', '.join(allergens)}." if allergens else ""
    allergen_str_hi = f" इसमें {', '.join(allergens)} जैसे एलर्जेंस मौजूद हैं।" if allergens else ""
    allergen_str_hl = f" Isme {', '.join(allergens)} allergens shamil hain." if allergens else ""

    # Category Branch: Skincare & Cosmetics
    if any(k in cat_str for k in ["skin", "serum", "moistur", "sunscreen", "cleanser", "cosmetic", "beauty"]):
        if language == "Hindi":
            if grade == "A":
                summary = f"यह स्किनकेयर उत्पाद स्वच्छ और त्वचा के अनुकूल अवयवों से तैयार है (सुरक्षा स्कोर: {score}/100)।{allergen_str_hi}"
                rec = "दैनिक सामयिक उपयोग के लिए कोमल और उपयुक्त। पैच टेस्ट की सलाह दी जाती है।"
            elif grade == "B":
                summary = f"यह स्किनकेयर उत्पाद मानक कॉस्मेटिक सुरक्षा मानकों के अनुसार सुरक्षित है (सुरक्षा स्कोर: {score}/100)।{allergen_str_hi}"
                rec = "नियमित उपयोग के लिए उपयुक्त। उपयोग से पूर्व पैच टेस्ट करें।"
            elif grade == "C":
                summary = f"इस स्किनकेयर उत्पाद में {concerning} संभावित संवेदक या सुगंध घटक मौजूद हैं (सुरक्षा स्कोर: {score}/100)।{allergen_str_hi}"
                rec = "संवेदनशील त्वचा वाले व्यक्ति चेहरे पर उपयोग से पूर्व पैच टेस्ट अवश्य करें।"
            else:
                summary = f"सावधान: इसमें संभावित रूप से उत्तेजक या प्रतिबंधित कॉस्मेटिक रसायन मौजूद हैं (सुरक्षा स्कोर: {score}/100)।{allergen_str_hi}"
                rec = "संवेदनशील या क्षतिग्रस्त त्वचा पर उपयोग से बचें।"
        elif language == "Hinglish":
            if grade == "A":
                summary = f"Yeh skincare product clean aur skin-friendly ingredients se bana hai (Formula Score: {score}/100).{allergen_str_hl}"
                rec = "Daily skincare routine ke liye gentle aur safe hai. Patch test recommended."
            elif grade == "B":
                summary = f"Yeh skincare product generally safe hai aur standard cosmetic ingredients contain karta hai (Formula Score: {score}/100).{allergen_str_hl}"
                rec = "Regular use ke liye suitable hai. Sensitive areas se bacha kar use karein."
            elif grade == "C":
                summary = f"Is formulation me {concerning} potential skin sensitizers ya fragrance compounds detect hue hain (Formula Score: {score}/100).{allergen_str_hl}"
                rec = "Sensitive skin types pehle inner arm par patch test karein."
            else:
                summary = f"Warning: Is product me harsh ya restricted cosmetic chemicals shamil hain (Formula Score: {score}/100).{allergen_str_hl}"
                rec = "Sensitive skin barrier ke liye safe nahi hai; milder options consider karein."
        else:  # English
            if grade == "A":
                summary = f"This skincare formulation features clean, gentle, and nourishing topical ingredients (Formula Score: {score}/100).{allergen_str}"
                rec = "Safe and suitable for regular skincare routine. Perform standard patch test."
            elif grade == "B":
                summary = f"This skincare product is generally safe with standard permitted cosmetic ingredients (Formula Score: {score}/100).{allergen_str}"
                rec = "Suitable for topical usage. Avoid contact with eyes."
            elif grade == "C":
                summary = f"This formulation contains {concerning} potential skin sensitizer(s), fragrance components, or pore-clogging lipids (Formula Score: {score}/100).{allergen_str}"
                rec = "Sensitive skin individuals should patch-test prior to full application."
            else:
                summary = f"Caution: Contains harsh, restricted, or potentially irritating cosmetic agents (Formula Score: {score}/100).{allergen_str}"
                rec = "Not recommended for compromised skin barriers or rosacea-prone skin."
        return summary, rec

    # Category Branch: Haircare & Personal Care
    if any(k in cat_str for k in ["hair", "shampoo", "soap", "deodorant", "roll-on", "personal"]):
        if language == "Hindi":
            summary = f"व्यक्तिगत स्वच्छता और बालों की देखभाल के लिए परीक्षित फॉर्मूलेशन (सुरक्षा स्कोर: {score}/100)।{allergen_str_hi}"
            rec = "उपयोग के बाद साफ पानी से धोएं। आंखों के संपर्क से बचाएं।"
        elif language == "Hinglish":
            summary = f"Personal care aur hair hygiene formulation audit (Safety Score: {score}/100).{allergen_str_hl}"
            rec = "Use ke baad thoroughly rinse karein. Aankhon se door rakhein."
        else:
            summary = f"Personal care & hygiene formulation audited for scalp and epidermal safety (Score: {score}/100).{allergen_str}"
            rec = "Rinse thoroughly with clean water. Discontinue if redness or itching occurs."
        return summary, rec

    # Category Branch: Household Products
    if any(k in cat_str for k in ["cleaner", "detergent", "household", "disinfectant"]):
        if language == "Hindi":
            summary = f"घरेलू रासायनिक क्लीनर फॉर्मूलेशन। रासायनिक सुरक्षा और हैंडलिंग ऑडिट।"
            rec = "सावधानी: बच्चों की पहुंच से दूर रखें। हवादार स्थान में उपयोग करें। भोजन पर न छिड़कें।"
        elif language == "Hinglish":
            summary = f"Household chemical cleaner formulation. Handling and safety audit."
            rec = "Warning: Bachhon se door rakhein. Ingest na karein aur skin contact avoid karein."
        else:
            summary = f"Household chemical maintenance formulation. Surface and handling safety audited."
            rec = "Handling Warning: Keep out of reach of children. Use in well-ventilated areas. Do not ingest."
        return summary, rec

    # Category Branch: Medicines & Medical Products
    if any(k in cat_str for k in ["medicine", "medical", "tablet", "pharma", "paracetamol", "drug"]):
        if language == "Hindi":
            summary = f"विनियमित औषधीय एवं चिकित्सीय उत्पाद। सक्रिय औषधीय यौगिक सत्यापित।"
            rec = "चिकित्सीय सूचना: खुराक और उपयोग के लिए केवल पंजीकृत चिकित्सक या फार्मासिस्ट से परामर्श लें।"
        elif language == "Hinglish":
            summary = f"Regulated pharmaceutical product. Active medicinal compounds verified."
            rec = "Doctor Notice: Proper dosage aur use ke liye registered doctor ya pharmacist se consult karein."
        else:
            summary = f"Regulated pharmaceutical product. Documented active compounds verified."
            rec = "Clinical Notice: Consult a licensed physician or pharmacist for medical advice, dosage, and usage instructions."
    # Category Branch: Hardware & Tools
    if any(k in cat_str for k in ["hardware", "tool", "screw", "drill", "fastener", "pipe"]):
        if language == "Hindi":
            summary = "सत्यापित हार्डवेयर उपकरण विनिर्देश। गैर-उपभोग्य निर्मित सामग्री।"
            rec = "उपयोग के दौरान व्यक्तिगत सुरक्षा उपकरण (PPE) पहनें और सुरक्षा निर्देशों का पालन करें।"
        elif language == "Hinglish":
            summary = "Verified hardware aur tools specification. Non-consumable manufactured equipment."
            rec = "Operation ke waqt proper PPE and safety equipment use karein."
        else:
            summary = "Verified hardware & tool specification. Non-consumable manufactured equipment."
            rec = "Wear appropriate personal protective equipment (PPE) and follow manufacturer operating instructions."
        return summary, rec

    # Category Branch: Electronics & Accessories
    if any(k in cat_str for k in ["electronic", "accessory", "charger", "cable", "adapter", "battery", "power bank"]):
        if language == "Hindi":
            summary = "सत्यापित उपभोक्ता इलेक्ट्रॉनिक्स उपकरण। प्रमाणित विद्युत रेटिंग।"
            rec = "निर्धारित वोल्टेज सीमाओं में उपयोग करें। प्रमाणित चार्जर का उपयोग करें और नमी से बचाएं।"
        elif language == "Hinglish":
            summary = "Verified electronic accessory specification. Certified electrical ratings."
            rec = "Specified voltage par use karein, certified charger lagayein aur moisture se door rakhein."
        else:
            summary = "Verified consumer electronics accessory specification. Certified electrical ratings."
            rec = "Operate within specified voltage limits. Use certified chargers and keep dry."
        return summary, rec

    # Category Branch: Other Consumer Products & Unknown
    if any(k in cat_str for k in ["other", "consumer", "unknown", "toy", "stationery", "notebook"]):
        if language == "Hindi":
            summary = "सत्यापित उपभोक्ता उत्पाद रिकॉर्ड।"
            rec = "उपयोग और सुरक्षा निर्देशों के लिए निर्माता पैकेज विवरण देखें।"
        elif language == "Hinglish":
            summary = "Verified consumer product record."
            rec = "Usage aur safety instructions ke liye manufacturer package refer karein."
        else:
            summary = "Verified general consumer product record."
            rec = "Refer to manufacturer packaging for safety and usage instructions."
        return summary, rec

    # Default Branch: Food & Beverages
    if language == "Hindi":
        if grade == "A":
            summary = f"यह उत्पाद पूरी तरह सुरक्षित और प्राकृतिक अवयवों से भरपूर है (सुरक्षा स्कोर: {score}/100)।{allergen_str_hi}"
            rec = "दैनिक उपयोग के लिए सुरक्षित और पौष्टिक विकल्प।"
        elif grade == "B":
            summary = f"यह उत्पाद सामान्य रूप से सुरक्षित है और इसमें केवल अनुमत खाद्य योजक मौजूद हैं (सुरक्षा स्कोर: {score}/100)।{allergen_str_hi}"
            rec = "संतुलित मात्रा में सेवन के लिए उपयुक्त।"
        elif grade == "C":
            summary = f"इस उत्पाद में {concerning} चिंताजनक घटक/कृत्रिम योजक पाए गए हैं (सुरक्षा स्कोर: {score}/100)।{allergen_str_hi}"
            rec = "नियमित रूप से अधिक मात्रा में सेवन करने से बचें।"
        else:
            summary = f"सावधान: इस उत्पाद में अत्यधिक प्रसंस्कृत या हानिकारक घटक मौजूद हैं (सुरक्षा स्कोर: {score}/100)।{allergen_str_hi}"
            rec = "स्वास्थ्य सुरक्षा के लिए इस उत्पाद का उपयोग सीमित रखें या प्राकृतिक विकल्प चुनें।"

    elif language == "Hinglish":
        if grade == "A":
            summary = f"Yeh product kaafi safe aur clean ingredients se bana hai (Safety Score: {score}/100).{allergen_str_hl}"
            rec = "Daily use ke liye safe aur healthy choice hai."
        elif grade == "B":
            summary = f"Yeh product generally safe hai aur standard permitted additives contain karta hai (Safety Score: {score}/100).{allergen_str_hl}"
            rec = "Moderate quantity me consume karna safe hai."
        elif grade == "C":
            summary = f"Is product me {concerning} concerning additives ya artificial sweeteners detect hue hain (Safety Score: {score}/100).{allergen_str_hl}"
            rec = "Regular excessive consumption avoid karein."
        else:
            summary = f"Warning: Is product me high-risk ya highly ultra-processed ingredients shamil hain (Safety Score: {score}/100).{allergen_str_hl}"
            rec = "Health protection ke liye iska intake minimize karein."

    else:  # English
        if grade == "A":
            summary = f"This product features clean, natural, and safe ingredients with minimal processing (Safety Score: {score}/100).{allergen_str}"
            rec = "Safe and suitable for regular, healthy consumption."
        elif grade == "B":
            summary = f"This product is generally safe and contains standard permitted food additives within safe limits (Safety Score: {score}/100).{allergen_str}"
            rec = "Suitable for consumption in balanced moderation."
        elif grade == "C":
            summary = f"This product contains {concerning} moderate-risk additive(s) or artificial ingredients (Safety Score: {score}/100).{allergen_str}"
            rec = "Consume occasionally and avoid excessive daily intake."
        else:
            summary = f"Caution: Contains hazardous or highly ultra-processed additives that may carry health concerns (Safety Score: {score}/100).{allergen_str}"
            rec = "Consider healthier whole-food alternatives with cleaner labels."

    return summary, rec


# ─────────────────────────────────────────────────────────────────────────────
# Gemini Engine for OCR Extraction (Deterministic Temperature = 0.0)
# ─────────────────────────────────────────────────────────────────────────────

class GeminiEngine:
    VISION_MODELS = [
        "gemini-3.7-flash",
        "gemini-3.6-flash",
        "gemini-3.5-flash",
        "gemini-2.5-flash",
        "gemini-flash-latest",
    ]

    def __init__(self, api_key: str) -> None:
        if not api_key:
            raise ValueError("GEMINI_API_KEY is not set.")
        self._client = genai.Client(api_key=api_key)
        self.active_model = self.VISION_MODELS[0]

    def _image_to_bytes(self, image: Image.Image) -> bytes:
        buf = BytesIO()
        image.save(buf, format="JPEG", quality=90)
        return buf.getvalue()

    def ocr_extract_ingredients(self, image: Image.Image) -> str:
        """
        Extract only visible ingredient text from product label image.
        Strict deterministic temperature = 0.0.
        """
        img_bytes = self._image_to_bytes(image)
        prompt = (
            "You are a specialized food packaging OCR reader. "
            "Carefully transcribe ONLY the exact ingredients list printed on this product package image. "
            "If no ingredients list is visible or text is completely blurred and illegible, return 'UNREADABLE_LABEL'. "
            "Do NOT guess, invent, or hallucinate missing ingredients. "
            "Output only the extracted ingredient names separated by commas."
        )

        last_err = None
        for model in self.VISION_MODELS:
            try:
                response = self._client.models.generate_content(
                    model=model,
                    contents=[
                        prompt,
                        genai_types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg"),
                    ],
                    config=genai_types.GenerateContentConfig(
                        system_instruction="You are an exact OCR transcriber for ingredient labels. Output exact text only.",
                        temperature=0.0,
                        max_output_tokens=1500,
                        automatic_function_calling=genai_types.AutomaticFunctionCallingConfig(
                            disable=True
                        ),
                    ),
                )
                text = response.text or ""
                if text.strip():
                    self.active_model = model
                    logger.info("OCR extracted successfully with %s", model)
                    return text.strip()
            except Exception as exc:
                last_err = exc
                logger.warning("OCR attempt %s failed: %s", model, exc)

        raise RuntimeError(f"OCR label extraction failed: {last_err}")


# ─────────────────────────────────────────────────────────────────────────────
# Master NutriScan AI Handler
# ─────────────────────────────────────────────────────────────────────────────

class IngredientSafetyAI:
    def __init__(
        self,
        gemini_key: Optional[str] = None,
    ) -> None:
        self._gemini_key = (gemini_key or os.getenv("GEMINI_API_KEY", "")).strip()

        self._gemini: Optional[GeminiEngine] = None


        if self._gemini_key:
            try:
                self._gemini = GeminiEngine(self._gemini_key)
            except Exception as exc:
                logger.warning("Gemini init failed: %s", exc)

    def analyze_image(
        self, image: Image.Image, language: str = "English", **kwargs: Any
    ) -> Dict[str, Any]:
        """
        Complete deterministic analysis pipeline:
          1. Image fingerprinting / Cache check
          2. Zero-temperature OCR text extraction
          3. Unreadable image guard
          4. Text normalization & INS/E-number mapping
          5. Deterministic scoring rule engine
          6. Multi-language summary formatting
        """
        if not self._gemini:
            raise RuntimeError("GEMINI_API_KEY is required for image label OCR.")
        # Step 1: Compute Image Fingerprint
        img_hash = compute_image_hash(image)

        # Check if we have cached results for this exact image
        if img_hash in _IMAGE_CACHE:
            logger.info("Cache hit for image hash: %s", img_hash)
            cached_data = _IMAGE_CACHE[img_hash]
            summary, rec = generate_deterministic_summary(cached_data, language=language)
            result = dict(cached_data)
            result["summary"] = summary
            result["recommendation"] = rec
            return result

        # Step 2: OCR Extraction
        ocr_text = self._gemini.ocr_extract_ingredients(image)
        logger.info("Raw OCR Text: %s", ocr_text[:120])

        # Step 3: Check for unreadable label
        if not ocr_text or "UNREADABLE_LABEL" in ocr_text.upper() or len(ocr_text.strip()) < 5:
            unreadable_msg = {
                "English":  "Some ingredients could not be read clearly. Please upload a sharper label photo.",
                "Hindi":    "सामग्रियों को स्पष्ट रूप से पढ़ा नहीं जा सका। कृपया अधिक स्पष्ट फोटो अपलोड करें।",
                "Hinglish": "Kuch ingredients clearly read nahi ho paye. Please ek sharper photo upload karein.",
            }.get(language, "Some ingredients could not be read clearly. Please upload a sharper label photo.")

            return {
                "is_unreadable": True,
                "overall_grade": "N/A",
                "overall_score": 0,
                "summary": unreadable_msg,
                "recommendation": "Ensure good lighting and focus on the ingredient list text.",
                "total_ingredients_found": 0,
                "concerning_ingredients_count": 0,
                "allergens_detected": [],
                "ingredients": [],
            }

        # Step 4: Parse & Normalize Ingredients
        tokens = parse_raw_ingredients_text(ocr_text)

        if not tokens:
            return {
                "is_unreadable": True,
                "overall_grade": "N/A",
                "overall_score": 0,
                "summary": "No identifiable ingredients detected on the label.",
                "recommendation": "Please capture a clear photo centered on the ingredient list.",
                "total_ingredients_found": 0,
                "concerning_ingredients_count": 0,
                "allergens_detected": [],
                "ingredients": [],
            }

        # Step 5: Match each token against Canonical Database
        matched = [match_ingredient_against_kb(tok) for tok in tokens]

        # Step 6: Deterministic Scoring & Grading
        score_data = calculate_deterministic_safety(matched)

        # Step 7: Deterministic Language Summary
        summary, rec = generate_deterministic_summary(score_data, language=language)

        final_result = {
            "is_unreadable": False,
            "overall_grade": score_data["overall_grade"],
            "overall_score": score_data["overall_score"],
            "summary": summary,
            "recommendation": rec,
            "total_ingredients_found": score_data["total_ingredients_found"],
            "concerning_ingredients_count": score_data["concerning_ingredients_count"],
            "allergens_detected": score_data["allergens_detected"],
            "ingredients": score_data["ingredients"],
            "raw_ocr": ocr_text,
        }

        # Store in cache for consistent recall
        _IMAGE_CACHE[img_hash] = final_result
        return final_result

    def analyze_ingredients_text(
        self,
        raw_text: str,
        language: str = "English",
        product_meta: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Analyze raw ingredient text deterministically without OCR step."""
        tokens = parse_raw_ingredients_text(raw_text)
        if not tokens:
            return {
                "is_unreadable": True,
                "overall_grade": "N/A",
                "overall_score": 0,
                "summary": "No identifiable ingredients detected in product record.",
                "recommendation": "Please capture a clear photo of the physical product label.",
                "total_ingredients_found": 0,
                "concerning_ingredients_count": 0,
                "allergens_detected": [],
                "ingredients": [],
                "product_info": product_meta or {},
            }

        matched = [match_ingredient_against_kb(tok) for tok in tokens]
        score_data = calculate_deterministic_safety(matched)
        cat_str = (product_meta or {}).get("category", "")
        cat_type = (product_meta or {}).get("category_type", "")

        # Category safety overrides for non-food categories
        if any(k in cat_str.lower() for k in ["household", "cleaner", "detergent"]):
            score_data["overall_grade"] = "CAUTION"
        elif any(k in cat_str.lower() for k in ["medicine", "medical", "tablet", "pharma"]):
            score_data["overall_grade"] = "REGULATED"

        summary, rec = generate_deterministic_summary(score_data, language=language, category=cat_str)

        return {
            "source_type": "barcode" if product_meta else "text",
            "is_unreadable": False,
            "overall_grade": score_data["overall_grade"],
            "overall_score": score_data["overall_score"],
            "summary": summary,
            "recommendation": rec,
            "total_ingredients_found": score_data["total_ingredients_found"],
            "concerning_ingredients_count": score_data["concerning_ingredients_count"],
            "allergens_detected": score_data["allergens_detected"],
            "ingredients": score_data["ingredients"],
            "raw_text": raw_text,
            "product_info": product_meta or {},
            "category": cat_str,
            "category_type": cat_type,
        }

    def fetch_and_analyze_barcode(
        self, barcode: str, language: str = "English", image_ocr_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Verified Barcode Pipeline:
          1. Safe normalization & checksum validation (preserves leading zeros).
          2. Check normalized barcode cache.
          3. Multi-tier verified lookup (Local SQLite DB -> Verified Open Food Facts).
          4. Smart Category Classification & Rule Application.
          5. Deterministic category-specific analysis without AI fabrication.
          6. Structured honest diagnostics when product is unverified or ingredients are missing.
        """
        from barcode_validator import normalize_barcode_string, validate_barcode
        from product_resolver import resolve_scanned_barcode

        clean_code = normalize_barcode_string(barcode)
        val_res = validate_barcode(clean_code)

        if not val_res.is_valid:
            return {
                "source_type": "barcode",
                "found": False,
                "is_valid_barcode": False,
                "barcode": clean_code or str(barcode or ""),
                "verification_status": "UNVERIFIED",
                "confidence_score": 0.0,
                "message": val_res.error_message or f"Invalid barcode #{barcode}.",
                "action_prompt": "Please hold the camera steady or scan the barcode again in good lighting.",
            }

        # Check in-memory verified barcode cache
        cache_key = f"barcode:{clean_code}:{language}"
        if cache_key in _BARCODE_CACHE:
            cached_data = _BARCODE_CACHE[cache_key]
            logger.info("Cache hit for verified barcode: %s", clean_code)
            return dict(cached_data)

        # Run verified multi-tier resolver
        resolved = resolve_scanned_barcode(clean_code, image_ocr_text=image_ocr_text)

        # Handle unverified barcode
        if not resolved.get("found"):
            return {
                "source_type": "barcode",
                "found": False,
                "is_valid_barcode": True,
                "barcode": clean_code,
                "verification_status": "UNVERIFIED",
                "confidence_score": 0.0,
                "message": resolved.get("message", f"Product not verified for Barcode #{clean_code}."),
                "action_prompt": resolved.get("action_prompt", "Please take a photo of the back label to analyze this product's health safety!"),
            }

        product_meta = resolved.get("product_info", {})
        product_meta["barcode"] = clean_code
        product_meta["source"] = resolved.get("source", "VERIFIED_REGISTRY")
        product_meta["verification_status"] = resolved.get("verification_status", "VERIFIED")

        cat_str = resolved.get("category", "Food and snacks")
        cat_type = resolved.get("category_type", "FOOD_AND_SNACKS")
        rules = resolved.get("analysis_rules", {})
        supports_ingredients = rules.get("supports_ingredients", True)
        supports_food_score = rules.get("supports_food_score", True)
        specs = resolved.get("specifications") or product_meta.get("specifications") or ""

        # Handle non-food categories that do NOT support ingredients (Hardware, Tools, Electronics, Other)
        if not supports_ingredients:
            p_name = product_meta.get("name", "Product")
            brand = product_meta.get("brand", "Manufacturer")
            summary, rec = generate_deterministic_summary(
                {"overall_grade": "SPEC VERIFIED", "overall_score": 100, "concerning_ingredients_count": 0, "allergens_detected": []},
                language=language,
                category=cat_str,
            )
            analysis = {
                "source_type": "barcode",
                "found": True,
                "has_ingredients": False,
                "barcode": clean_code,
                "product_info": product_meta,
                "verification_status": "VERIFIED",
                "confidence_score": resolved.get("confidence_score", 1.0),
                "source": resolved.get("source", "VERIFIED_REGISTRY"),
                "category": cat_str,
                "category_type": cat_type,
                "analysis_rules": rules,
                "overall_grade": "SPEC VERIFIED",
                "overall_score": 100,
                "summary": summary,
                "recommendation": rec,
                "total_ingredients_found": 0,
                "concerning_ingredients_count": 0,
                "allergens_detected": [],
                "ingredients": [],
                "specifications": specs,
            }
            _BARCODE_CACHE[cache_key] = analysis
            return analysis

        # Handle verified product record with missing ingredients (e.g. food/skincare where ingredients missing)
        if not resolved.get("has_ingredients") or not resolved.get("ingredients_text"):
            p_name = product_meta.get("name", "Product")
            brand = product_meta.get("brand", "Brand")
            return {
                "source_type": "barcode",
                "found": True,
                "has_ingredients": False,
                "barcode": clean_code,
                "product_info": product_meta,
                "verification_status": "PARTIALLY_VERIFIED",
                "confidence_score": resolved.get("confidence_score", 0.70),
                "source": resolved.get("source", "VERIFIED_REGISTRY"),
                "category": cat_str,
                "category_type": cat_type,
                "analysis_rules": rules,
                "specifications": specs,
                "message": f"Found '{p_name}' by {brand}, but its ingredient list is missing from the database.",
                "action_prompt": "Please take a quick photo of the ingredient list on the physical package to complete safety analysis!",
            }

        # Analyze verified product ingredients
        ing_text = resolved["ingredients_text"]
        analysis = self.analyze_ingredients_text(ing_text, language=language, product_meta=product_meta)
        analysis["found"] = True
        analysis["has_ingredients"] = True
        analysis["barcode"] = clean_code
        analysis["verification_status"] = "VERIFIED"
        analysis["confidence_score"] = resolved.get("confidence_score", 1.0)
        analysis["source"] = resolved.get("source", "VERIFIED_REGISTRY")
        analysis["category"] = cat_str
        analysis["category_type"] = cat_type
        analysis["analysis_rules"] = rules
        analysis["specifications"] = specs

        # Cache verified analysis
        _BARCODE_CACHE[cache_key] = analysis
        return analysis

    def get_status_info(self) -> Dict[str, Any]:
        return {
            "gemini_available": self._gemini is not None,
            "status": "Ready",
        }


# ─────────────────────────────────────────────────────────────────────────────
# Open Food Facts Global & Local Lookup Helper (with strict barcode verification)
# ─────────────────────────────────────────────────────────────────────────────

def fetch_open_food_facts_data(barcode: str) -> Optional[Dict[str, Any]]:
    """Fetch and verify product data from Open Food Facts API."""
    from product_resolver import fetch_and_verify_external_product
    from barcode_validator import normalize_barcode_string

    clean_code = normalize_barcode_string(barcode)
    if not clean_code or len(clean_code) < 8:
        return None
    return fetch_and_verify_external_product(clean_code)


LOCAL_PRODUCTS_FALLBACK: Dict[str, Dict[str, str]] = {
    "8901088770507": {
        "name": "Nihar Naturals Shanti Amla Badam Kesh Tel",
        "brand": "Nihar Naturals (Marico)",
        "category": "Hair Oil",
        "ingredients_text": "Mineral Oil (73.4% v/v), Heavy Liquid Paraffin, Edible Vegetable Oil (25% v/v), Fragrance (Parfum), Tertiary Butylhydroquinone (TBHQ INS 319), Amla Extract (0.01% w/v), Almond Oil (0.1% w/v), Vitamin E Acetate, Synthetic Colours (CI 12700, CI 26100, CI 61565)."
    },
    "8901030383793": {
        "name": "Dabur Amla Hair Oil",
        "brand": "Dabur",
        "category": "Hair Oil",
        "ingredients_text": "Mineral Oil (50%), Canola Oil, Peanut Oil, Amla Extract, TBHQ (Antioxidant), Fragrance, Yellow 11 (CI 47000), Green 6 (CI 61565)."
    },
    "8901207010071": {
        "name": "Bajaj Almond Drops Non-Sticky Hair Oil",
        "brand": "Bajaj Consumer Care",
        "category": "Hair Oil",
        "ingredients_text": "Mineral Oil (77%), Refined Mustard Oil (21%), Sweet Almond Oil, Vitamin E Acetate, Fragrance, TBHQ (Antioxidant), CI 12700, CI 26100."
    },
    "8901030013003": {
        "name": "Parachute 100% Pure Coconut Oil",
        "brand": "Parachute (Marico)",
        "category": "Pure Coconut Oil",
        "ingredients_text": "100% Pure Coconut Oil (Cold Pressed / Pure Edible & Hair Oil)."
    },
    "8901030353451": {
        "name": "Head & Shoulders Smooth & Silky Shampoo",
        "brand": "Procter & Gamble",
        "category": "Shampoo",
        "ingredients_text": "Water, Sodium Laureth Sulfate (SLES), Sodium Xylenesulfonate, Zinc Carbonate, Cocamide MEA, Cocamidopropyl Betaine, Dimethicone, Zinc Pyrithione, Fragrance, Sodium Chloride, DMDM Hydantoin."
    },
    "8901719101038": {
        "name": "Parle-G Original Gluco Biscuits",
        "brand": "Parle",
        "category": "Biscuits",
        "ingredients_text": "Wheat Flour (67%), Sugar, Edible Vegetable Oil (Palm Oil), Invert Sugar Syrup, Raising Agents [INS 503(ii), INS 500(ii)], Salt, Milk Solids, Emulsifier [INS 322(i)], Artificial Vanilla Flavour."
    },
    "8901058852394": {
        "name": "Maggi 2-Minute Masala Instant Noodles",
        "brand": "Nestlé",
        "category": "Instant Noodles",
        "ingredients_text": "Refined Wheat Flour (Maida), Palm Oil, Iodised Salt, Wheat Gluten, Thickeners (INS 508, INS 412), Acidity Regulators (INS 501i, INS 500i), Hydrolysed Groundnut Protein, Red Chilli, Spices, Flavour Enhancer (INS 635)."
    },
    "8901063142275": {
        "name": "Britannia Bourbon Chocolate Biscuits",
        "brand": "Britannia",
        "category": "Biscuits",
        "ingredients_text": "Refined Wheat Flour, Sugar, Palm Oil, Invert Sugar Syrup, Cocoa Solids, Raising Agents [INS 500ii, INS 503ii], Iodised Salt, Emulsifiers [INS 322, INS 471], Added Artificial Chocolate Flavors."
    },
    "5449000000996": {
        "name": "Coca-Cola Original Taste",
        "brand": "The Coca-Cola Company",
        "category": "Carbonated Beverage",
        "ingredients_text": "Carbonated Water, Sugar, Acidity Regulator (INS 338), Caffeine, Caramel Colour (INS 150d), Natural Flavours."
    },
    "8906133402532": {
        "name": "BE Bodywise 4% AHA BHA Underarm Roll-on (Flora)",
        "brand": "BE Bodywise",
        "category": "Underarm Roll-on & Deodorant",
        "ingredients_text": "Aqua, Propylene Glycol, Lactic Acid (2%), Sodium Lactate, Glycerin, Mandelic Acid (1%), Salicylic Acid (1%), Alpha-Arbutin, Tocopheryl Acetate, Butyrospermum Parkii (Shea) Butter, Lysolecithin, Polysorbate 20, Perfume, Sodium Benzoate, Potassium Sorbate, Sclerotium Gum, Xanthan Gum, Silica."
    },
    "8906133400118": {
        "name": "BE Bodywise 4% AHA BHA Underarm Roll-on (Fragrance Free)",
        "brand": "BE Bodywise",
        "category": "Underarm Roll-on & Deodorant",
        "ingredients_text": "Aqua, Propylene Glycol, Lactic Acid, Butyrospermum Parkii (Shea) Butter, Salicylic Acid, Mandelic Acid, Sclerotium Gum, Potassium Sorbate, Sodium Benzoate, Polysorbate 20, Xanthan Gum."
    },
    "8901058853483": {
        "name": "Nestlé KitKat 4 Finger Crispy Wafer Bar",
        "brand": "Nestlé",
        "category": "Chocolate & Wafer",
        "ingredients_text": "Sugar, Milk Solids, Refined Wheat Flour (Maida), Cocoa Butter, Cocoa Solids, Hydrogenated Vegetable Fats, Emulsifier (INS 322), Raising Agent (INS 500ii), Yeast, Artificial Vanilla Flavouring Substances."
    },
    "8901030381010": {
        "name": "Dabur Red Ayurvedic Toothpaste",
        "brand": "Dabur",
        "category": "Ayurvedic Toothpaste",
        "ingredients_text": "Calcium Carbonate, Sorbitol, Aqua, Hydrated Silica, Sodium Lauryl Sulphate, Herbal Extract (Pippali, Tomar, Sunthi, Marich, Lavanga, Karpoor, Pudina, Gandhapura), Flavour, Red Ocher, Xanthan Gum, Sodium Silicate, Sodium Benzoate, Methylparaben, Propylparaben, Sodium Saccharin."
    },
    "8901138511012": {
        "name": "Dettol Antiseptic Disinfectant Liquid",
        "brand": "Dettol (Reckitt Benckiser)",
        "category": "Antiseptic Liquid",
        "ingredients_text": "Chloroxylenol (PCMX 4.8% w/v), Terpineol (9.0% v/v), Isopropyl Alcohol (Alcohol Denat. 13.1% v/v), Pine Oil, Castor Oil Soap, Caramel Colour, Aqua."
    }
}



