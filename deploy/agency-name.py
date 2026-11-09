#!/usr/bin/env python3
"""
Print the Agency Name the EAC-CPF Export Will Use

The deploy refuses to publish EAC-CPF records without a maintenance agency,
because the engine would otherwise name the site title as the agency on
every record. This script prints the name the engine will use, in the
engine's own order: the `legal_name` in `exports/publisher.json` (a string,
trimmed), else `eac_agency_name` under `[params]` in `hugo.toml`. It prints
an empty line when there is neither, and the workflow treats that as a
failure.

A missing `publisher.json`, as in an export written to data contract 1.0,
is not an error: the script falls through to `hugo.toml`. A `publisher.json`
that does not parse is an error, since the build would stop on it too.

Usage:
    python3 deploy/agency-name.py <exports-dir> <hugo.toml>

Version: v1.3.0
"""

import json
import sys
import tomllib
from pathlib import Path


def agency_name(exports_dir, hugo_toml):
    publisher = Path(exports_dir) / "publisher.json"
    if publisher.is_file():
        data = json.loads(publisher.read_text(encoding="utf-8"))
        legal = data.get("legal_name") if isinstance(data, dict) else None
        if isinstance(legal, str) and legal.strip():
            return legal.strip()
    with open(hugo_toml, "rb") as handle:
        params = tomllib.load(handle).get("params", {})
    return str(params.get("eac_agency_name", "") or "").strip()


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2:
        print("usage: agency-name.py <exports-dir> <hugo.toml>", file=sys.stderr)
        return 2
    print(agency_name(args[0], args[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())

# Version: v1.3.0
