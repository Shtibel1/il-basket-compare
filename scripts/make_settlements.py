"""Rebuild pricecompare/settlements.json: every Israeli locality with its coordinates.

Names and CBS locality codes (סמל יישוב) come from the CBS localities table on
data.gov.il; coordinates come from Wikidata (CC0), joined on the CBS code
(property P3466), because the CBS file with coordinates is not publicly
downloadable. Run it once in a while; the output is committed.

    python scripts/make_settlements.py
"""

import json
import os
import re

import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "pricecompare", "settlements.json")
LOCALITIES = "https://data.gov.il/api/3/action/datastore_search"
RESOURCE = "5c78e9fa-c2e2-4771-93ff-7f400a12f7ba"
SPARQL = "https://query.wikidata.org/sparql"
UA = {"User-Agent": "il-basket-compare/1.0 (https://github.com/Shtibel1/il-basket-compare)"}


def main():
    rows = requests.get(LOCALITIES, params={"resource_id": RESOURCE, "limit": 5000}, headers=UA, timeout=60).json()["result"]["records"]
    q = "SELECT ?code (SAMPLE(?c) AS ?coord) WHERE { ?s wdt:P3466 ?code; wdt:P625 ?c } GROUP BY ?code"
    r = requests.get(SPARQL, params={"query": q}, headers={**UA, "Accept": "application/sparql-results+json"}, timeout=120)
    coords = {}
    for b in r.json()["results"]["bindings"]:
        m = re.match(r"Point\(([-\d.]+) ([-\d.]+)\)", b["coord"]["value"])
        if m and b["code"]["value"].isdigit():
            coords[str(int(b["code"]["value"]))] = (round(float(m.group(2)), 4), round(float(m.group(1)), 4))
    out = []
    for row in rows:
        code = str(row["סמל_ישוב"]).strip()
        if not code.isdigit() or int(code) == 0:
            continue
        code = str(int(code))
        name = " ".join(row["שם_ישוב"].split())
        name_en = " ".join((row.get("שם_ישוב_לועזי") or "").split()).title()
        lat, lon = coords.get(code, (None, None))
        out.append([code, name, name_en, lat, lon])
    out.sort(key=lambda r: int(r[0]))
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print(f"wrote {OUT}: {len(out)} localities, {sum(1 for r in out if r[3] is not None)} with coordinates")


if __name__ == "__main__":
    main()
