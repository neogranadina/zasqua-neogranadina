"""
Tests for the Redirect Table Builder

These tests exercise `deploy/build-redirects.py` against small export files
written to a temporary directory: no network and no mocks. They cover the
happy path (one retired code per file, including a description code with
`?` and an en dash), the empty case, and each rule that makes the script
stop — a former code that equals a live code, one claimed by two records,
one containing a slash, and a former-codes field of the wrong type — plus
a missing export file.

Version: v1.3.0
"""

import json

import pytest


def write(directory, name, records):
    (directory / name).write_text(json.dumps(records), encoding="utf-8")


def run(build_redirects, directory, capsys):
    out = directory / "out.json"
    build_redirects.main(["build-redirects.py", str(directory), str(out)])
    return json.loads(out.read_text(encoding="utf-8")), capsys.readouterr().out


def full_exports(tmp_path):
    write(tmp_path, "entities.json", [
        {"entity_code": "ne-aaszvt", "former_codes": ["ne-u3ufz"]},
        {"entity_code": "ne-bbbbbb"},
    ])
    write(tmp_path, "places.json", [
        {"place_code": "nl-s9z5px", "former_codes": ["nl-mab94"]},
    ])
    write(tmp_path, "descriptions.json", [
        {
            "reference_code": "co-cihjml-acc-09188-civil-i-nt-1",
            "former_reference_codes": ["co-cihjml-acc-09188-civil-i-nt?–(1)"],
        },
        {"reference_code": "co-x", "former_reference_codes": []},
    ])


def test_three_files_one_former_code_each(build_redirects, tmp_path, capsys):
    full_exports(tmp_path)
    table, out = run(build_redirects, tmp_path, capsys)
    assert table == [
        {"key": "/ne-u3ufz/", "value": "/ne-aaszvt/"},
        {"key": "/nl-mab94/", "value": "/nl-s9z5px/"},
        {
            "key": "/co-cihjml-acc-09188-civil-i-nt?–(1)/",
            "value": "/co-cihjml-acc-09188-civil-i-nt-1/",
        },
    ]
    assert out.strip() == "redirects built=3 entities=1 places=1 descriptions=1"


def test_no_former_fields_gives_empty_table(build_redirects, tmp_path, capsys):
    write(tmp_path, "entities.json", [{"entity_code": "ne-aaszvt"}])
    write(tmp_path, "places.json", [{"place_code": "nl-s9z5px"}])
    write(tmp_path, "descriptions.json", [{"reference_code": "co-x"}])
    table, out = run(build_redirects, tmp_path, capsys)
    assert table == []
    assert out.strip() == "redirects built=0 entities=0 places=0 descriptions=0"


def test_former_code_equal_to_live_code(build_redirects, tmp_path, capsys):
    write(tmp_path, "entities.json", [
        {"entity_code": "ne-aaaaaa", "former_codes": ["nl-s9z5px"]},
    ])
    write(tmp_path, "places.json", [{"place_code": "nl-s9z5px"}])
    with pytest.raises(SystemExit) as exc:
        run(build_redirects, tmp_path, capsys)
    assert exc.value.code == 1
    assert "nl-s9z5px" in capsys.readouterr().err


def test_same_former_code_on_two_records(build_redirects, tmp_path, capsys):
    write(tmp_path, "entities.json", [
        {"entity_code": "ne-aaaaaa", "former_codes": ["ne-old01"]},
        {"entity_code": "ne-bbbbbb", "former_codes": ["ne-old01"]},
    ])
    with pytest.raises(SystemExit) as exc:
        run(build_redirects, tmp_path, capsys)
    assert exc.value.code == 1
    err = capsys.readouterr().err
    assert "ne-aaaaaa" in err and "ne-bbbbbb" in err


def test_former_code_with_slash(build_redirects, tmp_path, capsys):
    write(tmp_path, "entities.json", [
        {"entity_code": "ne-aaaaaa", "former_codes": ["ne/old"]},
    ])
    with pytest.raises(SystemExit) as exc:
        run(build_redirects, tmp_path, capsys)
    assert exc.value.code == 1
    assert "ne/old" in capsys.readouterr().err


def test_former_codes_not_an_array(build_redirects, tmp_path, capsys):
    write(tmp_path, "places.json", [
        {"place_code": "nl-s9z5px", "former_codes": "nl-mab94"},
    ])
    with pytest.raises(SystemExit) as exc:
        run(build_redirects, tmp_path, capsys)
    assert exc.value.code == 1
    assert "nl-s9z5px" in capsys.readouterr().err


def test_missing_places_file_still_builds(build_redirects, tmp_path, capsys):
    full_exports(tmp_path)
    (tmp_path / "places.json").unlink()
    table, out = run(build_redirects, tmp_path, capsys)
    assert len(table) == 2
    assert out.strip() == "redirects built=2 entities=1 places=0 descriptions=1"


def test_all_files_missing_is_an_error(build_redirects, tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        run(build_redirects, tmp_path, capsys)
    assert exc.value.code == 1


# Version: v1.3.0
