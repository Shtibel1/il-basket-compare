import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone

from pricecompare import report
from pricecompare.__main__ import main

NOW = datetime(2026, 11, 14, 8, 0, tzinfo=timezone.utc)
SAMPLE = os.path.join(os.path.dirname(__file__), "..", "web", "sample-data.json")


def store(sid, chain, items, asof="2026-11-14T04:00+00:00"):
    return {"id": sid, "chain": chain, "name": sid, "address": "", "items": items, "asof": asof}


def data(stores, chains=None, sprices=None, generated="2026-11-14T04:00+00:00"):
    return {"generated": generated, "chains": chains or {"shufersal": "שופרסל", "ramilevy": "רמי לוי"},
            "stores": stores, "sprices": sprices if sprices is not None else [[] for _ in stores]}


class SingleTest(unittest.TestCase):
    def test_counts_branches_items_and_promos_per_chain(self):
        rep = report.single(data([store("a", "shufersal", 100), store("b", "shufersal", 300),
                                  store("c", "ramilevy", 50)],
                                 sprices=[[0, 0, 1, 1], [0, 0], []]), now=NOW)
        sh, rl = rep.chains["shufersal"], rep.chains["ramilevy"]
        self.assertEqual((sh.branches, sh.median_items, sh.min_items, sh.promos), (2, 200, 100, 3))
        self.assertEqual((rl.branches, rl.promos), (1, 0))
        self.assertEqual(rep.branches, 3)
        self.assertEqual(rep.warnings, [])

    def test_warns_about_a_configured_chain_with_no_branches(self):
        rep = report.single(data([store("a", "shufersal", 10)]), now=NOW)
        self.assertEqual(rep.chains["ramilevy"].branches, 0)
        self.assertTrue(any("ramilevy" in w and "no branches" in w for w in rep.warnings))

    def test_flags_stale_branches_by_their_own_asof(self):
        rep = report.single(data([store("old", "shufersal", 10, asof="2026-11-12T04:00+00:00"),
                                  store("new", "shufersal", 10), store("r", "ramilevy", 5)]),
                            now=NOW, max_age_hours=36)
        self.assertEqual(rep.chains["shufersal"].stale, 1)
        self.assertTrue(any("old" in w and "36" in w for w in rep.warnings))
        self.assertFalse(any("every branch" in w for w in rep.warnings))

    def test_a_chain_whose_every_branch_is_stale_is_called_out(self):
        rep = report.single(data([store("a", "ramilevy", 5, asof="2026-11-01T00:00+00:00"),
                                  store("b", "shufersal", 5)]), now=NOW)
        self.assertTrue(any("ramilevy" in w and "every branch" in w for w in rep.warnings))

    def test_missing_or_bad_asof_falls_back_to_generated_then_counts_as_stale(self):
        s1, s2 = store("a", "shufersal", 1, asof=None), store("b", "ramilevy", 1, asof="yesterday")
        rep = report.single(data([s1, s2]), now=NOW)
        self.assertEqual(rep.chains["shufersal"].stale, 0)
        self.assertEqual(rep.chains["ramilevy"].stale, 1)

    def test_markdown_lists_every_chain_and_the_warnings(self):
        md = report.to_markdown(report.single(data([store("a", "shufersal", 10)]), now=NOW))
        self.assertIn("| שופרסל | 1 | 0 | 10 | 10 | 0 |", md)
        self.assertIn("| רמי לוי | 0 |", md)
        self.assertIn("### Warnings", md)
        self.assertNotIn("Cities", md)


class HostedTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        os.makedirs(os.path.join(self.dir, "cities"))
        cities = {"6500": [store("h1", "shufersal", 100), store("h2", "ramilevy", 80)],
                  "7400": [store("n1", "shufersal", 200)]}
        for code, stores in cities.items():
            with open(os.path.join(self.dir, "cities", f"{code}.json"), "w", encoding="utf-8") as f:
                json.dump(data(stores), f, ensure_ascii=False)
        index = {"generated": "2026-11-14T05:00+00:00",
                 "cities": [["6500", "חדרה", "Hadera", 32.4, 34.9, 2, 2], ["7400", "נתניה", "Netanya", 32.3, 34.8, 1, 1],
                            ["5000", "תל אביב - יפו", "Tel Aviv", 32.0, 34.7, 1, 1]]}
        with open(os.path.join(self.dir, "index.json"), "w", encoding="utf-8") as f:
            json.dump(index, f, ensure_ascii=False)

    def tearDown(self):
        self.tmp.cleanup()

    def test_aggregates_chains_across_city_files(self):
        rep = report.hosted(self.dir, now=NOW)
        self.assertEqual(rep.cities, 3)
        self.assertEqual(rep.chains["shufersal"].branches, 2)
        self.assertEqual(rep.chains["shufersal"].cities, {"6500", "7400"})
        self.assertGreater(rep.size_bytes, 0)

    def test_warns_when_the_index_points_at_a_missing_city_file(self):
        rep = report.hosted(self.dir, now=NOW)
        self.assertTrue(any("5000" in w for w in rep.warnings))
        self.assertIn("Cities |", report.to_markdown(rep))


class CliTest(unittest.TestCase):
    def test_report_on_the_sample_data_appends_to_the_summary_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = os.path.join(tmp, "summary.md")
            with redirect_stdout(io.StringIO()) as out:
                code = main(["report", "--data", SAMPLE, "--max-age-hours", "100000", "--summary-file", summary])
            self.assertEqual(code, 0)
            with open(summary, encoding="utf-8") as f:
                self.assertEqual(f.read(), out.getvalue())
            self.assertIn("## Price data report", out.getvalue())

    def test_strict_fails_on_warnings(self):
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(["report", "--data", SAMPLE, "--strict"]), 1)

    def test_missing_data_is_a_clear_error(self):
        self.assertEqual(main(["report", "--data", "/nonexistent/data.json"]), 2)
