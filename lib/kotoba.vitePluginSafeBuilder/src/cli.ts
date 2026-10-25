#!/usr/bin/env node
/**
 * CLI for SSG build output validation.
 *
 * Usage:
 *   npx @etzhayyim/vite-plugin-safe-builder ssg-validate
 *   npx ssg-validate                              # auto-detect from cwd
 *   npx ssg-validate --build-dir build             # explicit build dir
 *   npx ssg-validate --strict                      # treat warnings as errors
 *   npx ssg-validate --no-links                    # skip link checking
 */

import path from "node:path";
import { validateSSGOutput, formatResult } from "./ssg-validate.js";

function parseArgs(argv: string[]): Record<string, string | boolean> {
  const args: Record<string, string | boolean> = {};
  for (let i = 2; i < argv.length; i++) {
    const arg = argv[i];
    if (arg.startsWith("--no-")) {
      args[arg.slice(5)] = false;
    } else if (arg.startsWith("--")) {
      const key = arg.slice(2);
      const next = argv[i + 1];
      if (next && !next.startsWith("--")) {
        args[key] = next;
        i++;
      } else {
        args[key] = true;
      }
    }
  }
  return args;
}

function main(): void {
  const args = parseArgs(process.argv);

  if (args["help"]) {
    console.log(`Usage: ssg-validate [options]

Options:
  --build-dir <dir>   Build output directory (default: auto-detect)
  --project-dir <dir> Project root directory (default: cwd)
  --strict            Treat warnings as errors
  --no-locales        Skip locale route checking
  --no-links          Skip internal link checking
  --no-etzhayyim           Skip etzhayyim.json route checking
  --required <paths>  Comma-separated paths that must exist
  --help              Show this help
`);
    process.exit(0);
  }

  const projectDir = path.resolve(
    typeof args["project-dir"] === "string" ? args["project-dir"] : process.cwd()
  );

  let buildDir: string;
  if (typeof args["build-dir"] === "string") {
    buildDir = path.resolve(projectDir, args["build-dir"]);
  } else {
    // Auto-detect: try "build" then "out"
    const candidates = ["build", "out", "dist", ".svelte-kit/output"];
    const found = candidates.find((d) => {
      try {
        const stat = require("node:fs").statSync(path.join(projectDir, d));
        return stat.isDirectory();
      } catch {
        return false;
      }
    });
    buildDir = path.join(projectDir, found ?? "build");
  }

  const requiredPaths =
    typeof args["required"] === "string"
      ? args["required"].split(",").map((s: string) => s.trim())
      : [];

  const result = validateSSGOutput({
    buildDir,
    projectDir,
    checkLocales: args["locales"] !== false,
    checkLinks: args["links"] !== false,
    checketzhayyimRoutes: args["etzhayyim"] !== false,
    requiredPaths,
    strict: args["strict"] === true,
  });

  console.log(formatResult(result));

  if (!result.ok) {
    process.exit(1);
  }
}

main();
