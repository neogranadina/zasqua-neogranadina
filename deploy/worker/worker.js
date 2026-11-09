/**
 * @file worker/worker.js
 * @description Cloudflare Worker serving zasqua.org (prod) and
 *   staging.zasqua.org (staging). Handles pretty-URL resolution, edge
 *   caching, and — on the staging deployment only (STAGING=true in
 *   wrangler.toml [env.staging].vars) — two crawler-deterrent mitigations:
 *     1. /robots.txt returns a blanket Disallow: / .
 *     2. Every response carries X-Robots-Tag: noindex, nofollow.
 *
 *   Storage origin — the R2 -> B2 transition (2026-07): this Worker can
 *   read the SITE from either of two origins, chosen per deployment by an
 *   environment variable, with no build step and no code fork:
 *     * R2 binding (default) — when SITE_ORIGIN is unset, the site is read
 *       from the bound R2 bucket (env.SITE). This is the production path today.
 *     * B2 HTTP origin — when SITE_ORIGIN is set to a public Backblaze B2
 *       download base URL, the Worker fetches site objects over HTTP from B2
 *       instead. This is how staging proves the B2 serving path before
 *       production cuts over.
 *   Because the mode is a variable, rollback from B2 to R2 is a config-only
 *   change: drop SITE_ORIGIN and redeploy — the R2 binding the environment
 *   still carries takes over again. The transition covers the site only.
 *
 *   The one subtlety the B2 path must respect is key encoding. R2 bindings
 *   look objects up by their raw, decoded UTF-8 key; a B2 HTTP origin needs
 *   that key percent-encoded back into a URL path (the exact inverse of the
 *   decodeURIComponent applied to url.pathname up front), encoding each
 *   path segment while preserving the slashes — otherwise every non-ASCII
 *   slug (e.g. `…eclesiástico…`) would 404 at the origin. See encodeKey().
 *
 *   Mitigation 2 (X-Robots-Tag) was added in v0.3.0 after the first staging
 *   deploy showed that Cloudflare's zone-level Managed Robots.txt feature
 *   prepends its own content-signal block (including User-agent: * Allow: /)
 *   before the Worker's Disallow. First-match REP parsers (Googlebot, per
 *   RFC 9309) would see the Allow and ignore the later Disallow. X-Robots-Tag
 *   on every response is the reliable belt-and-braces signal.
 *
 *   Retired addresses — entity, place and description pages whose codes
 *   have changed keep answering at their old `/<code>/` address. The
 *   exports record each retired code on the record itself, and the deploy
 *   workflow (via `deploy/build-redirects.py`) loads them into a KV
 *   namespace bound as REDIRECTS, keyed by the old path (`/ne-u3ufz/`) with
 *   the new path as the value. The Worker consults it only after the site
 *   origin has missed, and only for a single-segment path, so a request that
 *   hits the bucket never pays a KV read. A hit answers 301 to the new path,
 *   keeping the query string, with an empty body and a one-hour
 *   cache-control; it is not stored in the edge cache. Where REDIRECTS is
 *   not bound, or holds nothing, the 404 passes through unchanged.
 *
 *   Prod and staging share this one source file; behaviour diverges only on
 *   env.STAGING and the SITE_ORIGIN variable. No build step.
 *
 * @version v1.3.0
 */

