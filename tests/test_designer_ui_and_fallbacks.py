# tests/test_designer_ui_and_fallbacks.py
"""
Test Suite for NutriScan Senior Designer UI, Zero-Purple/Pink Theme,
Light/Dark/System Theme Switcher, and Smart Category Formulation Fallbacks.
"""

import re
import pytest
from pathlib import Path

FRONTEND_PATH = Path("frontend/index.html")

@pytest.fixture
def frontend_content():
    return FRONTEND_PATH.read_text(encoding="utf-8")

def test_zero_emojis_in_frontend(frontend_content):
    """Ensure the entire app contains strictly ZERO emojis."""
    emoji_pattern = re.compile(
        "[\U00010000-\U0010ffff]|[\u2600-\u27bf]|[\u2300-\u23ff]|[\u2b50-\u2b55]|[\u203c-\u2049]|[\u25aa-\u25fe]",
        flags=re.UNICODE
    )
    matches = emoji_pattern.findall(frontend_content)
    assert len(matches) == 0, f"Found unexpected emojis: {[hex(ord(c)) for c in matches]}"

def test_zero_dark_purple_or_pink_tokens(frontend_content):
    """Ensure all dark purple, magenta, and neon pink accents are completely eradicated."""
    forbidden = ["#ec4899", "rgba(236, 72, 153", "rgba(236,72,153", "#f472b6", "#a855f7"]
    for token in forbidden:
        assert token.lower() not in frontend_content.lower(), f"Forbidden color token found: {token}"

def test_light_and_dark_theme_support(frontend_content):
    """Ensure data-theme='light' and data-theme='dark' design tokens and JS controllers exist."""
    assert 'html[data-theme="dark"]' in frontend_content
    assert 'html[data-theme="light"]' in frontend_content
    assert '--bg-main: #090d16' in frontend_content
    assert '--bg-main: #f8fafc' in frontend_content
    assert 'function initThemeSystem' in frontend_content
    assert 'function setAppTheme' in frontend_content
    assert 'function cycleAppTheme' in frontend_content
    assert 'id="theme-toggle-btn"' in frontend_content
    assert 'id="theme-btn-light"' in frontend_content
    assert 'id="theme-btn-dark"' in frontend_content
    assert 'id="theme-btn-system"' in frontend_content

def test_mobile_designer_button_system(frontend_content):
    """Ensure professional tactile buttons without oversized neon AI glow."""
    assert '.btn-primary' in frontend_content
    assert '.btn-secondary' in frontend_content
    assert '.shutter-main-ring' in frontend_content
    assert '.shutter-main-core' in frontend_content
    assert 'transform: scale(0.97)' in frontend_content

def test_category_formulation_benchmarks_exist(frontend_content):
    """Ensure category formulation benchmarks prevent dead-end 'unavailable' errors."""
    assert 'var CATEGORY_BENCHMARKS = {' in frontend_content
    assert 'FOOD_AND_SNACKS' in frontend_content
    assert 'SKINCARE' in frontend_content
    assert 'HAIRCARE_AND_PERSONAL_CARE' in frontend_content
    assert 'HOUSEHOLD_PRODUCTS' in frontend_content
    assert 'MEDICINES_AND_MEDICAL' in frontend_content
    assert 'benchmark-notice-box' in frontend_content
    assert 'Scan Physical Packaging Label' in frontend_content

def test_unregistered_product_resolution_card(frontend_content):
    """Ensure unlisted barcodes provide actionable camera OCR and search rather than broken errors."""
    assert 'function renderUnverifiedBarcodeResult' in frontend_content
    assert 'Unregistered Product Barcode' in frontend_content
    assert 'Scan Ingredient Label (Camera OCR)' in frontend_content
    assert 'Search by Product Name' in frontend_content

def test_expanded_product_catalog(frontend_content):
    """Ensure top everyday consumer brands are available in LOCAL_PRODUCT_DB."""
    sample_barcodes = [
        ("8901499008589", "Kurkure Masala Munch"),
        ("8901499008602", "Lay's India's Magic Masala"),
        ("8901719101038", "Parle-G"),
        ("8901058852394", "Maggi 2-Minute Masala"),
        ("8901233024035", "Cadbury Dairy Milk"),
        ("8901262010108", "Amul Pasteurised Salted Butter"),
        ("8901764012235", "Coca-Cola Original"),
        ("8901396001027", "Dettol Original"),
        ("8901030001017", "Dove Cream Beauty"),
        ("8901117001008", "Crocin 650"),
        ("8901396112006", "Colin Glass and Surface Cleaner"),
        ("8901396144007", "Lizol Disinfectant Surface Floor Cleaner"),
        ("0034993000019", "Cetaphil Gentle Skin Cleanser"),
        ("8906128100016", "Minimalist SPF 50 Multi-Vitamin Sunscreen")
    ]
    for code, name in sample_barcodes:
        assert code in frontend_content, f"Barcode {code} ({name}) not found in LOCAL_PRODUCT_DB"

def test_all_five_navigation_pages(frontend_content):
    """Ensure all 5 tabs and views are present and wired up."""
    for p in ["scan", "report", "history", "guide", "profile"]:
        assert f'id="page-{p}"' in frontend_content
        assert f'id="nav-btn-{p}"' in frontend_content
