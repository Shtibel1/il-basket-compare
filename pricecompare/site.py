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


def render_html(template, cfg):
    b = cfg["branding"]
    esc = html.escape
    dark = _css(b.get("colors_dark") or {})
    brand_css = _css(b.get("colors") or {})
    if dark:
        brand_css += f" }}\n:root[data-theme=\"dark\"] {{ {dark} }}\n@media (prefers-color-scheme: dark) {{ :root:not([data-theme=\"light\"]) {{ {dark} }}"
    logo = f'<img class="logo" src="{esc(b["logo"])}" alt="">' if b.get("logo") else ""
    favicon = f'<link rel="icon" href="{esc(b["favicon"])}">' if b.get("favicon") else ""
    site = {"storage_prefix": b["storage_prefix"], "images": cfg["images"], "region": cfg["region"]["name"]}
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


def render(cfg, out_dir, data_path=None):
    """Write dist/: index.html, data.json (real or the committed sample), assets, images if enabled."""
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(WEB, "index.html"), encoding="utf-8") as f:
        page = render_html(f.read(), cfg)
    with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)
    data_path = data_path or os.path.join(WEB, "data.json")
    if not os.path.exists(data_path):
        data_path = os.path.join(WEB, "sample-data.json")
    shutil.copyfile(data_path, os.path.join(out_dir, "data.json"))
    for name in os.listdir(WEB):
        src = os.path.join(WEB, name)
        if name in ("index.html", "data.json", "sample-data.json") or (name == "img" and not cfg["images"]):
            continue
        dst = os.path.join(out_dir, name)
        if os.path.isdir(src):
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copyfile(src, dst)
    return out_dir
