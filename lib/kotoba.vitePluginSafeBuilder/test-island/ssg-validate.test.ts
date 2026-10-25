/**
 * @etzhayyim/vite-plugin-safe-builder — ssg-validate tests (coverage loop iter 20).
 *
 * ssg-validate is the build-output gate every Svelte SSG app runs: it scans
 * the static build for broken internal links, missing locale routes, and
 * required paths before deploy. Zero tests; a false-negative ships a broken
 * site, a false-positive blocks deploys. Driven via tmp build-dir fixtures.
 */
import { describe, it, expect, beforeEach, afterEach } from "vitest";
import { mkdtemp, mkdir, writeFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";

import { validateSSGOutput, formatResult } from "../src/ssg-validate.ts";

let base: string, build: string, proj: string;
beforeEach(async () => {
  base = await mkdtemp(join(tmpdir(), "ssgval-"));
  build = join(base, "build");
  proj = join(base, "proj");
  await mkdir(build, { recursive: true });
  await mkdir(proj, { recursive: true });
});
afterEach(async () => { await rm(base, { recursive: true, force: true }); });

const html = (body: string) => `<!doctype html><html><body>${body}</body></html>`;
async function file(rel: string, content: string) {
  const full = join(build, rel);
  await mkdir(join(full, ".."), { recursive: true });
  await writeFile(full, content, "utf8");
}

// ── missing build dir ────────────────────────────────────────────────────────

describe("validateSSGOutput — missing build dir", () => {
  it("returns a build-dir error, not ok", () => {
    const r = validateSSGOutput({ buildDir: join(base, "nope"), projectDir: proj });
    expect(r.ok).toBe(false);
    expect(r.issues[0].check).toBe("build-dir");
  });
});

// ── internal link checking ───────────────────────────────────────────────────

describe("validateSSGOutput — internal links", () => {
  it("accepts links resolving to a file, file.html, or dir/index.html", async () => {
    await file("index.html", html(`
      <a href="/about">about</a>
      <a href="/docs/">docs</a>
      <img src="/logo.png">
      <a href="page.html">rel</a>
    `));
    await file("about.html", html("about"));         // /about → about.html
    await file("docs/index.html", html("docs"));     // /docs/ → docs/index.html
    await file("logo.png", "binary");                // /logo.png → file
    await file("page.html", html("p"));              // relative page.html
    const r = validateSSGOutput({ buildDir: build, projectDir: proj, checkLocales: false, checketzhayyimRoutes: false });
    expect(r.summary.brokenLinks).toBe(0);
    expect(r.ok).toBe(true);
    expect(r.summary.htmlFilesScanned).toBeGreaterThanOrEqual(1);
  });

  it("flags a broken internal link as a warning", async () => {
    await file("index.html", html(`<a href="/missing">x</a>`));
    const r = validateSSGOutput({ buildDir: build, projectDir: proj, checkLocales: false, checketzhayyimRoutes: false });
    expect(r.summary.brokenLinks).toBe(1);
    const issue = r.issues.find((i) => i.check === "internal-links")!;
    expect(issue.level).toBe("warning");
    expect(r.ok).toBe(true);          // warnings don't fail in non-strict
  });

  it("skips external, anchor, mailto, and framework-asset links", async () => {
    await file("index.html", html(`
      <a href="https://x.test">ext</a>
      <a href="//cdn.test/a">proto-rel</a>
      <a href="#top">anchor</a>
      <a href="mailto:a@b.c">mail</a>
      <a href="/_app/immutable/chunk.js">svelte chunk</a>
      <a href="/api/thing">api</a>
    `));
    const r = validateSSGOutput({ buildDir: build, projectDir: proj, checkLocales: false, checketzhayyimRoutes: false });
    expect(r.summary.brokenLinks).toBe(0);
  });

  it("strict mode fails when only warnings exist", async () => {
    await file("index.html", html(`<a href="/missing">x</a>`));
    const r = validateSSGOutput({ buildDir: build, projectDir: proj, checkLocales: false, checketzhayyimRoutes: false, strict: true });
    expect(r.ok).toBe(false);
  });
});

// ── locale routes ────────────────────────────────────────────────────────────

describe("validateSSGOutput — locale routes", () => {
  async function inlang(tags: string[], source: string) {
    const dir = join(proj, "project.inlang");
    await mkdir(dir, { recursive: true });
    await writeFile(join(dir, "settings.json"),
      JSON.stringify({ sourceLanguageTag: source, languageTags: tags }), "utf8");
  }

  it("counts found vs expected locales (base at /, others under prefix)", async () => {
    await inlang(["en", "ja"], "en");
    await file("index.html", html("home"));     // base en at /
    await file("ja/index.html", html("ホーム")); // ja prefix
    const r = validateSSGOutput({ buildDir: build, projectDir: proj, checkLinks: false, checketzhayyimRoutes: false });
    expect(r.summary.localesExpected).toBe(2);
    expect(r.summary.localesFound).toBe(2);
  });

  it("reports a missing locale route as an error", async () => {
    await inlang(["en", "fr"], "en");
    await file("index.html", html("home"));     // en present, fr missing
    const r = validateSSGOutput({ buildDir: build, projectDir: proj, checkLinks: false, checketzhayyimRoutes: false });
    expect(r.summary.localesFound).toBeLessThan(r.summary.localesExpected);
    expect(r.ok).toBe(false);
    expect(r.issues.some((i) => i.check === "locale-routes" && i.level === "error")).toBe(true);
  });
});

// ── required paths ───────────────────────────────────────────────────────────

describe("validateSSGOutput — requiredPaths", () => {
  it("errors when a required path is absent and passes when present", async () => {
    await file("index.html", html("home"));
    const missing = validateSSGOutput({
      buildDir: build, projectDir: proj, checkLocales: false, checkLinks: false,
      checketzhayyimRoutes: false, requiredPaths: ["sitemap.xml"],
    });
    expect(missing.ok).toBe(false);

    await file("sitemap.xml", "<urlset/>");
    const ok = validateSSGOutput({
      buildDir: build, projectDir: proj, checkLocales: false, checkLinks: false,
      checketzhayyimRoutes: false, requiredPaths: ["sitemap.xml"],
    });
    expect(ok.ok).toBe(true);
  });
});

// ── formatResult ─────────────────────────────────────────────────────────────

describe("formatResult", () => {
  it("renders PASS with summary lines", () => {
    const out = formatResult({
      ok: true, issues: [],
      summary: { localesExpected: 2, localesFound: 2, htmlFilesScanned: 5, brokenLinks: 0 },
    });
    expect(out).toContain("Locales: 2/2 found");
    expect(out).toContain("HTML files scanned: 5");
    expect(out).toContain("[ssg-validate] PASS");
  });

  it("renders FAIL with grouped errors + warnings and truncates >20 warnings", () => {
    const warnings = Array.from({ length: 25 }, (_, i) => ({
      level: "warning" as const, check: "internal-links", message: `w${i}`,
    }));
    const out = formatResult({
      ok: false,
      issues: [{ level: "error", check: "build-dir", message: "boom" }, ...warnings],
      summary: { localesExpected: 0, localesFound: 0, htmlFilesScanned: 1, brokenLinks: 25 },
    });
    expect(out).toContain("ERRORS (1):");
    expect(out).toContain("[build-dir] boom");
    expect(out).toContain("WARNINGS (25):");
    expect(out).toContain("... and 5 more");
    expect(out).toContain("[ssg-validate] FAIL");
  });
});
