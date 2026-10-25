/**
 * @etzhayyim/vite-plugin-safe-builder — svelte5-compat tests (coverage loop iter 21).
 *
 * checkSvelteFile is the Svelte-4-anti-pattern detector the build runs over
 * component shims; a missed <slot> / `export let` / dropped snippet prop ships
 * a component whose snippets silently don't render. Pure (filePath, content) →
 * issues[]; zero tests. (Exported here purely for testing — no behavior change.)
 */
import { describe, it, expect } from "vitest";
import { checkSvelteFile } from "../src/svelte5-compat.ts";

const P = "/repo/src/lib/Foo.svelte";

// ── <slot> detection ─────────────────────────────────────────────────────────

describe("slot detection", () => {
  it("flags <slot /> and named slots", () => {
    expect(checkSvelteFile(P, "<slot />").join()).toMatch(/Svelte 4 <slot>/);
    expect(checkSvelteFile(P, '<slot name="header"></slot>').join()).toMatch(/<slot>/);
  });

  it("does not flag {@render} usage", () => {
    expect(checkSvelteFile(P, "{@render children()}")).toEqual([]);
  });
});

// ── export let detection ─────────────────────────────────────────────────────

// Svelte 4 `export let` props (detector matches `export let` at line start, m flag)
const exportLet = "<script>\nexport let name;\n</script>";

describe("export let detection", () => {
  it("flags `export let prop` on its own line", () => {
    const issues = checkSvelteFile(P, exportLet);
    expect(issues.join()).toMatch(/'export let' detected/);
  });

  it("does not flag export type / interface / const / $props", () => {
    expect(checkSvelteFile(P, "<script>\nexport type T = string;\n</script>")).toEqual([]);
    expect(checkSvelteFile(P, "<script>\nexport interface I {}\n</script>")).toEqual([]);
    expect(checkSvelteFile(P, "<script>\nconst { name } = $props();\n</script>")).toEqual([]);
  });
});

// ── required snippet props (known component names) ───────────────────────────

describe("required snippet props", () => {
  it("flags an AppShell shim that does not call $props()", () => {
    const issues = checkSvelteFile("/repo/src/AppShell.svelte", "<div>no props</div>");
    expect(issues.join()).toMatch(/does not use \$props\(\)/);
  });

  it("flags missing snippet props when $props() is present but a name is absent", () => {
    // Header requires left, right, children — provide only left+children
    const content = "<script>const { left, children } = $props();</script>{@render children()}";
    const issues = checkSvelteFile("/repo/src/Header.svelte", content);
    expect(issues.join()).toMatch(/missing snippet props: right/);
  });

  it("passes an AppShell shim that destructures all required snippet props", () => {
    const content = "<script>const { sidebar, header, footer, children } = $props();</script>";
    expect(checkSvelteFile("/repo/src/AppShell.svelte", content)).toEqual([]);
  });

  it("ignores snippet-prop rules for an unknown component name", () => {
    expect(checkSvelteFile("/repo/src/RandomThing.svelte", "<div>hi</div>")).toEqual([]);
  });
});

// ── combined / clean ─────────────────────────────────────────────────────────

describe("combined", () => {
  it("reports both slot and export let in one file", () => {
    const issues = checkSvelteFile(P, "<script>\nexport let x;\n</script>\n<slot />");
    expect(issues.length).toBe(2);
  });

  it("a clean Svelte 5 component yields no issues", () => {
    const content = "<script lang=\"ts\">const { items } = $props();</script>{@render items()}";
    expect(checkSvelteFile(P, content)).toEqual([]);
  });
});
