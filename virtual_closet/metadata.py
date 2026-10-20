"""Shared upload review and naming rules."""
from .attributes import CATEGORIES, SUBCATEGORIES
UNKNOWN = {"", "unknown", "none", "other / unspecified", "uncategorized"}

def clean_brand(value):
    return (value or "").strip() or None

def reviewed_attributes(attributes, category):
    attrs = dict(attributes)
    category = (category or "").strip() or "Uncategorized"
    category = next((c for c in CATEGORIES if c.casefold() == category.casefold()), category)
    attrs["Category"] = category
    if attrs.get("Subcategory") not in SUBCATEGORIES.get(category, []):
        attrs["Subcategory"] = "Other / unspecified"
    return attrs

def automatic_name(attributes, brand=None):
    brand = clean_brand(brand)
    color = str(attributes.get("Color") or "").strip()
    sub = str(attributes.get("Subcategory") or "").strip()
    category = str(attributes.get("Category") or "").strip()
    kind = sub if sub.casefold() not in UNKNOWN else category
    parts = [brand, color if color.casefold() not in UNKNOWN else None,
             kind if kind.casefold() not in UNKNOWN else None]
    return " ".join(p for p in parts if p) or "Clothing item"

def saved_name(value, attributes, brand=None):
    return (value or "").strip() or automatic_name(attributes, brand)

