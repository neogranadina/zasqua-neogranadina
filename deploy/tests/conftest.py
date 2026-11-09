#!/usr/bin/env python3
"""
Pytest Fixtures for upload-to-b2 Unit Tests

This module wires the test suite for `deploy/upload-to-b2.py`
into pytest. The script file name contains a hyphen so Python cannot
import it with the usual `import upload_to_b2` syntax —
`importlib.util.spec_from_file_location` loads it as a module anyway,
and the `upload_to_b2` session-scoped fixture exposes that module to
every test file.

The moto library is used in place of a live R2 or MinIO endpoint:
`mock_aws` intercepts the boto3 HTTP calls and replays the S3 API in
process. Each test gets a fresh mock via the function-scoped
`s3_client` fixture, and the `src_bucket` / `dst_bucket` fixtures
provision the empty buckets used by copy-mode and pagination tests.

Mocked endpoints mean these tests never touch real R2 credentials,
never hit the network, and run in milliseconds — exactly what this
test suite needs. The diff, safety-cap, multipart-ETag, and copy-mode
paths are all verified without side effects.

The `build_redirects` fixture does the same for `deploy/build-redirects.py`,
which needs no mocks: its tests write small export files to `tmp_path`.

Version: v1.3.0
"""

import importlib.util
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1] / "upload-to-b2.py"
)


REDIRECTS_PATH = (
    Path(__file__).resolve().parents[1] / "build-redirects.py"
)


@pytest.fixture(scope="session")
def upload_to_b2():
    """Load deploy/upload-to-b2.py as a module so tests can call its
    helpers directly. The `if __name__ == "__main__": main()` guard at the
    bottom of the file means importing never triggers a real upload."""
    spec = importlib.util.spec_from_file_location(
        "upload_to_b2", SCRIPT_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def s3_client():
    """Return a boto3 S3 client wired to a moto mock that lives for the
    duration of a single test. Region is pinned to us-east-1 because moto
    defaults to it and the production region (R2 "auto") is not a valid
    moto value."""
    with mock_aws():
        client = boto3.client("s3", region_name="us-east-1")
        yield client


@pytest.fixture
def src_bucket(s3_client):
    """Create an empty source bucket inside the active moto mock."""
    s3_client.create_bucket(Bucket="zasqua-staging-test")
    return "zasqua-staging-test"


@pytest.fixture
def dst_bucket(s3_client):
    """Create an empty destination bucket inside the active moto mock."""
    s3_client.create_bucket(Bucket="zasqua-site-test")
    return "zasqua-site-test"


@pytest.fixture(scope="session")
def build_redirects():
    """Load deploy/build-redirects.py as a module (hyphenated file name)."""
    spec = importlib.util.spec_from_file_location(
        "build_redirects", REDIRECTS_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


FETCH_EXPORT_PATH = (
    Path(__file__).resolve().parents[1] / "fetch-export-r2.py"
)


@pytest.fixture(scope="session")
def fetch_export():
    """Load deploy/fetch-export-r2.py as a module (hyphenated file name)."""
    spec = importlib.util.spec_from_file_location(
        "fetch_export", FETCH_EXPORT_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
