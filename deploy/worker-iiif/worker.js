/**
 * @file worker-iiif/worker.js
 * @description Cloudflare Worker serving iiif.zasqua.org — the IIIF Image
 *   API tile store (manifests reference these tiles as `service` endpoints;
 *   viewers like TIFY fetch `info.json` and `.../full/max/0/default.jpg`
 *   directly from this host).
 *
 *   Storage origin — the R2 -> B2 transition (2026-07): this Worker reads
 *   tiles from either of two origins, chosen per deployment by an
 *   environment variable, with no build step and no code fork:
 *     * R2 binding (default) — when SITE_ORIGIN is unset, tiles are read
 *       from the bound R2 bucket (env.SITE, `zasqua-iiif-tiles`). This is
 *       the path today, and stays the default until the migration
 *       (see zasqua-preservation/scripts/iiif-r2-b2/) is verified complete.
 *     * B2 HTTP origin — when SITE_ORIGIN is set to a public Backblaze B2
 *       download base URL, the Worker fetches tiles over HTTP from B2
 *       instead. Rollback from B2 to R2 is a config-only change: drop
 *       SITE_ORIGIN and redeploy — the R2 binding takes over again, no
 *       code path changes.
 *
 *   This Worker is deliberately thinner than the site Worker it is adapted
 *   from (`deploy/worker/worker.js`): it carries none of the site's
 *   pretty-URL resolution, STAGING/robots handling, or 404.html rewrite — a
 *   missing tile is a plain 404, and IIIF paths are never directories. It
 *   adds one thing the site Worker does not need: every response gets
 *   `access-control-allow-origin: *`, because IIIF viewers (TIFY, Mirador,
 *   OpenSeadragon) fetch tiles and info.json cross-origin from whatever
 *   host renders the manifest. Tiles are written immutable at tiling time,
 *   so the object's own `cache-control` is passed through unchanged rather
 *   than recomputed here.
 *
 *   Key encoding follows the site Worker exactly: R2 bindings look objects
 *   up by their raw, decoded UTF-8 key; a B2 HTTP origin needs that key
 *   percent-encoded back into a URL path, encoding each segment while
 *   preserving the slashes. See encodeKey().
 *
 * @version v1.1.0
 */

export default {
  async fetch(request, env) {
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      return iiifHeaders(new Response('Method Not Allowed', { status: 405 }));
    }

    const url = new URL(request.url);

    // R2 stores keys as raw UTF-8 bytes; Workers expose url.pathname
    // percent-encoded, so decode once up front (mirrors the site Worker —
    // see its comment for the malformed-escape fallback rationale).
    let decodedPathname;
    try {
      decodedPathname = decodeURIComponent(url.pathname);
    } catch (_) {
      decodedPathname = url.pathname;
    }

    // Strip leading slash for the object key. No pretty-URL/index.html
    // resolution here — every IIIF path (info.json, tile paths) is a
    // fully-qualified object key, never a directory.
    const key = decodedPathname.slice(1);

    // Check edge cache first
    const cache = caches.default;
    const cacheKey = new Request(url.toString(), request);
    let response = await cache.match(cacheKey);
    if (response) return iiifHeaders(response);

    // Fetch the object from whichever origin this deployment is wired to:
    // a public B2 HTTP origin when SITE_ORIGIN is set, otherwise the bound
    // R2 bucket.
    if (env.SITE_ORIGIN) {
      response = await serveFromOrigin(env.SITE_ORIGIN, key);
    } else {
      response = await serveFromBinding(env.SITE, key);
    }

    // Store successful hits in the edge cache (non-blocking). 404s are not
    // cached.
    if (request.method === 'GET' && response.status === 200) {
      cache.put(cacheKey, response.clone());
    }

    return iiifHeaders(response);
  },
};

// Re-encode a decoded object key for use in an origin URL path. Encodes
// each path segment while preserving the slashes that separate them. Copied
// verbatim from the site Worker (deploy/worker/worker.js) — this is the
// exact inverse of the decodeURIComponent(url.pathname) applied above.
function encodeKey(key) {
  return key.split('/').map(encodeURIComponent).join('/');
}

