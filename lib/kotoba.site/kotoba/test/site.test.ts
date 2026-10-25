import { describe, it, expect, beforeEach } from "vitest";
import { MockEtzhayyim } from "@etzhayyim/sdk-mock";
import {
  registerTopic,
  getTopic,
  listTopics,
  registerDomain,
  getDomain,
  listDomains,
  registerPage,
  getPage,
  listPages,
  registerWat,
  listWat,
  recordFollowerEvent,
  listFollowerEvents,
  getFollowerEvent,
  coverage,
} from "../src/index.js";

const OWNER = "did:web:site.etzhayyim.com";

describe("site kotoba (Internet Clone Gateway product front)", () => {
  let e: any;
  beforeEach(() => {
    e = new MockEtzhayyim({ did: OWNER });
  });

  describe("topic (PLAINTEXT catalog)", () => {
    it("registers, dedups, gets, lists/filters by category", async () => {
      expect((await registerTopic(e, { slug: "technology", topic: "Technology", category: "general" })).status).toBe("registered");
      expect((await registerTopic(e, { slug: "technology", topic: "Technology" })).status).toBe("alreadyExists");
      expect((await registerTopic(e, { slug: "", topic: "x" })).status).toBe("rejected");
      await registerTopic(e, { slug: "jp_classics", topic: "Japanese Classics", category: "literature" });
      expect((await getTopic(e, { slug: "technology" })).topic?.topic).toBe("Technology");
      expect((await getTopic(e, { slug: "nope" })).error).toBe("notFound");
      expect((await listTopics(e)).total).toBe(2);
      expect((await listTopics(e, { category: "general" })).total).toBe(1);
    });
  });

  describe("domain (PLAINTEXT catalog)", () => {
    it("registers, dedups, validates pageCount, lists/filters by topic", async () => {
      expect((await registerDomain(e, { domain: "example.com", tld: "com", pageCount: 12, topics: ["technology"] })).status).toBe("registered");
      expect((await registerDomain(e, { domain: "example.com" })).status).toBe("alreadyExists");
      expect((await registerDomain(e, { domain: "bad.com", pageCount: -1 })).status).toBe("rejected");
      await registerDomain(e, { domain: "lit.jp", topics: ["jp_classics"] });
      expect((await getDomain(e, { domain: "example.com" })).domain?.pageCount).toBe(12);
      expect((await listDomains(e)).total).toBe(2);
      expect((await listDomains(e, { topic: "technology" })).total).toBe(1);
    });
  });

  describe("page (PLAINTEXT catalog, FK → domain via exists)", () => {
    it("rejects page for unknown domain, registers once domain exists, dedups, lists", async () => {
      expect((await registerPage(e, { url: "https://example.com/a", domain: "example.com" })).status).toBe("rejected"); // unknownDomain
      await registerDomain(e, { domain: "example.com", topics: ["technology"] });
      expect((await registerPage(e, { url: "https://example.com/a", domain: "example.com", title: "A", statusCode: 200, topics: ["technology"] })).status).toBe("registered");
      expect((await registerPage(e, { url: "https://example.com/a", domain: "example.com" })).status).toBe("alreadyExists");
      expect((await registerPage(e, { url: "https://example.com/b", domain: "example.com", statusCode: -5 })).status).toBe("rejected"); // invalidStatusCode
      await registerPage(e, { url: "https://example.com/c", domain: "example.com" });
      expect((await getPage(e, { url: "https://example.com/a" })).page?.title).toBe("A");
      expect((await listPages(e, { domain: "example.com" })).total).toBe(2);
    });
  });

  describe("wat (PLAINTEXT link-graph metadata)", () => {
    it("registers, dedups, validates outlinkCount, lists/filters by domain", async () => {
      expect((await registerWat(e, { url: "https://example.com/a", domain: "example.com", outlinkCount: 7, statusCode: 200 })).status).toBe("registered");
      expect((await registerWat(e, { url: "https://example.com/a", domain: "example.com" })).status).toBe("alreadyExists");
      expect((await registerWat(e, { url: "https://example.com/x", domain: "example.com", outlinkCount: -1 })).status).toBe("rejected");
      await registerWat(e, { url: "https://other.org/z", domain: "other.org" });
      expect((await listWat(e)).total).toBe(2);
      expect((await listWat(e, { domain: "example.com" })).total).toBe(1);
    });
  });

  describe("followerEvent (E2E-ENCRYPTED message-metadata)", () => {
    it("seals via encryptedWrite, round-trips via encryptedRead, validates", async () => {
      const ok = await recordFollowerEvent(e, { eventId: "ev1", followerDid: "did:web:handotai.etzhayyim.com", topicSlug: "technology", action: "follow" });
      expect(ok.status).toBe("recorded");
      expect(ok.keyId).toBeTruthy();
      expect((await recordFollowerEvent(e, { eventId: "evX", followerDid: "", topicSlug: "t", action: "follow" })).status).toBe("rejected");
      const got = await getFollowerEvent(e, { eventId: "ev1" });
      expect(got.event?.followerDid).toBe("did:web:handotai.etzhayyim.com");
      expect(got.event?.topicSlug).toBe("technology");
      await recordFollowerEvent(e, { eventId: "ev2", followerDid: "did:web:f2", topicSlug: "science", action: "unfollow" });
      expect((await listFollowerEvents(e)).total).toBe(2);
      expect((await listFollowerEvents(e, { topicSlug: "technology" })).total).toBe(1);
    });

    it("enforces read-cap: a non-recipient DID cannot decrypt the event", async () => {
      await recordFollowerEvent(e, { eventId: "ev1", followerDid: "did:web:f1", topicSlug: "technology", action: "follow" });
      const outsider: any = new MockEtzhayyim({ did: "did:web:outsider.example" });
      expect((await listFollowerEvents(outsider)).total).toBe(0);
    });

    it("grants read-cap to an explicit recipient", async () => {
      const partner = "did:web:partner.example";
      const r = await recordFollowerEvent(e, { eventId: "ev1", followerDid: "did:web:f1", topicSlug: "technology", action: "follow", recipients: [partner] });
      expect(r.status).toBe("recorded");
      expect((await listFollowerEvents(e)).total).toBe(1);
    });
  });

  describe("coverage rollup", () => {
    it("counts plaintext catalog + E2E follower events", async () => {
      await registerTopic(e, { slug: "technology", topic: "Technology" });
      await registerDomain(e, { domain: "example.com", topics: ["technology"] });
      await registerPage(e, { url: "https://example.com/a", domain: "example.com" });
      await registerPage(e, { url: "https://example.com/b", domain: "example.com" });
      await registerWat(e, { url: "https://example.com/a", domain: "example.com", outlinkCount: 3 });
      await recordFollowerEvent(e, { eventId: "ev1", followerDid: "did:web:f1", topicSlug: "technology", action: "follow" });
      const cov = await coverage(e);
      expect(cov.topicCount).toBe(1);
      expect(cov.domainCount).toBe(1);
      expect(cov.pageCount).toBe(2);
      expect(cov.watCount).toBe(1);
      expect(cov.followerEventCount).toBe(1);
      expect(cov.pagesByDomain?.["example.com"]).toBe(2);
    });
  });
});
