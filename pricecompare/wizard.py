"""`python -m pricecompare init`: write site.config.json for a city.

1. Resolve the city to its CBS locality code (סמל יישוב) through the public
   localities table on data.gov.il.
2. Ask every supported chain for its branch list and keep the chains that have
   at least one branch in the city.
3. Write the config, keeping any branding you already had.
"""

import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor

import requests

from . import config
from .chains import CHAINS, source_for
from .parse import matches_region

LOCALITIES_URL = "https://data.gov.il/api/3/action/datastore_search"
LOCALITIES_RESOURCE = "5c78e9fa-c2e2-4771-93ff-7f400a12f7ba"


def _clean(s):
    return " ".join(str(s or "").replace("-", " ").split()).strip().lower()


def find_city(query, get=requests.get):
    """Candidate localities for a Hebrew or English name: [{code, name, name_en}], exact matches first."""
    r = get(LOCALITIES_URL, params={"resource_id": LOCALITIES_RESOURCE, "q": query, "limit": 30}, timeout=30)
    r.raise_for_status()
    rows = r.json()["result"]["records"]
    out = [{"code": str(row["סמל_ישוב"]).strip(), "name": row["שם_ישוב"].strip(),
            "name_en": (row.get("שם_ישוב_לועזי") or "").strip().title()} for row in rows]
    q = _clean(query)
    exact = [c for c in out if q in (_clean(c["name"]), _clean(c["name_en"]))]
    return exact + [c for c in out if c not in exact]


def discover(region, chains=CHAINS, make_source=source_for, workers=8, log=print):
    """{chain key: [branch dicts]} for chains with branches in the region; portal errors are skipped."""
    def one(chain):
        try:
            stores = [s for s in make_source(chain).stores() if matches_region(s, region)]
            unique = list({s["store_id"]: s for s in stores}.values())
            return chain, unique, None
        except Exception as e:  # a slow or broken portal must not stop the wizard
            return chain, [], e
    found = {}
    with ThreadPoolExecutor(workers) as pool:
        for chain, stores, err in pool.map(one, chains):
            if err:
                log(f"  ! {chain['name']} ({chain['key']}): portal error, skipped ({type(err).__name__})")
            elif stores:
                log(f"  ✓ {chain['name']} ({chain['key']}): {len(stores)} branches")
                found[chain["key"]] = stores
            else:
                log(f"  · {chain['name']} ({chain['key']}): none")
    return found


def make_config(city, chain_keys, extra_names=(), existing=None):
    existing = existing or {}
    branding = dict(existing.get("branding") or {})
    branding["title_highlight"] = city["name"]
    branding["tagline"] = f"בונים סל קניות, ורואים באיזה סופר ב{city['name']} הוא יוצא הכי זול."
    branding.setdefault("title_prefix", "סל")
    branding["storage_prefix"] = (city["name_en"] or city["code"]).lower().replace(" ", "-")
    return {
        "region": {"name": city["name"], "name_en": city["name_en"], "city_codes": [city["code"]],
                   "names": [city["name"], *extra_names]},
        "chains": [c["key"] for c in CHAINS if c["key"] in chain_keys],
        "branding": branding,
        "images": bool(existing.get("images", False)),
    }


def run(argv_city=None, out=None, yes=False, extra_names=(), ask=input, log=print,
        find=find_city, scan=discover):
    out = out or config.path()
    query = argv_city or ask("City (Hebrew or English, e.g. נתניה / Netanya): ").strip()
    candidates = find(query)
    if not candidates:
        log(f"No locality matches {query!r} in the CBS table.")
        return 1
    city = candidates[0]
    if len(candidates) > 1 and not yes and _clean(query) not in (_clean(city["name"]), _clean(city["name_en"])):
        for i, c in enumerate(candidates[:10], 1):
            log(f"  {i}. {c['name']} / {c['name_en']} ({c['code']})")
        pick = ask("Pick a number [1]: ").strip() or "1"
        city = candidates[int(pick) - 1]
    log(f"City: {city['name']} / {city['name_en']} (CBS code {city['code']})")
    log("Looking for branches in every supported chain (takes a minute)…")
    region = {"name": city["name"], "city_codes": {city["code"]}, "names": [city["name"], *extra_names]}
    found = scan(region, log=log)
    if not found:
        log("No chain has a branch there. Nothing written.")
        return 1
    existing = {}
    if os.path.exists(out):
        try:
            with open(out, encoding="utf-8") as f:
                existing = json.load(f)
        except ValueError:
            pass
        if not yes and ask(f"Overwrite {out}? [y/N] ").strip().lower() not in ("y", "yes"):
            log("Cancelled.")
            return 1
    cfg = make_config(city, set(found), extra_names, existing)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
        f.write("\n")
    total = sum(len(v) for v in found.values())
    log(f"Wrote {out}: {len(found)} chains, {total} branches. Next: python -m pricecompare update && python -m pricecompare serve")
    return 0
