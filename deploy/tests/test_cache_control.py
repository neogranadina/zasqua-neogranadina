#!/usr/bin/env python3
"""
Unit Tests for upload-to-b2.py cache_control()

Pins the per-extension Cache-Control tier, in particular the Pagefind
chunk extensions: `.pf_index`, `.pf_fragment`, `.pf_filter`, and
`.pf_meta` carry content-hashed filenames (e.g. `es_283012b.pf_filter`)
and get the immutable (1-year) tier, while `.pagefind` (the WASM
runtime, e.g. `wasm.es.pagefind`) ships under a fixed filename tied to
the Pagefind package version and gets the same 7-day tier as its
sibling .js/.css runtime files.

Run:
    pytest instance/deploy/tests/ -v

Version: v1.0.0
"""


def test_pagefind_data_chunks_are_immutable(upload_to_b2):
    immutable = upload_to_b2.CACHE_CONTROL["immutable"]
    assert upload_to_b2.cache_control("es_283012b.pf_filter") == immutable
    assert upload_to_b2.cache_control("es_00b28d5.pf_fragment") == immutable
    assert upload_to_b2.cache_control("es_0446d86.pf_index") == immutable
    assert upload_to_b2.cache_control("pagefind.es_13ac485552.pf_meta") == immutable


def test_pagefind_wasm_runtime_is_long_not_immutable(upload_to_b2):
    long_tier = upload_to_b2.CACHE_CONTROL["long"]
    assert upload_to_b2.cache_control("wasm.es.pagefind") == long_tier
    assert upload_to_b2.cache_control("wasm.unknown.pagefind") == long_tier


def test_pagefind_support_scripts_unaffected(upload_to_b2):
    long_tier = upload_to_b2.CACHE_CONTROL["long"]
    assert upload_to_b2.cache_control("pagefind.js") == long_tier
    assert upload_to_b2.cache_control("pagefind-worker.js") == long_tier


def test_unknown_extension_still_falls_back_to_short(upload_to_b2):
    assert upload_to_b2.cache_control("pagefind-entry.json") == upload_to_b2.CACHE_CONTROL["medium"]
    assert upload_to_b2.cache_control("robots.txt") == upload_to_b2.CACHE_CONTROL["short"]
