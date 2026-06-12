import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["test/**/*.test.ts"],
    environment: "node",
    coverage: {
      provider: "v8",
      thresholds: {
        lines: 70,
        branches: 60,
        functions: 65,
        statements: 70,
      },
    },
  },
});
