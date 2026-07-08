#!/usr/bin/env python3
"""
Unit Tests for the Backblaze B2 Endpoint Swap in upload-to-b2.py

The R2 -> B2 storage transition moves the instance's serving buckets from
Cloudflare R2 to Backblaze B2. Because `upload-to-b2.py` talks to an
S3-compatible API through boto3, the swap is meant to be a pure
endpoint/credentials/region change with no logic change — these tests pin
that contract.

Three things are checked here:

  1. `resolve_s3_config()` — the generic `S3_*` variables win over the
     `R2_*` back-compat aliases, the aliases still work when the generic
     names are absent, and the signing region defaults to "auto" (R2's
     value) but can be overridden for B2.
  2. `_build_s3_client()` actually threads the region into the boto3
     client. This matters because B2 signs against the real region in its
     endpoint hostname (e.g. us-west-004); if the region did not reach the
     client, every B2 request would fail its signature.
  3. Content-Type AND Cache-Control survive a round-trip through an upload.
     The transition must not silently drop the per-extension headers the
     serving Worker relies on, so we upload via `upload_file` and read the
     stored metadata back.

What these tests deliberately do NOT cover: moto mocks the S3 API in
process and does not verify SigV4 signatures, so it cannot prove that B2
accepts a request signed for `us-west-004` or rejects one signed for
"auto". That is a live-credential behaviour, checked by the one-off B2
dry-run smoke test in the transition runbook, not here.

Run:
    pytest deploy/tests/ -v

Version: v1.0.0
"""

import boto3


# ---------------------------------------------------------------------------
# resolve_s3_config() — env precedence and region handling
# ---------------------------------------------------------------------------

def test_generic_s3_vars_win_over_r2_aliases(upload_to_b2, monkeypatch):
    monkeypatch.setenv("S3_ENDPOINT", "https://s3.us-west-004.backblazeb2.com")
    monkeypatch.setenv("S3_ACCESS_KEY_ID", "b2-key")
    monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "b2-secret")
    monkeypatch.setenv("S3_REGION", "us-west-004")
    # R2 aliases also set — the generic names must take precedence.
    monkeypatch.setenv("R2_ENDPOINT", "https://acct.r2.cloudflarestorage.com")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "r2-key")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "r2-secret")
    monkeypatch.setenv("R2_REGION", "auto")

    endpoint, access_key, secret_key, region = upload_to_b2.resolve_s3_config()
    assert endpoint == "https://s3.us-west-004.backblazeb2.com"
    assert access_key == "b2-key"
    assert secret_key == "b2-secret"
    assert region == "us-west-004"


def test_r2_aliases_used_when_generic_absent(upload_to_b2, monkeypatch):
    for var in ("S3_ENDPOINT", "S3_ACCESS_KEY_ID",
                "S3_SECRET_ACCESS_KEY", "S3_REGION"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("R2_ENDPOINT", "https://acct.r2.cloudflarestorage.com")
    monkeypatch.setenv("R2_ACCESS_KEY_ID", "r2-key")
    monkeypatch.setenv("R2_SECRET_ACCESS_KEY", "r2-secret")

    endpoint, access_key, secret_key, region = upload_to_b2.resolve_s3_config()
    assert endpoint == "https://acct.r2.cloudflarestorage.com"
    assert access_key == "r2-key"
    assert secret_key == "r2-secret"
    # No region set anywhere -> the R2-safe default.
    assert region == "auto"


def test_region_defaults_to_auto_for_r2(upload_to_b2, monkeypatch):
    for var in ("S3_REGION", "R2_REGION"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("S3_ENDPOINT", "https://acct.r2.cloudflarestorage.com")
    monkeypatch.setenv("S3_ACCESS_KEY_ID", "k")
    monkeypatch.setenv("S3_SECRET_ACCESS_KEY", "s")

    _, _, _, region = upload_to_b2.resolve_s3_config()
    assert region == "auto"


def test_missing_credentials_resolve_to_none(upload_to_b2, monkeypatch):
    for var in ("S3_ENDPOINT", "S3_ACCESS_KEY_ID", "S3_SECRET_ACCESS_KEY",
                "S3_REGION", "R2_ENDPOINT", "R2_ACCESS_KEY_ID",
                "R2_SECRET_ACCESS_KEY", "R2_REGION"):
        monkeypatch.delenv(var, raising=False)

    endpoint, access_key, secret_key, region = upload_to_b2.resolve_s3_config()
    assert endpoint is None
    assert access_key is None
    assert secret_key is None
    # Region always resolves to a usable default even with no creds.
    assert region == "auto"


# ---------------------------------------------------------------------------
# _build_s3_client() — region actually reaches the client
# ---------------------------------------------------------------------------

def test_region_threads_into_client(upload_to_b2):
    client = upload_to_b2._build_s3_client(
        endpoint="https://s3.us-west-004.backblazeb2.com",
        access_key="k",
        secret_key="s",
        concurrency=10,
        region="us-west-004",
    )
    assert client.meta.region_name == "us-west-004"


def test_client_region_defaults_to_auto(upload_to_b2):
    client = upload_to_b2._build_s3_client(
        endpoint="https://acct.r2.cloudflarestorage.com",
        access_key="k",
        secret_key="s",
        concurrency=10,
    )
    assert client.meta.region_name == "auto"


# ---------------------------------------------------------------------------
# Content-Type + Cache-Control round-trip through an upload
# ---------------------------------------------------------------------------

def test_upload_sets_content_type_and_cache_control(
        upload_to_b2, s3_client, src_bucket, tmp_path):
    """The whole point of the per-extension header logic is that the object
    lands in the bucket carrying the right Content-Type and Cache-Control.
    Upload one file of each interesting class and read the stored metadata
    back, so the B2 swap cannot silently regress it."""
    cases = {
        "index.html": (
            "text/html; charset=utf-8",
            upload_to_b2.CACHE_CONTROL["short"],
        ),
        "data.json": (
            "application/json; charset=utf-8",
            upload_to_b2.CACHE_CONTROL["medium"],
        ),
        "app.js": (
            "application/javascript; charset=utf-8",
            upload_to_b2.CACHE_CONTROL["long"],
        ),
        "es_283012b.pf_filter": (
            "application/octet-stream",
            upload_to_b2.CACHE_CONTROL["immutable"],
        ),
    }
    for key in cases:
        local = tmp_path / key
        local.write_text("x")
        upload_to_b2.upload_file(s3_client, src_bucket, str(local), key)

    for key, (want_type, want_cache) in cases.items():
        head = s3_client.head_object(Bucket=src_bucket, Key=key)
        assert head["ContentType"] == want_type, key
        assert head["CacheControl"] == want_cache, key


# ---------------------------------------------------------------------------
# Bucket allowlist under the mirror-names decision
# ---------------------------------------------------------------------------

def test_mirrored_bucket_names_pass_the_allowlist(upload_to_b2):
    """The transition mirrors the R2 bucket names onto B2 (zasqua-staging,
    zasqua-site), so the physical store is chosen by endpoint + credentials,
    not by name. That means the existing name-based allowlist needs no B2
    change — the same names remain valid in delete-sync mode on either
    store."""
    assert upload_to_b2.bucket_allowed("zasqua-staging", no_delete=False)
    assert upload_to_b2.bucket_allowed("zasqua-site", no_delete=False)
