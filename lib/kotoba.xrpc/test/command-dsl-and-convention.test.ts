import { describe, expect, it, vi } from "vitest";
import {
  registerCommand,
  registerQuery,
  withWLexicon,
  resolveAutoCrudConvention,
  appNamespace,
  defaultAppCollection,
  wLexiconCollection,
} from "../src/index.js";

const SITE_NS = appNamespace("site");
const SITE_LIST = `${SITE_NS}.list`;
const SITE_SEARCH = `${SITE_NS}.search`;
const SITE_CREATE = `${SITE_NS}.create`;
const SITE_CUSTOM = `${SITE_NS}.custom`;
const SITE_ARTICLE = defaultAppCollection("site", "Article");
const W_SITE_LIST = wLexiconCollection("site-list");

describe("command dsl", () => {
  it("registers command into methodMap and wRoutes", () => {
    const entries: Array<{ name: string; handler: unknown; lexiconSuffix: string; note?: string }> = [];
    const methodMap = new Map<string, unknown>();
    const wRoutes = new Map<string, string>();
    const handler = vi.fn();

    registerCommand({
      entries,
      methodMap,
      wRoutes,
      entry: { name: SITE_LIST, handler, lexiconSuffix: "" },
      opts: [withWLexicon("site-list"), (e) => { e.note = "ok"; }],
    });

    expect(entries).toHaveLength(1);
    expect(methodMap.get(SITE_LIST)).toBe(handler);
    expect(wRoutes.get(W_SITE_LIST)).toBe(SITE_LIST);
    expect(entries[0].note).toBe("ok");
  });

  it("registers query into methodMap", () => {
    const entries: Array<{ name: string; handler: unknown }> = [];
    const methodMap = new Map<string, unknown>();
    const handler = vi.fn();

    registerQuery({ entries, methodMap, entry: { name: SITE_SEARCH, handler } });

    expect(entries).toEqual([{ name: SITE_SEARCH, handler }]);
    expect(methodMap.get(SITE_SEARCH)).toBe(handler);
  });
});

describe("autoCrud convention", () => {
  it("builds default command names and defaults", () => {
    const c = resolveAutoCrudConvention({ domain: "site", label: "Article" });
    expect(c.ns).toBe(SITE_NS);
    expect(c.collection).toBe(SITE_ARTICLE);
    expect(c.command.create).toBe(SITE_CREATE);
    expect(c.fields).toEqual(["name", "description"]);
    expect(c.statuses).toContain("active");
  });

  it("respects custom collection/fields/statuses", () => {
    const c = resolveAutoCrudConvention({
      domain: "site",
      label: "Article",
      collection: SITE_CUSTOM,
      searchFields: ["title"],
      statuses: ["active", "retired"],
    });
    expect(c.collection).toBe(SITE_CUSTOM);
    expect(c.fields).toEqual(["title"]);
    expect(c.statuses).toEqual(["active", "retired"]);
  });
});
