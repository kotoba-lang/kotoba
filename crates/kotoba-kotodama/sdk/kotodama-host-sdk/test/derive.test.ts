/**
 * Unit tests for the derive template resolver.
 * Focus on the expression set actually used by DERIVE_RULES (mangaka chapter/page).
 */
import { describe, it, expect, beforeEach } from "vitest";
import { resolveValue, resolveFacetIndices, type TemplateContext, type SelfRef } from "../src/derive/template.js";
import { DERIVE_RULES, rulesForCollection } from "../src/derive/registry.js";
import { recordLink, getLink, clearLinks, linkCount } from "../src/derive/state.js";

function makeCtx(record: Record<string, unknown>, selfUri = "at://mng4k4x1.etzhayyim.com/com.etzhayyim.apps.mangaka.chapter/tid1", selfCid = "bafyTestCid"): TemplateContext {
  return { record, self: { uri: selfUri, cid: selfCid }, repo: "did:web:mangaka.etzhayyim.com", derivedPosts: {} };
}

describe("resolveValue — scalar templates", () => {
  it("resolves {{record.field}} on plain strings", () => {
    const out = resolveValue("hello {{record.name}}", makeCtx({ name: "Tamaki" }));
    expect(out).toBe("hello Tamaki");
  });

  it("resolves {{self.uri}} and {{self.cid}} passthrough", () => {
    const ctx = makeCtx({}, "at://did:web:x/y/z", "bafy123");
    expect(resolveValue("uri={{self.uri}} cid={{self.cid}}", ctx)).toBe("uri=at://did:web:x/y/z cid=bafy123");
  });

  it("resolves tagFromVolume helper", () => {
    const out = resolveValue("#{{tagFromVolume record.volumeId}}", makeCtx({ volumeId: "vol01-loneliness" }));
    expect(out).toBe("#sip-vol1");
  });

  it("resolves resolve(ref).workDid to at-uri authority", () => {
    const out = resolveValue("{{resolve(record.workRef).workDid}}", makeCtx({
      workRef: { uri: "at://mng4k4x1.etzhayyim.com/com.etzhayyim.apps.mangaka.work/abc", cid: "bafy" },
    }));
    expect(out).toBe("mng4k4x1.etzhayyim.com");
  });

  it("preserves whole-string structured values (SelfRef)", () => {
    const ctx = makeCtx({}, "at://x", "bafy");
    const embed = resolveValue({ uri: "{{self.uri}}", cid: "{{self.cid}}" }, ctx);
    expect(embed).toEqual({ uri: "at://x", cid: "bafy" });
  });

  it("returns empty-string stringification for missing path", () => {
    expect(resolveValue("<{{record.missing}}>", makeCtx({}))).toBe("<>");
  });
});

describe("resolveValue — _from/_each iteration", () => {
  it("expands array iteration over record.charactersAppearing", () => {
    const facets = [
      {
        _from: "record.charactersAppearing",
        _each: {
          index: { _matchText: "@{{item.displayName}}" },
          features: [{ $type: "app.bsky.richtext.facet#mention", did: "did:web:mangaka.etzhayyim.com:character:{{item.slug}}" }],
        },
      },
    ];
    const out = resolveValue(facets, makeCtx({
      charactersAppearing: [
        { slug: "tamaki", displayName: "Tamaki" },
        { slug: "nei",    displayName: "Nei" },
      ],
    }));
    expect(Array.isArray(out)).toBe(true);
    const arr = out as Array<Record<string, unknown>>;
    expect(arr).toHaveLength(2);
    expect((arr[0].index as Record<string, string>)._matchText).toBe("@Tamaki");
    expect(((arr[0].features as Array<Record<string, string>>)[0]).did).toBe("did:web:mangaka.etzhayyim.com:character:tamaki");
    expect(((arr[1].features as Array<Record<string, string>>)[0]).did).toBe("did:web:mangaka.etzhayyim.com:character:nei");
  });

  it("expands scalar string array via {{item}}", () => {
    const facets = [
      {
        _from: "record.arcIds",
        _each: {
          index: { _matchText: "#{{item}}" },
          features: [{ $type: "app.bsky.richtext.facet#tag", tag: "{{item}}" }],
        },
      },
    ];
    const out = resolveValue(facets, makeCtx({ arcIds: ["TamakiGrowth", "NeiChanDebt"] })) as Array<Record<string, unknown>>;
    expect(out).toHaveLength(2);
    expect((out[1].index as Record<string, string>)._matchText).toBe("#NeiChanDebt");
    expect(((out[1].features as Array<Record<string, string>>)[0]).tag).toBe("NeiChanDebt");
  });

  it("produces empty output when _from resolves to non-array", () => {
    const facets = [{ _from: "record.missing", _each: { x: "{{item}}" } }];
    const out = resolveValue(facets, makeCtx({})) as unknown[];
    expect(out).toEqual([]);
  });
});

