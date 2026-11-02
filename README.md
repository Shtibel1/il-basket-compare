<p align="center"><img src="docs/banner.svg" alt="il-basket-compare" width="100%"></p>

<p align="center">
  <a href="https://github.com/Shtibel1/il-basket-compare/actions/workflows/ci.yml"><img src="https://github.com/Shtibel1/il-basket-compare/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="MIT"></a>
  <img src="https://img.shields.io/badge/python-3.11+-3776AB?logo=python&logoColor=white" alt="Python 3.11+">
  <img src="https://img.shields.io/badge/hosting-GitHub%20Pages-222?logo=github" alt="GitHub Pages">
  <img src="https://img.shields.io/badge/UI-Hebrew%20RTL-0f5b45" alt="Hebrew RTL">
  <a href="README.he.md"><img src="https://img.shields.io/badge/README-עברית-ffd233" alt="עברית"></a>
</p>

### 🛒 Use it now: **[shtibel1.github.io/il-basket-compare](https://shtibel1.github.io/il-basket-compare/)**

Type your city (or tap *use my location*) and compare your basket across every supermarket branch nearby. One free site for the whole country, updated daily. No fork needed. Share a city directly with `?city=<CBS code>`, e.g. [`?city=7400`](https://shtibel1.github.io/il-basket-compare/?city=7400) for Netanya.

**il-basket-compare** is also a template for a supermarket price-comparison site for any Israeli city. Shoppers build a basket and see which supermarket near them sells it for the least. The data comes from the price files that every large chain must publish under the Price Transparency Law. A daily GitHub Actions job downloads them, and the site is served from GitHub Pages. There are no servers, no database and no API keys.

<p align="center">
  <img src="docs/screenshot-desktop.png" alt="Desktop: basket and ranking of supermarkets" width="72%">
  <img src="docs/screenshot-mobile.png" alt="Mobile view" width="22%">
</p>

## Features

- **18 chains, 4 portals**: Shufersal, Carrefour, Rami Levy, Yohananof, Osher Ad, Tiv Taam and more (see [`pricecompare/chains.py`](pricecompare/chains.py)).
- **Exact matching for packaged goods** by barcode, plus **generic matching for fresh produce** by name (chicken breast, tomatoes, eggs): each store's cheapest matching item is used.
- **Promotions open to all customers** (sale price, multi-buy, 1+1). Club, credit-card and coupon deals are excluded.
- **Ranking by chain or by branch**, with missing-item handling, a breakdown per store and a mobile summary bar.
- **One static page**: vanilla JS, Hebrew RTL, dark mode. The basket is saved in `localStorage`.
- **Config-driven**: city, chains and branding live in [`site.config.json`](site.config.json).
- **Setup wizard**: `python -m pricecompare init` finds your city's CBS code and the branches of every chain.

## Hosted nationwide mode

The upstream repo publishes one site for every city. The daily job runs `python -m pricecompare national`, which:

1. downloads every chain's branch list and places each branch in a CBS locality (by the locality code in the chain's Stores file, or by the locality name in the branch name or address);
2. downloads each branch's price and promotion files once;
3. writes `data/cities/<code>.json` (that city's branches and only the products they price, in the same layout as `data.json`) and `data/index.json` (the covered cities with their coordinates).

The page (`render --hosted`) searches [`pricecompare/settlements.json`](pricecompare/settlements.json), every Israeli locality with coordinates, bundled as static JSON. *Use my location* maps the browser's position to the nearest locality. A locality without branches opens the nearest covered city within 15 km and offers the other nearby ones. The chosen city is kept in `localStorage`, and *החלפת עיר* changes it.

To keep Pages small, a city file keeps the 25,000 products priced in the most of its branches (`MAX_PRODUCTS`), plus every generic fresh product. A repo created from the template keeps publishing its own city; set the repository variable `HOSTED=true` to publish the nationwide site instead.

```bash
python -m pricecompare national          # all chains, all cities: web/data/
python -m pricecompare render --hosted   # dist/ with the city picker
```

## Quick start (your own city site)

**Option A: GitHub only (about 5 minutes)**

1. Click **Use this template** → *Create a new repository* (or fork it).
2. Edit `site.config.json` for your city, or run the wizard locally (see below) and commit the result.
3. Go to **Settings → Pages → Source: GitHub Actions**.
4. Go to **Actions → Update prices and deploy → Run workflow**. Your site goes live at `https://<you>.github.io/<repo>/` and refreshes every day.

**Option B: locally**

```bash
git clone https://github.com/<you>/<repo> && cd <repo>
pip install -r requirements.txt
python -m pricecompare init            # asks for a city, e.g. נתניה or Netanya
python -m pricecompare update          # downloads today's prices (a few minutes)
python -m pricecompare serve           # http://localhost:8000
```

Before you run `update`, `serve` shows the committed sample data (`web/sample-data.json`), so you can see the UI offline right away.

Example wizard run:

```text
$ python -m pricecompare init --city Netanya --yes
City: נתניה / Netanya (CBS code 7400)
  ✓ שופרסל (shufersal): 11 branches
  ✓ קרפור (carrefour): 7 branches
  ✓ רמי לוי (ramilevy): 5 branches
  ...
Wrote site.config.json: 13 chains, 42 branches.
```

## Configuration

```jsonc
{
  "region": {
    "name": "חדרה",                 // shown in the UI
    "name_en": "Hadera",
    "city_codes": ["6500"],         // CBS locality codes (סמל יישוב)
    "names": ["חדרה", "גבעת אולגה"]  // fallback text match for chains that leave the code empty
  },
  "chains": ["shufersal", "ramilevy"], // or "all"
  "branding": {
    "title_prefix": "סל", "title_highlight": "חדרה",
    "tagline": "…", "logo": "", "favicon": "",
    "storage_prefix": "hadera",       // localStorage key prefix
    "colors": { "--accent": "#0f5b45", "--tag": "#ffd233" },
    "colors_dark": {}
  },
  "images": false                     // product photos, off by default (see Legal)
}
```

`python -m pricecompare render` fills the branding into `web/index.html` and writes the finished site to `dist/`. Every CSS variable in the page (`--accent`, `--tag`, `--ground`, …) can be overridden.

## Architecture

```mermaid
flowchart LR
  subgraph Portals["Chain price portals (public)"]
    SH[Shufersal]
    CF[Carrefour]
    CB["Cerberus<br/>url.publishedprices.co.il"]
    BN["Bina Projects<br/>*.binaprojects.com"]
  end
  CFG[site.config.json] --> UPD
  SH & CF & CB & BN -->|Stores / PriceFull / PromoFull XML| UPD["pricecompare update<br/>parse · match barcodes · generics · promos"]
  CACHE[(Actions cache<br/>previous snapshot)] <--> UPD
  UPD --> DATA[data.json]
  CFG --> RND[pricecompare render]
  DATA --> RND
  TPL[web/index.html] --> RND
  RND --> DIST[dist/] --> PAGES[GitHub Pages]
  PAGES --> U((Shopper's browser))
```

| Module | Job |
| --- | --- |
| `pricecompare/chains.py` | Registry of supported chains and their portal settings |
| `pricecompare/sources.py` | One downloader per portal |
| `pricecompare/parse.py` | Store and price XML parsing, region matching |
| `pricecompare/generic.py` | Name rules for fresh produce |
| `pricecompare/promos.py` | Promotions that are open to everyone |
| `pricecompare/build.py` | Builds the compact `data.json` |
| `pricecompare/site.py` | Renders the branded static site |
| `pricecompare/wizard.py` | The `init` setup wizard |
| `pricecompare/nationwide.py` | Hosted mode: places every branch in a locality, writes per-city shards |
| `pricecompare/settlements.json` | Every Israeli locality: CBS code, names, coordinates (rebuilt by `scripts/make_settlements.py`) |

## Adding a chain or a portal

- **A chain on a supported portal**: add one line to `CHAINS` in [`pricecompare/chains.py`](pricecompare/chains.py). For Cerberus that is the public username; for Bina, the subdomain prefix and chain ID. Then run `python -m pricecompare init` again to check that it finds branches.
- **A new portal**: add a class to [`pricecompare/sources.py`](pricecompare/sources.py) with `stores()`, `latest_price_files(ids)` and `latest_promo_files(ids)`, register it in `source_for()`, and add a test with a recorded sample file.

Locality names and codes come from the CBS localities table on data.gov.il. Coordinates come from Wikidata (CC0), joined on the CBS code, because the CBS file with coordinates is not openly downloadable.

## Legal note about the data

The prices are public: under the Promotion of Competition in the Food Sector Law (Price Transparency), 2014, large chains must publish their prices for every branch. This project only downloads those files from the chains' own public portals. It is not affiliated with any chain, and the prices may be late or wrong, so always check in the store. Product photos are **off by default** because they are copyrighted and are not part of the published data. If you turn on `"images": true`, it is your responsibility to make sure you are allowed to use the image source.

## Roadmap

- [ ] More portals (Victory, Mahsaney Hashuk, Hazi Hinam)
- [ ] Several cities in one deployment, with a city picker
- [ ] Price history and "cheapest day" trends
- [ ] Sharable basket links
- [ ] English UI option
- [ ] PWA / offline mode

## Contributing

PRs are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE) © Nadav Shtibel
