# Plutonium Module Registry

The community registry of **modules** and **packs** for Plutonium Black Ops II Zombies, listed by
name at exact commits, for people and their coding agents. It is one file, `registry.json`, in the
format the [Plutonium Agent Toolkit](https://github.com/SickoHours/plutonium-agent-toolkit) reads
(`docs/REGISTRY.md` there), plus a generated catalog for browsing. It holds no game bytes: every
entry points at a public GitHub repository at a 40-character commit.

## Use it

```sh
pat registry add https://raw.githubusercontent.com/SickoHours/plutonium-module-registry/main/registry.json --json
pat registry search saints-row --json          # words, --category, --kind, --tag, --base, --map
pat module fetch <owner>/<id>@<commit> --output ../jobs/fetch-001 --json
```

A fetched module or pack is planned and built with `pat module plan|build`; the toolkit's playbooks
`compose-a-pack.md` and `attach-to-a-pack.md` say how. The catalog for reading is at
<https://sickohours.github.io/plutonium-module-registry/> (`catalog.json` and `llms.txt` beside it
for agents). The toolkit also ships its own registry of built-in modules and packs; the same entries
appear here so one search finds everything.

## Words

**Module**: one feature with its declaration (`module.json`) beside its payload. **Composition**
(a pack, in plain speech): a `composition.json` naming a base, a map and its members. **Registry**:
this file. **Catalog**: the generated projection. **Entry**: `<github-owner>/<module id>`; the
repository must live under that owner. Never "plugin" (in Plutonium a plugin is a native DLL) and
never "marketplace" (nothing is sold). Definitions: the toolkit's `CONTEXT.md`.

## List your module or pack

1. Put `module.json` (or `composition.json`) beside your payload in a public GitHub repository and
   push the commit you tested. `pat module plan` on it must succeed. Ship only assets you have the
   right to publish; a prebuilt package you cannot publish is listed as `distribution: private`
   with its declaration and manifest only. The toolkit's playbook `publish-a-module.md` walks
   through it and fetches your own listing back the way a stranger would.
2. Open a pull request that adds one entry to `registry.json`, or open a **Submit an entry** issue
   if you would rather not edit JSON; a maintainer turns it into the pull request. Your agent may
   draft either, show it to you, and file it only on your explicit go.
3. The `Validate registry` check validates the file with `pat registry add`, fetches every added or
   changed entry at its listed commit with `pat module fetch`, and compares the entry's declaration
   summary with the fetched declaration. A maintainer merges. That merge is the one human action,
   bound to the exact commit the check saw.
4. To list a newer commit, change `listed` and append the earlier listing to `history`. Listings
   are never rewritten; a module that moves repositories is a new entry.

## What a listing means

A listing says what this file claimed at that commit: the repository, the commit, and a copy of
the declaration. `verification.snapshot_status` is `unverified` until a maintainer has run the
toolkit's static baseline on the snapshot, then `snapshot verified`; the daily catalog build marks
an entry `update unverified` when the repository's current head has moved past the listed commit
(the listed snapshot is unchanged; only the drift is shown). None of this is a security audit,
certification, warranty or endorsement, and nothing here says anything about play: offline
verified, installed, launched, playable and accepted are earned per user, per base and per map,
by receipts, never by a listing.

## Who runs it

A community project maintained by [SickoHours](https://github.com/SickoHours), the author of the
toolkit. It is not affiliated with Plutonium or Activision. Rights concerns: [NOTICE.md](NOTICE.md).
Security: [SECURITY.md](SECURITY.md). Agents: [AGENTS.md](AGENTS.md). License: Apache-2.0 for the
files in this repository; every listed module keeps its own.
