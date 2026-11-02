"""Site configuration: region, chains and branding, read from site.config.json.

The file lives at the repository root (override with the SITE_CONFIG
environment variable). `python -m pricecompare init` writes it for your city.
"""

import json
import os

from .chains import BY_KEY

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_PATH = os.path.join(ROOT, "site.config.json")

DEFAULT_BRANDING = {
    "title_prefix": "סל",
    "tagline": "",
    "logo": "",
    "favicon": "",
    "storage_prefix": "",
    "colors": {},
    "colors_dark": {},
}


class ConfigError(ValueError):
    pass


def path():
    return os.environ.get("SITE_CONFIG", DEFAULT_PATH)


def load(file=None):
    """Read and validate the config; returns a dict with every field filled in."""
    file = file or path()
    try:
        with open(file, encoding="utf-8") as f:
            raw = json.load(f)
    except FileNotFoundError:
        raise ConfigError(f"{file} not found. Run `python -m pricecompare init` to create it.") from None
    except ValueError as e:
        raise ConfigError(f"{file} is not valid JSON: {e}") from None
    return normalize(raw)


def normalize(raw):
    region = raw.get("region") or {}
    name = region.get("name")
    if not name:
        raise ConfigError("region.name is required")
    codes = [str(c) for c in region.get("city_codes", [])]
    names = list(region.get("names") or [name])
    if not codes and not names:
        raise ConfigError("region needs city_codes or names")

    keys = raw.get("chains", "all")
    if keys == "all":
        keys = list(BY_KEY)
    unknown = [k for k in keys if k not in BY_KEY]
    if unknown:
        raise ConfigError(f"unknown chains: {', '.join(unknown)} (see pricecompare/chains.py)")
    if not keys:
        raise ConfigError("chains must list at least one chain")

    branding = {**DEFAULT_BRANDING, **(raw.get("branding") or {})}
    branding.setdefault("title_highlight", name)
    if not branding.get("title_highlight"):
        branding["title_highlight"] = name
    if not branding["tagline"]:
        branding["tagline"] = f"בונים סל קניות, ורואים באיזה סופר ב{name} הוא יוצא הכי זול."
    if not branding["storage_prefix"]:
        branding["storage_prefix"] = "basket-" + (codes[0] if codes else "site")

    return {
        "region": {"name": name, "name_en": region.get("name_en", ""), "city_codes": set(codes), "names": names},
        "chains": [BY_KEY[k] for k in keys],
        "branding": branding,
        "images": bool(raw.get("images", False)),
    }


def hosted():
    """Config of the hosted nationwide site: every chain, the city is picked on the page."""
    return normalize({
        "region": {"name": "ישראל", "name_en": "Israel", "city_codes": [], "names": ["ישראל"]},
        "chains": "all",
        "branding": {
            "title_prefix": "סל",
            "title_highlight": "בעיר שלך",
            "tagline": "בוחרים עיר, בונים סל קניות, ורואים באיזה סופר באזור הוא יוצא הכי זול.",
            "storage_prefix": "il-basket",
            "colors": {"--accent": "#0f5b45", "--tag": "#ffd233"},
        },
        "images": False,
    })
