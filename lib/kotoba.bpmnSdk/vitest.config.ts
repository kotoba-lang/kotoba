/// <reference types="vitest" />
import { defineConfig } from 'vitest/config';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'node:url';

const rootDir = dirname(fileURLToPath(import.meta.url));
const r = (p: string) => resolve(rootDir, p);

export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: [r('./vitest.setup.ts')],
    include: ['packages/**/src/**/*.test.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'json', 'html'],
      include: ['packages/**/src/**/*.{ts,tsx}'],
      exclude: ['**/node_modules/**', 'examples/**'],
      all: true,
      thresholds: {
        global: {
          branches: 100,
          functions: 100,
          lines: 100,
          statements: 100,
        },
      },
    },
  },
  resolve: {
    alias: {
      '@etzhayyim/bpmn-sdk-core': r('./packages/core/src/index.ts'),
      '@etzhayyim/bpmn-sdk-dsl': r('./packages/dsl/src/index.ts'),
      '@etzhayyim/bpmn-sdk-compiler': r('./packages/compiler/src/index.ts'),
      '@etzhayyim/bpmn-sdk-runtime': r('./packages/runtime/src/index.ts'),
      '@etzhayyim/bpmn-sdk-importer': r('./packages/importer/src/index.ts'),
      '@etzhayyim/bpmn-sdk-human': r('./packages/human/src/index.ts'),
      '@etzhayyim/bpmn-sdk-validation': r('./packages/validation/src/index.ts'),
      '@etzhayyim/bpmn-sdk-testing': r('./packages/testing/src/index.ts'),
      '@etzhayyim/bpmn-sdk-ops': r('./packages/ops/src/index.ts'),
      '@etzhayyim/bpmn-sdk-form': r('./packages/form/src/index.ts'),
      '@etzhayyim/bpmn-sdk-dmn': r('./packages/dmn/src/index.ts'),
      '@etzhayyim/bpmn-sdk/testkit': r('./packages/internal/testkit/src/index.ts'),
    },
  },
});