describe("resolveFacetIndices — byteStart/byteEnd", () => {
  it("locates ASCII _matchText", () => {
    const text = "hello #sip-vol1 world";
    const facets = [{ index: { _matchText: "#sip-vol1" }, features: [{ $type: "tag", tag: "sip-vol1" }] }];
    const out = resolveFacetIndices(facets, text);
    expect(out).toHaveLength(1);
    expect(out[0].index).toEqual({ byteStart: 6, byteEnd: 15 });
  });

  it("locates UTF-8 Japanese _matchText with correct byte offsets", () => {
    const text = "📖 新章公開  vol01-loneliness ch.1 — 第1話";
    // "第1話" starts after "ch.1 — " — needs byte offsets, not char offsets
    const facets = [{ index: { _matchText: "第1話" }, features: [{ $type: "tag" }] }];
    const out = resolveFacetIndices(facets, text);
    expect(out).toHaveLength(1);
    const enc = new TextEncoder();
    expect(enc.encode(text).slice(out[0].index.byteStart, out[0].index.byteEnd)).toEqual(enc.encode("第1話"));
  });

  it("drops facet when _matchText is not found in text", () => {
    const out = resolveFacetIndices(
      [{ index: { _matchText: "not-present" }, features: [{ $type: "tag" }] }],
      "text without the needle",
    );
    expect(out).toEqual([]);
  });

  it("passes through pre-resolved byteStart/byteEnd facets", () => {
    const out = resolveFacetIndices(
      [{ index: { byteStart: 3, byteEnd: 7 }, features: [{ $type: "link" }] }],
      "ignored-by-passthrough",
    );
    expect(out).toEqual([{ index: { byteStart: 3, byteEnd: 7 }, features: [{ $type: "link" }] }]);
  });
});

describe("derived(ref).strongRef resolution", () => {
  beforeEach(() => clearLinks());

  it("returns null when no link is recorded", () => {
    const ctx: TemplateContext = {
      record: { chapterRef: { uri: "at://a/b/c", cid: "bafy-c" } },
      self: { uri: "at://self", cid: "bafy-self" },
      repo: "did:web:x",
      resolveDerivedPost: (u) => getLink(u),
    };
    const r = resolveValue("{{derived(record.chapterRef).strongRef}}", ctx);
    expect(r).toBeNull();
  });

  it("returns recorded link via in-memory callback", () => {
    const chapterUri = "at://mng4k4x1.etzhayyim.com/com.etzhayyim.apps.mangaka.chapter/ch01";
    const postRef: SelfRef = { uri: "at://mng4k4x1.etzhayyim.com/app.bsky.feed.post/tid-ch01-post", cid: "bafy-post-cid" };
    recordLink(chapterUri, postRef);
    expect(linkCount()).toBe(1);

    const ctx: TemplateContext = {
      record: { chapterRef: { uri: chapterUri, cid: "bafy-ch-cid" } },
      self: { uri: "at://self", cid: "bafy-self" },
      repo: "did:web:mangaka.etzhayyim.com",
      resolveDerivedPost: (u) => getLink(u),
    };
    const r = resolveValue("{{derived(record.chapterRef).strongRef}}", ctx);
    expect(r).toEqual(postRef);
  });

  it("pre-resolved derivedPosts map wins over callback", () => {
    const chapterUri = "at://x/y/chapter1";
    const mapRef: SelfRef = { uri: "at://map-wins", cid: "map-cid" };
    const callbackRef: SelfRef = { uri: "at://callback", cid: "cb-cid" };
    recordLink(chapterUri, callbackRef);
    const ctx: TemplateContext = {
      record: { chapterRef: { uri: chapterUri, cid: "x" } },
      self: { uri: "at://self", cid: "s" },
      repo: "r",
      derivedPosts: { [chapterUri]: mapRef },
      resolveDerivedPost: (u) => getLink(u),
    };
    expect(resolveValue("{{derived(record.chapterRef).strongRef}}", ctx)).toEqual(mapRef);
  });

  it("page-published-social reply resolves once chapter link is recorded", () => {
    const chapterUri = "at://mng4k4x1.etzhayyim.com/com.etzhayyim.apps.mangaka.chapter/sip-vol01-loneliness-ch01";
    const chapterPostRef: SelfRef = { uri: "at://mng4k4x1.etzhayyim.com/app.bsky.feed.post/tid-post-1", cid: "bafy-p1" };
    recordLink(chapterUri, chapterPostRef);

    const rule = DERIVE_RULES.find((r) => r.id === "page-published-social")!;
    const pageRecord = {
      chapterRef: { uri: chapterUri, cid: "bafy-ch-cid" },
      pageNum: 3,
      compositedImageCid: "bafy-page-png",
      altText: "Page 3 — tamaki reunites with nei",
      width: 1080, height: 1920,
      charactersAppearing: [{ slug: "tamaki", displayName: "Tamaki" }],
    };
    const ctx: TemplateContext = {
      record: pageRecord,
      self: { uri: "at://mng4k4x1.etzhayyim.com/com.etzhayyim.apps.mangaka.page/p3", cid: "bafy-p3-cid" },
      repo: "did:web:mangaka.etzhayyim.com",
      resolveDerivedPost: (u) => getLink(u),
    };
    const reply = resolveValue(rule.emit.reply, ctx) as { root: SelfRef; parent: SelfRef };
    expect(reply.root).toEqual(chapterPostRef);
    expect(reply.parent).toEqual(chapterPostRef);
  });

  it("recordLink CAP evicts oldest", () => {
    // small stress — insert 10 entries then ensure later ones win
    for (let i = 0; i < 10; i++) recordLink(`at://x/${i}`, { uri: `post-${i}`, cid: `cid-${i}` });
    expect(linkCount()).toBe(10);
    expect(getLink("at://x/0")).toEqual({ uri: "post-0", cid: "cid-0" });
    expect(getLink("at://x/9")).toEqual({ uri: "post-9", cid: "cid-9" });
  });
});

