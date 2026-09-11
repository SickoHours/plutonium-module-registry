# Agent instructions for the Plutonium Module Registry

You are a coding agent helping a person list, find or maintain modules and packs for Plutonium T6
Zombies. This repository is one data file, `registry.json`, a catalog built from it, and the checks
that keep it honest. Read `README.md` first; the words are the Plutonium Agent Toolkit's
(`CONTEXT.md` there): module, composition (pack), registry, catalog, entry. Never plugin, never
marketplace.

## Finding and fetching

- Record this registry once: `pat registry add <raw URL of registry.json> --json`. Then `pat
  registry search` and `pat registry show <owner/id>` read it offline, and `pat module fetch
  <owner/id>@<commit> --output <new dir> --json` downloads the exact snapshot with a receipt.
- A listing is a claim at a commit. Fetch, then `pat module plan`; the receipts are the facts.
  `snapshot_status` describes the registry's own static checks, never gameplay and never safety.
- `catalog.json` and `llms.txt` on the site are read-only projections of `registry.json` with
  drift (`observed_head`) added; the file in `main` is the source.

## Submitting for a person

1. Their module or pack is in a public GitHub repository under their own account or organisation,
   at a pushed commit, with `module.json` or `composition.json` beside the payload, and
   `pat module plan` succeeds on it. Run the toolkit's playbook `docs/playbooks/publish-a-module.md`
   first: it fetches their own listing back the way a stranger would.
2. Draft the entry: `name` is `<github-owner>/<module id>` in lowercase, `repository` the
   `https://github.com/<owner>/<repo>` URL, `path` the directory inside it, `listed.commit` the
   40-character commit, `listed.at` today's date, `distribution` as the declaration says,
   `declaration` a copy of the declaration's id, version, title, category, kind, tags, bases, maps
   and provides, `verification: {"snapshot_status": "unverified"}`, `history: []`.
3. Show the person the exact entry and the pull request or issue body. **File it only on their
   explicit go.** Never file on their behalf silently, and never confirm rights on their behalf:
   the checklist is theirs to tick.
4. Run the same checks the pull request will run before opening it:
   `pat registry add registry.json --json`, `pat registry baseline <the directory> --output <new dir> --json`
   on their checkout, and `python tools/check_entries.py --base origin/main`.
   A `declaration-mismatch` means their `module.json` `source` names another repository or commit;
   fix the declaration, push, list the new commit.

## Maintaining

- The `Validate registry` workflow is the gate: it validates the file, fetches every added or
  changed entry at its listed commit and compares declaration summaries. Merge only green pull
  requests; the merge is the approval and it is bound to the commit the check fetched.
- Do not edit a listing in place. A newer commit changes `listed` and appends the old listing to
  `history`. A repository that moved is a new entry; retire the old one by setting
  `verification.snapshot_status` to `unverified` and noting the move in `history`, or remove it
  through the rights process in `NOTICE.md`.
- Set `snapshot verified` only when the validate check's baseline on that exact snapshot is
  `passed` and you have read its rows; the check refuses the claim on any other outcome. A
  `review-required` baseline lists capabilities (installers, bundled packages, Lua UI, file IO)
  for you to read before merging; it does not block. No model sets a status, a label or an
  approval here.
- Never add game bytes, recordings, logs, credentials or personal paths to this repository.

## What is not here

No accounts, no server, no download counts, no ratings. Popularity, if ever shown, never touches
verification. Version strings are recorded, not compared; a composition pins commits.
