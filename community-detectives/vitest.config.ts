import { defineConfig } from 'vitest/config';
export default defineConfig({
  test: {
    include: ['tests/**/*.test.ts'],
    environment: 'node',
    testTimeout: 30_000,
    hookTimeout: 60_000,
    fileParallelism: false,
    globalSetup: ['tests/global-setup.ts'],
    env: { NODE_ENV: 'test', DATABASE_URL: process.env.TEST_DATABASE_URL ?? 'postgresql://detectives:detectives@localhost:5432/community_detectives_test' },
  },
});
