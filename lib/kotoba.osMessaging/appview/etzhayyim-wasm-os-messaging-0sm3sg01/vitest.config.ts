import { defineConfig } from "vitest/config";
import path from "node:path";
const root = __dirname;
export default defineConfig({
  resolve: {
    alias: [
      { find: /^@etzhayyim\/kotodama-host-sdk$/, replacement: path.resolve(root, "../../../../40-engine/kotoba/crates/kotoba-kotodama/sdk/kotodama-host-sdk/src/index.ts") },
      { find: /^@etzhayyim\/kotodama-host-sdk\/(.*)$/, replacement: path.resolve(root, "../../../../40-engine/kotoba/crates/kotoba-kotodama/sdk/kotodama-host-sdk/src/$1") },
      { find: /^@etzhayyim\/xrpc$/, replacement: path.resolve(root, "../../../../../com-etzhayyim-xrpc/src/index.ts") },
    ],
  },
  test: { globals: true, testTimeout: 15000 },
});
