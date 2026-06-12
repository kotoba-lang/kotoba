#!/usr/bin/env node
import { runServer } from "./server.js";

runServer().catch((err) => {
  console.error("Fatal error running open-seiyaku-mcp server:", err);
  process.exit(1);
});
