/**
 * Enriched Record Counts Invariant Test
 *
 * The canonical Zasqua export has 78,271 entities, 106,509
 * descriptions, and 6,705 places (verified 2026-04-21 against a
 * fresh B2 pull that carries `modified_at`, normalised
 * `date_expression`, and the entity cleanup pass that produced the
 * +11 active-entity delta from the merge/reclassify/wipe/split
 * work). Any enrichment step that drops records silently is a data-
 * quality bug; any step that invents records is worse. This test
 * locks the counts: the files under `assets/hugo-data/` must match
 * the canonical totals — or, in DEV_MODE,
 * `min(canonical, DEV_LIMIT)`.
 *
 * Descriptions are sharded by a fixed record count so no individual
 * file busts V8's 512 MiB string limit; the test sums across
 * shards. Entities and places are small enough to live in one file
 * each.
 *
 * This test lives in the instance and reads from `assets/hugo-data/`
 * relative to the instance root (process.cwd() when run with `npm test`
 * from the instance/ directory). Tests skip cleanly when hugo-data is
 * absent so a run without a prior build/enrichment does not hard-fail.
 *
 * @version v2.0.0
 */

import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';

const DIR = path.resolve(process.cwd(), 'assets/hugo-data');
const DATA_PRESENT = fs.existsSync(DIR);

const CANONICAL = {
  descriptions: 106509,
  entities: 78271,
  places: 6705,
};

function expectedLen(canonical) {
  const limit = process.env.DEV_LIMIT ? Number(process.env.DEV_LIMIT) : Infinity;
  return Math.min(canonical, limit);
}

function sumShards(dir) {
  const files = fs.readdirSync(dir).filter(f => f.endsWith('.json'));
  let total = 0;
  for (const file of files) {
    const records = JSON.parse(fs.readFileSync(path.join(dir, file), 'utf8'));
    total += records.length;
  }
  return total;
}

describe('enriched record counts invariant', () => {
  it.skipIf(!DATA_PRESENT)('descriptions shards sum to 106,509 (or DEV_LIMIT)', () => {
    const shardsDir = path.join(DIR, 'descriptions');
    if (!fs.existsSync(shardsDir)) {
      console.log('SKIP: assets/hugo-data/descriptions/ not present — run enrichment first');
      return;
    }
    expect(sumShards(shardsDir)).toBe(expectedLen(CANONICAL.descriptions));
  });

  it.skipIf(!DATA_PRESENT)('descriptions-index.json covers every reference_code', () => {
    const indexFile = path.join(DIR, 'descriptions-index.json');
    if (!fs.existsSync(indexFile)) {
      console.log('SKIP: assets/hugo-data/descriptions-index.json not present — run enrichment first');
      return;
    }
    const index = JSON.parse(fs.readFileSync(indexFile, 'utf8'));
    expect(Object.keys(index).length).toBe(expectedLen(CANONICAL.descriptions));
  });

  for (const key of ['entities', 'places']) {
    it.skipIf(!DATA_PRESENT)(`${key}.json length matches ${CANONICAL[key]} (or DEV_LIMIT)`, () => {
      const file = path.join(DIR, `${key}.json`);
      if (!fs.existsSync(file)) {
        console.log(`SKIP: assets/hugo-data/${key}.json not present — run enrichment first`);
        return;
      }
      const records = JSON.parse(fs.readFileSync(file, 'utf8'));
      expect(records.length).toBe(expectedLen(CANONICAL[key]));
    });
  }
});
