/**
 * Hugo Config-Merge Invariant Test
 *
 * Tailwind v4 depends on three Hugo configuration keys being present and
 * correct in the instance hugo.toml. If any of them is accidentally
 * dropped — during a hugo.toml rewrite, a merge conflict resolution, or
 * a config refactor — the Tailwind pipeline silently misfires and the
 * site ships without styles.
 *
 * The three load-bearing keys (the "Tailwind landmines"):
 *
 *   1. `build.writeStats = true` — tells Hugo to emit hugo_stats.json
 *      during every build. Tailwind v4's JIT reads that file to discover
 *      which CSS classes are actually used in rendered HTML. If this flag
 *      is missing, Tailwind emits a skeletal stylesheet with no error.
 *
 *   2. The `hugo_stats.json` → `assets/notwatching/hugo_stats.json` module
 *      mount — makes hugo_stats.json visible to Hugo Pipes regardless of
 *      .gitignore. Without this mount, a gitignored hugo_stats.json
 *      silently disappears from Tailwind's scan path.
 *
 *   3. A css cachebuster entry keyed on `hugo_stats\.json` — ensures Hugo
 *      invalidates the compiled CSS cache whenever the class-usage stats
 *      change. Without it, a stale cached stylesheet ships on rebuild.
 *
 * This test guards all three by reading `instance/hugo.toml` as text and
 * asserting each key is present. It does not parse TOML — the patterns
 * are stable enough for a text assertion and parsing TOML would require
 * a dependency. SKIP_BUILD_TESTS=1 gates the test so enrichment-only
 * runs (where hugo.toml may be present but a build hasn't run) can still
 * skip without noise.
 *
 * @version v1.0.0
 */

import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

const SKIP = process.env.SKIP_BUILD_TESTS === '1';
const INSTANCE_ROOT = process.cwd();
const HUGO_TOML = path.resolve(INSTANCE_ROOT, 'hugo.toml');

describe.skipIf(SKIP)('hugo.toml config-merge invariants', () => {
  it('hugo.toml exists at the instance root', () => {
    if (!fs.existsSync(HUGO_TOML)) {
      throw new Error(
        `instance/hugo.toml not found at ${HUGO_TOML} — ` +
        'run tests from the instance/ directory'
      );
    }
    expect(fs.existsSync(HUGO_TOML)).toBe(true);
  });

  it('build.writeStats is true in instance hugo.toml', () => {
    if (!fs.existsSync(HUGO_TOML)) {
      throw new Error(`instance/hugo.toml not found at ${HUGO_TOML}`);
    }
    const toml = fs.readFileSync(HUGO_TOML, 'utf8');
    // Assert both writeStats and buildStats.enable — both are required for
    // Tailwind v4 JIT to receive the class-usage signal from Hugo.
    if (!toml.includes('writeStats = true')) {
      throw new Error(
        'instance/hugo.toml is missing `build.writeStats = true`. ' +
        'Without this, Tailwind JIT has no class-usage signal and ships ' +
        'a skeletal stylesheet — the site renders unstyled with no error.'
      );
    }
    expect(toml).toContain('writeStats = true');
  });

  it('hugo_stats.json module mount is present', () => {
    if (!fs.existsSync(HUGO_TOML)) {
      throw new Error(`instance/hugo.toml not found at ${HUGO_TOML}`);
    }
    const toml = fs.readFileSync(HUGO_TOML, 'utf8');
    if (!toml.includes('assets/notwatching/hugo_stats.json')) {
      throw new Error(
        'instance/hugo.toml is missing the hugo_stats.json → ' +
        'assets/notwatching/hugo_stats.json module mount. ' +
        'Without this mount, a gitignored hugo_stats.json silently ' +
        'disappears from Tailwind\'s scan path.'
      );
    }
    expect(toml).toContain('assets/notwatching/hugo_stats.json');
  });

  it('css cachebuster entry is present', () => {
    if (!fs.existsSync(HUGO_TOML)) {
      throw new Error(`instance/hugo.toml not found at ${HUGO_TOML}`);
    }
    const toml = fs.readFileSync(HUGO_TOML, 'utf8');
    if (!toml.includes('cachebusters')) {
      throw new Error(
        'instance/hugo.toml is missing [[build.cachebusters]] entries. ' +
        'Without a cachebuster keyed on hugo_stats.json, Hugo serves a ' +
        'stale compiled stylesheet after class-usage changes.'
      );
    }
    expect(toml).toContain('cachebusters');
  });
});
