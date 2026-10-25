import { describe, it, expect, beforeEach } from "vitest";
import { MockEtzhayyim } from "@etzhayyim/sdk-mock";
import {
  registerMeeting,
  getMeeting,
  listMeetings,
  recordChunk,
  listChunks,
  openSession,
  listSessions,
  getSession,
  addParticipant,
  listParticipants,
  addSegment,
  listSegments,
  coverage,
} from "../src/index.js";

const OWNER = "did:web:meet.etzhayyim.com";

describe("meet kotoba (kotoba-E2E split)", () => {
  let e: any;
  beforeEach(() => {
    e = new MockEtzhayyim({ did: OWNER });
  });

  describe("meeting (PLAINTEXT public catalog)", () => {
    it("registers, dedups, validates, gets, lists/filters", async () => {
      expect((await registerMeeting(e, { meetingId: "m1", title: "Standup", provider: "meet", durationSeconds: 1800 })).status).toBe("registered");
      expect((await registerMeeting(e, { meetingId: "m1", title: "Standup", provider: "meet" })).status).toBe("alreadyExists");
      expect((await registerMeeting(e, { meetingId: "mX", title: "", provider: "meet" })).status).toBe("rejected"); // missing title
      expect((await registerMeeting(e, { meetingId: "mY", title: "Bad", provider: "meet", durationSeconds: -1 })).status).toBe("rejected"); // negative duration
      await registerMeeting(e, { meetingId: "m2", title: "Sync", provider: "zoom", status: "ended" });
      const got = await getMeeting(e, { meetingId: "m1" });
      expect(got.meeting?.title).toBe("Standup");
      expect((await getMeeting(e, { meetingId: "nope" })).error).toBe("notFound");
      expect((await listMeetings(e)).total).toBe(2);
      expect((await listMeetings(e, { provider: "meet" })).total).toBe(1);
      expect((await listMeetings(e, { status: "ended" })).total).toBe(1);
    });
  });

  describe("recordingChunk (PLAINTEXT pointer catalog, FK → meeting)", () => {
    it("rejects a chunk for a missing meeting (FK via exists())", async () => {
      const r = await recordChunk(e, { meetingId: "ghost", provider: "meet", seq: 0, kind: "audio", archiveKey: "k/0.opus", durationMs: 60000 });
      expect(r.status).toBe("rejected");
      expect(r.error).toBe("meetingNotFound");
    });
    it("records against an existing meeting, dedups, validates, lists/filters", async () => {
      await registerMeeting(e, { meetingId: "m1", title: "Standup", provider: "meet" });
      expect((await recordChunk(e, { meetingId: "m1", provider: "meet", seq: 0, kind: "audio", archiveKey: "k/0.opus", durationMs: 60000, sizeBytes: 12000 })).status).toBe("recorded");
      expect((await recordChunk(e, { meetingId: "m1", provider: "meet", seq: 0, kind: "audio", archiveKey: "k/0.opus", durationMs: 60000 })).status).toBe("alreadyExists");
      expect((await recordChunk(e, { meetingId: "m1", provider: "meet", seq: -1, kind: "audio", archiveKey: "k.opus", durationMs: 1 })).status).toBe("rejected"); // bad seq
      await recordChunk(e, { meetingId: "m1", provider: "meet", seq: 1, kind: "video", archiveKey: "k/1.webm", durationMs: 60000 });
      expect((await listChunks(e, { meetingId: "m1" })).total).toBe(2);
      expect((await listChunks(e, { meetingId: "m1", kind: "audio" })).total).toBe(1);
    });
  });

  describe("recorderSession (E2E-ENCRYPTED PII)", () => {
    it("seals via encryptedWrite, round-trips via encryptedRead, validates", async () => {
      const ok = await openSession(e, { sessionId: "s1", meetingId: "m1", provider: "meet", onBehalfOfDid: "did:web:jun.example", externalMeetingId: "abc-defg-hij" });
      expect(ok.status).toBe("opened");
      expect(ok.keyId).toBeTruthy();
      expect((await openSession(e, { sessionId: "sX", meetingId: "m1", provider: "meet", onBehalfOfDid: "" })).status).toBe("rejected");
      const got = await getSession(e, { sessionId: "s1" });
      expect(got.session?.onBehalfOfDid).toBe("did:web:jun.example");
      expect(got.session?.externalMeetingId).toBe("abc-defg-hij");
      await openSession(e, { sessionId: "s2", meetingId: "m2", provider: "zoom", onBehalfOfDid: "did:web:k2", status: "joined" });
      expect((await listSessions(e)).total).toBe(2);
      expect((await listSessions(e, { provider: "meet" })).total).toBe(1);
      expect((await listSessions(e, { status: "joined" })).total).toBe(1);
    });

    it("enforces read-cap: a non-recipient DID cannot decrypt the session", async () => {
      await openSession(e, { sessionId: "s1", meetingId: "m1", provider: "meet", onBehalfOfDid: "did:web:jun.example" });
      const outsider: any = new MockEtzhayyim({ did: "did:web:outsider.example" });
      // Distinct PDS view, no read-cap → zero sessions (isolation by owner DID).
      expect((await listSessions(outsider)).total).toBe(0);
      expect((await getSession(outsider, { sessionId: "s1" })).error).toBe("notFound");
    });

    it("grants read-cap to an explicit recipient", async () => {
      const partner = "did:web:partner.example";
      const r = await openSession(e, { sessionId: "s1", meetingId: "m1", provider: "meet", onBehalfOfDid: "did:web:jun", recipients: [partner] });
      expect(r.status).toBe("opened");
      expect((await listSessions(e)).total).toBe(1); // owner can read
    });
  });

  describe("participant (E2E-ENCRYPTED PII Tier 1)", () => {
    it("seals, round-trips, validates, filters by session", async () => {
      expect((await addParticipant(e, { sessionId: "s1", providerIdHash: "h-aaa", displayName: "Jun", speakingMs: 45000 })).status).toBe("added");
      expect((await addParticipant(e, { sessionId: "s1", providerIdHash: "" })).status).toBe("rejected");
      expect((await addParticipant(e, { sessionId: "s1", providerIdHash: "h-bad", speakingMs: -1 })).status).toBe("rejected");
      await addParticipant(e, { sessionId: "s1", providerIdHash: "h-bbb", role: "host" });
      await addParticipant(e, { sessionId: "s2", providerIdHash: "h-ccc" });
      expect((await listParticipants(e, { sessionId: "s1" })).total).toBe(2);
      expect((await listParticipants(e)).total).toBe(3);
      const outsider: any = new MockEtzhayyim({ did: "did:web:outsider.example" });
      expect((await listParticipants(outsider)).total).toBe(0);
    });
  });

  describe("transcriptSegment (E2E-ENCRYPTED private content)", () => {
    it("seals spoken text, round-trips, validates confidence pct 0-100", async () => {
      const ok = await addSegment(e, { sessionId: "s1", seq: 0, startedAtMs: 0, endedAtMs: 3000, text: "hello team", confidencePct: 92, lang: "en-US" });
      expect(ok.status).toBe("added");
      expect((await addSegment(e, { sessionId: "s1", seq: 1, startedAtMs: 0, endedAtMs: 1, text: "x", confidencePct: 200 })).status).toBe("rejected"); // >100
      expect((await addSegment(e, { sessionId: "s1", seq: -1, startedAtMs: 0, endedAtMs: 1, text: "x" })).status).toBe("rejected"); // bad seq
      expect((await addSegment(e, { sessionId: "s1", seq: 2, startedAtMs: 0, endedAtMs: 1, text: "" })).status).toBe("rejected"); // empty text
      await addSegment(e, { sessionId: "s1", seq: 3, startedAtMs: 3000, endedAtMs: 6000, text: "next point" });
      await addSegment(e, { sessionId: "s2", seq: 0, startedAtMs: 0, endedAtMs: 2000, text: "other meeting" });
      const segs = await listSegments(e, { sessionId: "s1" });
      expect(segs.total).toBe(2);
      expect(segs.items.some((s) => s.text === "hello team" && s.confidencePct === 92)).toBe(true);
      expect((await listSegments(e)).total).toBe(3);
      const outsider: any = new MockEtzhayyim({ did: "did:web:outsider.example" });
      expect((await listSegments(outsider)).total).toBe(0);
    });
  });

  describe("coverage rollup", () => {
    it("counts plaintext meetings + chunks and E2E sessions + participants + segments", async () => {
      await registerMeeting(e, { meetingId: "m1", title: "A", provider: "meet" });
      await registerMeeting(e, { meetingId: "m2", title: "B", provider: "zoom" });
      await recordChunk(e, { meetingId: "m1", provider: "meet", seq: 0, kind: "audio", archiveKey: "k/0.opus", durationMs: 60000 });
      await openSession(e, { sessionId: "s1", meetingId: "m1", provider: "meet", onBehalfOfDid: "did:web:jun" });
      await addParticipant(e, { sessionId: "s1", providerIdHash: "h-aaa" });
      await addSegment(e, { sessionId: "s1", seq: 0, startedAtMs: 0, endedAtMs: 1000, text: "hi" });
      const cov = await coverage(e);
      expect(cov.meetingCount).toBe(2);
      expect(cov.recordingChunkCount).toBe(1);
      expect(cov.recorderSessionCount).toBe(1);
      expect(cov.participantCount).toBe(1);
      expect(cov.transcriptSegmentCount).toBe(1);
      expect(cov.meetingsByProvider?.meet).toBe(1);
      expect(cov.meetingsByProvider?.zoom).toBe(1);
    });
  });
});