// Join a public origin base URL (e.g. a B2 download URL like
// `https://f001.backblazeb2.com/file/zasqua-iiif-tiles`, no trailing slash
// required) to an encoded object key. Copied verbatim from the site Worker.
function originUrl(origin, key) {
  return origin.replace(/\/$/, '') + '/' + encodeKey(key);
}

// Serve a tile object from the bound R2 bucket (the default path). A
// missing tile is a plain 404 — no 404.html rewrite, unlike the site
// Worker, because there is no HTML fallback page for a IIIF tile store.
async function serveFromBinding(bucket, key) {
  const object = await bucket.get(key);
  if (!object) {
    return new Response('Not Found', { status: 404 });
  }

  const headers = new Headers();
  headers.set('content-type', object.httpMetadata?.contentType || contentType(key));
  headers.set('cache-control', object.httpMetadata?.cacheControl || 'public, max-age=31536000, immutable');
  headers.set('etag', object.httpEtag);
  return new Response(object.body, { headers });
}

// Origin-fetch resilience (B2 path): B2 can throttle (429) or blip (5xx),
// especially while other jobs are loading the same B2 account. Retry a few
// times with short backoff so a transient upstream failure never surfaces to
// a IIIF viewer as a spurious 404.
const ORIGIN_MAX_ATTEMPTS = 3;
const ORIGIN_BACKOFF_MS = [150, 400]; // waits before attempts 2 and 3

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// Serve a tile object from a public B2 HTTP origin (the post-migration path).
// Mirrors serveFromBinding's contract — a genuinely missing object is a 404 —
// but a transient upstream failure (429 throttle, 5xx, or network error) is
// retried with short backoff and, if it never recovers, surfaced as 503
// rather than 404. Returning 404 for a throttle blip would tell viewers a
// tile that exists is missing; 503 tells them to retry. Only 200s are
// edge-cached by the caller, so neither 404 nor 503 is ever cached.
async function serveFromOrigin(origin, key) {
  const target = originUrl(origin, key);
  let originResp = null;

  for (let attempt = 0; attempt < ORIGIN_MAX_ATTEMPTS; attempt++) {
    if (attempt > 0) await sleep(ORIGIN_BACKOFF_MS[attempt - 1]);
    try {
      originResp = await fetch(target);
    } catch (_) {
      originResp = null; // network error — transient, retry
      continue;
    }
    if (originResp.status === 200) break;
    if (originResp.status === 404) return new Response('Not Found', { status: 404 });
    if (originResp.status === 429 || originResp.status >= 500) continue; // transient — retry
    return new Response('Bad Gateway', { status: 502 }); // unexpected, not a plain miss
  }

  if (!originResp || originResp.status !== 200) {
    return new Response('Origin Unavailable', { status: 503, headers: { 'retry-after': '2' } });
  }

  const headers = new Headers();
  headers.set('content-type', originResp.headers.get('content-type') || contentType(key));
  headers.set('cache-control', originResp.headers.get('cache-control') || 'public, max-age=31536000, immutable');
  const etag = originResp.headers.get('etag');
  if (etag) headers.set('etag', etag);
  return new Response(originResp.body, { headers });
}

// Every response gets permissive CORS (IIIF viewers fetch cross-origin) and
// passes the object's own Cache-Control through unchanged (tiles are written
// immutable at tiling time). Content-Type comes from the origin/binding.
function iiifHeaders(resp) {
  const h = new Headers(resp.headers);
  h.set('access-control-allow-origin', '*');
  return new Response(resp.body, { status: resp.status, headers: h });
}

// Fallback content-type inference for the rare object stored without its
// own httpMetadata.contentType (e.g. objects written by a tool that did not
// set it). IIIF Level 0 tile stores are almost entirely info.json + .jpg.
function contentType(key) {
  const ext = key.split('.').pop().toLowerCase();
  if (ext === 'json') return 'application/json; charset=utf-8';
  if (ext === 'jpg' || ext === 'jpeg') return 'image/jpeg';
  return 'application/octet-stream';
}

// Version: v1.1.0
