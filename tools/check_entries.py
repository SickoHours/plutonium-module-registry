#!/usr/bin/env python3
"""Validate registry.json and prove every added or changed entry against its snapshot.

    python tools/check_entries.py [--base <git ref>] [--registry registry.json] [--all]

Steps, each a row in the JSON report on stdout (exit 1 on any failure):

1. ``pat registry add registry.json`` in a private toolkit home: the file is well formed by the
   toolkit's own validator (names, owners, commits, kinds, declaration summaries, duplicates).
2. The entries that differ from ``--base`` (default ``origin/main``; ``--all`` takes every entry):
   ``pat module fetch <name>@<commit>`` downloads the exact snapshot and refuses a declaration
   whose ``source`` names another repository or commit; the fetched ``module.json`` or
   ``composition.json`` is then compared with the entry's declaration summary field by field.
3. The toolkit's static baseline runs on the fetched snapshot (``pat registry baseline``, the
   directory that holds the entry and every member it names, with the listing's repository and
   commit): a blocking finding (``needs-fixes``) or an unreadable tree (``incomplete``) fails the
   check; ``review-required`` passes with its rows in the report for the maintainer to read;
   ``passed`` is what a listing may call ``snapshot verified``. The baseline never executes
   anything in the snapshot and is not a security audit; the report says so.
4. History is append-only: an entry whose ``listed.commit`` changed carries its previous listing
   under ``history``; an entry present in the base and absent now is reported (removals go
   through NOTICE.md and are named in the pull request).
5. A listing may claim ``snapshot verified`` only when this run's baseline on that snapshot is
   ``passed``; any other claim of that status is a problem.

Nothing here executes anything from a snapshot: it reads JSON files, hashes and compares them.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SUMMARY_KEYS = ("id", "version", "title", "category", "kind", "tags", "bases", "maps", "provides")


def pat(args: list[str], home: Path) -> dict:
    env = dict(os.environ, PAT_HOME=str(home))
    proc = subprocess.run([sys.executable, "-m", "plutonium_agent_toolkit", *args, "--json"], capture_output=True, text=True, env=env)
    try:
        payload = json.loads(proc.stdout) if proc.stdout.strip() else {"ok": False, "error_code": "no_output", "message": proc.stderr[-800:]}
    except ValueError:
        payload = {"ok": False, "error_code": "not_json", "message": proc.stdout[-800:] + proc.stderr[-800:]}
    payload["_exit"] = proc.returncode
    return payload


def load(text: str) -> dict:
    data = json.loads(text)
    if not isinstance(data, dict) or not isinstance(data.get("entries"), list):
        raise SystemExit("registry.json must be an object with an entries list")
    return data


def base_registry(ref: str | None, path: Path) -> dict | None:
    if not ref:
        return None
    proc = subprocess.run(["git", "show", f"{ref}:{path.relative_to(ROOT).as_posix()}"], capture_output=True, text=True, cwd=ROOT)
    if proc.returncode != 0:
        return None
    return load(proc.stdout)


def summary_of(fetched: dict, kind: str) -> dict:
    """The declaration summary a listing should carry, derived from the fetched file."""
    if kind == "module":
        return {k: fetched.get(k) for k in SUMMARY_KEYS if k in fetched}
    row = {"id": fetched.get("name")}
    for key, src in (("title", "title"), ("tags", "tags")):
        if src in fetched:
            row[key] = fetched[src]
    row["category"] = "pack"
    if "base" in fetched:
        row["bases"] = [fetched["base"]]
    if "map" in fetched:
        row["maps"] = [fetched["map"]]
    return row


def compare(entry: dict, fetched: dict, kind: str) -> list[str]:
    expected = summary_of(fetched, kind)
    listed = entry.get("declaration", {})
    problems = []
    if "id" not in listed:
        problems.append("declaration summary has no id")
    for key, value in listed.items():
        if key not in expected:
            if key in ("provides", "version", "kind") and kind == "composition":
                problems.append(f"declaration.{key} is not a composition field")
            continue
        if value != expected[key]:
            problems.append(f"declaration.{key} is {value!r} in the listing but {expected[key]!r} in the fetched file")
    if kind == "composition" and listed.get("category", "pack") != "pack":
        problems.append("a composition's category is pack")
    return problems


def changed_entries(current: dict, base: dict | None, everything: bool) -> tuple[list[dict], list[str], list[str]]:
    """(entries to prove, history problems, removed names)."""
    if everything or base is None:
        return list(current["entries"]), [], []
    before = {e["name"]: e for e in base["entries"]}
    now = {e["name"]: e for e in current["entries"]}
    to_prove, problems = [], []
    for name, entry in now.items():
        old = before.get(name)
        if old is None:
            to_prove.append(entry)
            continue
        if old != entry:
            to_prove.append(entry)
        if old["listed"]["commit"] != entry["listed"]["commit"]:
            previous = {k: v for k, v in old.items() if k != "history"}
            history = entry.get("history", [])
            if not any(h.get("listed", {}).get("commit") == old["listed"]["commit"] for h in history):
                problems.append(f"{name}: listed.commit changed from {old['listed']['commit'][:12]} but the earlier listing is not under history")
            if old.get("history", []) and old["history"] != history[:len(old["history"])] and old["history"] != history[-len(old["history"]):]:
                problems.append(f"{name}: earlier history rows were rewritten")
            del previous
    removed = sorted(set(before) - set(now))
    return to_prove, problems, removed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="origin/main", help="git ref holding the previous registry.json; entries equal to it are not re-fetched")
    ap.add_argument("--registry", default="registry.json")
    ap.add_argument("--all", action="store_true", help="prove every entry, not only the changed ones")
    ap.add_argument("--no-fetch", action="store_true", help="validate and diff only; do not download snapshots")
    ap.add_argument("--no-baseline", action="store_true", help="fetch and compare, but skip the toolkit's static baseline on each snapshot")
    args = ap.parse_args()
    path = (ROOT / args.registry).resolve()
    current = load(path.read_text(encoding="utf-8"))
    report = {"registry": str(path.relative_to(ROOT)), "steps": [], "ok": True}
    home = Path(tempfile.mkdtemp(prefix="registry-check-home-"))
    work = Path(tempfile.mkdtemp(prefix="registry-check-work-"))
    try:
        added = pat(["registry", "add", str(path)], home)
        report["steps"].append({"step": "pat registry add", "ok": bool(added.get("ok")), "error_code": added.get("error_code"), "message": added.get("message"),
                                "entries": (added.get("result") or {}).get("entries")})
        if not added.get("ok"):
            report["ok"] = False
            return finish(report)
        base = base_registry(None if args.all else args.base, path)
        to_prove, problems, removed = changed_entries(current, base, args.all)
        report["steps"].append({"step": "history is append-only", "ok": not problems, "problems": problems, "removed": removed,
                                "base": None if args.all else args.base, "base_found": base is not None})
        report["ok"] &= not problems
        report["to_prove"] = [e["name"] for e in to_prove]
        if args.no_fetch:
            report["steps"].append({"step": "fetch and compare", "ok": True, "skipped": "--no-fetch"})
            return finish(report)
        for index, entry in enumerate(to_prove, 1):
            out = work / f"fetch-{index:03d}"
            fetched = pat(["module", "fetch", f"{entry['name']}@{entry['listed']['commit']}", "--output", str(out)], home)
            row = {"step": f"fetch {entry['name']}", "ok": bool(fetched.get("ok")), "error_code": fetched.get("error_code"), "message": fetched.get("message")}
            if fetched.get("ok"):
                result = fetched["result"]
                kind = result["kind"]
                row["kind"] = kind
                row["archive_sha256"] = result["archive_sha256"]
                if kind != entry["kind"]:
                    row["ok"] = False
                    row["problems"] = [f"listed as {entry['kind']} but the snapshot holds a {kind}"]
                else:
                    declared = Path(result["module_dir"]) / ("module.json" if kind == "module" else "composition.json")
                    problems = compare(entry, json.loads(declared.read_text(encoding="utf-8")), kind)
                    row["problems"] = problems
                    row["ok"] = not problems
            report["steps"].append(row)
            report["ok"] &= row["ok"]
            if not fetched.get("ok") or args.no_baseline:
                continue
            # The baseline scans the snapshot root (the entry and every member a pack names live
            # under it), pinned to the listing's repository and commit.
            snapshot_root = Path(fetched["result"]["module_dir"])
            for _ in Path(entry.get("path", ".")).parts:
                snapshot_root = snapshot_root.parent
            scanned = pat(["registry", "baseline", str(snapshot_root), "--repository", entry["repository"],
                           "--commit", entry["listed"]["commit"], "--output", str(work / f"baseline-{index:03d}")], home)
            brow = baseline_row(entry, scanned)
            report["steps"].append(brow)
            report["ok"] &= brow["ok"]
        return finish(report)
    finally:
        shutil.rmtree(home, ignore_errors=True)
        shutil.rmtree(work, ignore_errors=True)


def baseline_row(entry: dict, scanned: dict) -> dict:
    """One report row for the baseline of one entry: the outcome decides, the rows inform."""
    row = {"step": f"baseline {entry['name']}", "ok": False, "error_code": scanned.get("error_code"), "message": scanned.get("message")}
    result = scanned.get("result") if scanned.get("ok") else None
    if not isinstance(result, dict):
        row["problems"] = ["the baseline did not run to a report; see error_code and message"]
        return row
    outcome = result.get("outcome")
    row.update({"outcome": outcome, "blocked": bool(result.get("blocked")), "policy_version": result.get("policy_version"),
                "tree_sha256": result.get("tree_sha256"), "findings": result.get("findings", []),
                "capabilities": result.get("capabilities", []), "warnings": result.get("warnings", []),
                "unreadable": result.get("unreadable", []), "not_a_security_audit": True})
    problems = []
    if outcome in ("needs-fixes", "incomplete") or row["blocked"]:
        problems.append(f"baseline outcome {outcome}: " + "; ".join(f"{f.get('id')} at {f.get('file')}" for f in result.get("findings", []) if f.get("blocking")) or f"baseline outcome {outcome}")
    claimed = (entry.get("verification") or {}).get("snapshot_status", "unverified")
    if claimed == "snapshot verified" and outcome != "passed":
        problems.append(f"the listing claims snapshot verified but the baseline is {outcome}")
    row["problems"] = problems
    row["ok"] = not problems
    return row


def finish(report: dict) -> int:
    print(json.dumps(report, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
