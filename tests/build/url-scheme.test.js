/**
 * Flat-Code URL Scheme Invariant Test
 *
 * The public URL scheme pins every description to the bare
 * reference code: a description lives at `/{reference_code}/`,
 * never under a section prefix like `/descripcion/{code}/`. This
 * keeps printed URLs stable across future information-architecture
 * changes. The test looks for
 * `public/{smoke-test-reference-code}/index.html` after a build
 * and simultaneously asserts the section-prefixed path does NOT
 * exist. Gated by SKIP_BUILD_TESTS=1 so enrichment-only runs can
 * skip the build dependency.
 *
 * This test lives in the instance and reads from `public/` relative
 * to the instance root (process.cwd() when run with `npm test` from
 * the instance/ directory). The smoke reference code matches the one
 * used by the parity harness (`co-ahrb-aht-001`).
 *
 * @version v2.0.0
 */

import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

const PUBLIC = path.resolve(process.cwd(), 'public');
const SMOKE_REF = 'co-ahrb-aht-001';
// Skip when explicitly opted out (SKIP_BUILD_TESTS=1) OR when no build output
// is present, so a plain `npm test` with no prior build skips cleanly instead
// of hard-failing. CI runs a full build first, so the assertions still fire there.
const SKIP = process.env.SKIP_BUILD_TESTS === '1' || !fs.existsSync(PUBLIC);

describe.skipIf(SKIP)('flat-code URL scheme', () => {
  it(`public/${SMOKE_REF}/index.html exists after build`, () => {
    const target = path.join(PUBLIC, SMOKE_REF, 'index.html');
    if (!fs.existsSync(target)) {
      throw new Error(`expected ${target} to exist after the build`);
    }
    expect(fs.statSync(target).size).toBeGreaterThan(0);
  });

  it('does NOT render under /descripcion/ prefix (flat-code scheme, not section-prefixed)', () => {
    const sectioned = path.join(PUBLIC, 'descripcion', SMOKE_REF, 'index.html');
    expect(fs.existsSync(sectioned)).toBe(false);
  });
});
