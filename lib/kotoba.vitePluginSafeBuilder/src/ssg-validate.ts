/**
 * SSG Build Output Validator
 *
 * Checks:
 * 1. Locale routes — all configured locales have index.html in build output
 * 2. Internal links — href/src in HTML resolve to existing files
 * 3. etzhayyim.json routes — declared routes have corresponding content
 */

import fs from "node:fs";
import path from "node:path";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SSGValidateOptions {
  /** Absolute path to SSG build output (e.g. "build/", "out/") */
  buildDir: string;
  /** Absolute path to the project root (where etzhayyim.json, project.inlang live) */
  projectDir: string;
  /** Check that all Paraglide locales have routes in build output (default: true) */
  checkLocales?: boolean;
  /** Check internal links in HTML files (default: true) */
  checkLinks?: boolean;
  /** Check routes declared in etzhayyim.json (default: true) */
  checketzhayyimRoutes?: boolean;
  /** Additional route paths to validate exist (e.g. ["/dashboard", "/settings"]) */
  requiredPaths?: string[];
  /** Treat warnings as errors (default: false) */
  strict?: boolean;
}

export interface ValidationIssue {
  level: "error" | "warning";
  check: string;
  message: string;
  file?: string;
}

export interface ValidationResult {
  ok: boolean;
  issues: ValidationIssue[];
  summary: {
    localesExpected: number;
    localesFound: number;
    htmlFilesScanned: number;
    brokenLinks: number;
  };
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fileExists(p: string): boolean {
  try {
    return fs.statSync(p).isFile();
  } catch {
    return false;
  }
}

function dirExists(p: string): boolean {
  try {
    return fs.statSync(p).isDirectory();
  } catch {
    return false;
  }
}

function readJson(p: string): unknown {
  try {
    return JSON.parse(fs.readFileSync(p, "utf8"));
  } catch {
    return null;
  }
}

/** Recursively collect files matching a predicate */
function walkFiles(dir: string, match: (name: string) => boolean): string[] {
  const results: string[] = [];
  if (!dirExists(dir)) return results;

  const entries = fs.readdirSync(dir, { withFileTypes: true });
  for (const entry of entries) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...walkFiles(full, match));
    } else if (entry.isFile() && match(entry.name)) {
      results.push(full);
    }
  }
  return results;
}

/** Extract href and src attributes from HTML content */
function extractLinks(html: string): string[] {
  const links: string[] = [];
  // Match href="..." and src="..." (skip external, anchor, data:, javascript:, mailto:)
  const re = /(?:href|src)\s*=\s*["']([^"']+)["']/gi;
  let m: RegExpExecArray | null;
  while ((m = re.exec(html)) !== null) {
    const link = m[1];
    if (
      link.startsWith("http://") ||
      link.startsWith("https://") ||
      link.startsWith("//") ||
      link.startsWith("#") ||
      link.startsWith("data:") ||
      link.startsWith("javascript:") ||
      link.startsWith("mailto:") ||
      link.startsWith("tel:")
    ) {
      continue;
    }
    links.push(link);
  }
  return links;
}

// ---------------------------------------------------------------------------
// Locale detection
// ---------------------------------------------------------------------------

interface InlangSettings {
  sourceLanguageTag?: string;
  languageTags?: string[];
}

function detectLocales(projectDir: string): string[] {
  // Try project.inlang/settings.json (Paraglide)
  const inlangPath = path.join(projectDir, "project.inlang", "settings.json");
  const inlang = readJson(inlangPath) as InlangSettings | null;
  if (inlang?.languageTags && inlang.languageTags.length > 0) {
    return inlang.languageTags;
  }
  return [];
}

function detectBaseLocale(projectDir: string): string {
  const inlangPath = path.join(projectDir, "project.inlang", "settings.json");
  const inlang = readJson(inlangPath) as InlangSettings | null;
  return inlang?.sourceLanguageTag ?? "en";
}

// ---------------------------------------------------------------------------
// Check: Locale routes
// ---------------------------------------------------------------------------

