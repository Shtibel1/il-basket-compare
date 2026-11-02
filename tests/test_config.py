import json
import os
import tempfile
import unittest

from pricecompare import config, site
from pricecompare.chains import BY_KEY

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def write(obj):
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(obj, f, ensure_ascii=False)
    f.close()
    return f.name


class ConfigTest(unittest.TestCase):
    def test_example_config_loads(self):
        cfg = config.load(os.path.join(ROOT, "site.config.json"))
        self.assertEqual(cfg["region"]["city_codes"], {"6500"})
        self.assertTrue(all(c["key"] in BY_KEY for c in cfg["chains"]))
        self.assertFalse(cfg["images"])

    def test_defaults_fill_in(self):
        cfg = config.load(write({"region": {"name": "נתניה", "city_codes": [7400]}}))
        self.assertEqual(len(cfg["chains"]), len(BY_KEY))  # "all" by default
        self.assertEqual(cfg["region"]["city_codes"], {"7400"})
        self.assertEqual(cfg["region"]["names"], ["נתניה"])
        b = cfg["branding"]
        self.assertEqual(b["title_highlight"], "נתניה")
        self.assertIn("נתניה", b["tagline"])
        self.assertEqual(b["storage_prefix"], "basket-7400")
        self.assertFalse(cfg["images"])

    def test_images_opt_in(self):
        cfg = config.load(write({"region": {"name": "x", "city_codes": ["1"]}, "images": True}))
        self.assertTrue(cfg["images"])

    def test_errors(self):
        with self.assertRaises(config.ConfigError):
            config.load("/nonexistent/site.config.json")
        with self.assertRaises(config.ConfigError):
            config.load(write({"region": {}}))
        with self.assertRaises(config.ConfigError):
            config.load(write({"region": {"name": "x"}, "chains": ["nope"]}))
        bad = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        bad.write("{oops"); bad.close()
        with self.assertRaises(config.ConfigError):
            config.load(bad.name)

    def test_env_override(self):
        p = write({"region": {"name": "x", "city_codes": ["1"]}})
        os.environ["SITE_CONFIG"] = p
        try:
            self.assertEqual(config.path(), p)
        finally:
            del os.environ["SITE_CONFIG"]


class RenderTest(unittest.TestCase):
    def cfg(self, **branding):
        return config.normalize({"region": {"name": "נתניה", "city_codes": ["7400"]},
                                 "branding": {"storage_prefix": "netanya", **branding}})

    def test_placeholders_filled_and_escaped(self):
        with open(os.path.join(ROOT, "web", "index.html"), encoding="utf-8") as f:
            tpl = f.read()
        out = site.render_html(tpl, self.cfg(tagline="<b>x</b>", colors={"--accent": "#123456", "evil": "x"}))
        self.assertNotIn("{{", out)
        self.assertIn("<title>סל נתניה</title>", out)
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", out)
        self.assertIn("--accent: #123456;", out)
        self.assertNotIn("evil:", out)
        self.assertIn('"storage_prefix": "netanya"', out)
        self.assertIn('"images": false', out)

    def test_template_is_city_neutral(self):
        with open(os.path.join(ROOT, "web", "index.html"), encoding="utf-8") as f:
            tpl = f.read()
        self.assertNotIn("חדרה", tpl)
        self.assertNotIn("hadera", tpl.lower())

    def test_render_uses_sample_data(self):
        out = tempfile.mkdtemp()
        site.render(self.cfg(), out, data_path="/nonexistent.json")
        self.assertTrue(os.path.exists(os.path.join(out, "index.html")))
        with open(os.path.join(out, "data.json"), encoding="utf-8") as f:
            data = json.load(f)
        self.assertTrue(data["stores"] and data["products"])
        self.assertFalse(os.path.exists(os.path.join(out, "img")))
