"""
Tests for the R2 Export Fetcher

These tests exercise `deploy/fetch-export-r2.py` through its `--source-dir`
option, against a small directory that has Fisqua's layout: the five single
files, a `descriptions-index.json` whose keys carry the `neogranadina/`
prefix, and one `descriptions-<fonds>.json` per fonds. There is no network
and no mock. They check that concatenation keeps every record and the index
order, and that the script stops on a missing listed file, a duplicate
description id, a file that is not an array, and a count that disagrees with
the index.

The optional `publisher.json` and `vocabulary.json` are checked both ways:
copied when present, skipped when absent (a contract 1.0 export) with any
stale copy in the output removed, and refused when present but not an
object. One test reads from a mocked R2 bucket, because there a missing key
is an S3 error rather than a missing file, and only that error may count as
absent.

Version: v1.3.0
"""

import json

import boto3
import pytest
from moto import mock_aws


def write(directory, name, data):
    (directory / name).write_text(json.dumps(data), encoding="utf-8")


def make_layout(directory, fonds=None):
    """Write a valid export into `directory` and return the fonds data."""
    fonds = fonds or {
        "co-aaa": [
            {"id": "u1", "reference_code": "co-aaa", "title": "Ñandú", "extra": {"k": [1, 2]}},
            {"id": "u2", "reference_code": "co-aaa-1", "title": "B"},
        ],
        "co-bbb": [
            {"id": "u3", "reference_code": "co-bbb", "title": "C", "date_start": None},
        ],
    }
    for code, records in fonds.items():
        write(directory, f"descriptions-{code}.json", records)
    write(directory, "descriptions-index.json", {
        "version": 1,
        "generated_at": "2026-10-31T00:00:00.000Z",
        "total_record_count": sum(len(r) for r in fonds.values()),
        "fonds": [
            {
                "fonds_code": code,
                "key": f"neogranadina/descriptions-{code}.json",
                "record_count": len(records),
            }
            for code, records in fonds.items()
        ],
    })
    for name in ["entities", "places", "repositories", "entity_links", "place_links"]:
        write(directory, f"{name}.json", [{"name": name}])
    return fonds


def run(fetch_export, source, out):
    return fetch_export.main(["--source-dir", str(source), "--output-dir", str(out)])


def test_concatenation_keeps_records_and_order(fetch_export, tmp_path, capsys):
    src, out = tmp_path / "src", tmp_path / "out"
    src.mkdir()
    fonds = make_layout(src)
    assert run(fetch_export, src, out) == 0
    combined = json.loads((out / "descriptions.json").read_text(encoding="utf-8"))
    assert combined == fonds["co-aaa"] + fonds["co-bbb"]
    for name in ["entities", "places", "repositories", "entity_links", "place_links"]:
        assert json.loads((out / f"{name}.json").read_text()) == [{"name": name}]
    printed = capsys.readouterr().out
    assert "descriptions.json records=3 fonds_files=2" in printed
    assert "entities.json records=1" in printed


def test_missing_listed_file_fails(fetch_export, tmp_path, capsys):
    src, out = tmp_path / "src", tmp_path / "out"
    src.mkdir()
    make_layout(src)
    (src / "descriptions-co-bbb.json").unlink()
    assert run(fetch_export, src, out) == 1
    assert "missing file" in capsys.readouterr().err


def test_missing_single_file_fails(fetch_export, tmp_path, capsys):
    src, out = tmp_path / "src", tmp_path / "out"
    src.mkdir()
    make_layout(src)
    (src / "places.json").unlink()
    assert run(fetch_export, src, out) == 1
    assert "places.json" in capsys.readouterr().err


def test_duplicate_id_across_fonds_fails(fetch_export, tmp_path, capsys):
    src, out = tmp_path / "src", tmp_path / "out"
    src.mkdir()
    make_layout(src, {
        "co-aaa": [{"id": "dup", "reference_code": "a"}],
        "co-bbb": [{"id": "dup", "reference_code": "b"}],
    })
    assert run(fetch_export, src, out) == 1
    assert "duplicate description id" in capsys.readouterr().err


