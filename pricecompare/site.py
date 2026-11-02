"""Render the static site: web/index.html + site.config.json -> dist/.

The page is one HTML file with {{placeholders}}; branding is filled in here so
the published page needs no runtime config request.
"""

import html
import json
import os
import shutil

WEB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "web")


def _css(colors):
    return " ".join(f"{k}: {v};" for k, v in colors.items() if k.startswith("--") and ";" not in str(v) and "}" not in str(v))


def render_html(template, cfg, hosted=False):
    b = cfg["branding"]
    esc = html.escape
    dark = _css(b.get("colors_dark") or {})
    brand_css = _css(b.get("colors") or {})
    if dark:
        brand_css += f" }}\n:root[data-theme=\"dark\"] {{ {dark} }}\n@media (prefers-color-scheme: dark) {{ :root:not([data-theme=\"light\"]) {{ {dark} }}"
    logo = f'<img class="logo" src="{esc(b["logo"])}" alt="">' if b.get("logo") else ""
    favicon = f'<link rel="icon" href="{esc(b["favicon"])}">' if b.get("favicon") else ""
    site = {"storage_prefix": b["storage_prefix"], "images": cfg["images"], "region": cfg["region"]["name"], "hosted": hosted}
    values = {
        "title": esc(f'{b["title_prefix"]} {b["title_highlight"]}'.strip()),
        "title_prefix": esc(b["title_prefix"]),
        "title_highlight": esc(b["title_highlight"]),
        "tagline": esc(b["tagline"]),
        "accent": esc((b.get("colors") or {}).get("--accent", "#0f5b45")),
        "favicon": favicon,
        "logo": logo,
        "brand_css": brand_css,
        "site_json": json.dumps(site, ensure_ascii=False).replace("</", "<\\/"),
    }
    out = template
    for k, v in values.items():
        out = out.replace("{{" + k + "}}", v)
    return out


SAMPLE_CITY = "6500"  # the committed sample data is Hadera's


def _hosted_data(out_dir, data_dir):
    """dist/data/: the real shards from `national`, or the sample as a one-city index."""
    dst = os.path.join(out_dir, "data")
    shutil.rmtree(dst, ignore_errors=True)
    if os.path.exists(os.path.join(data_dir, "index.json")):
        shutil.copytree(data_dir, dst)
        return
    from .nationwide import load_settlements
    s = next(r for r in load_settlements() if r[0] == SAMPLE_CITY)
    os.makedirs(os.path.join(dst, "cities"))
    with open(os.path.join(WEB, "sample-data.json"), encoding="utf-8") as f:
        sample = json.load(f)
    sample["city"] = SAMPLE_CITY
    with open(os.path.join(dst, "cities", f"{SAMPLE_CITY}.json"), "w", encoding="utf-8") as f:
        json.dump(sample, f, ensure_ascii=False, separators=(",", ":"))
    index = {"generated": sample["generated"], "fallback_km": 15, "sample": True,
             "cities": [[s[0], s[1], s[2], s[3], s[4], len(sample["stores"]), len({x["chain"] for x in sample["stores"]})]]}
    with open(os.path.join(dst, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, separators=(",", ":"))


def render(cfg, out_dir, data_path=None, hosted=False, data_dir=None):
    """Write dist/: index.html, data (real or the committed sample), assets, images if enabled.

    hosted: the nationwide site; data/ holds index.json + cities/<code>.json and
    settlements.json feeds the city search, instead of one data.json.
    """
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(WEB, "index.html"), encoding="utf-8") as f:
        page = render_html(f.read(), cfg, hosted)
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)
    for name in os.listdir(WEB):
        src = os.path.join(WEB, name)
        if name in ("index.html", "data.json", "sample-data.json", "data") or (name == "img" and not cfg["images"]):
            continue
        dst = os.path.join(out_dir, name)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copyfile(src, dst)
    if hosted:
        _hosted_data(out_dir, data_dir or os.path.join(WEB, "data"))
        shutil.copyfile(os.path.join(os.path.dirname(os.path.abspath(__file__)), "settlements.json"),
                        os.path.join(out_dir, "settlements.json"))
        return out_dir
    data_path = data_path or os.path.join(WEB, "data.json")
    if not os.path.exists(data_path):
        data_path = os.path.join(WEB, "sample-data.json")
    shutil.copyfile(data_path, os.path.join(out_dir, "data.json"))
    return out_dir
