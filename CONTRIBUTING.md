# Contributing

Thanks for helping. Bug reports, new chains and new portals are all welcome.

## Setup

```bash
pip install -r requirements.txt pytest
pytest -q
python -m pricecompare serve   # UI on the sample data
```

## Guidelines

- Keep the site a single static page with no build tools and no runtime dependencies.
- Network code belongs in `pricecompare/sources.py`. Tests must not touch the network, so use recorded XML snippets or fakes, as in `tests/test_wizard.py`.
- Nothing city-specific in code. Use `site.config.json`.
- One topic per PR, with tests for new behavior. CI must pass.
- Don't commit real `web/data.json` or product images. To refresh the sample, run `python scripts/make_sample.py <full data.json>`.

## Adding a chain

Add an entry to `pricecompare/chains.py`, then run `python -m pricecompare init --city <a city where the chain has branches>` and paste the output into the PR.
