"""Shrink a full data.json into web/sample-data.json (popular products only).

    python scripts/make_sample.py full-data.json [--products 600]
"""

import argparse
import json


MUST = {"7290004131074", "7290004127329", "7290000066318", "7290000176420", "7290000060880", "7290106577282"}  # the page's example basket


def shrink(data, keep):
    n = len(data["products"])
    pop = [0] * n
    stores_prices = []
    for flat in data["prices"]:
        d, i = {}, 0
        for k in range(0, len(flat), 2):
            i += flat[k]; d[i] = flat[k + 1]; pop[i] += 1
        stores_prices.append(d)
    top = sorted(range(n), key=lambda i: (-pop[i], i))[:keep]
    chosen = sorted(set(top) | {i for i, p in enumerate(data["products"]) if p[0] in MUST})
    remap = {old: new for new, old in enumerate(chosen)}
    used_deals = {}
    out = dict(data)
    out["products"] = [data["products"][i] for i in chosen]
    out["prices"] = []
    for d in stores_prices:
        flat, prev = [], 0
        for old in chosen:
            if old in d:
                flat += [remap[old] - prev, d[old]]; prev = remap[old]
        out["prices"].append(flat)
    out["sprices"] = []
    for flat in data.get("sprices", []):
        res, i, prev = [], 0, 0
        for k in range(0, len(flat), 2):
            i += flat[k]
            if i in remap:
                deal = used_deals.setdefault(flat[k + 1], len(used_deals))
                res += [remap[i] - prev, deal]; prev = remap[i]
        out["sprices"].append(res)
    table = data.get("promos", [])
    out["promos"] = [table[old] for old, _ in sorted(used_deals.items(), key=lambda kv: kv[1])]
    for s, d in zip(out["stores"], out["prices"]):
        s["items"] = len(d) // 2
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--products", type=int, default=600)
    ap.add_argument("--out", default="web/sample-data.json")
    a = ap.parse_args()
    with open(a.src, encoding="utf-8") as f:
        data = shrink(json.load(f), a.products)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
