"""Data-quality report for the price data the site serves.

`python -m pricecompare report` reads what `update` (web/data.json) or
`national` (web/data/index.json + data/cities/*.json) wrote and summarizes it
per chain: branches, how many products each branch prices, how many branches
carry stale prices, and how many promotions are attached. Chains that are
configured but returned no branch, and branches whose prices are older than
`--max-age-hours`, are listed as warnings.

The daily workflow appends the Markdown version to the Actions job summary
(`--summary-file "$GITHUB_STEP_SUMMARY"`), so a chain that silently stopped
publishing shows up in the run page instead of only as a gap on the site.
`--strict` makes warnings fail the command.
"""

import json
import os
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from .chains import BY_KEY


@dataclass
class ChainStats:
    key: str
    name: str
    branches: int = 0
    stale: int = 0
    items: list = field(default_factory=list)
    promos: int = 0
    cities: set = field(default_factory=set)

    @property
    def median_items(self):
        return int(statistics.median(self.items)) if self.items else 0

    @property
    def min_items(self):
        return min(self.items) if self.items else 0


@dataclass
class Report:
    generated: str
    chains: dict
    cities: int = 0
    size_bytes: int = 0
    warnings: list = field(default_factory=list)

    @property
    def branches(self):
        return sum(c.branches for c in self.chains.values())


def _parse_time(value):
    try:
        t = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return t if t.tzinfo else t.replace(tzinfo=timezone.utc)


def _chain(stats, key, names):
    if key not in stats:
        stats[key] = ChainStats(key, names.get(key) or BY_KEY.get(key, {}).get("name", key))
    return stats[key]


def _add(stats, data, now, max_age, city=None):
    """Fold one data.json-layout dict into the per-chain stats; returns the stale branch ids."""
    names = data.get("chains") or {}
    for key in names:
        _chain(stats, key, names)
    stale = []
    sprices = data.get("sprices") or [[] for _ in data.get("stores", [])]
    for store, sp in zip(data.get("stores", []), sprices):
        c = _chain(stats, store["chain"], names)
        c.branches += 1
        c.items.append(store.get("items", 0))
        c.promos += len(sp) // 2
        if city:
            c.cities.add(city)
        asof = _parse_time(store.get("asof") or data.get("generated"))
        if asof is None or now - asof > max_age:
            c.stale += 1
            stale.append(store["id"])
    return stale


def _warn_chains(rep):
    for c in rep.chains.values():
        if not c.branches:
            rep.warnings.append(f"{c.name} ({c.key}): no branches in the data")
        elif c.stale == c.branches:
            rep.warnings.append(f"{c.name} ({c.key}): every branch has stale prices")


def single(data, now=None, max_age_hours=36):
    """Report on one data.json (single-city site)."""
    now = now or datetime.now(timezone.utc)
    stats = {}
    stale = _add(stats, data, now, timedelta(hours=max_age_hours))
    rep = Report(data.get("generated", ""), stats, cities=1)
    _warn_chains(rep)
    if stale:
        rep.warnings.append(f"{len(stale)} branch(es) older than {max_age_hours}h: {', '.join(stale[:10])}"
                            + (" ..." if len(stale) > 10 else ""))
    return rep


def hosted(data_dir, now=None, max_age_hours=36):
    """Report on the nationwide shards (data/index.json + data/cities/*.json)."""
    now = now or datetime.now(timezone.utc)
    with open(os.path.join(data_dir, "index.json"), encoding="utf-8") as f:
        index = json.load(f)
    stats, stale, size, missing = {}, 0, 0, []
    for code, *_rest in index.get("cities", []):
        path = os.path.join(data_dir, "cities", f"{code}.json")
        if not os.path.exists(path):
            missing.append(str(code))
            continue
        size += os.path.getsize(path)
        with open(path, encoding="utf-8") as f:
            stale += len(_add(stats, json.load(f), now, timedelta(hours=max_age_hours), city=code))
    rep = Report(index.get("generated", ""), stats, cities=len(index.get("cities", [])), size_bytes=size)
    _warn_chains(rep)
    if stale:
        rep.warnings.append(f"{stale} branch(es) older than {max_age_hours}h")
    if missing:
        rep.warnings.append(f"index.json lists cities with no data file: {', '.join(missing[:10])}")
    return rep


def to_markdown(rep):
    hosted_mode = any(c.cities for c in rep.chains.values()) or rep.cities > 1
    lines = ["## Price data report", ""]
    summary = f"Generated **{rep.generated or 'unknown'}** · **{rep.branches}** branches"
    if hosted_mode:
        summary += f" in **{rep.cities}** cities · {rep.size_bytes / 1e6:.1f} MB of city files"
    lines += [summary, ""]
    head = "| Chain | Branches | Stale | Median items | Min items | Promo offers |"
    sep = "|---|---:|---:|---:|---:|---:|"
    if hosted_mode:
        head += " Cities |"
        sep += "---:|"
    lines += [head, sep]
    for c in sorted(rep.chains.values(), key=lambda c: (-c.branches, c.key)):
        row = f"| {c.name} | {c.branches} | {c.stale} | {c.median_items} | {c.min_items} | {c.promos} |"
        if hosted_mode:
            row += f" {len(c.cities)} |"
        lines.append(row)
    lines.append("")
    if rep.warnings:
        lines += ["### Warnings", ""] + [f"- {w}" for w in rep.warnings]
    else:
        lines.append("No warnings.")
    return "\n".join(lines) + "\n"


def main(data_path, hosted_mode=False, max_age_hours=36, summary_file=None, strict=False):
    if hosted_mode:
        rep = hosted(data_path, max_age_hours=max_age_hours)
    else:
        with open(data_path, encoding="utf-8") as f:
            rep = single(json.load(f), max_age_hours=max_age_hours)
    md = to_markdown(rep)
    print(md, end="")
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write(md)
    return 1 if strict and rep.warnings else 0
