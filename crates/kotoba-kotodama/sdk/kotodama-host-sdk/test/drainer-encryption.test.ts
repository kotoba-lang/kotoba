import { describe, it, expect, vi } from "vitest";
import { OrganismPostDrainer, NDJSONRecord } from "../src/drainer/index.js";
import { Etzhayyim } from "@etzhayyim/sdk";

// Mock the SDK
vi.mock("@etzhayyim/sdk", () => {
  return {
    Etzhayyim: vi.fn().mockImplementation(() => ({
      write: vi.fn().mockResolvedValue(true)
    })),
    signal: {
      establishSession: vi.fn().mockResolvedValue({}),
      wrapKey: vi.fn().mockResolvedValue({ ciphertext: new Uint8Array(), signalSessionId: "test" })
    }
  };
});

describe("OrganismPostDrainer Wave 3.2 Signal-keywrap Mock", () => {
  it("should encrypt plaintext messages before dispatching", async () => {
    const drainer = new OrganismPostDrainer("/tmp/dummy.ndjson", "http://localhost:2583");

    // Create a mock line for a message that needs encryption
    const plaintextMessage: NDJSONRecord = {
      v: 1,
      ts: Date.now(),
      actorDid: "did:web:sender",
      recipientDid: "did:web:recipient",
      lexicon: "com.etzhayyim.organism.message",
      text: "Secret contract proposal",
      createdAt: new Date().toISOString()
    };

    await drainer.processLine(JSON.stringify(plaintextMessage));

    // Verify that Etzhayyim was instantiated
    expect(Etzhayyim).toHaveBeenCalledWith({ did: "did:web:sender", pdsUrl: "http://localhost:2583" });

    const mockSdk = (Etzhayyim as any).mock.results[0].value;
    expect(mockSdk.write).toHaveBeenCalled();

    const writeCall = mockSdk.write.mock.calls[0][0];
    expect(writeCall.collection).toBe("com.etzhayyim.organism.message");

    // The payload should be encrypted and no longer raw text
    const record = writeCall.record;
    expect(record.recipientDid).toBe("did:web:recipient");
    expect(record.encryptedPayload).toBeDefined();

    // Verify our mock encryption format
    const base64Expected = Buffer.from("Secret contract proposal").toString("base64");
    expect(record.encryptedPayload).toBe(`mock-signal-keywrap-v1(${base64Expected})`);
  });

  it("should skip encryption if already encrypted", async () => {
    const drainer = new OrganismPostDrainer("/tmp/dummy.ndjson", "http://localhost:2583");

    const alreadyEncrypted: NDJSONRecord = {
      v: 1,
      ts: Date.now(),
      actorDid: "did:web:sender",
      recipientDid: "did:web:recipient",
      lexicon: "com.etzhayyim.organism.message",
      encryptedPayload: "mock-signal-keywrap-v1(already)",
      createdAt: new Date().toISOString()
    };

    await drainer.processLine(JSON.stringify(alreadyEncrypted));

    const mockSdk = (Etzhayyim as any).mock.results[1].value;
    const writeCall = mockSdk.write.mock.calls[0][0];
    expect(writeCall.record.encryptedPayload).toBe("mock-signal-keywrap-v1(already)");
  });
});
