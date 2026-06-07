/**
 * Tailwind CSS Compiled Invariant Test
 *
 * Tailwind v4 uses a JIT (just-in-time) compiler that scans the
 * built HTML for class names and emits only the rules it sees. If
 * the JIT pipeline misfires — the most common symptom being a
 * `.gitignore` silent-skip that stops the compiler from reaching
 * the generated HTML — the compiled stylesheet ends up near-empty
 * and the whole site renders unstyled.
 *
 * This test catches that regression by asserting the compiled
 * stylesheet is > 1 KB and
 * that at least one class name present in a built page also appears
 * in the CSS. Gated by SKIP_BUILD_TESTS=1 so enrichment-only runs
 * don't require a preceding Hugo build.
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

function findCompiledCss(dir) {
  if (!fs.existsSync(dir)) return null;
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      const nested = findCompiledCss(full);
      if (nested) return nested;
    } else if (entry.isFile() && entry.name.endsWith('.css')) {
      return full;
    }
  }
  return null;
}

describe.skipIf(SKIP)('Tailwind CSS compiled', () => {
  it('compiled CSS exists under public/ and is > 1 KB', () => {
    const css = findCompiledCss(path.join(PUBLIC, 'css')) || findCompiledCss(PUBLIC);
    if (!css) {
      throw new Error('expected a compiled .css file under public/ after the build');
    }
    const size = fs.statSync(css).size;
    expect(size).toBeGreaterThan(1024);
  });

  it('at least one class from a built page appears in the compiled CSS', () => {
    const css = findCompiledCss(path.join(PUBLIC, 'css')) || findCompiledCss(PUBLIC);
    const page = path.join(PUBLIC, SMOKE_REF, 'index.html');
    if (!css || !fs.existsSync(page)) {
      throw new Error(`expected both a compiled CSS file and ${page} to exist after the build`);
    }
    const cssText = fs.readFileSync(css, 'utf8');
    const html = fs.readFileSync(page, 'utf8');
    const classes = new Set();
    for (const match of html.matchAll(/class="([^"]+)"/g)) {
      for (const cls of match[1].split(/\s+/)) {
        if (cls) classes.add(cls);
      }
    }
    const hit = [...classes].some(cls => cssText.includes(`.${cls}`));
    expect(hit).toBe(true);
  });
});
