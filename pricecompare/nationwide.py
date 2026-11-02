"""Hosted nationwide mode: one site for every Israeli city.

`python -m pricecompare national` downloads every chain's branch list and
price files once and writes sharded output for the hosted site:

    data/index.json              cities that have branches:
                                 {"generated", "cities": [[code, name, name_en, lat, lon, stores, chains]]}
    data/cities/<code>.json      one data file per city, in the same layout as
                                 the single-city data.json (see build.py), with
                                 only that city's branches and the products they price

Branches are placed in a city by the CBS locality code in the chain's Stores
file, or, when a chain leaves it empty, by the locality name found in the
branch name or address. The page maps a city without branches to the nearest
covered city within FALLBACK_KM (see web/index.html).

Downloads are cached per branch under .cache/national/ so the slow part can be
resumed, and so sharding runs with one city in memory at a time.
"""

import gzip
import json
import logging
import os
import pickle
import re
import shutil
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from . import promos
from .build import assemble
from .chains import CHAINS, source_for
from .parse import parse_prices

log = logging.getLogger("pricecompare")

HERE = os.path.dirname(os.path.abspath(__file__))
SETTLEMENTS = os.path.join(HERE, "settlements.json")
FALLBACK_KM = 15
# Product list cap per city file: products priced in the most branches first.
# Generic fresh products are separate and always kept.
# 25,000 covers every product sold in 3+ Tel Aviv branches and keeps the
# biggest city file around 10 MB (about 2 MB gzipped on the wire).
MAX_PRODUCTS = int(os.environ.get("MAX_PRODUCTS", "25000")) or None

# Names chains write that differ from the CBS spelling.
ALIASES = {
    "תל אביב": "5000", "תל אביב יפו": "5000", "ת א": "5000", "יפו": "5000",
    "ראשון לציון": "8300", "ראשלצ": "8300", "פתח תקוה": "7900", "פתח תקווה": "7900", "פת": None,
    "באר שבע": "9000", "מודיעין": "1200", "קרית אתא": "6800", "נצרת עילית": "1061",
    "מעלות": "1063", "הרצליה": "6400", "רעננה": "8700", "כפר סבא": "6900",
}


# Locality names that are also everyday words in addresses ("אזור התעשייה",
# "רחוב", "שדרות ירושלים"); they never count in an address, and in a branch name
# only when they are not plain street words (or the name starts with them).
COMMON_WORDS = {"אזור", "רחוב", "אלון", "שדרות", "יעל", "גנים", "מעוז", "כרמים", "הדרים", "צור", "נווה", "מרכז",
                "אמירים", "עומר", "שחר", "ניר", "גבעות", "אורה", "שוקדה", "דליה", "רינתיה", "אביגיל", "לשם"}
STREET_WORDS = {"אזור", "רחוב", "מרכז", "אלון"}