function checkLocaleRoutes(
  buildDir: string,
  projectDir: string,
  issues: ValidationIssue[]
): { expected: number; found: number } {
  const locales = detectLocales(projectDir);
  if (locales.length === 0) {
    return { expected: 0, found: 0 };
  }

  const baseLocale = detectBaseLocale(projectDir);
  let found = 0;

  for (const locale of locales) {
    if (locale === baseLocale) {
      // Base locale may not have a prefix (served at /)
      const rootIndex = path.join(buildDir, "index.html");
      if (fileExists(rootIndex)) {
        found++;
      } else {
        issues.push({
          level: "error",
          check: "locale-routes",
          message: `Base locale "${locale}" missing: ${rootIndex}`,
        });
      }
      continue;
    }

    // Non-base locales should have /{locale}/index.html
    const localeIndex = path.join(buildDir, locale, "index.html");
    const localeHtml = path.join(buildDir, `${locale}.html`);
    if (fileExists(localeIndex) || fileExists(localeHtml)) {
      found++;
    } else {
      issues.push({
        level: "error",
        check: "locale-routes",
        message: `Locale "${locale}" has no route in build output. Expected: ${localeIndex}`,
      });
    }
  }

  return { expected: locales.length, found };
}

// ---------------------------------------------------------------------------
// Check: Internal links
// ---------------------------------------------------------------------------

function checkInternalLinks(
  buildDir: string,
  issues: ValidationIssue[]
): { scanned: number; broken: number } {
  const htmlFiles = walkFiles(buildDir, (name) => name.endsWith(".html"));
  let broken = 0;

  for (const htmlFile of htmlFiles) {
    const content = fs.readFileSync(htmlFile, "utf8");
    const links = extractLinks(content);

    for (const link of links) {
      // Resolve relative to the HTML file's directory
      const cleanLink = link.split("?")[0].split("#")[0];
      if (!cleanLink) continue;

      let resolved: string;
      if (cleanLink.startsWith("/")) {
        resolved = path.join(buildDir, cleanLink);
      } else {
        resolved = path.resolve(path.dirname(htmlFile), cleanLink);
      }

      // Check if target exists (file, file.html, dir/index.html)
      if (
        fileExists(resolved) ||
        fileExists(resolved + ".html") ||
        fileExists(path.join(resolved, "index.html"))
      ) {
        continue;
      }

      // Skip common framework assets that may be lazy-loaded
      if (
        cleanLink.startsWith("/_next/") ||
        cleanLink.startsWith("/_app/") ||
        cleanLink.startsWith("/__data") ||
        cleanLink.startsWith("/api/")
      ) {
        continue;
      }

      broken++;
      issues.push({
        level: "warning",
        check: "internal-links",
        message: `Broken link "${link}" in ${path.relative(buildDir, htmlFile)}`,
        file: path.relative(buildDir, htmlFile),
      });
    }
  }

  return { scanned: htmlFiles.length, broken };
}

// ---------------------------------------------------------------------------
// Check: etzhayyim.json routes
// ---------------------------------------------------------------------------

interface etzhayyimJson {
  spa?: boolean;
  routes?: Array<{ host?: string; path?: string; paths?: string[] }>;
}

