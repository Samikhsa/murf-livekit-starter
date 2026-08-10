# Day5.md — Catalogue & Pricing Tools for ShopMitra

A complete reference for the **two function-call tools** added in Day 5, how the data is structured, and how failure is handled gracefully.

---

## Why These Tools?

Day 4 gave ShopMitra memory. But memory of *past orders* is useless if the agent can't answer the most basic question a shopper asks:

> **"Do you have Basmati Rice? How much is it today?"**

Without a tool, the agent would either hallucinate a price or refuse to answer. Both are worse than silence. Day 5 fixes this by giving the agent two grounded tools:

| Tool | Answers |
|---|---|
| `check_catalogue` | "Is it in stock? What's the price?" |
| `compute_order_total` | "How much will my basket cost?" |

---

## Data Source

**Local (hand-built dataset)** — `backend/data/catalogue.json`

No public Indian grocery API with live per-item stock data was available. The catalogue is a hand-crafted JSON file with ~30 common grocery items across all ABC Store categories:

| Category | Example items |
|---|---|
| Grains | Basmati Rice, Sona Masoori Rice, Wheat Flour (Atta) |
| Pulses | Toor Dal, Moong Dal, Chana Dal, Masoor Dal |
| Dairy | Milk, Curd, Paneer, Butter, Ghee (out of stock) |
| Groceries | Cooking Oil, Sugar, Salt, Onion, Potato, Tomato, Spices |
| Beverages | Tea, Coffee, Bottled Water |
| Snacks | Marie Biscuits, Namkeen, Potato Chips |
| Household | Bath Soap, Detergent, Dish Wash Liquid |

Prices are representative of pan-India retail rates as of `2026-08-10`. The file includes a `price_last_updated` field so the agent always says *"As of today's data"* rather than claiming live prices.

---

## Tool 1: `check_catalogue`

**When it fires**: Any time a customer mentions a product name, asks "do you have…", or asks "how much is…"

**Tool description** (what the LLM sees):
> Search the ABC Store product catalogue for a product by name, category, or keyword. Call this tool EVERY TIME a customer asks about: whether a product is available or in stock; the price of any product; what products are in a given category. Do NOT invent prices or stock information — always call this tool first.

**Arguments**:
- `query` (str) — free-text search (e.g. "rice", "dal", "दूध")
- `category` (str | None) — optional filter (Groceries, Dairy, Pulses, etc.)

**Returns** (happy path):
```json
{
  "data_as_of": "2026-08-10",
  "results": [
    {
      "id": "rice_basmati_1kg",
      "name": "Basmati Rice",
      "name_hi": "बासमती चावल",
      "category": "Grains",
      "unit": "1 kg",
      "price_inr": 120,
      "in_stock": true,
      "quantity_available": 45
    }
  ],
  "total_found": 1
}
```

**Agent speaks**:
> "As of today's data, Basmati Rice is ₹120 per kilogram and we have it in stock."

**Returns** (failure path — catalogue file missing/corrupt):
```json
{
  "error": "catalogue_unavailable",
  "message": "The product catalogue is temporarily unavailable. Tell the customer..."
}
```

**Agent speaks**:
> "I'm having trouble checking our system right now. Let me connect you to our store staff who can help you directly."

---

## Tool 2: `compute_order_total`

**When it fires**: Customer selects multiple items and wants to know the total before confirming.

**Tool description** (what the LLM sees):
> Calculate the total cost of a customer's order. Call this when the customer has selected one or more products and wants to know how much they owe before confirming. Pass a list of products and quantities. Returns a line-item breakdown and grand total in ₹.

**Arguments**:
- `items_json` (str) — JSON-encoded list of `{product_id, quantity}` pairs

**Returns** (happy path):
```json
{
  "data_as_of": "2026-08-10",
  "line_items": [
    {"name": "Basmati Rice", "unit": "1 kg", "price_inr": 120, "quantity": 2, "subtotal_inr": 240},
    {"name": "Full Cream Milk", "unit": "1 litre", "price_inr": 60, "quantity": 3, "subtotal_inr": 180},
    {"name": "Sugar", "unit": "1 kg", "price_inr": 42, "quantity": 1, "subtotal_inr": 42}
  ],
  "grand_total_inr": 462,
  "unknown_ids": []
}
```

**Agent speaks**:
> "Your total comes to ₹462 — that's 2 kg Basmati Rice at ₹240, 3 litres of Milk at ₹180, and 1 kg Sugar at ₹42, as of today's prices."

---

## Search Scoring Algorithm

`catalogue.py` uses a simple relevance scorer (no external deps) to handle:
- Exact product name matches (+10 points)
- Hindi name matches (+10 points)
- Keyword matches — both English and Hindi transliterations (+5 points)
- Partial word matches (+2–3 points)
- Category matches (+4 points)

Results are sorted by score; the top 5 are returned. This allows queries like "doodh" (Hindi transliteration) to correctly find Full Cream Milk.

---

## Failure Handling Summary

| Failure | What happens | Agent says |
|---|---|---|
| `catalogue.json` missing | `CatalogueUnavailableError` raised, caught in tool | "I'm having trouble checking our system…" |
| `catalogue.json` corrupted (bad JSON) | `CatalogueUnavailableError` raised, caught in tool | "I'm having trouble checking our system…" |
| Unknown product_id in order | Added to `unknown_ids` list, rest of order calculated | "That item wasn't found, but your total for the rest is…" |
| Malformed `items_json` | JSON parse error, returns `invalid_input` error | "Could not parse the item list. Please try again." |

The agent **never goes silent** and **never invents a number**. Every failure path produces a spoken fallback.

---

## Day 5 Checklist

- [x] `check_catalogue` tool fires whenever a customer asks about a product or price
- [x] `compute_order_total` tool fires when customer wants a basket total
- [x] Returned data is spoken naturally — not read out as JSON
- [x] Data timestamp always mentioned: "as of today's data"
- [x] Catalogue file missing → graceful spoken fallback, not silence
- [x] Out-of-stock items handled: agent offers alternatives
- [x] Low stock (< 5 units) triggers proactive upsell mention
- [x] Day 4 memory chain: if past_orders match current query, agent offers to re-add
- [x] README states data source is local, not a live API
- [x] All tests passing (`test_catalogue.py`)

---

## Advanced — Replacing with a Live API

The `search_products()` and `compute_order_total()` functions in `catalogue.py` are the only place you'd need to change. Replace the JSON file read with an HTTP call:

```python
import httpx

async def search_products(query: str, category: str | None = None) -> dict:
    async with httpx.AsyncClient(timeout=3.0) as client:
        resp = await client.get(
            "https://your-inventory-api.example.com/search",
            params={"q": query, "category": category},
        )
        resp.raise_for_status()
        data = resp.json()
    # ... map to the same return shape
```

Add `try/except httpx.TimeoutException` and raise `CatalogueUnavailableError` — the tool layer and system prompt fallback are already in place.

---

*Part of the 10 Days of Voice Agents challenge — powered by Murf Falcon TTS.*
