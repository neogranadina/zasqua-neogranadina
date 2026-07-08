#!/usr/bin/env python3
"""
Tests for the additive prefix-upload mode (--prefix / --no-delete) and the
mode-aware bucket allowlist added for the METS → zasqua-manifests path.

These cover the safety-critical claims:
  - the delete-sync mode can NEVER target the shared manifests bucket;
  - the additive mode can ONLY target it, and cannot delete;
  - a prefix-scoped LIST never enumerates sibling prefixes (so the /iiif/
    corpus is invisible to a mets/ upload's diff);
  - collect_files prepends the key prefix.

Version: v1.0.0
"""

import pytest


# ---------------------------------------------------------------------------
# Bucket allowlist guard
# ---------------------------------------------------------------------------

def test_delete_mode_allows_site_buckets(upload_to_b2):
    assert upload_to_b2.bucket_allowed("zasqua-site", no_delete=False)
    assert upload_to_b2.bucket_allowed("zasqua-staging", no_delete=False)


def test_delete_mode_refuses_manifests_bucket(upload_to_b2):
    # The whole point: delete-sync can never be aimed at zasqua-manifests,
    # so a mistyped target_bucket + --confirm-deletes cannot wipe /iiif/.
    assert not upload_to_b2.bucket_allowed("zasqua-manifests", no_delete=False)


def test_additive_mode_allows_only_manifests(upload_to_b2):
    assert upload_to_b2.bucket_allowed("zasqua-manifests", no_delete=True)
    assert not upload_to_b2.bucket_allowed("zasqua-site", no_delete=True)
    assert not upload_to_b2.bucket_allowed("zasqua-staging", no_delete=True)


def test_unknown_bucket_refused_in_both_modes(upload_to_b2):
    assert not upload_to_b2.bucket_allowed("some-other-bucket", no_delete=False)
    assert not upload_to_b2.bucket_allowed("some-other-bucket", no_delete=True)


# ---------------------------------------------------------------------------
# collect_files — key prefix
# ---------------------------------------------------------------------------

def test_collect_files_prepends_key_prefix(upload_to_b2, tmp_path):
    (tmp_path / "co-x.xml").write_text("<x/>")
    (tmp_path / "co-y.xml").write_text("<y/>")
    files = upload_to_b2.collect_files(str(tmp_path), key_prefix="mets/")
    keys = sorted(k for _, k in files)
    assert keys == ["mets/co-x.xml", "mets/co-y.xml"]


def test_collect_files_no_prefix_keeps_root_keys(upload_to_b2, tmp_path):
    (tmp_path / "index.html").write_text("<html/>")
    files = upload_to_b2.collect_files(str(tmp_path))
    assert [k for _, k in files] == ["index.html"]


# ---------------------------------------------------------------------------
# list_remote_etags — prefix scoping never sees sibling prefixes
# ---------------------------------------------------------------------------

def test_list_remote_etags_prefix_excludes_siblings(upload_to_b2, s3_client):
    s3_client.create_bucket(Bucket="zasqua-manifests")
    # A shared bucket holding both iiif/ and mets/ keys.
    s3_client.put_object(Bucket="zasqua-manifests", Key="iiif/a/manifest.json", Body=b"{}")
    s3_client.put_object(Bucket="zasqua-manifests", Key="iiif/b/manifest.json", Body=b"{}")
    s3_client.put_object(Bucket="zasqua-manifests", Key="mets/co-x.xml", Body=b"<x/>")
    s3_client.put_object(Bucket="zasqua-manifests", Key="mets/co-y.xml", Body=b"<y/>")

    scoped = upload_to_b2.list_remote_etags(s3_client, "zasqua-manifests", prefix="mets/")
    assert set(scoped.keys()) == {"mets/co-x.xml", "mets/co-y.xml"}
    # The iiif/ corpus is invisible to a mets/ upload.
    assert not any(k.startswith("iiif/") for k in scoped)

    # Sanity: an unscoped LIST does see everything (the dangerous default).
    full = upload_to_b2.list_remote_etags(s3_client, "zasqua-manifests")
    assert any(k.startswith("iiif/") for k in full)


# ---------------------------------------------------------------------------
# diff within a prefix — orphans are confined to the prefix
# ---------------------------------------------------------------------------

def test_diff_orphans_confined_to_prefix(upload_to_b2, s3_client):
    """A mets/ upload that omits one remote mets/ key reports exactly that key
    as an orphan, and never the iiif/ keys — because the LIST was prefix-scoped.
    With --no-delete the caller surfaces (does not delete) this set."""
    s3_client.create_bucket(Bucket="zasqua-manifests")
    s3_client.put_object(Bucket="zasqua-manifests", Key="iiif/a/manifest.json", Body=b"{}")
    s3_client.put_object(Bucket="zasqua-manifests", Key="mets/co-x.xml", Body=b"<x/>")
    s3_client.put_object(Bucket="zasqua-manifests", Key="mets/co-gone.xml", Body=b"<g/>")

    remote = upload_to_b2.list_remote_etags(s3_client, "zasqua-manifests", prefix="mets/")
    # Local tree (post key-prefix) has co-x but not co-gone.
    local = [("/tmp/co-x.xml", "mets/co-x.xml", "deadbeef" * 4)]
    _to_upload, _to_skip, to_delete = upload_to_b2.diff_files(local, remote)

    assert to_delete == ["mets/co-gone.xml"]
    assert not any(k.startswith("iiif/") for k in to_delete)
