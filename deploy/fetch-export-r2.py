#!/usr/bin/env python3
"""
Fetch Fisqua's Export from Cloudflare R2

This script gets the data files the Zasqua build reads, from the place
Fisqua publishes them: the R2 bucket `zasqua-export`, under the prefix
`neogranadina/`. It is the R2 counterpart of the Backblaze B2 download step
in the deploy workflow, and the workflow chooses between the two.

Fisqua does not publish one large `descriptions.json`. It writes one file
per fonds (`descriptions-<fonds>.json`) and a small `descriptions-index.json`
that lists them, because the largest fonds is too big to assemble inside a
Worker. This script reads the index, downloads each file it lists, and joins
the arrays into `exports/descriptions.json`, which is the file the build
expects. Records are kept exactly as Fisqua wrote them, in the order the
index lists the fonds; no field is dropped or rewritten. The five other
files (`entities`, `places`, `repositories`, `entity_links`, `place_links`)
are copied across as they are, after a check that each is a JSON array.

Two more files are optional: `publisher.json` (the publishing institution)
and `vocabulary.json` (labels for entity and place types, roles and
authority sources). Each is one JSON object, not an array. An export
written to data contract 1.0 has neither, and the build then renders
without them; when one is absent, a copy left in `exports/` by an earlier
run is removed, so the build never reads a stale publisher.

The script stops with a non-zero exit status, before the build starts, when
a file the index lists is missing, when any array file is not a JSON array,
when an optional file is present but is not a JSON object, or when two fonds
files carry a description with the same `id`. A partial or
inconsistent export would otherwise build a site with missing pages.

Pipeline context: runs after checkout and before the redirect table and
`zasqua build`; writes into `exports/`.

Practical details:
  - R2 is reached through its S3 API, as in `upload-to-r2.py`, using
    R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY and R2_ENDPOINT
    (https://<account_id>.r2.cloudflarestorage.com).
  - `--source-dir DIR` reads the same layout from a local directory (the
    contents of the prefix) instead of R2, for tests and dry runs; no
    credentials are needed.
  - The keys in the index include the prefix (`neogranadina/descriptions-
    <fonds>.json`); the script strips the prefix when reading a local
    directory.
  - Each count is printed on one line: `fetch-export <file> records=<N>`;
    an optional file prints `fields=<N>` when present and `absent` when not.

Usage:
    python3 deploy/fetch-export-r2.py [--bucket zasqua-export]
        [--prefix neogranadina] [--output-dir exports] [--source-dir DIR]

Version: v1.3.0
"""

import argparse
import json
import os
import sys
from pathlib import Path

SINGLE_FILES = [
    "entities.json",
    "places.json",
    "repositories.json",
    "entity_links.json",
    "place_links.json",
]
OPTIONAL_OBJECT_FILES = [
    "publisher.json",
    "vocabulary.json",
]
INDEX_NAME = "descriptions-index.json"


class ExportError(Exception):
    """A problem with the export that must stop the deploy."""


class LocalSource:
    """Reads the export layout from a local directory."""

    def __init__(self, directory, prefix):
        self.directory = Path(directory)
        self.prefix = prefix.strip("/")

    def read(self, key):
        relative = key
        if self.prefix and key.startswith(self.prefix + "/"):
            relative = key[len(self.prefix) + 1:]
        path = self.directory / relative
        if not path.is_file():
            raise ExportError(f"missing file: {key} (looked for {path})")
        return path.read_bytes()

    def read_optional(self, key):
        """Return the file's bytes, or None when it is not there."""
        try:
            return self.read(key)
        except ExportError:
            return None


class R2Source:
    """Reads the export layout from an R2 bucket through the S3 API."""

    def __init__(self, bucket, endpoint, access_key, secret_key):
        import boto3
        from botocore.config import Config

        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name="auto",
            config=Config(retries={"max_attempts": 3, "mode": "standard"}),
        )

    def read(self, key):
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
        except self.client.exceptions.NoSuchKey:
            raise ExportError(f"missing file: {key} in bucket {self.bucket}")
        return response["Body"].read()

    def read_optional(self, key):
        """Return the object's bytes, or None when the key does not exist.

        Only a missing key counts as absent; any other error, such as a
        denied read, still stops the deploy.
        """
        try:
            response = self.client.get_object(Bucket=self.bucket, Key=key)
        except self.client.exceptions.NoSuchKey:
            return None
        return response["Body"].read()


