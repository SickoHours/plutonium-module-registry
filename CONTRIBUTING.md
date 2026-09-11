# Contributing

Two kinds of change land here: a listing (one entry in `registry.json`) and a change to the
checks or the catalog. Both come as pull requests; the `Validate registry` check must be green
and a maintainer merges.

## A listing

Follow the README's "List your module or pack". Keep the pull request to one entry (or one
update of one entry) so the fetch step's report reads plainly. Run the checks yourself first:

```sh
python -m pip install "git+https://github.com/SickoHours/plutonium-agent-toolkit@<the commit validate.yml pins>"
PAT_HOME=/tmp/registry-home python tools/check_entries.py --base origin/main
```

`check_entries.py` fetches your entry's snapshot with `pat module fetch` and compares the
declaration summary you wrote with the declaration in the snapshot; `declaration-mismatch` means
the snapshot's `source` names another repository or commit.

## The checks or the catalog

`tools/check_entries.py`, `tools/build_catalog.py` and `tests/test_tools.py` change together.
`python -m unittest discover -s tests -v` runs offline. The toolkit commit the validation installs
is pinned in `.github/workflows/validate.yml`; bump it deliberately, with the reason in the pull
request, and never to a moving ref. GitHub Actions are pinned by SHA.

## What never lands

Game bytes, recordings, logs, credentials, personal paths, a listing whose repository is not
under the entry's owner, a rewritten history row, a trust word (safe, trusted, certified) on
anything.