describe("DERIVE_RULES registry + end-to-end chapter commit", () => {
  it("rulesForCollection finds mangaka chapter rule", () => {
    const rules = rulesForCollection("com.etzhayyim.apps.mangaka.chapter");
    expect(rules).toHaveLength(1);
    expect(rules[0].id).toBe("chapter-published-social");
  });

  it("full resolution of chapter-published-social emits a valid post shape", () => {
    const rule = DERIVE_RULES.find((r) => r.id === "chapter-published-social")!;
    const record = {
      workRef: { uri: "at://mng4k4x1.etzhayyim.com/com.etzhayyim.apps.mangaka.work/spirit-in-physics", cid: "bafy-work" },
      chapterNum: 1,
      titleJP: "第1話 配属の日",
      volumeId: "vol01-loneliness",
      arcIds: ["TamakiGrowth"],
      charactersAppearing: [{ slug: "tamaki", displayName: "Tamaki" }, { slug: "nei", displayName: "Nei" }],
      coverCid: "bafy-cover-cid",
      coverAlt: "Vol1 cover",
      readerUri: "https://mangaka.etzhayyim.com/at/mng4k4x1.etzhayyim.com/com.etzhayyim.apps.mangaka.chapter/sip-vol01-loneliness-ch01",
      status: "published",
    };
    const ctx = makeCtx(record);

    const did = resolveValue(rule.emit.did, ctx);
    expect(did).toBe("mng4k4x1.etzhayyim.com");

    const text = resolveValue(rule.emit.text, ctx) as string;
    expect(text).toContain("📖 新章公開");
    expect(text).toContain("vol01-loneliness ch.1");
    expect(text).toContain("第1話 配属の日");
    expect(text).toContain("#sip-vol1");
    expect(text).toContain("https://mangaka.etzhayyim.com/at/");

    const facetsExpanded = resolveValue(rule.emit.facets, ctx);
    const facets = resolveFacetIndices(facetsExpanded, text);
    // 2 @mentions + 1 arc #tag + 1 volume #tag + 1 reader #link = 5
    expect(facets.length).toBe(5);
    const mentionFeatures = facets.flatMap((f) => f.features).filter((feat) => (feat as Record<string, string>).$type === "app.bsky.richtext.facet#mention");
    expect(mentionFeatures.map((f) => (f as Record<string, string>).did)).toEqual([
      "did:web:mangaka.etzhayyim.com:character:tamaki",
      "did:web:mangaka.etzhayyim.com:character:nei",
    ]);
    const tagFeatures = facets.flatMap((f) => f.features).filter((feat) => (feat as Record<string, string>).$type === "app.bsky.richtext.facet#tag");
    expect(tagFeatures.map((f) => (f as Record<string, string>).tag).sort()).toEqual(["TamakiGrowth", "sip-vol1"]);
    const linkFeatures = facets.flatMap((f) => f.features).filter((feat) => (feat as Record<string, string>).$type === "app.bsky.richtext.facet#link");
    expect(linkFeatures.length).toBe(1);
    expect((linkFeatures[0] as Record<string, string>).uri).toBe(record.readerUri);

    // embed simplified to images-only (no strongRef) — Kysely-direct writes don't have AT URI/CID
    const embed = resolveValue(rule.emit.embed, ctx) as Record<string, unknown>;
    expect(embed.$type).toBe("app.bsky.embed.images");
    const images = embed.images as Array<Record<string, unknown>>;
    expect(images[0].alt).toBe("Vol1 cover");
    const imgRef = (images[0].image as { ref?: { $link?: string } }).ref;
    expect(imgRef?.$link).toBe("bafy-cover-cid");
  });
});
