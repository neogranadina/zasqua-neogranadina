/**
 * Vitest Configuration — Zasqua Neogranadina Instance
 *
 * Configures Vitest for the Neogranadina instance overlay of the
 * Zasqua archive platform. Tests live under `instance/tests/` in two
 * sub-folders: `tests/enrichment/` (pure-function and JSON-shape
 * tests, runnable without a full build) and `tests/build/` (assertions
 * against the built `public/` output or instance config, gated by the
 * SKIP_BUILD_TESTS env var for local iteration).
 *
 * Tests run in Node (not a browser) because all assertions either
 * check JavaScript enrichment logic or read files produced by the
 * build pipeline.
 *
 * `process.cwd()` resolves to the instance root when tests are run
 * from this directory, which is the expected invocation path
 * (`zasqua test` or `vitest run` from `instance/`).
 *
 * @version v1.0.0
 */

import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    include: ['tests/**/*.test.js'],
    environment: 'node',
    testTimeout: 10000,
  },
});
