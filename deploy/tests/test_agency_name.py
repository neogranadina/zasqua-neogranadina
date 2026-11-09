"""
Tests for the EAC-CPF Agency Name Lookup

These tests run `deploy/agency-name.py` against small export directories and
hugo.toml files. They check the engine's order: the publisher's legal_name
wins, `eac_agency_name` is used when there is no publisher file or the
legal name is empty, and the result is empty when there is neither, which
the deploy treats as a failure.

Version: v1.3.0
"""

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "agency-name.py"


@pytest.fixture(scope="module")
def agency():
    spec = importlib.util.spec_from_file_location("agency_name", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.agency_name


def setup(tmp_path, publisher=None, toml_agency=None):
    exports = tmp_path / "exports"
    exports.mkdir()
    if publisher is not None:
        (exports / "publisher.json").write_text(json.dumps(publisher), encoding="utf-8")
    toml = tmp_path / "hugo.toml"
    line = f'  eac_agency_name = "{toml_agency}"\n' if toml_agency is not None else ""
    toml.write_text('title = "Zasqua"\n[params]\n' + line, encoding="utf-8")
    return exports, toml


def test_legal_name_wins(agency, tmp_path):
    exports, toml = setup(tmp_path, {"legal_name": " Fundación A "}, "Fundación B")
    assert agency(exports, toml) == "Fundación A"


def test_hugo_toml_without_publisher_file(agency, tmp_path):
    exports, toml = setup(tmp_path, None, "Fundación B")
    assert agency(exports, toml) == "Fundación B"


def test_hugo_toml_when_legal_name_empty(agency, tmp_path):
    exports, toml = setup(tmp_path, {"legal_name": "  "}, "Fundación B")
    assert agency(exports, toml) == "Fundación B"


def test_empty_when_neither(agency, tmp_path):
    exports, toml = setup(tmp_path, {"legal_name": None}, None)
    assert agency(exports, toml) == ""


# Version: v1.3.0
