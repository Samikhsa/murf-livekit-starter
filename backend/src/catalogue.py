"""
catalogue.py — Product catalogue and order tools for ShopMitra (Day 5)

Uses a hand-built local JSON catalogue (`backend/data/catalogue.json`).
Data source: local — not a live API. Prices are representative of pan-India
retail rates as of the date stamped in the catalogue's _meta.price_last_updated
field. See README for details.

Public API
----------
search_products(query, category=None)  -> dict
compute_order_total(items)             -> dict
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger("agent.catalogue")

# ---------------------------------------------------------------------------
# Catalogue file location
# ---------------------------------------------------------------------------
_CATALOGUE_PATH = Path(__file__).resolve().parents[1] / "data" / "catalogue.json"

# In-memory cache — loaded once on first access
_catalogue_cache: dict | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_catalogue() -> dict:
    """Load (or return cached) the catalogue JSON."""
    global _catalogue_cache
    if _catalogue_cache is None:
        with open(_CATALOGUE_PATH, encoding="utf-8") as f:
            _catalogue_cache = json.load(f)
        logger.info(
            "Catalogue loaded: %d products, prices as of %s",
            len(_catalogue_cache["products"]),
            _catalogue_cache["_meta"]["price_last_updated"],
        )
    return _catalogue_cache


def _score_match(product: dict, query_lower: str) -> int:
    """
    Return a relevance score for a product against a query string.
    Higher is more relevant. 0 means no match.
    """
    score = 0
    q = query_lower.strip()

    # Exact match on product name
    if q in product["name"].lower():
        score += 10
    if q in product["name_hi"]:
        score += 10

    # Keyword match
    for kw in product.get("keywords", []):
        if q in kw.lower() or kw.lower() in q:
            score += 5

    # Partial word matches on name
    for word in q.split():
        if len(word) >= 3:
            if word in product["name"].lower():
                score += 3
            for kw in product.get("keywords", []):
                if word in kw.lower():
                    score += 2

    # Category match
    if q in product["category"].lower():
        score += 4

    return score


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def search_products(query: str, category: str | None = None) -> dict:
    """
    Search the ABC Store product catalogue by name, keyword, or category.

    Args:
        query:    Free-text search string (product name, Hindi name, keyword).
        category: Optional category filter — one of: Groceries, Dairy, Pulses,
                  Grains, Snacks, Beverages, Household.

    Returns a dict with:
        - data_as_of:  date the prices were last updated
        - results:     list of up to 5 matching products (sorted by relevance)
        - total_found: number of results returned
    """
    try:
        cat = _load_catalogue()
    except FileNotFoundError:
        logger.error("Catalogue file not found at %s", _CATALOGUE_PATH)
        raise CatalogueUnavailableError("Catalogue file missing.")
    except json.JSONDecodeError as exc:
        logger.error("Catalogue JSON is malformed: %s", exc)
        raise CatalogueUnavailableError("Catalogue data is corrupted.")

    products = cat["products"]
    query_lower = query.lower()

    # Optional category filter (case-insensitive)
    if category:
        cat_lower = category.lower()
        products = [p for p in products if p["category"].lower() == cat_lower]

    # Score and sort
    scored = [
        (p, _score_match(p, query_lower))
        for p in products
    ]
    scored = [(p, s) for p, s in scored if s > 0]
    scored.sort(key=lambda x: x[1], reverse=True)

    top = scored[:5]

    results = []
    for product, _ in top:
        results.append({
            "id": product["id"],
            "name": product["name"],
            "name_hi": product["name_hi"],
            "category": product["category"],
            "unit": product["unit"],
            "price_inr": product["price_inr"],
            "in_stock": product["in_stock"],
            "quantity_available": product["quantity_available"],
        })

    return {
        "data_as_of": cat["_meta"]["price_last_updated"],
        "results": results,
        "total_found": len(results),
    }


def compute_order_total(items: list[dict]) -> dict:
    """
    Compute the total cost of an order.

    Args:
        items: List of dicts, each with:
               - product_id  (str)  — the product's `id` field from catalogue
               - quantity    (int or float)  — number of units

    Returns a dict with:
        - data_as_of:    date the prices were last updated
        - line_items:    list of {name, unit, price_inr, quantity, subtotal}
        - grand_total:   total in ₹ (int)
        - unknown_ids:   list of product_ids not found in the catalogue
    """
    try:
        cat = _load_catalogue()
    except FileNotFoundError:
        logger.error("Catalogue file not found at %s", _CATALOGUE_PATH)
        raise CatalogueUnavailableError("Catalogue file missing.")
    except json.JSONDecodeError as exc:
        logger.error("Catalogue JSON is malformed: %s", exc)
        raise CatalogueUnavailableError("Catalogue data is corrupted.")

    product_map = {p["id"]: p for p in cat["products"]}

    line_items = []
    grand_total = 0
    unknown_ids = []

    for item in items:
        pid = str(item.get("product_id", "")).strip()
        try:
            qty = float(item.get("quantity", 1))
        except (TypeError, ValueError):
            qty = 1.0

        if pid not in product_map:
            unknown_ids.append(pid)
            continue

        product = product_map[pid]
        subtotal = round(product["price_inr"] * qty)
        grand_total += subtotal

        line_items.append({
            "name": product["name"],
            "unit": product["unit"],
            "price_inr": product["price_inr"],
            "quantity": qty,
            "subtotal_inr": subtotal,
        })

    return {
        "data_as_of": cat["_meta"]["price_last_updated"],
        "line_items": line_items,
        "grand_total_inr": grand_total,
        "unknown_ids": unknown_ids,
    }


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class CatalogueUnavailableError(Exception):
    """Raised when the catalogue cannot be loaded (missing file, bad JSON)."""
