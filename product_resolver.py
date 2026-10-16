"""
product_resolver.py
===================
Deterministic Verified Product Matching Pipeline for NutriScan · NY.
DEVELOPED BY NITIN YADAV

Follows strict priority:
  A. Scan and validate the barcode (format, length, GS1 checksum, leading zeros preserved).
  B. Search verified in-memory TTL cache for instantaneous recall.
  C. Search local SQLite database for an exact normalized barcode match.
  D. If no verified local match, query authoritative external databases in parallel with short-circuiting.
  E. Verify the returned product's barcode matches the scanned barcode before accepting.
  F. Classify product category using extensible Smart Category Classifier.
  G. Support optional package image cross-verification without UI changes.
  H. Never fabricate products, ingredients, or food scores when a barcode is unknown or non-food.
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import re
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from barcode_validator import BarcodeValidationResult, normalize_barcode_string, validate_barcode
from category_classifier import ProductCategory, classify_product, get_category_analysis_rules
from product_database import get_product_database

logger = logging.getLogger(__name__)

# User-Agent strictly identifying the application
USER_AGENT = "NutriScan-NY/2.0 (Product Safety Scanner; contact@nutriscan.ny; Nitin Yadav)"
REQUEST_TIMEOUT = 3.0
MAX_RETRIES = 1

# ─────────────────────────────────────────────────────────────────────────────
# In-Memory Verified Product TTL Cache
# ─────────────────────────────────────────────────────────────────────────────
_VERIFIED_RESOLVER_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_RESOLVER_CACHE_LOCK = threading.Lock()
_CACHE_TTL_SECONDS = 3600.0  # 1 hour


def clear_resolver_cache() -> None:
    """Clear all entries in the verified resolver cache."""
    with _RESOLVER_CACHE_LOCK:
        _VERIFIED_RESOLVER_CACHE.clear()


def get_resolver_cache_stats() -> Dict[str, Any]:
    """Return cache statistics for diagnostics and performance profiling."""
    with _RESOLVER_CACHE_LOCK:
        return {
            "size": len(_VERIFIED_RESOLVER_CACHE),
            "cached_barcodes": list(_VERIFIED_RESOLVER_CACHE.keys()),
        }


def query_external_api_with_backoff(url: str, timeout: float = REQUEST_TIMEOUT) -> Optional[Dict[str, Any]]:
    """
    HTTP GET request with timeout, exponential backoff, rate-limit detection,
    and schema validation.
    """
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
    }

    for attempt in range(MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as response:
                if response.status == 200:
                    raw_bytes = response.read()
                    data = json.loads(raw_bytes.decode("utf-8", errors="ignore"))
                    if isinstance(data, dict):
                        return data
                elif response.status == 429:
                    logger.warning("Rate limited (429) from %s on attempt %d", url, attempt)
                    time.sleep(0.5 * (attempt + 1))
                else:
                    logger.warning("External API HTTP %d for %s", response.status, url)
                    return None
        except urllib.error.HTTPError as http_err:
            if http_err.code == 404:
                return None
            if http_err.code == 429:
                logger.warning("HTTP 429 rate limit: %s", http_err)
                time.sleep(0.5 * (attempt + 1))
            else:
                logger.warning("HTTP error %s for %s", http_err, url)
        except urllib.error.URLError as url_err:
            logger.debug("Network / URL error on attempt %d: %s", attempt, url_err)
            if attempt < MAX_RETRIES:
                time.sleep(0.3 * (attempt + 1))
        except Exception as exc:
            logger.debug("Unexpected request exception on attempt %d: %s", attempt, exc)
            if attempt < MAX_RETRIES:
                time.sleep(0.3)

    return None


def fetch_and_verify_external_product(clean_barcode: str) -> Optional[Dict[str, Any]]:
    """
    Query Open Food Facts (global + Indian nodes) and Open Beauty Facts in parallel.
    Validates that the returned product record's code matches clean_barcode exactly.
    Short-circuits immediately when a valid matching product is returned.
    """
    endpoints = [
        f"https://world.openfoodfacts.org/api/v2/product/{clean_barcode}.json",
        f"https://in.openfoodfacts.org/api/v2/product/{clean_barcode}.json",
        f"https://world.openbeautyfacts.org/api/v2/product/{clean_barcode}.json",
    ]

    def _check_endpoint(ep: str) -> Optional[Dict[str, Any]]:
        data = query_external_api_with_backoff(ep, timeout=REQUEST_TIMEOUT)
        if not data:
            return None

        # Open Food Facts API schema validation
        status = data.get("status")
        product = data.get("product")
        if status == 1 and isinstance(product, dict):
            returned_code = normalize_barcode_string(
                product.get("code") or product.get("_id") or data.get("code") or ""
            )

            # Strict verification: Returned barcode must match the requested barcode
            if returned_code and returned_code != clean_barcode:
                logger.warning(
                    "External API returned mismatched barcode! Scanned: %s, Returned: %s. Discarding.",
                    clean_barcode,
                    returned_code,
                )
                return None

            # Check that product has at least a valid name
            p_name = (
                product.get("product_name")
                or product.get("product_name_en")
                or product.get("product_name_hi")
                or ""
            ).strip()

            if not p_name:
                return None

            brand = (
                product.get("brands")
                or product.get("brand_owner")
                or "Unknown Brand"
            ).strip()

            category = (
                product.get("categories")
                or (product.get("categories_tags_en", ["Food"])[0] if isinstance(product.get("categories_tags_en"), list) and product.get("categories_tags_en") else "Consumer Product")
            )
            if isinstance(category, list):
                category = ", ".join(category[:2])

            img_url = (
                product.get("image_front_url")
                or product.get("image_url")
                or product.get("image_small_url")
                or ""
            )

            nutriscore = (product.get("nutriscore_grade") or "").upper()

            ing_text = (
                product.get("ingredients_text")
                or product.get("ingredients_text_en")
                or product.get("ingredients_text_hi")
                or product.get("ingredients_text_with_allergens")
                or ""
            ).strip()

            source_name = "OPEN_BEAUTY_FACTS" if "openbeautyfacts" in ep else "OPEN_FOOD_FACTS"

            return {
                "barcode": clean_barcode,
                "name": p_name,
                "brand": brand,
                "category": category,
                "ingredients_text": ing_text,
                "image_url": img_url,
                "nutriscore": nutriscore,
                "verification_status": "VERIFIED" if ing_text else "PARTIALLY_VERIFIED",
                "confidence_score": 0.95 if ing_text else 0.70,
                "source": source_name,
            }

        return None

    # Execute parallel queries with fast short-circuit on first verified match
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(endpoints)) as executor:
        future_map = {executor.submit(_check_endpoint, ep): ep for ep in endpoints}
        for future in concurrent.futures.as_completed(future_map):
            try:
                res = future.result()
                if res is not None:
                    return res
            except Exception as exc:
                logger.debug("Parallel resolution exception: %s", exc)

    return None


def cross_verify_image_identity(product_name: str, brand: str, ocr_text: str) -> Tuple[bool, str]:
    """
    Cross-checks product name and brand keywords against front-label OCR text
    if an image is available. Image evidence never overrides an exact barcode,
    but acts as an additional confidence validator.
    """
    if not ocr_text or len(ocr_text.strip()) < 4:
        return True, "No image text provided for cross-verification."

    norm_ocr = ocr_text.lower()
    name_tokens = [t.lower() for t in re.split(r"[\s,\-\(\)]+", product_name) if len(t) > 3]
    brand_tokens = [t.lower() for t in re.split(r"[\s,\-\(\)]+", brand) if len(t) > 3]

    matched_tokens = [t for t in (name_tokens + brand_tokens) if t in norm_ocr]
    if matched_tokens:
        return True, f"Image cross-verification confirmed keywords: {', '.join(matched_tokens[:3])}"

    return False, "Visible package label keywords do not strongly match the database record."


def resolve_scanned_barcode(
    raw_barcode: str | int | None,
    image_ocr_text: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Full verified barcode identification pipeline:
      1. Normalize & preserve leading zeros.
      2. Checksum validation (EAN-13, UPC-A, EAN-8, GTIN-14).
      3. Check in-memory TTL verified cache for instant lookup.
      4. Query local SQLite database (exact match).
      5. Query external API (Open Food Facts / Open Beauty Facts) in parallel.
      6. Smart category classification & rule application.
      7. Safe caching in SQLite database for newly verified items.
      8. Return deterministic diagnostic payload on failure (never hallucinate!).
    """
    # Step A: Validate barcode
    val_res: BarcodeValidationResult = validate_barcode(raw_barcode)
    if not val_res.is_valid:
        return {
            "found": False,
            "is_valid_barcode": False,
            "barcode": val_res.normalized_barcode or str(raw_barcode or ""),
            "verification_status": "UNVERIFIED",
            "message": val_res.error_message or "Invalid barcode scanned.",
            "action_prompt": "Please hold the camera steady or scan the barcode again in good lighting.",
        }

    clean_code = val_res.normalized_barcode

    # Step B: Check in-memory verified cache
    with _RESOLVER_CACHE_LOCK:
        if clean_code in _VERIFIED_RESOLVER_CACHE:
            ts, cached_payload = _VERIFIED_RESOLVER_CACHE[clean_code]
            if time.time() - ts < _CACHE_TTL_SECONDS:
                logger.info("Verified cache hit for barcode %s", clean_code)
                return dict(cached_payload)
            else:
                del _VERIFIED_RESOLVER_CACHE[clean_code]

    db = get_product_database()

    # Step C: Local Database exact match
    local_prod = db.get_product_by_barcode(clean_code)
    if local_prod:
        logger.info("Verified local database match for barcode %s: %s", clean_code, local_prod["name"])
        ing_text = (local_prod.get("ingredients_text") or "").strip()
        specs = (local_prod.get("specifications") or "").strip()
        raw_cat = local_prod.get("category", "Consumer Product")

        # Smart Category Detection
        cat_enum, cat_conf, cat_rationale = classify_product(
            name=local_prod["name"],
            brand=local_prod.get("brand", ""),
            raw_category=raw_cat,
            ingredients_text=ing_text,
            specifications=specs,
        )
        rules = get_category_analysis_rules(cat_enum)
        has_ingredients = bool(ing_text)

        img_verified, img_note = cross_verify_image_identity(
            local_prod["name"], local_prod.get("brand", ""), image_ocr_text or ""
        )

        resolved_payload = {
            "found": True,
            "is_valid_barcode": True,
            "barcode": clean_code,
            "has_ingredients": has_ingredients,
            "verification_status": "VERIFIED" if (has_ingredients or not rules.supports_ingredients) else "PARTIALLY_VERIFIED",
            "confidence_score": local_prod.get("confidence_score", 1.0),
            "source": local_prod.get("source", "LOCAL_DATABASE"),
            "image_cross_verified": img_verified,
            "image_verification_note": img_note,
            "category": cat_enum.value,
            "category_type": cat_enum.name,
            "category_confidence": cat_conf,
            "category_rationale": cat_rationale,
            "analysis_rules": {
                "display_title": rules.display_title,
                "display_type": rules.display_type,
                "supports_food_score": rules.supports_food_score,
                "supports_ingredients": rules.supports_ingredients,
                "requires_handling_warnings": rules.requires_handling_warnings,
                "requires_medical_disclaimer": rules.requires_medical_disclaimer,
                "gauge_metric_label": rules.gauge_metric_label,
                "default_summary": rules.default_summary,
                "default_advice": rules.default_advice,
            },
            "product_info": {
                "name": local_prod["name"],
                "brand": local_prod.get("brand", "Packaged Product"),
                "category": cat_enum.value,
                "sub_category": raw_cat,
                "category_type": cat_enum.name,
                "image_url": local_prod.get("image_url", ""),
                "nutriscore": local_prod.get("nutriscore", "") if rules.supports_food_score else "",
                "barcode": clean_code,
                "specifications": specs,
                "supports_food_score": rules.supports_food_score,
                "supports_ingredients": rules.supports_ingredients,
            },
            "ingredients_text": ing_text,
            "specifications": specs,
        }

        # Cache verified record
        with _RESOLVER_CACHE_LOCK:
            _VERIFIED_RESOLVER_CACHE[clean_code] = (time.time(), dict(resolved_payload))

        return resolved_payload

    # Step D: External API parallel query with strict barcode check
    external_prod = fetch_and_verify_external_product(clean_code)
    if external_prod:
        logger.info("Verified external match for barcode %s: %s", clean_code, external_prod["name"])
        # Persist verified record into local database safely
        try:
            db.upsert_product(
                barcode=clean_code,
                name=external_prod["name"],
                brand=external_prod["brand"],
                category=external_prod.get("category", "Consumer Product"),
                ingredients_text=external_prod.get("ingredients_text", ""),
                image_url=external_prod.get("image_url", ""),
                nutriscore=external_prod.get("nutriscore", ""),
                verification_status=external_prod["verification_status"],
                confidence_score=external_prod["confidence_score"],
                source=external_prod["source"],
                reason="Automatic verified external lookup caching",
            )
        except Exception as db_err:
            logger.warning("Could not cache external product in database: %s", db_err)

        ing_text = (external_prod.get("ingredients_text") or "").strip()
        raw_cat = external_prod.get("category", "Consumer Product")

        # Smart Category Detection
        cat_enum, cat_conf, cat_rationale = classify_product(
            name=external_prod["name"],
            brand=external_prod.get("brand", ""),
            raw_category=raw_cat,
            ingredients_text=ing_text,
        )
        rules = get_category_analysis_rules(cat_enum)
        has_ingredients = bool(ing_text)

        resolved_payload = {
            "found": True,
            "is_valid_barcode": True,
            "barcode": clean_code,
            "has_ingredients": has_ingredients,
            "verification_status": external_prod["verification_status"],
            "confidence_score": external_prod["confidence_score"],
            "source": external_prod["source"],
            "category": cat_enum.value,
            "category_type": cat_enum.name,
            "category_confidence": cat_conf,
            "category_rationale": cat_rationale,
            "analysis_rules": {
                "display_title": rules.display_title,
                "display_type": rules.display_type,
                "supports_food_score": rules.supports_food_score,
                "supports_ingredients": rules.supports_ingredients,
                "requires_handling_warnings": rules.requires_handling_warnings,
                "requires_medical_disclaimer": rules.requires_medical_disclaimer,
                "gauge_metric_label": rules.gauge_metric_label,
                "default_summary": rules.default_summary,
                "default_advice": rules.default_advice,
            },
            "product_info": {
                "name": external_prod["name"],
                "brand": external_prod["brand"],
                "category": cat_enum.value,
                "sub_category": raw_cat,
                "category_type": cat_enum.name,
                "image_url": external_prod.get("image_url", ""),
                "nutriscore": external_prod.get("nutriscore", "") if rules.supports_food_score else "",
                "barcode": clean_code,
                "specifications": "",
                "supports_food_score": rules.supports_food_score,
                "supports_ingredients": rules.supports_ingredients,
            },
            "ingredients_text": ing_text,
            "specifications": "",
        }

        # Cache verified external record
        with _RESOLVER_CACHE_LOCK:
            _VERIFIED_RESOLVER_CACHE[clean_code] = (time.time(), dict(resolved_payload))

        return resolved_payload

    # Step E: Product not verified. Honest error state. NEVER hallucinate!
    return {
        "found": False,
        "is_valid_barcode": True,
        "barcode": clean_code,
        "verification_status": "UNVERIFIED",
        "confidence_score": 0.0,
        "source": "NONE",
        "category": ProductCategory.UNKNOWN.value,
        "category_type": ProductCategory.UNKNOWN.name,
        "message": f"Product not verified for Barcode #{clean_code}. Please scan again or check the barcode.",
        "action_prompt": "You can take a clear photo of the ingredient list on the physical package to analyze its safety!",
    }
