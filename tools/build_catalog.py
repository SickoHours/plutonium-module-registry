#!/usr/bin/env python3
"""Build the catalog: the read-only projection of registry.json for people and agents.

    python tools/build_catalog.py [--registry registry.json] [--output site] [--observe-heads]

Writes ``site/catalog.json`` (every entry with its declaration summary, fetch command and
verification), ``site/entries/<owner>/<id>.json``, ``site/llms.txt`` (the same facts as plain
text for an agent that reads pages), ``site/index.html`` (a static table, no script) and
``site/registry.json`` (a byte copy of the source). With ``--observe-heads`` each repository's
current default-branch head is read from the GitHub API (``GITHUB_TOKEN`` when set) and an entry
whose head moved past its listed commit is shown as ``update unverified``; the listed snapshot
and its status are unchanged. Deterministic for the same inputs: no time and no machine path is
written unless a head was observed.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE_URL = "https://sickohours.github.io/plutonium-module-registry"
RAW_URL = "https://raw.githubusercontent.com/SickoHours/plutonium-module-registry/main/registry.json"


def observe_head(repository: str, token: str | None) -> str | None:
    owner_repo = repository.removeprefix("https://github.com/").strip("/")
    request = urllib.request.Request(f"https://api.github.com/repos/{owner_repo}/commits/HEAD",
                                     headers={"Accept": "application/vnd.github.sha", "User-Agent": "plutonium-module-registry",
                                              **({"Authorization": f"Bearer {token}"} if token else {})})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
            return response.read().decode("utf-8").strip() or None
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


def project(entry: dict, head: str | None) -> dict:
    listed = entry["listed"]["commit"]
    verification = dict(entry.get("verification", {}))
    status = verification.get("snapshot_status", "unverified")
    if head and head != listed and status != "update unverified":
        verification["snapshot_status"] = "update unverified"
        verification["listed_status"] = status
    if head:
        verification["observed_head"] = head
    return {"name": entry["name"], "kind": entry["kind"], "repository": entry["repository"], "path": entry.get("path", "."),
            "listed": entry["listed"], "distribution": entry.get("distribution", "source"), "declaration": entry.get("declaration", {}),
            "verification": verification, "history": entry.get("history", []),
            "fetch": ["pat", "module", "fetch", f"{entry['name']}@{listed}", "--output", "<new dir>"],
            "snapshot_url": f"{entry['repository']}/tree/{listed}/{entry.get('path', '.')}".replace("/tree/" + listed + "/.", "/tree/" + listed),
            "entry_url": f"{SITE_URL}/entries/{entry['name']}.json"}


def llms_text(catalog: dict) -> str:
    lines = ["# Plutonium Module Registry", "",
             "Modules and packs for Plutonium T6 Zombies, listed by name at exact commits. Read with the Plutonium Agent Toolkit:",
             f"  pat registry add {RAW_URL} --json", "  pat registry search <words> --json", "  pat module fetch <owner/id>@<commit> --output <new dir> --json", "",
             "Words: module, composition (pack), registry, catalog, entry; never plugin or marketplace. A listing is a claim at a commit; "
             "fetch, then plan; the receipts are the facts. snapshot_status is the registry's own static check, never gameplay and never safety.", "",
             f"Entries: {len(catalog['entries'])}", ""]
    for e in catalog["entries"]:
        d = e["declaration"]
        lines.append(f"## {e['name']}")
        lines.append(f"- kind: {e['kind']}; distribution: {e['distribution']}; category: {d.get('category', '')}/{d.get('kind', '')}; tags: {', '.join(d.get('tags', []))}")
        lines.append(f"- title: {d.get('title', '')}; version: {d.get('version', '')}; bases: {', '.join(d.get('bases', []))}; maps: {', '.join(d.get('maps', []))}")
        lines.append(f"- repository: {e['repository']} path: {e['path']} commit: {e['listed']['commit']} listed: {e['listed'].get('at', '')}")
        lines.append(f"- verification: {e['verification'].get('snapshot_status', 'unverified')}" + (f" (head {e['verification']['observed_head'][:12]})" if e['verification'].get('observed_head') else ""))
        lines.append(f"- fetch: {' '.join(e['fetch'])}")
        lines.append("")
    return "\n".join(lines)


def index_html(catalog: dict) -> str:
    rows = []
    for e in catalog["entries"]:
        d = e["declaration"]
        rows.append("<tr>"
                    f"<td><a href=\"{html.escape(e['snapshot_url'])}\">{html.escape(e['name'])}</a></td>"
                    f"<td>{html.escape(e['kind'])}</td><td>{html.escape(d.get('category', ''))}{('/' + html.escape(d['kind'])) if d.get('kind') else ''}</td>"
                    f"<td>{html.escape(', '.join(d.get('tags', [])))}</td><td>{html.escape(', '.join(d.get('bases', [])))}</td>"
                    f"<td>{html.escape(', '.join(d.get('maps', [])))}</td><td>{html.escape(e['distribution'])}</td>"
                    f"<td>{html.escape(e['verification'].get('snapshot_status', 'unverified'))}</td>"
                    f"<td><code>{html.escape(e['listed']['commit'][:12])}</code></td>"
                    "</tr>")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>Plutonium Module Registry</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>body{{font:16px/1.5 system-ui,sans-serif;max-width:72rem;margin:2rem auto;padding:0 1rem;color:#1c1c1c}}table{{border-collapse:collapse;width:100%}}th,td{{text-align:left;padding:.4rem .6rem;border-bottom:1px solid #ddd;vertical-align:top}}code,pre{{font-family:ui-monospace,monospace;font-size:.9em}}pre{{background:#f4f4f4;padding:.8rem;overflow:auto}}p.note{{color:#555}}</style></head>
<body>
<h1>Plutonium Module Registry</h1>
<p>Modules and packs for Plutonium Black Ops II Zombies, listed by name at exact commits, for people and their coding agents. The source is <a href="registry.json">registry.json</a>; this page, <a href="catalog.json">catalog.json</a> and <a href="llms.txt">llms.txt</a> are generated from it.</p>
<pre>pat registry add {html.escape(RAW_URL)} --json
pat registry search &lt;words&gt; --json
pat module fetch &lt;owner/id&gt;@&lt;commit&gt; --output &lt;new dir&gt; --json</pre>
<p class="note">A listing is what this registry claimed at that commit. Fetch, then plan; the receipts are the facts. <em>snapshot_status</em> is the registry's own static check on the exact snapshot: never gameplay, never a security audit, certification, warranty or endorsement. <em>update unverified</em> means the repository moved past the listed commit; the listed snapshot is unchanged. How to list yours: <a href="https://github.com/SickoHours/plutonium-module-registry#list-your-module-or-pack">README</a>.</p>
<table><thead><tr><th>Entry</th><th>Kind</th><th>Category</th><th>Tags</th><th>Bases</th><th>Maps</th><th>Distribution</th><th>Status</th><th>Commit</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
<p class="note">{len(catalog['entries'])} entries. Community-run by SickoHours; not affiliated with Plutonium or Activision. Apache-2.0 for the files here; every listed module keeps its own license.</p>
</body></html>
"""


