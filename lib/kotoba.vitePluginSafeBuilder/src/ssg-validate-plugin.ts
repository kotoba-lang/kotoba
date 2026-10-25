/**
 * Vite plugin for SSG build output validation.
 *
 * The plugin runs after the bundle is closed (closeBundle hook) and
 * validates that the SSG output has all expected locale routes and
 * no broken internal links.
 */

import path from "node:path";
import fs from "node:fs";
import type { Plugin } from "vite";
import {
  validateSSGOutput,
  formatResult,
  type SSGValidateOptions,
} from "./ssg-validate.js";

export interface SSGValidatePluginOptions {
  /** Check locale route completeness (default: true) */
  checkLocales?: boolean;
  /** Check internal links in HTML (default: true) */
  checkLinks?: boolean;
  /** Check etzhayyim.json route declarations (default: true) */
  checketzhayyimRoutes?: boolean;
  /** Additional paths that must exist in build output */
  requiredPaths?: string[];
  /** Treat warnings as errors (default: false) */
  strict?: boolean;
  /** Override build output directory (auto-detected from SvelteKit/Vite config) */
  buildDir?: string;
}

function detectBuildDir(projectDir: string): string {
  // Try SvelteKit adapter-static output ("build" is default)
  const svelteConfig = path.join(projectDir, "svelte.config.js");
  if (fs.existsSync(svelteConfig)) {
    return path.join(projectDir, "build");
  }

  // Try Next.js export output
  const nextConfig = path.join(projectDir, "next.config.js");
  if (fs.existsSync(nextConfig)) {
    // Next.js `output: "export"` writes to "out", but etzhayyim apps rename to "build"
    const buildDir = path.join(projectDir, "build");
    if (fs.existsSync(buildDir)) return buildDir;
    return path.join(projectDir, "out");
  }

  // Default
  return path.join(projectDir, "build");
}

export function ssgValidate(options: SSGValidatePluginOptions = {}): Plugin {
  let projectRoot: string;

  return {
    name: "ssg-validate",
    enforce: "post",

    configResolved(config) {
      projectRoot = config.root;
    },

    closeBundle: {
      sequential: true,
      order: "post",
      async handler() {
        const buildDir = options.buildDir
          ? path.resolve(projectRoot, options.buildDir)
          : detectBuildDir(projectRoot);

        if (!fs.existsSync(buildDir)) {
          // Build dir might not exist yet if adapter hasn't written it
          // (e.g. SvelteKit adapter-static runs after closeBundle in some setups)
          console.warn(
            `[ssg-validate] Build directory not found: ${buildDir} — skipping validation`
          );
          return;
        }

        const validateOptions: SSGValidateOptions = {
          buildDir,
          projectDir: projectRoot,
          checkLocales: options.checkLocales ?? true,
          checkLinks: options.checkLinks ?? true,
          checketzhayyimRoutes: options.checketzhayyimRoutes ?? true,
          requiredPaths: options.requiredPaths ?? [],
          strict: options.strict ?? false,
        };

        const result = validateSSGOutput(validateOptions);
        console.log(formatResult(result));

        if (!result.ok) {
          this.error(
            `[ssg-validate] Build validation failed with ${
              result.issues.filter((i) => i.level === "error").length
            } error(s). Fix the issues above before deploying.`
          );
        }
      },
    },
  };
}
