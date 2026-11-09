#!/usr/bin/env python3
"""
Build the Redirect Table for Retired Addresses

Every entity, place and description on zasqua.org has a page at `/<code>/`.
When a record is recoded — an entity or place moves from a five-character
code to a six-character one, or a description's reference code changes —
the old address must keep working. The export files record this on the
record itself: `former_codes` on entities and places, and
`former_reference_codes` on descriptions. This script turns those lists
into the lookup table the serving Worker uses to answer an old address
with a permanent redirect (301) to the new one.

It reads `entities.json`, `places.json` and `descriptions.json` from the
exports directory and writes a JSON array in the bulk format that
`wrangler kv bulk put` accepts: `[{"key": "/ne-u3ufz/", "value":
"/ne-aaszvt/"}, ...]`. Codes are used exactly as found — no encoding, no
case change, no trimming — because the Worker decodes the request path and
looks it up as written. Old reference codes can contain `?`, `)`, `–`
(U+2013) and non-ASCII letters; they pass through untouched.

The deploy workflow runs this after fetching the exports and before the
build, and uploads the result to the Worker's `REDIRECTS` KV namespace. An
export with no former codes produces `[]`, which the workflow treats as
nothing to upload.

The script stops with exit status 1 and a message when the table would be
wrong:
  - a former code equals a live code in any of the three files (it would
    shadow a real page);
  - the same former code is claimed by two records;
  - a former code is blank or contains `/` (it cannot be one path segment);
  - the former-codes field is present but is not an array of strings.

Any one of the three files may be absent and is then skipped with a note;
all three absent is an error.

Usage:
  python3 deploy/build-redirects.py <exports-dir> <output.json>

Prints one summary line on stdout:
  redirects built=<N> entities=<n> places=<n> descriptions=<n>

Version: v1.3.0
"""

import json
import sys
from pathlib import Path

# (file, live-code field, former-codes field, summary label)
SOURCES = [
    ("entities.json", "entity_code", "former_codes", "entities"),
    ("places.json", "place_code", "former_codes", "places"),
    ("descriptions.json", "reference_code", "former_reference_codes", "descriptions"),
]


def fail(message):
    print(f"error: {message}", file=sys.stderr)
    raise SystemExit(1)


def load_records(exports_dir):
    """Return {label: (live_field, former_field, records)} for each file present."""
    loaded = {}
    for filename, live_field, former_field, label in SOURCES:
        path = exports_dir / filename
        if not path.is_file():
            print(f"note: {filename} not found, skipped", file=sys.stderr)
            continue
        with path.open(encoding="utf-8") as fh:
            records = json.load(fh)
        if not isinstance(records, list):
            fail(f"{filename} is not a JSON array")
        loaded[label] = (live_field, former_field, records)
    if not loaded:
        fail(f"none of the export files were found in {exports_dir}")
    return loaded


def build(exports_dir):
    """Return (pairs, counts): the redirect pairs and per-file counts."""
    loaded = load_records(exports_dir)

    live_codes = set()
    for live_field, _former_field, records in loaded.values():
        for record in records:
            code = record.get(live_field)
            if isinstance(code, str):
                live_codes.add(code)

    pairs = {}
    counts = {label: 0 for _f, _l, _r, label in SOURCES}
    for label, (live_field, former_field, records) in loaded.items():
        for record in records:
            if former_field not in record:
                continue
            live = record.get(live_field)
            former_codes = record[former_field]
            if not isinstance(former_codes, list) or not all(
                isinstance(c, str) for c in former_codes
            ):
                fail(
                    f"{former_field} on {label} record {live!r} "
                    "is not an array of strings"
                )
            for former in former_codes:
                if not former.strip():
                    fail(f"blank former code on {label} record {live!r}")
                if "/" in former:
                    fail(
                        f"former code {former!r} on {label} record {live!r} "
                        "contains '/'"
                    )
                if former in live_codes:
                    fail(
                        f"former code {former!r} on {label} record {live!r} "
                        "equals a live code and would shadow its page"
                    )
                if not isinstance(live, str) or not live:
                    fail(
                        f"{label} record with former code {former!r} "
                        f"has no {live_field}"
                    )
                if former in pairs:
                    other = pairs[former][0]
                    if other != live:
                        fail(
                            f"former code {former!r} is claimed by both "
                            f"{other!r} and {live!r}"
                        )
                    continue
                pairs[former] = (live, label)
                counts[label] += 1

    table = [
        {"key": f"/{former}/", "value": f"/{live}/"}
        for former, (live, _label) in pairs.items()
    ]
    return table, counts


def main(argv):
    if len(argv) != 3:
        print(
            "usage: build-redirects.py <exports-dir> <output.json>",
            file=sys.stderr,
        )
        raise SystemExit(2)
    table, counts = build(Path(argv[1]))
    with open(argv[2], "w", encoding="utf-8") as fh:
        json.dump(table, fh, ensure_ascii=False)
    print(
        f"redirects built={len(table)} entities={counts['entities']} "
        f"places={counts['places']} descriptions={counts['descriptions']}"
    )


if __name__ == "__main__":
    main(sys.argv)

# Version: v1.3.0