def build(registry_path: Path, output: Path, observe: bool) -> dict:
    raw = registry_path.read_text(encoding="utf-8")
    registry = json.loads(raw)
    token = os.environ.get("GITHUB_TOKEN") if observe else None
    heads: dict[str, str | None] = {}
    entries = []
    for entry in registry["entries"]:
        head = None
        if observe:
            if entry["repository"] not in heads:
                heads[entry["repository"]] = observe_head(entry["repository"], token)
            head = heads[entry["repository"]]
        entries.append(project(entry, head))
    catalog = {"schema": 1, "name": registry["name"], "description": registry.get("description", ""), "source": RAW_URL,
               "entries": entries, "counts": {"entries": len(entries), "modules": sum(1 for e in entries if e["kind"] == "module"),
                                             "compositions": sum(1 for e in entries if e["kind"] == "composition"),
                                             "update_unverified": sum(1 for e in entries if e["verification"].get("snapshot_status") == "update unverified")},
               "heads_observed": observe}
    output.mkdir(parents=True, exist_ok=True)
    (output / "registry.json").write_text(raw, encoding="utf-8")
    (output / "catalog.json").write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    (output / "llms.txt").write_text(llms_text(catalog), encoding="utf-8")
    (output / "index.html").write_text(index_html(catalog), encoding="utf-8")
    (output / ".nojekyll").write_text("", encoding="utf-8")
    for e in entries:
        p = output / "entries" / f"{e['name']}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(e, indent=2) + "\n", encoding="utf-8")
    return catalog


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--registry", default="registry.json")
    ap.add_argument("--output", default="site")
    ap.add_argument("--observe-heads", action="store_true")
    args = ap.parse_args()
    catalog = build((ROOT / args.registry).resolve(), (ROOT / args.output).resolve(), args.observe_heads)
    print(json.dumps({"ok": True, "output": args.output, "counts": catalog["counts"], "heads_observed": args.observe_heads}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
