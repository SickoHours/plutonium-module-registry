"""The registry's own checks, offline: the diff and comparison logic of check_entries.py and the
catalog builder's outputs. Network steps (`pat module fetch`, head observation) are not run here;
the Validate workflow runs them against real snapshots."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check = load("check_entries")
build = load("build_catalog")
COMMIT = "a" * 40
OTHER = "b" * 40


def entry(name="someone/thing", commit=COMMIT, **over):
    row = {"name": name, "kind": "module", "repository": "https://github.com/someone/mods", "path": "thing",
           "listed": {"commit": commit, "at": "2026-09-11"}, "distribution": "source",
           "declaration": {"id": "thing", "version": "0.1.0", "title": "Thing", "category": "scripts", "kind": "script",
                           "tags": ["example"], "bases": ["stock"], "maps": ["*"]},
           "verification": {"snapshot_status": "unverified"}, "history": []}
    row.update(over)
    return row


class RegistryFileTests(unittest.TestCase):
    def test_the_committed_registry_is_well_formed_and_matches_the_toolkit_format(self):
        data = json.loads((ROOT / "registry.json").read_text(encoding="utf-8"))
        self.assertEqual(data["schema"], 1)
        self.assertEqual(data["name"], "plutonium-module-registry")
        names = [e["name"] for e in data["entries"]]
        self.assertEqual(len(names), len(set(names)))
        for e in data["entries"]:
            self.assertRegex(e["name"], r"^[a-z0-9][a-z0-9-]{0,38}/[a-z0-9_]{1,64}$")
            self.assertRegex(e["listed"]["commit"], r"^[0-9a-f]{40}$")
            owner = e["name"].split("/")[0]
            self.assertTrue(e["repository"].lower().startswith(f"https://github.com/{owner}/"), e["name"])
            self.assertIn(e["kind"], ("module", "composition"))
            self.assertIn("id", e["declaration"])
            self.assertIsInstance(e.get("history", []), list)


class CheckEntriesTests(unittest.TestCase):
    def test_changed_entries_and_append_only_history(self):
        base = {"entries": [entry(), entry(name="someone/other")]}
        same = {"entries": [entry(), entry(name="someone/other")]}
        to_prove, problems, removed = check.changed_entries(same, base, False)
        self.assertEqual((to_prove, problems, removed), ([], [], []))
        added = {"entries": [entry(), entry(name="someone/other"), entry(name="someone/new")]}
        to_prove, problems, removed = check.changed_entries(added, base, False)
        self.assertEqual([e["name"] for e in to_prove], ["someone/new"])
        bumped_bad = {"entries": [entry(commit=OTHER), entry(name="someone/other")]}
        to_prove, problems, removed = check.changed_entries(bumped_bad, base, False)
        self.assertEqual([e["name"] for e in to_prove], ["someone/thing"])
        self.assertTrue(problems and "not under history" in problems[0])
        previous = {k: v for k, v in entry().items() if k != "history"}
        bumped_good = {"entries": [entry(commit=OTHER, history=[previous]), entry(name="someone/other")]}
        to_prove, problems, removed = check.changed_entries(bumped_good, base, False)
        self.assertEqual(problems, [])
        gone = {"entries": [entry()]}
        to_prove, problems, removed = check.changed_entries(gone, base, False)
        self.assertEqual(removed, ["someone/other"])
        to_prove, _, _ = check.changed_entries(same, base, True)
        self.assertEqual(len(to_prove), 2, "--all proves everything")
        to_prove, _, _ = check.changed_entries(same, None, False)
        self.assertEqual(len(to_prove), 2, "no base means everything is new")

    def test_declaration_summary_comparison(self):
        fetched = {"schema": 1, "id": "thing", "version": "0.1.0", "title": "Thing", "category": "scripts", "kind": "script",
                   "tags": ["example"], "recipe": "project.json", "bases": ["stock"], "maps": ["*"]}
        self.assertEqual(check.compare(entry(), fetched, "module"), [])
        wrong = entry(declaration={**entry()["declaration"], "bases": ["b2"]})
        problems = check.compare(wrong, fetched, "module")
        self.assertEqual(len(problems), 1)
        self.assertIn("declaration.bases", problems[0])
        pack = {"schema": 1, "name": "stock_pack", "title": "A pack", "tags": ["example"], "base": "stock", "map": "zm_transit", "modules": ["../a"]}
        listing = entry(kind="composition", declaration={"id": "stock_pack", "title": "A pack", "category": "pack", "tags": ["example"],
                                                          "bases": ["stock"], "maps": ["zm_transit"]})
        self.assertEqual(check.compare(listing, pack, "composition"), [])
        listing["declaration"]["version"] = "1.0"
        self.assertTrue(any("not a composition field" in p for p in check.compare(listing, pack, "composition")))
        self.assertTrue(any("no id" in p for p in check.compare(entry(declaration={"title": "x"}), fetched, "module")))


class BaselineRowTests(unittest.TestCase):
    def test_outcomes_decide_and_claims_are_checked(self):
        e = entry()
        passed = {"ok": True, "result": {"outcome": "passed", "blocked": False, "policy_version": 1, "tree_sha256": "a" * 64,
                                         "findings": [], "capabilities": [], "warnings": [], "unreadable": []}}
        row = check.baseline_row(e, passed)
        self.assertTrue(row["ok"]); self.assertEqual(row["outcome"], "passed"); self.assertTrue(row["not_a_security_audit"])
        review = dict(passed, result=dict(passed["result"], outcome="review-required", capabilities=[{"id": "installer", "file": "setup.ps1"}]))
        row = check.baseline_row(e, review)
        self.assertTrue(row["ok"], "review-required passes; the maintainer reads the rows")
        self.assertEqual(row["capabilities"][0]["id"], "installer")
        blocked = dict(passed, result=dict(passed["result"], outcome="needs-fixes", blocked=True,
                                           findings=[{"id": "native-plugin", "blocking": True, "file": "bin/hook.dll"}]))
        row = check.baseline_row(e, blocked)
        self.assertFalse(row["ok"]); self.assertIn("native-plugin at bin/hook.dll", row["problems"][0])
        incomplete = dict(passed, result=dict(passed["result"], outcome="incomplete", blocked=True, unreadable=["x"]))
        self.assertFalse(check.baseline_row(e, incomplete)["ok"])
        failed = {"ok": False, "error_code": "input_limit", "message": "too big"}
        row = check.baseline_row(e, failed)
        self.assertFalse(row["ok"]); self.assertEqual(row["error_code"], "input_limit")
        claiming = entry(verification={"snapshot_status": "snapshot verified"})
        row = check.baseline_row(claiming, review)
        self.assertFalse(row["ok"]); self.assertIn("claims snapshot verified", row["problems"][0])
        self.assertTrue(check.baseline_row(claiming, passed)["ok"])


class CatalogTests(unittest.TestCase):
    def test_build_is_deterministic_and_marks_drift_only_when_a_head_was_observed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            reg = root / "registry.json"
            reg.write_text(json.dumps({"schema": 1, "name": "plutonium-module-registry", "description": "d",
                                       "entries": [entry(), entry(name="someone/pack", kind="composition",
                                                                  declaration={"id": "stock_pack", "title": "P", "category": "pack", "tags": [],
                                                                               "bases": ["stock"], "maps": ["zm_transit"]})]}))
            first = build.build(reg, root / "site", observe=False)
            self.assertEqual(first["counts"], {"entries": 2, "modules": 1, "compositions": 1, "update_unverified": 0})
            files = sorted(p.relative_to(root / "site").as_posix() for p in (root / "site").rglob("*") if p.is_file())
            self.assertEqual(files, [".nojekyll", "catalog.json", "entries/someone/pack.json", "entries/someone/thing.json", "index.html", "llms.txt", "registry.json"])
            catalog_a = (root / "site" / "catalog.json").read_bytes()
            build.build(reg, root / "site", observe=False)
            self.assertEqual((root / "site" / "catalog.json").read_bytes(), catalog_a, "same inputs, same bytes")
            page = (root / "site" / "index.html").read_text()
            self.assertIn("someone/thing", page)
            self.assertNotIn("<script", page)
            self.assertIn("never gameplay", page)
            text = (root / "site" / "llms.txt").read_text()
            self.assertIn("pat registry add", text)
            self.assertIn("## someone/pack", text)
            self.assertEqual((root / "site" / "registry.json").read_bytes(), reg.read_bytes())
            # Drift is a projection: the listed snapshot and its status are kept, the head is shown.
            moved = build.project(entry(), head=OTHER)
            self.assertEqual(moved["verification"]["snapshot_status"], "update unverified")
            self.assertEqual(moved["verification"]["listed_status"], "unverified")
            self.assertEqual(moved["verification"]["observed_head"], OTHER)
            still = build.project(entry(), head=COMMIT)
            self.assertEqual(still["verification"]["snapshot_status"], "unverified")
            self.assertEqual(moved["listed"]["commit"], COMMIT)


if __name__ == "__main__":
    unittest.main()