def test_non_array_fonds_file_fails(fetch_export, tmp_path, capsys):
    src, out = tmp_path / "src", tmp_path / "out"
    src.mkdir()
    make_layout(src)
    write(src, "descriptions-co-aaa.json", {"id": "u1"})
    assert run(fetch_export, src, out) == 1
    assert "not a JSON array" in capsys.readouterr().err


def test_non_array_single_file_fails(fetch_export, tmp_path, capsys):
    src, out = tmp_path / "src", tmp_path / "out"
    src.mkdir()
    make_layout(src)
    write(src, "entities.json", {"entities": []})
    assert run(fetch_export, src, out) == 1
    assert "not a JSON array" in capsys.readouterr().err


def test_record_count_mismatch_fails(fetch_export, tmp_path, capsys):
    src, out = tmp_path / "src", tmp_path / "out"
    src.mkdir()
    make_layout(src)
    write(src, "descriptions-co-bbb.json", [])
    assert run(fetch_export, src, out) == 1
    assert "index lists" in capsys.readouterr().err


PUBLISHER = {"legal_name": {"es": "Fundación", "en": "Foundation"}, "credits": []}
VOCABULARY = {"entity_types": [], "authority_sources": []}


def test_optional_files_copied_when_present(fetch_export, tmp_path, capsys):
    src, out = tmp_path / "src", tmp_path / "out"
    src.mkdir()
    make_layout(src)
    write(src, "publisher.json", PUBLISHER)
    write(src, "vocabulary.json", VOCABULARY)
    assert run(fetch_export, src, out) == 0
    assert json.loads((out / "publisher.json").read_text(encoding="utf-8")) == PUBLISHER
    assert json.loads((out / "vocabulary.json").read_text(encoding="utf-8")) == VOCABULARY
    printed = capsys.readouterr().out
    assert "publisher.json fields=2" in printed
    assert "vocabulary.json fields=2" in printed


def test_optional_files_absent_removes_stale_copy(fetch_export, tmp_path, capsys):
    src, out = tmp_path / "src", tmp_path / "out"
    src.mkdir()
    out.mkdir()
    make_layout(src)
    write(out, "publisher.json", PUBLISHER)
    assert run(fetch_export, src, out) == 0
    assert not (out / "publisher.json").exists()
    assert not (out / "vocabulary.json").exists()
    printed = capsys.readouterr().out
    assert "publisher.json absent" in printed
    assert "vocabulary.json absent" in printed


def test_optional_file_that_is_not_an_object_fails(fetch_export, tmp_path, capsys):
    src, out = tmp_path / "src", tmp_path / "out"
    src.mkdir()
    make_layout(src)
    write(src, "vocabulary.json", [VOCABULARY])
    assert run(fetch_export, src, out) == 1
    assert "not a JSON object" in capsys.readouterr().err


@mock_aws
def test_r2_missing_optional_key_counts_as_absent(fetch_export, tmp_path, capsys):
    src, out = tmp_path / "src", tmp_path / "out"
    src.mkdir()
    make_layout(src)
    write(src, "publisher.json", PUBLISHER)
    client = boto3.client("s3", region_name="us-east-1")
    client.create_bucket(Bucket="zasqua-export")
    for path in src.iterdir():
        client.put_object(
            Bucket="zasqua-export", Key=f"neogranadina/{path.name}", Body=path.read_bytes()
        )
    source = fetch_export.R2Source("zasqua-export", None, "test", "test")
    source.client = client
    fetch_export.fetch_descriptions(source, "neogranadina", out)
    fetch_export.fetch_optional_files(source, "neogranadina", out)
    assert json.loads((out / "publisher.json").read_text(encoding="utf-8")) == PUBLISHER
    assert not (out / "vocabulary.json").exists()
    assert "vocabulary.json absent" in capsys.readouterr().out


# Version: v1.3.0
