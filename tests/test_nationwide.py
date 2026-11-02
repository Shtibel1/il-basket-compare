import gzip
import json
import os
import pickle
import tempfile
import unittest

from pricecompare import config, nationwide, site

SETTLEMENTS = [
    ["6500", "חדרה", "Hadera", 32.434, 34.919],
    ["5000", "תל אביב - יפו", "Tel Aviv - Yafo", 32.08, 34.78],
    ["7400", "נתניה", "Netanya", 32.33, 34.86],
    ["2400", "אזור", "Azor", 32.02, 34.80],
    ["1200", "מודיעין-מכבים-רעות", "Modi'In", 31.9, 35.0],
    ["171", "פרדסיה", "Pardesiyya", 32.30, 34.91],
]


def item(barcode, price, name="חלב 3%"):
    return {"code": barcode, "barcode": barcode, "name": name, "manufacturer": "תנובה", "quantity": 1.0,
            "unit": "ליטר", "weighted": False, "price": price}


class LocatorTest(unittest.TestCase):
    def setUp(self):
        self.loc = nationwide.Locator(SETTLEMENTS)

    def test_uses_the_cbs_code_when_valid(self):
        self.assertEqual(self.loc.city_of({"city": "06500", "name": "x", "address": ""}), "6500")

    def test_falls_back_to_the_name_then_the_address(self):
        self.assertEqual(self.loc.city_of({"city": "0", "name": "בן צבי תל אביב", "address": "unknown"}), "5000")
        self.assertEqual(self.loc.city_of({"city": "0", "name": "סניף 3", "address": "הרצל 1 נתניה"}), "7400")
        self.assertEqual(self.loc.city_of({"city": "0", "name": "מודיעין ישפרו", "address": ""}), "1200")

    def test_street_words_that_are_also_localities_do_not_match(self):
        self.assertIsNone(self.loc.city_of({"city": "0", "name": "מפוח", "address": "המפוח 11, אזור התעשיה"}))
        self.assertEqual(self.loc.city_of({"city": "0", "name": "אזור", "address": ""}), "2400")

    def test_unknown_store_is_skipped(self):
        self.assertIsNone(self.loc.city_of({"city": "0", "name": "סופר מול", "address": "unknown"}))


class ShardTest(unittest.TestCase):
    def _cache(self, root, chain, sid, city, items):
        path = nationwide._cache_file(root, chain, sid)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with gzip.open(path, "wb") as f:
            pickle.dump({"store": {"store_id": sid, "name": f"סניף {sid}", "address": "", "city": city},
                         "city": city, "items": items, "deals": []}, f)

    def test_writes_one_file_per_city_and_an_index(self):
        with tempfile.TemporaryDirectory() as d:
            cache, out = os.path.join(d, "cache"), os.path.join(d, "data")
            self._cache(cache, "shufersal", "1", "6500", [item("7290000000011", 6.5), item("7290000000028", 9.9, "קוטג׳ 5%")])
            self._cache(cache, "ramilevy", "2", "6500", [item("7290000000011", 5.9)])
            self._cache(cache, "ramilevy", "3", "7400", [item("7290000000011", 6.1)])
            idx = nationwide.shard(cache, out, settlements=SETTLEMENTS)
            self.assertEqual([c[0] for c in idx["cities"]], ["6500", "7400"])
            self.assertEqual(idx["cities"][0][5:], [2, 2])
            with open(os.path.join(out, "cities", "6500.json"), encoding="utf-8") as f:
                hadera = json.load(f)
            self.assertEqual(hadera["region"], "חדרה")
            self.assertEqual({s["id"] for s in hadera["stores"]}, {"shufersal-1", "ramilevy-2"})
            self.assertEqual(set(hadera["chains"]), {"shufersal", "ramilevy"})
            with open(os.path.join(out, "cities", "7400.json"), encoding="utf-8") as f:
                netanya = json.load(f)
            self.assertEqual([p[0] for p in netanya["products"]], ["7290000000011"])  # only what its branches price

    def test_trim_keeps_the_most_priced_products(self):
        data = {"products": [["a"], ["b"], ["c"]], "prices": [[0, 100, 1, 200, 1, 300], [2, 50]],
                "promos": [["x"], ["y"]], "sprices": [[1, 1, 1, 0], []]}
        out = nationwide.trim(data, 2)
        self.assertEqual(out["products"], [["a"], ["b"]])
        self.assertEqual(out["prices"], [[0, 100, 1, 200], []])
        self.assertEqual(out["promos"], [["y"]])  # the deal on "c" is gone, "y" is renumbered
        self.assertEqual(out["sprices"], [[1, 0], []])


class HostedRenderTest(unittest.TestCase):
    def test_hosted_render_has_picker_settlements_and_sample_shard(self):
        with tempfile.TemporaryDirectory() as d:
            site.render(config.hosted(), d, hosted=True, data_dir=os.path.join(d, "none"))
            with open(os.path.join(d, "index.html"), encoding="utf-8") as f:
                page = f.read()
            self.assertIn('"hosted": true', page)
            self.assertIn('id="picker"', page)
            with open(os.path.join(d, "data", "index.json"), encoding="utf-8") as f:
                idx = json.load(f)
            code = idx["cities"][0][0]
            self.assertTrue(os.path.exists(os.path.join(d, "data", "cities", f"{code}.json")))
            self.assertTrue(os.path.exists(os.path.join(d, "settlements.json")))
            self.assertFalse(os.path.exists(os.path.join(d, "data.json")))

    def test_fork_render_is_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            site.render(config.normalize({"region": {"name": "חדרה", "city_codes": ["6500"]}, "chains": ["shufersal"]}), d)
            with open(os.path.join(d, "index.html"), encoding="utf-8") as f:
                self.assertIn('"hosted": false', f.read())
            self.assertTrue(os.path.exists(os.path.join(d, "data.json")))
            self.assertFalse(os.path.exists(os.path.join(d, "data")))

    def test_bundled_settlements_cover_the_big_cities(self):
        rows = {r[0]: r for r in nationwide.load_settlements()}
        self.assertGreater(len(rows), 1200)
        for code in ("6500", "7400", "5000", "3000", "4000"):
            self.assertIsNotNone(rows[code][3], code)
