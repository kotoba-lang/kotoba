import { chromium } from "playwright";
import type { ExamplePortalHandle, ExamplePortalReadHeadingOutput, ExamplePortalSearchTermOutput } from "./tools.js";

export interface DefaultHandleOptions {
  baseUrl?: string;
}

export function createDefaultExamplePortalHandle(_opts: DefaultHandleOptions): ExamplePortalHandle {
  const handle: ExamplePortalHandle = {
  async read_heading(input) {
    const out: Record<string, unknown> = { ok: false };
    let browser;
    try {
      browser = await chromium.launch({ headless: true });
      const ctx = await browser.newContext();
      const page = await ctx.newPage();
      await page.goto("https://example.com/");
      await page.waitForSelector("h1", { timeout: 5000 });
      out["heading"] = (await page.locator("h1").first().textContent()) ?? undefined;
      out.ok = true;
    } catch (err) {
      out.error = (err as Error).message;
    } finally {
      try { await browser?.close(); } catch { /* noop */ }
    }
    return out as ExamplePortalReadHeadingOutput;
  },
  async search_term(input) {
    const out: Record<string, unknown> = { ok: false };
    let browser;
    try {
      browser = await chromium.launch({ headless: true });
      const ctx = await browser.newContext();
      const page = await ctx.newPage();
      await page.goto("https://example.com/search");
      await page.waitForSelector("input[name=q]", { timeout: 5000 });
      await page.fill("input[name=q]", String((input as Record<string, unknown>)["query"] ?? ""));
      await page.click("button[type=submit]");
      await page.waitForSelector(".result", { timeout: 8000 });
      await page.locator(".result:last-child").first().scrollIntoViewIfNeeded();
      out["result_titles"] = await page.locator(".result h2").allTextContents();
      out["result_count_label"] = (await page.locator(".result-count").first().textContent()) ?? undefined;
      out.ok = true;
    } catch (err) {
      out.error = (err as Error).message;
    } finally {
      try { await browser?.close(); } catch { /* noop */ }
    }
    return out as ExamplePortalSearchTermOutput;
  },
  };
  return handle;
}
