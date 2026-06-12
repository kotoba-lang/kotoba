import { describe, it, expect, vi, beforeEach } from "vitest";
import { OrganismPostDrainer, NDJSONRecord } from "../src/drainer/index.js";
import { Etzhayyim } from "@etzhayyim/sdk";

// Mock the entire SDK module
const mockWrite = vi.fn().mockResolvedValue(true);
vi.mock("@etzhayyim/sdk", () => {
  return {
    Etzhayyim: vi.fn().mockImplementation(() => ({
      write: mockWrite,
    })),
    // Mock named export 'signal' if it's used by the module under test
    signal: {
      establishSession: vi.fn(),
      wrapKey: vi.fn(),
    },
  };
});


describe("OrganismPostDrainer with Lifecycle Events", () => {
  const drainer = new OrganismPostDrainer("/tmp/dummy.ndjson", "http://localhost:2583");
  const actorDid = "did:web:test-actor";
  const now = new Date();
  const nowISO = now.toISOString();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  // Test for 'birth' lifecycle event
  it("should correctly dispatch a 'birth' lifecycle event", async () => {
    const birthEvent = {
      event: {
        type: "birth",
        sourceDid: "did:web:source",
        shard: "shard-1",
        curePeriod: 86400
      }
    };
    const record: NDJSONRecord = {
      v: 1,
      ts: now.getTime(),
      actorDid: actorDid,
      lexicon: "com.etzhayyim.organism.lifecycle",
      createdAt: nowISO,
      event: birthEvent.event
    };

    await drainer.processLine(JSON.stringify(record));

    expect(mockWrite).toHaveBeenCalledWith({
      collection: "com.etzhayyim.organism.lifecycle",
      record: {
        ...birthEvent.event,
        createdAt: nowISO,
      },
    });
  });

  // Test for 'clone' lifecycle event
  it("should correctly dispatch a 'clone' lifecycle event", async () => {
    const cloneEvent = {
      event: {
        type: "clone",
        sourceDid: "did:web:source",
        shard: "shard-2",
        curePeriod: 86400
      }
    };
    const record: NDJSONRecord = {
      v: 1,
      ts: now.getTime(),
      actorDid: actorDid,
      lexicon: "com.etzhayyim.organism.lifecycle",
      createdAt: nowISO,
      event: cloneEvent.event
    };

    await drainer.processLine(JSON.stringify(record));

    expect(mockWrite).toHaveBeenCalledWith({
      collection: "com.etzhayyim.organism.lifecycle",
      record: {
        ...cloneEvent.event,
        createdAt: nowISO,
      },
    });
  });

  // Test for 'retire' lifecycle event
  it("should correctly dispatch a 'retire' lifecycle event", async () => {
    const retireEvent = {
      event: {
        type: "retire",
        reason: "end_of_service"
      }
    };
    const record: NDJSONRecord = {
      v: 1,
      ts: now.getTime(),
      actorDid: actorDid,
      lexicon: "com.etzhayyim.organism.lifecycle",
      createdAt: nowISO,
      event: retireEvent.event
    };

    await drainer.processLine(JSON.stringify(record));

    expect(mockWrite).toHaveBeenCalledWith({
      collection: "com.etzhayyim.organism.lifecycle",
      record: {
        ...retireEvent.event,
        createdAt: nowISO,
      },
    });
  });

  // Test for 'excommunication' lifecycle event
  it("should correctly dispatch an 'excommunication' lifecycle event", async () => {
    const excommunicationEvent = {
      event: {
        type: "excommunication",
        reason: "policy_violation"
      }
    };
    const record: NDJSONRecord = {
      v: 1,
      ts: now.getTime(),
      actorDid: actorDid,
      lexicon: "com.etzhayyim.organism.lifecycle",
      createdAt: nowISO,
      event: excommunicationEvent.event
    };

    await drainer.processLine(JSON.stringify(record));

    expect(mockWrite).toHaveBeenCalledWith({
      collection: "com.etzhayyim.organism.lifecycle",
      record: {
        ...excommunicationEvent.event,
        createdAt: nowISO,
      },
    });
  });

  // Regression test for app.bsky.feed.post
  it("should still process app.bsky.feed.post records correctly", async () => {
    const postRecord = {
      v: 1,
      ts: now.getTime(),
      actorDid: actorDid,
      lexicon: "app.bsky.feed.post",
      text: "A regular post.",
      createdAt: nowISO
    };

    await drainer.processLine(JSON.stringify(postRecord));

    expect(mockWrite).toHaveBeenCalledWith({
      collection: "app.bsky.feed.post",
      record: {
        text: "A regular post.",
        createdAt: nowISO,
      },
    });
  });

  // Regression test for com.etzhayyim.organism.message (unencrypted path for simplicity)
  it("should still process com.etzhayyim.organism.message records correctly", async () => {
    const messageRecord = {
      v: 1,
      ts: now.getTime(),
      actorDid: actorDid,
      recipientDid: "did:web:recipient",
      lexicon: "com.etzhayyim.organism.message",
      text: "A secret message.",
      createdAt: nowISO
    };
    await drainer.processLine(JSON.stringify(messageRecord));

    const base64Expected = Buffer.from("A secret message.").toString("base64");
    expect(mockWrite).toHaveBeenCalledWith(expect.objectContaining({
      collection: "com.etzhayyim.organism.message",
      record: expect.objectContaining({
        encryptedPayload: `mock-signal-keywrap-v1(${base64Expected})`,
      }),
    }));
  });

  // Test processing mixed records in order
  it("should process a mix of record types in order", async () => {
    const records = [
      {
        v: 1,
        ts: now.getTime(),
        actorDid: actorDid,
        lexicon: "app.bsky.feed.post",
        text: "First post",
        createdAt: nowISO
      },
      {
        v: 1,
        ts: now.getTime(),
        actorDid: actorDid,
        lexicon: "com.etzhayyim.organism.lifecycle",
        createdAt: nowISO,
        event: { type: "birth", sourceDid: "did:web:source" }
      },
      {
        v: 1,
        ts: now.getTime(),
        actorDid: actorDid,
        recipientDid: "did:web:recipient",
        lexicon: "com.etzhayyim.organism.message",
        text: "A message after birth",
        createdAt: nowISO
      }
    ];

    for (const record of records) {
      await drainer.processLine(JSON.stringify(record));
    }

    expect(mockWrite).toHaveBeenCalledTimes(3);

    // Check first call (post)
    expect(mockWrite.mock.calls[0][0]).toEqual({
      collection: "app.bsky.feed.post",
      record: { text: "First post", createdAt: nowISO },
    });

    // Check second call (lifecycle)
    expect(mockWrite.mock.calls[1][0]).toEqual({
      collection: "com.etzhayyim.organism.lifecycle",
      record: { type: "birth", sourceDid: "did:web:source", createdAt: nowISO },
    });

    // Check third call (message)
    const base64Expected = Buffer.from("A message after birth").toString("base64");
    expect(mockWrite.mock.calls[2][0]).toEqual(expect.objectContaining({
        collection: "com.etzhayyim.organism.message",
        record: expect.objectContaining({ encryptedPayload: `mock-signal-keywrap-v1(${base64Expected})`})
    }));
  });
});