function checketzhayyimRoutes(
  buildDir: string,
  projectDir: string,
  issues: ValidationIssue[]
): void {
  const etzhayyimPath = path.join(projectDir, "etzhayyim.json");
  const etzhayyim = readJson(etzhayyimPath) as etzhayyimJson | null;
  if (!etzhayyim?.routes) return;

  // SPA apps use adapter-static with fallback — index.html is generated after
  // the SSR bundle closeBundle hook, so it won't exist at validation time.
  if (etzhayyim.spa) return;

  for (const route of etzhayyim.routes) {
    const paths = route.paths ?? (route.path ? [route.path] : ["/"]);
    for (const p of paths) {
      if (p === "/") {
        // Root route — just check index.html exists
        if (!fileExists(path.join(buildDir, "index.html"))) {
          issues.push({
            level: "error",
            check: "etzhayyim-routes",
            message: `etzhayyim.json declares route "${p}" but build output has no index.html`,
          });
        }
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Check: Required paths
// ---------------------------------------------------------------------------

function checkRequiredPaths(
  buildDir: string,
  requiredPaths: string[],
  issues: ValidationIssue[]
): void {
  for (const p of requiredPaths) {
    const clean = p.replace(/^\//, "");
    const candidates = [
      path.join(buildDir, clean, "index.html"),
      path.join(buildDir, `${clean}.html`),
      path.join(buildDir, clean),
    ];
    if (!candidates.some(fileExists)) {
      issues.push({
        level: "error",
        check: "required-paths",
        message: `Required path "${p}" not found in build output`,
      });
    }
  }
}

// ---------------------------------------------------------------------------
// Main validation
// ---------------------------------------------------------------------------

export function validateSSGOutput(options: SSGValidateOptions): ValidationResult {
  const {
    buildDir,
    projectDir,
    checkLocales = true,
    checkLinks = true,
    checketzhayyimRoutes: checketzhayyim = true,
    requiredPaths = [],
    strict = false,
  } = options;

  const issues: ValidationIssue[] = [];

  if (!dirExists(buildDir)) {
    return {
      ok: false,
      issues: [
        {
          level: "error",
          check: "build-dir",
          message: `Build directory does not exist: ${buildDir}`,
        },
      ],
      summary: {
        localesExpected: 0,
        localesFound: 0,
        htmlFilesScanned: 0,
        brokenLinks: 0,
      },
    };
  }

  let localesExpected = 0;
  let localesFound = 0;
  let htmlFilesScanned = 0;
  let brokenLinks = 0;

  if (checkLocales) {
    const result = checkLocaleRoutes(buildDir, projectDir, issues);
    localesExpected = result.expected;
    localesFound = result.found;
  }

  if (checkLinks) {
    const result = checkInternalLinks(buildDir, issues);
    htmlFilesScanned = result.scanned;
    brokenLinks = result.broken;
  }

  if (checketzhayyim) {
    checketzhayyimRoutes(buildDir, projectDir, issues);
  }

  if (requiredPaths.length > 0) {
    checkRequiredPaths(buildDir, requiredPaths, issues);
  }

  const errors = issues.filter((i) => i.level === "error");
  const warnings = issues.filter((i) => i.level === "warning");
  const ok = errors.length === 0 && (!strict || warnings.length === 0);

  return {
    ok,
    issues,
    summary: {
      localesExpected,
      localesFound,
      htmlFilesScanned,
      brokenLinks,
    },
  };
}

// ---------------------------------------------------------------------------
// Pretty printer
// ---------------------------------------------------------------------------

export function formatResult(result: ValidationResult): string {
  const lines: string[] = [];
  lines.push("[ssg-validate] Build output validation");
  lines.push("\u2500".repeat(50));

  if (result.summary.localesExpected > 0) {
    lines.push(
      `Locales: ${result.summary.localesFound}/${result.summary.localesExpected} found`
    );
  }
  if (result.summary.htmlFilesScanned > 0) {
    lines.push(`HTML files scanned: ${result.summary.htmlFilesScanned}`);
  }
  if (result.summary.brokenLinks > 0) {
    lines.push(`Broken links: ${result.summary.brokenLinks}`);
  }

  const errors = result.issues.filter((i) => i.level === "error");
  const warnings = result.issues.filter((i) => i.level === "warning");

  if (errors.length > 0) {
    lines.push("");
    lines.push(`ERRORS (${errors.length}):`);
    for (const e of errors) {
      lines.push(`  [${e.check}] ${e.message}`);
    }
  }

  if (warnings.length > 0) {
    lines.push("");
    lines.push(`WARNINGS (${warnings.length}):`);
    for (const w of warnings.slice(0, 20)) {
      lines.push(`  [${w.check}] ${w.message}`);
    }
    if (warnings.length > 20) {
      lines.push(`  ... and ${warnings.length - 20} more`);
    }
  }

  lines.push("");
  lines.push(result.ok ? "[ssg-validate] PASS" : "[ssg-validate] FAIL");
  return lines.join("\n");
}
