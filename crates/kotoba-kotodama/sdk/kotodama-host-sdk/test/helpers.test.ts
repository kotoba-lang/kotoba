// helpers.test.ts — Tests for shared utility functions and request cache.

import { describe, it, expect } from "vitest";
import { toSnake, toKebab, toPascal, humanizeIdentifier, inferCommandVerb, normalizeTag, dedupeStrings, firstNonEmpty, parseUrl, respondJson } from "../src/helpers.js";
import { makeRLSMeta } from "../src/app.js";
import type { AppContext } from "../src/types.js";

describe("toSnake", () => {
  it("converts camelCase to snakeCase", () => {
    expect(toSnake("generateArticle")).toBe("generate_article");
  });

  it("converts PascalCase to snakeCase", () => {
    expect(toSnake("GenerateArticle")).toBe("generate_article");
  });

  it("leaves snakeCase unchanged", () => {
    expect(toSnake("generate_article")).toBe("generate_article");
  });

  it("handles single word", () => {
    expect(toSnake("test")).toBe("test");
  });
});

describe("toKebab", () => {
  it("converts camelCase to kebab-case", () => {
    expect(toKebab("generateArticle")).toBe("generate-article");
  });

  it("converts PascalCase to kebab-case", () => {
    expect(toKebab("GenerateArticle")).toBe("generate-article");
  });
});

describe("toPascal", () => {
  it("converts snakeCase to PascalCase", () => {
    expect(toPascal("generateArticle")).toBe("GenerateArticle");
  });

  it("converts kebab-case to PascalCase", () => {
    expect(toPascal("generate-article")).toBe("GenerateArticle");
  });
});

describe("humanizeIdentifier", () => {
  it("converts camelCase to space-separated words", () => {
    expect(humanizeIdentifier("generateArticle")).toBe("generate article");
  });

  it("converts kebab-case to space-separated words", () => {
    expect(humanizeIdentifier("generate-article")).toBe("generate article");
  });
});

describe("inferCommandVerb", () => {
  it("extracts first word from snakeCase", () => {
    expect(inferCommandVerb("generateArticle")).toBe("generate");
  });

  it("extracts first word from camelCase via snake conversion", () => {
    expect(inferCommandVerb("generateArticle")).toBe("generate");
  });
});

describe("normalizeTag", () => {
  it("converts spaces to hyphens", () => {
    expect(normalizeTag("my tag")).toBe("my-tag");
  });

  it("trims and normalizes", () => {
    expect(normalizeTag("  Test App  ")).toBe("test-app");
  });

  it("returns empty for empty input", () => {
    expect(normalizeTag("")).toBe("");
    expect(normalizeTag("  ")).toBe("");
  });
});

describe("dedupeStrings", () => {
  it("removes duplicate strings", () => {
    expect(dedupeStrings(["a", "b", "a", "c"])).toEqual(["a", "b", "c"]);
  });

  it("filters empty strings", () => {
    expect(dedupeStrings(["a", "", "b", ""])).toEqual(["a", "b"]);
  });

  it("preserves order", () => {
    expect(dedupeStrings(["c", "b", "a"])).toEqual(["c", "b", "a"]);
  });
});

describe("firstNonEmpty", () => {
  it("returns first non-empty string", () => {
    expect(firstNonEmpty("", "  ", "hello", "world")).toBe("hello");
  });

  it("returns empty if all empty", () => {
    expect(firstNonEmpty("", "  ")).toBe("");
  });
});

describe("parseUrl", () => {
  it("extracts path and query", () => {
    expect(parseUrl("/api/test?foo=bar")).toEqual({ path: "/api/test", query: "foo=bar" });
  });

  it("handles no query string", () => {
    expect(parseUrl("/api/test")).toEqual({ path: "/api/test", query: "" });
  });
});

describe("respondJson", () => {
  it("returns correctly shaped response", () => {
    const res = respondJson(200, { ok: true });
    expect(res.status).toBe(200);
    expect(res.headers).toEqual([["content-type", "application/json"]]);
    const body = JSON.parse(new TextDecoder().decode(res.body));
    expect(body.ok).toBe(true);
  });

  it("encodes error responses", () => {
    const res = respondJson(404, { error: "not found" });
    expect(res.status).toBe(404);
    const body = JSON.parse(new TextDecoder().decode(res.body));
    expect(body.error).toBe("not found");
  });
});

describe("makeRLSMeta", () => {
  it("creates RLS meta from context", () => {
    const ctx: AppContext = {
      orgId: "org-1",
      userId: "user-1",
      actorId: "actor-1",
      convoId: "",
      appId: "test",
      now: "2026-03-25T00:00:00Z",
    };
    const rls = makeRLSMeta(ctx);
    expect(rls.orgId).toBe("org-1");
    expect(rls.userId).toBe("user-1");
    expect(rls.actorId).toBe("actor-1");
    expect(rls.createdAt).toBe("2026-03-25T00:00:00Z");
    expect(rls.updatedAt).toBe("2026-03-25T00:00:00Z");
  });
});