export default {
  async fetch(request, env) {
    if (request.method !== 'GET' && request.method !== 'HEAD') {
      return stagingHeaders(new Response('Method Not Allowed', { status: 405 }), env);
    }

    const url = new URL(request.url);

    // R2 stores keys as raw UTF-8 bytes (e.g. `co-cihjml-acc-09474-
    // eclesiástico-i-cap/index.html`). Cloudflare Workers expose
    // `url.pathname` in its percent-encoded form
    // (`…eclesi%C3%A1stico…`), so a literal key lookup against
    // pathname would miss for every non-ASCII slug. Decode once up
    // front so subsequent logic runs against the true key. A
    // malformed %-escape (rare, usually a misbehaving client) falls
    // back to the raw pathname — the lookup then misses and the
    // normal 404 path handles it, rather than the Worker throwing.
    let decodedPathname;
    try {
      decodedPathname = decodeURIComponent(url.pathname);
    } catch (_) {
      decodedPathname = url.pathname;
    }

    // On the staging deployment (STAGING=true in wrangler.toml
    // [env.staging].vars), intercept /robots.txt and serve a blanket
    // Disallow so crawlers don't index staging.zasqua.org. Prod Worker
    // passes /robots.txt through to the origin (STAGING is undefined there).
    // Paired with the X-Robots-Tag injection (see stagingHeaders) for
    // resilience against Cloudflare's Managed Robots.txt prepending an
    // Allow: / block ahead of our Disallow (v0.3.0).
    if (env.STAGING === 'true' && decodedPathname === '/robots.txt') {
      return stagingHeaders(new Response('User-agent: *\nDisallow: /\n', {
        headers: {
          'content-type': 'text/plain; charset=utf-8',
          'cache-control': 'public, max-age=3600',
        },
      }), env);
    }

    let path = decodedPathname;

    // Resolve directory paths to index.html
    if (path.endsWith('/')) {
      path += 'index.html';
    } else if (!path.includes('.', path.lastIndexOf('/'))) {
      // No file extension — try as directory
      path += '/index.html';
    }

    // Strip leading slash for the object key
    const key = path.slice(1);

    // Check edge cache first
    const cache = caches.default;
    const cacheKey = new Request(url.toString(), request);
    let response = await cache.match(cacheKey);
    if (response) return stagingHeaders(response, env);

    // Fetch the object from whichever origin this deployment is wired to:
    // a public B2 HTTP origin when SITE_ORIGIN is set, otherwise the bound
    // R2 bucket. Both paths return a Worker-authoritative response (our own
    // content-type and cache-control, so serving behaviour is identical
    // regardless of which store holds the bytes).
    if (env.SITE_ORIGIN) {
      response = await serveFromOrigin(env.SITE_ORIGIN, key);
    } else {
      response = await serveFromBinding(env.SITE, key);
    }

    // A miss on a single-segment path may be a retired code; look it up in
    // the redirect table. Only after the miss, so bucket hits never read KV.
    if (response.status === 404 && env.REDIRECTS &&
        /^\/[^/]+\/?$/.test(decodedPathname)) {
      const redirectKey = decodedPathname.endsWith('/')
        ? decodedPathname
        : decodedPathname + '/';
      const target = await env.REDIRECTS.get(redirectKey);
      if (target) {
        return stagingHeaders(new Response(null, {
          status: 301,
          headers: {
            location: url.origin + target + url.search,
            'cache-control': 'public, max-age=3600',
          },
        }), env);
      }
    }

    // Store successful hits in the edge cache (non-blocking). 404s are not
    // cached, matching the pre-transition behaviour.
    if (request.method === 'GET' && response.status === 200) {
      cache.put(cacheKey, response.clone());
    }

    return stagingHeaders(response, env);
  },
};

// Re-encode a decoded object key for use in an origin URL path. Encodes
// each path segment (so `eclesiástico` -> `eclesi%C3%A1stico`) while
// preserving the slashes that separate them. This is the exact inverse of
// the decodeURIComponent(url.pathname) applied at the top of fetch(), and
// it is the single most likely place for a B2-origin bug to hide — a naive
// encodeURIComponent(key) would also escape the slashes and break every
// nested key.
function encodeKey(key) {
  return key.split('/').map(encodeURIComponent).join('/');
}

// Join a public origin base URL (e.g. a B2 download URL like
// `https://f004.backblazeb2.com/file/zasqua-staging`, no trailing slash
// required) to an encoded object key.
function originUrl(origin, key) {
  return origin.replace(/\/$/, '') + '/' + encodeKey(key);
}