def load_settlements(path=SETTLEMENTS):
    """[[code, name, name_en, lat, lon]] (CBS codes as strings)."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _norm(text):
    text = re.sub(r"[\"'`׳״\-–_()*.,/\\]", " ", text or "")
    text = text.replace("קריית", "קרית").replace("תקווה", "תקוה")
    return " " + " ".join(text.split()) + " "


class Locator:
    """Place a branch in a CBS locality."""

    def __init__(self, settlements):
        self.by_code = {s[0]: s for s in settlements}
        names = {}
        for code, name, *_ in settlements:
            n = _norm(name).strip()
            names.setdefault(n, code)
            short = _norm(re.split(r"\s+-\s+|-", name)[0]).strip()
            if len(short) >= 3 and short != n:
                names.setdefault(short, code)
        for alias, code in ALIASES.items():
            n = _norm(alias).strip()
            if code is None:
                names.pop(n, None)
            elif code in self.by_code:
                names[n] = code
        # Longest names first so "קרית אתא" wins over "אתא" and "תל אביב" over "אביב".
        self.names = sorted(((n, c) for n, c in names.items() if len(n.replace(" ", "")) >= 3),
                            key=lambda nc: -len(nc[0]))

    def find_in(self, text, is_address=False):
        hay = _norm(text)
        for name, code in self.names:
            if f" {name} " not in hay:
                continue
            if name in COMMON_WORDS and (is_address or (name in STREET_WORDS and not hay.startswith(f" {name} "))):
                continue
            return code
        return None

    def city_of(self, store):
        raw = (store.get("city") or "").strip()
        if raw.isdigit() and str(int(raw)) in self.by_code:
            return str(int(raw))
        texts = [(raw, False), (store.get("name", ""), False), (store.get("address", ""), True)]
        for text, is_address in texts:
            if text and text != "unknown":
                code = self.find_in(text, is_address)
                if code:
                    return code
        return None


def _cache_file(cache, chain_key, store_id):
    return os.path.join(cache, chain_key, re.sub(r"[^\w-]", "_", store_id) + ".pkl.gz")


def collect_chain(chain, locator, cache, workers=4, max_age_h=20):
    """Download one chain's branches into the cache; returns the number of branches cached."""
    key = chain["key"]
    try:
        source = source_for(chain)
        stores = list({s["store_id"]: s for s in source.stores()}.values())
        placed = [(s, locator.city_of(s)) for s in stores]
        missing = [s for s, c in placed if not c]
        if missing:
            log.warning("%s: %d of %d branches have no known city, skipped: %s", key, len(missing), len(stores),
                        "; ".join(f"{s['name']} / {s['address']}" for s in missing[:8]))
        placed = [(s, c) for s, c in placed if c]
        fresh = time.time() - max_age_h * 3600
        todo = [(s, c) for s, c in placed
                if not (os.path.exists(_cache_file(cache, key, s["store_id"])) and
                        os.path.getmtime(_cache_file(cache, key, s["store_id"])) > fresh)]
        log.info("%s: %d branches in %d cities, %d to download", key, len(placed), len({c for _, c in placed}), len(todo))
        if not todo:
            return len(placed)
        ids = [s["store_id"] for s, _ in todo]
        files = source.latest_price_files(ids)
        try:
            promo_files = source.latest_promo_files(ids)
        except Exception:
            log.exception("%s: listing promotions failed", key)
            promo_files = {}

        def one(sc):
            store, city = sc
            sid = store["store_id"]
            fetch = files.get(sid)
            if not fetch:
                log.warning("%s store %s: no PriceFull file", key, sid)
                return 0
            try:
                items = list(parse_prices(fetch()))
            except Exception:
                log.exception("%s store %s: prices failed", key, sid)
                return 0
            if not items:
                return 0
            deals = []
            if promo_files.get(sid):
                try:
                    deals = list(promos.parse_promos(promo_files[sid]()))
                except Exception:
                    log.exception("%s store %s: promotions failed", key, sid)
            path = _cache_file(cache, key, sid)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with gzip.open(path + ".tmp", "wb", compresslevel=3) as f:
                pickle.dump({"store": store, "city": city, "items": items, "deals": deals}, f, protocol=4)
            os.replace(path + ".tmp", path)
            return 1

        with ThreadPoolExecutor(workers) as pool:
            done = sum(pool.map(one, todo))
        log.info("%s: cached %d of %d branches", key, done, len(todo))
        return len(placed)
    except Exception:  # one broken portal must not sink the whole update
        log.exception("%s: failed", key)
        return 0


def collect(cache, chains=CHAINS, settlements=None, workers=10, max_age_h=20):
    locator = Locator(settlements or load_settlements())
    with ThreadPoolExecutor(workers) as pool:
        list(pool.map(lambda c: collect_chain(c, locator, cache, max_age_h=max_age_h), chains))


