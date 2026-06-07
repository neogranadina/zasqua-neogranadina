/**
 * Ancestor Chain Invariant Test
 *
 * Archival descriptions form a hierarchy — a fonds contains series, a
 * series contains items, and so on. Each description record carries a
 * `parent_reference_code`, and the frontend needs the full ancestor
 * chain (all the way up to the root) to render breadcrumbs. The chain
 * is walked in `scripts/generate-content.js` so every record ships
 * with a prebuilt `ancestor_chain: Array<{reference_code, title,
 * description_level}>` in the enriched JSON.
 *
 * Enriched descriptions are sharded by a fixed record count so no
 * single file exceeds V8's 512 MiB max-string limit. This test loads
 * every shard, asserts the array-of-link-records shape on every record,
 * and then verifies on a sample of records that walking
 * `parent_reference_code` across the combined corpus reconstructs the
 * exact stored chain. The walk uses a globally built `byCode` Map —
 * fixed-count sharding can place a record and its parent in different
 * shards, so the invariant is corpus-wide, not per-shard.
 *
 * This test lives in the instance and reads from `assets/hugo-data/`
 * relative to the instance root (process.cwd() when run with `npm test`
 * from the instance/ directory). It requires a prior build or enrichment
 * run to have populated assets/hugo-data/descriptions/. Tests skip
 * cleanly when that data is absent.
 *
 * @version v2.0.0
 */

import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

const SHARDS_DIR = path.resolve(process.cwd(), 'assets/hugo-data/descriptions');
const DATA_PRESENT = fs.existsSync(SHARDS_DIR);

function loadAllShards() {
  const shards = {};
  for (const file of fs.readdirSync(SHARDS_DIR)) {
    if (!file.endsWith('.json')) continue;
    const code = file.replace(/\.json$/, '');
    shards[code] = JSON.parse(fs.readFileSync(path.join(SHARDS_DIR, file), 'utf8'));
  }
  return shards;
}

describe('ancestor_chain invariant (I2)', () => {
  it('descriptions shard directory exists', () => {
    if (!DATA_PRESENT) {
      console.log('SKIP: assets/hugo-data/descriptions/ not present — run enrichment first');
      return;
    }
    expect(fs.existsSync(SHARDS_DIR)).toBe(true);
  });

  it.skipIf(!DATA_PRESENT)('every record across every shard carries an ancestor_chain array of {reference_code, title, description_level}', () => {
    const shards = loadAllShards();
    let totalChecked = 0;
    for (const records of Object.values(shards)) {
      for (const d of records) {
        expect(Array.isArray(d.ancestor_chain)).toBe(true);
        for (const link of d.ancestor_chain) {
          expect(typeof link.reference_code).toBe('string');
          expect(typeof link.title).toBe('string');
          expect(typeof link.description_level).toBe('string');
        }
        totalChecked++;
      }
    }
    expect(totalChecked).toBeGreaterThan(0);
  });

  it.skipIf(!DATA_PRESENT || !!process.env.DEV_LIMIT)('ancestor_chain matches a fresh walk via parent_reference_code for a 50-record sample across all shards', () => {
    // Skipped under DEV_LIMIT because the enriched chain is built against
    // the full source corpus, while the shards reflect only the
    // DEV_LIMIT slice — missing ancestors would make the walk look
    // shorter than the stored chain. The full-run case is the real gate.
    const shards = loadAllShards();
    const allRecords = [].concat(...Object.values(shards));
    const byCode = new Map(allRecords.map(d => [d.reference_code, d]));

    const sample = [];
    const step = Math.max(1, Math.floor(allRecords.length / 50));
    for (let i = 0; i < allRecords.length && sample.length < 50; i += step) {
      if (allRecords[i].parent_reference_code && byCode.has(allRecords[i].parent_reference_code)) {
        sample.push(allRecords[i]);
      }
    }
    expect(sample.length, 'expected to sample at least 1 record with a parent_reference_code').toBeGreaterThan(0);

    for (const d of sample) {
      const walked = [];
      let cursor = byCode.get(d.parent_reference_code);
      while (cursor) {
        walked.unshift({
          reference_code: cursor.reference_code,
          title: cursor.title,
          description_level: cursor.description_level,
        });
        cursor = cursor.parent_reference_code ? byCode.get(cursor.parent_reference_code) : null;
      }
      expect(d.ancestor_chain, `record ${d.reference_code}`).toEqual(walked);
    }
  });
});
