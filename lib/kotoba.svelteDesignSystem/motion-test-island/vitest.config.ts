import { defineConfig } from "vitest/config";

// Anchor config here so vitest does not climb to the parent design-system
// vite.config.ts (which pulls in svelte plugins this island deliberately omits —
// motion/index.ts is pure math with only an erased `import type` from svelte).
export default defineConfig({
  root: __dirname,
  test: {
    include: ["*.test.ts"],
  },
});