def _cached(cache, max_age_h):
    """{city code: [(chain key, path)]} for cache entries fresh enough to publish."""
    out = defaultdict(list)
    limit = time.time() - max_age_h * 3600
    for chain_key in sorted(os.listdir(cache)) if os.path.isdir(cache) else []:
        folder = os.path.join(cache, chain_key)
        for name in sorted(os.listdir(folder)):
            path = os.path.join(folder, name)
            if not name.endswith(".pkl.gz") or os.path.getmtime(path) < limit:
                continue
            with gzip.open(path, "rb") as f:
                city = pickle.load(f)["city"]
            out[city].append((chain_key, path))
    return out


def trim(data, max_products):
    """Keep the `max_products` products priced in the most branches (generic products are separate)."""
    if not max_products or len(data["products"]) <= max_products:
        return data
    keep = max_products  # products are already sorted by how many branches price them
    for key in ("prices", "sprices"):
        packed = []
        for flat in data[key]:
            out, i, prev = [], 0, 0
            for k in range(0, len(flat), 2):
                i += flat[k]
                if i < keep:
                    out += [i - prev, flat[k + 1]]
                    prev = i
            packed.append(out)
        data[key] = packed
    data["products"] = data["products"][:keep]
    # Drop deals no kept product uses, and renumber the rest.
    used = sorted({flat[k + 1] for flat in data["sprices"] for k in range(0, len(flat), 2)})
    remap = {old: new for new, old in enumerate(used)}
    data["promos"] = [data["promos"][i] for i in used]
    data["sprices"] = [[v if k % 2 == 0 else remap[v] for k, v in enumerate(flat)] for flat in data["sprices"]]
    return data


def city_data(entries, settlement, max_products=MAX_PRODUCTS):
    """Data file for one city from its cached branches: [(chain key, path)]."""
    by_chain = defaultdict(list)
    for chain_key, path in entries:
        with gzip.open(path, "rb") as f:
            e = pickle.load(f)
        by_chain[chain_key].append((e["store"], e["items"], e["deals"]))
    chains = [c for c in CHAINS if c["key"] in by_chain]
    results = [(c, ([s for s, _, _ in by_chain[c["key"]]], by_chain[c["key"]])) for c in chains]
    data = assemble(results, chains, settlement[1])
    data["city"] = settlement[0]
    return trim(data, max_products)


def shard(cache, out_dir, settlements=None, max_age_h=36, max_products=MAX_PRODUCTS):
    """Write data/index.json and data/cities/*.json; returns the index."""
    settlements = settlements or load_settlements()
    by_code = {s[0]: s for s in settlements}
    cities_dir = os.path.join(out_dir, "cities")
    tmp = cities_dir + ".new"
    shutil.rmtree(tmp, ignore_errors=True)
    os.makedirs(tmp)
    index, total = [], 0
    for code, entries in sorted(_cached(cache, max_age_h).items(), key=lambda kv: int(kv[0])):
        data = city_data(entries, by_code[code], max_products)
        if not data["stores"]:
            continue
        path = os.path.join(tmp, f"{code}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        total += os.path.getsize(path)
        s = by_code[code]
        index.append([code, s[1], s[2], s[3], s[4], len(data["stores"]), len({x["chain"] for x in data["stores"]})])
        log.info("city %s %s: %d branches, %d products, %.1f MB", code, s[1], len(data["stores"]),
                 len(data["products"]), os.path.getsize(path) / 1e6)
    if not index:
        raise RuntimeError("no city has fresh prices; keeping the previous data")
    shutil.rmtree(cities_dir, ignore_errors=True)
    os.replace(tmp, cities_dir)
    out = {"generated": datetime.now(timezone.utc).isoformat(timespec="minutes"), "fallback_km": FALLBACK_KM,
           "cities": index}
    with open(os.path.join(out_dir, "index.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    log.info("wrote %d city files, %.1f MB in total", len(index), total / 1e6)
    return out


def main(out_dir, cache, skip_download=False, max_age_h=20):
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    if not skip_download:
        collect(cache, max_age_h=max_age_h)
    shard(cache, out_dir)
