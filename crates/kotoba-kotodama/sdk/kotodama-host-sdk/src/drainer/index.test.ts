import { OrganismPostDrainer } from './index';
import { vi, describe, it, expect, beforeEach } from 'vitest';

const mockWrite = vi.fn();

vi.mock('@etzhayyim/sdk', () => ({
  Etzhayyim: vi.fn().mockImplementation(() => ({
    write: mockWrite,
  })),
}));

describe('OrganismPostDrainer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('should parse and process a valid app.bsky.feed.post line', async () => {
    const drainer = new OrganismPostDrainer('dummy.ndjson', 'https://dummy.pds');

    const validPost = JSON.stringify({
      v: 1,
      ts: 1748131234567,
      actorDid: "did:web:etzhayyim.com:actor:c10101500",
      code: "10101500",
      text: "Test post",
      lexicon: "app.bsky.feed.post",
      createdAt: "2026-05-24T01:23:45Z"
    });

    await drainer.processLine(validPost);

    expect(mockWrite).toHaveBeenCalledWith({
      collection: "app.bsky.feed.post",
      record: {
        text: "Test post",
        createdAt: "2026-05-24T01:23:45Z"
      }
    });
  });

  it('should parse and process a valid com.etzhayyim.organism.message line', async () => {
    const drainer = new OrganismPostDrainer('dummy.ndjson', 'https://dummy.pds');

    const validMessage = JSON.stringify({
      v: 1,
      ts: 1748131234568,
      actorDid: "did:web:etzhayyim.com:actor:c10101500",
      recipientDid: "did:web:etzhayyim.com:actor:c10101501",
      encryptedPayload: "base64encodedencrypteddata",
      lexicon: "com.etzhayyim.organism.message",
      createdAt: "2026-05-26T01:23:45Z"
    });

    await drainer.processLine(validMessage);

    expect(mockWrite).toHaveBeenCalledWith({
      collection: "com.etzhayyim.organism.message",
      record: {
        recipientDid: "did:web:etzhayyim.com:actor:c10101501",
        senderDid: "did:web:etzhayyim.com:actor:c10101500",
        encryptedPayload: "base64encodedencrypteddata",
        createdAt: "2026-05-26T01:23:45Z"
      }
    });
  });

  it('should handle invalid JSON gracefully', async () => {
    const drainer = new OrganismPostDrainer('dummy.ndjson', 'https://dummy.pds');
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

    await drainer.processLine('invalid json {');

    expect(errSpy).toHaveBeenCalledWith(
      'Failed to parse line:', 'invalid json {'
    );

    errSpy.mockRestore();
  });
});
