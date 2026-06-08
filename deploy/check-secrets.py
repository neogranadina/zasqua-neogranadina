#!/usr/bin/env python3
"""
Secrets preflight — verify the deploy credentials without a build or deploy.

The deploy workflow (deploy.yml) needs seven repository secrets: two for
Backblaze B2 (the data fetch), three for Cloudflare R2 (the upload), and
two for Cloudflare (the cache purge). A wrong or missing value only
surfaces partway through a ~30-minute full build, so this script probes
each credential set with a cheap, read-only call and reports PASS/FAIL
per check up front. It is meant to be run by check-secrets.yml on demand,
as a gate before a real deploy.

It never prints a secret value — only whether each credential works and a
short, non-sensitive detail (a bucket reached, a zone name). It exits
non-zero if any check fails, so CI marks the run red.

The values come from the environment, injected by the workflow from the
repository secrets:

  B2_APPLICATION_KEY_ID / B2_APPLICATION_KEY
      -> authorize against B2 (validates the key pair)
  R2_ACCESS_KEY_ID / R2_SECRET_ACCESS_KEY / CLOUDFLARE_ACCOUNT_ID
      -> list, then write and delete a transient test key on zasqua-staging
  CF_API_TOKEN / CF_ZONE_ID
      -> verify the token is active, can read the zasqua.org zone, and
         holds the Cache Purge permission (a single-URL purge of a path
         the site never serves — exercises the permission, no-ops the cache)

Version: v1.1.1
"""

import os
import sys
import json
import urllib.request
import urllib.error

results = []  # list of (name, ok, detail)


def need(*keys):
    """Return the requested env values, raising if any is absent."""
    out = []
    for k in keys:
        v = os.environ.get(k)
        if not v:
            raise RuntimeError(f"missing env {k}")
        out.append(v)
    return out


def check(name, fn):
    try:
        results.append((name, True, fn()))
    except Exception as e:  # report, never raise — one failure must not hide the rest
        results.append((name, False, str(e)[:200]))


def b2_check():
    kid, key = need("B2_APPLICATION_KEY_ID", "B2_APPLICATION_KEY")
    from b2sdk.v2 import InMemoryAccountInfo, B2Api
    api = B2Api(InMemoryAccountInfo())
    api.authorize_account("production", kid, key)  # raises on bad credentials
    return "authorized"


def r2_check():
    akid, sak, acct = need("R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "CLOUDFLARE_ACCOUNT_ID")
    import boto3
    s3 = boto3.client(
        "s3",
        endpoint_url=f"https://{acct}.r2.cloudflarestorage.com",
        aws_access_key_id=akid,
        aws_secret_access_key=sak,
        region_name="auto",
    )
    s3.list_objects_v2(Bucket="zasqua-staging", MaxKeys=1)
    # Write-probe: confirm PUT + DELETE, not just read — a deploy writes.
    # The test key is transient (deleted immediately) and sits under a
    # __preflight__/ prefix the Worker never serves.
    probe_key = "__preflight__/write-check.txt"
    s3.put_object(Bucket="zasqua-staging", Key=probe_key, Body=b"zasqua secrets preflight")
    s3.delete_object(Bucket="zasqua-staging", Key=probe_key)
    return "list + write + delete OK on zasqua-staging"


def _cf_get(path, token):
    req = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4{path}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.load(resp)
    if not data.get("success"):
        raise RuntimeError(f"API said success=false: {data.get('errors')}")
    return data["result"]


def _cf_post(path, token, payload):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4{path}",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    # urlopen raises HTTPError on 4xx/5xx; catch it so a 401/403 (the exact
    # permission-gap symptom) is reported as a FAIL detail, not a traceback.
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.load(resp)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:200]
        raise RuntimeError(f"HTTP {e.code}: {detail}")
    if not data.get("success"):
        raise RuntimeError(f"API said success=false: {data.get('errors')}")
    return data["result"]


def cf_token_check():
    (token,) = need("CF_API_TOKEN")
    result = _cf_get("/user/tokens/verify", token)
    return f"token {result.get('status', '?')}"


def cf_zone_check():
    token, zone = need("CF_API_TOKEN", "CF_ZONE_ID")
    result = _cf_get(f"/zones/{zone}", token)
    return f"zone {result.get('name', '?')}"


def cf_purge_check():
    # Token verify + zone read pass with only Zone.Read, but the deploy's
    # cache purge needs the separate Cache Purge permission. Probe it with a
    # single-URL purge of a path the Worker never serves: it returns success
    # only if the permission is present, and purging a non-existent URL is a
    # no-op on the live cache.
    token, zone = need("CF_API_TOKEN", "CF_ZONE_ID")
    _cf_post(
        f"/zones/{zone}/purge_cache",
        token,
        {"files": ["https://zasqua.org/__preflight__/cache-check"]},
    )
    return "purge permission OK"


check("B2 (fetch)", b2_check)
check("R2 (upload)", r2_check)
check("Cloudflare token", cf_token_check)
check("Cloudflare zone", cf_zone_check)
check("Cloudflare purge", cf_purge_check)

print("\nSecrets preflight")
print("=================")
ok_all = True
for name, ok, detail in results:
    print(f"  [{'PASS' if ok else 'FAIL'}] {name} — {detail}")
    ok_all = ok_all and ok
print()
print("all checks passed" if ok_all else "one or more checks FAILED")
sys.exit(0 if ok_all else 1)

# Version: v1.1.1 (added Cloudflare purge-permission probe)
