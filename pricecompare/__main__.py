"""Usage:
    python -m pricecompare init   [--city נתניה] [--yes] [--also "שם נוסף"]
    python -m pricecompare update [--out web/data.json]
    python -m pricecompare images [--cache .cache/thumbs]
    python -m pricecompare render [--out dist]
    python -m pricecompare serve  [--port 8000]
"""

import argparse
import functools
import http.server
import logging
import os
import sys

from . import config

ROOT = config.ROOT
WEB_DIR = os.path.join(ROOT, "web")
DIST_DIR = os.path.join(ROOT, "dist")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="pricecompare")
    sub = parser.add_subparsers(dest="cmd", required=True)
    it = sub.add_parser("init", help="create site.config.json for your city")
    it.add_argument("--city")
    it.add_argument("--yes", action="store_true", help="no questions; take the best match")
    it.add_argument("--also", action="append", default=[], help="extra place name to match (repeatable)")
    up = sub.add_parser("update", help="download current prices for the region")
    up.add_argument("--out", default=os.path.join(WEB_DIR, "data.json"))
    im = sub.add_parser("images", help="build product thumbnails (only when images: true)")
    im.add_argument("--cache", default=os.path.join(ROOT, ".cache", "thumbs"))
    rd = sub.add_parser("render", help="build the static site into dist/")
    rd.add_argument("--out", default=DIST_DIR)
    sv = sub.add_parser("serve", help="render and serve the site locally")
    sv.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)

    if args.cmd == "init":
        from . import wizard
        return wizard.run(args.city, yes=args.yes, extra_names=args.also)
    try:
        cfg = config.load()
    except config.ConfigError as e:
        print(e, file=sys.stderr)
        return 2
    if args.cmd == "update":
        from . import build
        build.main(args.out, cfg)
    elif args.cmd == "images":
        if not cfg["images"]:
            print("images are off in site.config.json (\"images\": false); nothing to do")
            return 0
        from . import images
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
        images.build_images(os.path.join(WEB_DIR, "data.json"), os.path.join(WEB_DIR, "img"), args.cache)
    elif args.cmd == "render":
        from . import site
        print(site.render(cfg, args.out))
    else:
        from . import site
        site.render(cfg, DIST_DIR)
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=DIST_DIR)
        print(f"http://localhost:{args.port}")
        http.server.ThreadingHTTPServer(("", args.port), handler).serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
