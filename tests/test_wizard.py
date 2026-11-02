import json
import os
import tempfile
import unittest

from pricecompare import config, wizard

ROWS = [
    {"סמל_ישוב": "175", "שם_ישוב": "אביחיל ", "שם_ישוב_לועזי": "AVIHAYIL"},
    {"סמל_ישוב": "7400", "שם_ישוב": "נתניה ", "שם_ישוב_לועזי": "NETANYA"},
]


class FakeResponse:
    def __init__(self, rows): self.rows = rows
    def raise_for_status(self): pass
    def json(self): return {"result": {"records": self.rows}}


class FakeSource:
    def __init__(self, stores, fail=False): self._stores, self.fail = stores, fail
    def stores(self):
        if self.fail:
            raise ConnectionError("down")
        return self._stores


def store(sid, city, name="סניף"):
    return {"store_id": sid, "name": name, "address": "", "city": city}


CHAINS = [{"key": "a", "name": "A"}, {"key": "b", "name": "B"}, {"key": "c", "name": "C"}]
SOURCES = {
    "a": FakeSource([store("1", "7400"), store("1", "7400"), store("2", "6500")]),
    "b": FakeSource([store("9", "0", "נתניה מרכז")]),
    "c": FakeSource([], fail=True),
}


class WizardTest(unittest.TestCase):
    def test_find_city_exact_first_and_english(self):
        get = lambda *a, **k: FakeResponse(ROWS)
        self.assertEqual(wizard.find_city("Netanya", get=get)[0],
                         {"code": "7400", "name": "נתניה", "name_en": "Netanya"})
        self.assertEqual(wizard.find_city("נתניה", get=get)[0]["code"], "7400")

    def test_discover_by_code_and_name_skips_broken_portals(self):
        region = {"name": "נתניה", "city_codes": {"7400"}, "names": ["נתניה"]}
        logs = []
        found = wizard.discover(region, CHAINS, lambda c: SOURCES[c["key"]], log=logs.append)
        self.assertEqual({k: [s["store_id"] for s in v] for k, v in found.items()}, {"a": ["1"], "b": ["9"]})
        self.assertTrue(any("portal error" in line for line in logs))

    def test_run_writes_loadable_config(self):
        out = os.path.join(tempfile.mkdtemp(), "site.config.json")
        city = {"code": "7400", "name": "נתניה", "name_en": "Netanya"}
        code = wizard.run("Netanya", out=out, yes=True, log=lambda *_: None,
                          find=lambda q: [city], scan=lambda region, log: {"shufersal": [1], "ramilevy": [1]})
        self.assertEqual(code, 0)
        cfg = config.load(out)
        self.assertEqual(cfg["region"]["city_codes"], {"7400"})
        self.assertEqual([c["key"] for c in cfg["chains"]], ["shufersal", "ramilevy"])
        self.assertEqual(cfg["branding"]["storage_prefix"], "netanya")
        self.assertFalse(cfg["images"])

    def test_run_keeps_branding_and_asks_before_overwrite(self):
        out = os.path.join(tempfile.mkdtemp(), "site.config.json")
        with open(out, "w", encoding="utf-8") as f:
            json.dump({"branding": {"colors": {"--accent": "#111111"}}, "images": True}, f)
        city = {"code": "7400", "name": "נתניה", "name_en": "Netanya"}
        kw = dict(out=out, log=lambda *_: None, find=lambda q: [city], scan=lambda region, log: {"shufersal": [1]})
        self.assertEqual(wizard.run("נתניה", ask=lambda _: "n", **kw), 1)
        self.assertEqual(wizard.run("נתניה", ask=lambda _: "y", **kw), 0)
        cfg = config.load(out)
        self.assertEqual(cfg["branding"]["colors"], {"--accent": "#111111"})
        self.assertTrue(cfg["images"])

    def test_run_prompts_for_city_and_handles_no_match(self):
        asked = []
        code = wizard.run(None, out="/nonexistent/x.json", ask=lambda p: asked.append(p) or "Nowhere",
                          log=lambda *_: None, find=lambda q: [], scan=None)
        self.assertEqual(code, 1)
        self.assertTrue(asked)

    def test_run_no_branches(self):
        city = {"code": "1", "name": "x", "name_en": "X"}
        code = wizard.run("X", out="/nonexistent/x.json", yes=True, log=lambda *_: None,
                          find=lambda q: [city], scan=lambda region, log: {})
        self.assertEqual(code, 1)