def parse_array(data, key):
    """Parse bytes as JSON and require the top level to be an array."""
    try:
        parsed = json.loads(data)
    except json.JSONDecodeError as error:
        raise ExportError(f"{key} is not valid JSON: {error}")
    if not isinstance(parsed, list):
        raise ExportError(
            f"{key} is not a JSON array (found {type(parsed).__name__})"
        )
    return parsed


def parse_object(data, key):
    """Parse bytes as JSON and require the top level to be an object."""
    try:
        parsed = json.loads(data)
    except json.JSONDecodeError as error:
        raise ExportError(f"{key} is not valid JSON: {error}")
    if not isinstance(parsed, dict):
        raise ExportError(
            f"{key} is not a JSON object (found {type(parsed).__name__})"
        )
    return parsed


def write_json(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(records, handle, ensure_ascii=False)


def fetch_descriptions(source, prefix, output_dir):
    """Read the index, then each per-fonds file, and join them in order."""
    index_key = f"{prefix}/{INDEX_NAME}" if prefix else INDEX_NAME
    try:
        index = json.loads(source.read(index_key))
    except json.JSONDecodeError as error:
        raise ExportError(f"{index_key} is not valid JSON: {error}")
    fonds = index.get("fonds") if isinstance(index, dict) else None
    if not isinstance(fonds, list):
        raise ExportError(f"{index_key} has no 'fonds' list")

    combined = []
    seen = {}
    for entry in fonds:
        key = entry.get("key") if isinstance(entry, dict) else None
        if not key:
            raise ExportError(f"{index_key} has a fonds entry without a key")
        records = parse_array(source.read(key), key)
        expected = entry.get("record_count")
        if expected is not None and expected != len(records):
            raise ExportError(
                f"{key} has {len(records)} records but the index lists {expected}"
            )
        for record in records:
            record_id = record.get("id") if isinstance(record, dict) else None
            if record_id is not None:
                if record_id in seen:
                    raise ExportError(
                        f"duplicate description id {record_id!r} in {key} "
                        f"(first seen in {seen[record_id]})"
                    )
                seen[record_id] = key
        print(f"fetch-export {key} records={len(records)}")
        combined.extend(records)

    write_json(output_dir / "descriptions.json", combined)
    print(
        f"fetch-export descriptions.json records={len(combined)} "
        f"fonds_files={len(fonds)}"
    )
    return len(combined)


def fetch_single_files(source, prefix, output_dir):
    for name in SINGLE_FILES:
        key = f"{prefix}/{name}" if prefix else name
        records = parse_array(source.read(key), key)
        write_json(output_dir / name, records)
        print(f"fetch-export {name} records={len(records)}")


def fetch_optional_files(source, prefix, output_dir):
    for name in OPTIONAL_OBJECT_FILES:
        key = f"{prefix}/{name}" if prefix else name
        target = output_dir / name
        data = source.read_optional(key)
        if data is None:
            if target.exists():
                target.unlink()
            print(f"fetch-export {name} absent")
            continue
        parsed = parse_object(data, key)
        write_json(target, parsed)
        print(f"fetch-export {name} fields={len(parsed)}")


def build_parser():
    parser = argparse.ArgumentParser(
        description="Fetch Fisqua's export from R2 into exports/."
    )
    parser.add_argument("--bucket", default="zasqua-export")
    parser.add_argument("--prefix", default="neogranadina")
    parser.add_argument("--output-dir", default="exports")
    parser.add_argument(
        "--source-dir",
        help="read the same layout from this local directory instead of R2",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    prefix = args.prefix.strip("/")
    output_dir = Path(args.output_dir)

    if args.source_dir:
        source = LocalSource(args.source_dir, prefix)
    else:
        endpoint = os.environ.get("R2_ENDPOINT")
        access_key = os.environ.get("R2_ACCESS_KEY_ID")
        secret_key = os.environ.get("R2_SECRET_ACCESS_KEY")
        if not all([endpoint, access_key, secret_key]):
            print(
                "R2_ENDPOINT, R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY "
                "must be set (or pass --source-dir)",
                file=sys.stderr,
            )
            return 2
        source = R2Source(args.bucket, endpoint, access_key, secret_key)

    try:
        fetch_descriptions(source, prefix, output_dir)
        fetch_single_files(source, prefix, output_dir)
        fetch_optional_files(source, prefix, output_dir)
    except ExportError as error:
        print(f"fetch-export error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

# Version: v1.3.0