// Serve a site object from the bound R2 bucket (the production path).
async function serveFromBinding(bucket, key) {
  const object = await bucket.get(key);
  if (!object) {
    const notFound = await bucket.get('404.html');
    if (notFound) {
      return new Response(notFound.body, {
        status: 404,
        headers: { 'content-type': 'text/html; charset=utf-8' },
      });
    }
    return new Response('Not Found', { status: 404 });
  }

  const headers = new Headers();
  headers.set('content-type', contentType(key));
  headers.set('cache-control', cacheControl(key));
  headers.set('etag', object.httpEtag);
  return new Response(object.body, { headers });
}

// Serve a site object from a public B2 HTTP origin (the staging path during
// the transition). Mirrors serveFromBinding's contract exactly — same
// Worker-authoritative headers, same 404.html fallback — so the only thing
// that changes between R2 and B2 is where the bytes come from.
async function serveFromOrigin(origin, key) {
  const originResp = await fetch(originUrl(origin, key));
  if (!originResp.ok) {
    const nf = await fetch(originUrl(origin, '404.html'));
    if (nf.ok) {
      return new Response(nf.body, {
        status: 404,
        headers: { 'content-type': 'text/html; charset=utf-8' },
      });
    }
    return new Response('Not Found', { status: 404 });
  }

  const headers = new Headers();
  headers.set('content-type', contentType(key));
  headers.set('cache-control', cacheControl(key));
  const etag = originResp.headers.get('etag');
  if (etag) headers.set('etag', etag);
  return new Response(originResp.body, { headers });
}

// Inject X-Robots-Tag: noindex, nofollow on every staging response so
// crawlers that ignore or misparse robots.txt (or land before our
// Disallow in Cloudflare's managed robots.txt block) still skip the
// content. Prod responses pass through untouched (v0.3.0).
function stagingHeaders(response, env) {
  if (env.STAGING !== 'true') return response;
  const headers = new Headers(response.headers);
  headers.set('x-robots-tag', 'noindex, nofollow');
  return new Response(response.body, { status: response.status, headers });
}

function contentType(key) {
  const ext = key.split('.').pop().toLowerCase();
  const types = {
    html: 'text/html; charset=utf-8',
    css: 'text/css; charset=utf-8',
    js: 'application/javascript; charset=utf-8',
    json: 'application/json; charset=utf-8',
    xml: 'application/xml; charset=utf-8',
    svg: 'image/svg+xml',
    png: 'image/png',
    jpg: 'image/jpeg',
    jpeg: 'image/jpeg',
    gif: 'image/gif',
    ico: 'image/x-icon',
    webp: 'image/webp',
    woff: 'font/woff',
    woff2: 'font/woff2',
    ttf: 'font/ttf',
    txt: 'text/plain; charset=utf-8',
    webmanifest: 'application/manifest+json',
  };
  return types[ext] || 'application/octet-stream';
}

function cacheControl(key) {
  const ext = key.split('.').pop().toLowerCase();
  if (['html', 'xml'].includes(ext)) return 'public, max-age=3600';
  // `pagefind` (the WASM runtime, e.g. `wasm.es.pagefind`) ships under a
  // fixed filename tied to the Pagefind package version, not a content
  // hash, so it shares the 7-day tier with its sibling .js/.css runtime
  // files rather than the immutable tier below.
  if (['css', 'js', 'pagefind'].includes(ext)) return 'public, max-age=604800';
  if (['json'].includes(ext)) return 'public, max-age=86400';
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'ico', 'svg', 'woff', 'woff2', 'ttf'].includes(ext)) {
    return 'public, max-age=31536000, immutable';
  }
  // Pagefind index/fragment/filter/meta chunks — content-hashed
  // filenames (e.g. `es_283012b.pf_filter`), safe to cache for a year.
  if (['pf_index', 'pf_fragment', 'pf_filter', 'pf_meta'].includes(ext)) {
    return 'public, max-age=31536000, immutable';
  }
  return 'public, max-age=3600';
}

// Version: v1.3.0
