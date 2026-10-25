import { describe, expect, it } from "vitest";
import {
  appNamespace,
  defaultAppCollection,
  wLexiconCollection,
  resolveFlatDispatchMethod,
  resolveXrpcMethod,
} from "../src/index.js";

const SITE_NS = appNamespace("site");
const SITE_ARTICLE = defaultAppCollection("site", "Article");
const SITE_LIST = `${SITE_NS}.list`;
const SITE_COLLECT_AOZORA = `${SITE_NS}.collectAozora`;
const W_MESSAGE = wLexiconCollection("message");

describe("nsid app helpers", () => {
  it("builds app namespace and default collection", () => {
    expect(appNamespace("site")).toBe(SITE_NS);
    expect(defaultAppCollection("site", "Article")).toBe(SITE_ARTICLE);
  });

  it("builds w lexicon collection", () => {
    expect(wLexiconCollection("message")).toBe(W_MESSAGE);
  });
});

describe("flat dispatch resolution", () => {
  it("resolves flat method to canonical app nsid", () => {
    const registered = [
      SITE_COLLECT_AOZORA,
      SITE_LIST,
    ];
    expect(resolveFlatDispatchMethod("collect_aozora_site", registered)).toBe(SITE_COLLECT_AOZORA);
  });

  it("returns null when flat method does not match", () => {
    const registered = [SITE_COLLECT_AOZORA];
    expect(resolveFlatDispatchMethod("collect_aozora_news", registered)).toBeNull();
  });
});

describe("xrpc method resolver", () => {
  it("prefers direct nsid match", () => {
    const m = new Map<string, number>([
      [SITE_LIST, 1],
      [SITE_COLLECT_AOZORA, 2],
    ]);
    expect(resolveXrpcMethod(SITE_LIST, m)).toBe(1);
  });

  it("falls back to flat dispatcher match", () => {
    const m = new Map<string, number>([
      [SITE_COLLECT_AOZORA, 2],
    ]);
    expect(resolveXrpcMethod("collect_aozora_site", m)).toBe(2);
  });
});
