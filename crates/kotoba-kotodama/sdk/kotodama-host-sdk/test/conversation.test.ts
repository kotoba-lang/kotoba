import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  setConversationHost,
  startConversation,
  say,
  reply,
  getConversationHistory,
  endConversation,
  conversationSecureDecrypt,
} from "../src/conversation.js";
import { createMockHostImports } from "./mock-helpers.js";

describe("conversation helpers", () => {
  beforeEach(() => {
    setConversationHost(createMockHostImports());
  });

  it("startConversation proxies to host", () => {
    setConversationHost(createMockHostImports({
      conversationCreateSession: () => JSON.stringify({
        sessionId: "sess-1",
        topic: "test",
        participants: ["a", "b"],
        status: "active",
        createdAt: "2026-04-21T00:00:00Z",
      }),
    }));
    expect(startConversation("test", ["a", "b"]).sessionId).toBe("sess-1");
  });

  it("say encrypts and sends a conversation message", () => {
    const sendMessageSpy = vi.fn(() => JSON.stringify({
      messageId: "msg-1",
      sessionId: "sess-1",
      from: "alice",
      content: "Hello",
      createdAt: "2026-04-21T00:00:00Z",
    }));
    setConversationHost(createMockHostImports({
      conversationSendMessage: sendMessageSpy,
      signalSessionGroupEncrypt: () => { throw new Error("no signal"); },
    }));

    const message = say("sess-1", "Hello");
    expect(message.messageId).toBe("msg-1");
    expect(sendMessageSpy).toHaveBeenCalledWith("sess-1", "Hello");
  });

  it("reply reuses the same transport path", () => {
    const sendMessageSpy = vi.fn(() => JSON.stringify({
      messageId: "msg-2",
      sessionId: "sess-1",
      from: "alice",
      content: "World",
      createdAt: "2026-04-21T00:00:00Z",
    }));
    setConversationHost(createMockHostImports({
      conversationSendMessage: sendMessageSpy,
      signalSessionGroupEncrypt: () => { throw new Error("no signal"); },
    }));

    const message = reply("sess-1", "World", "msg-1");
    expect(message.messageId).toBe("msg-2");
    expect(sendMessageSpy).toHaveBeenCalledWith("sess-1", "World");
  });

  it("getConversationHistory proxies to host", () => {
    setConversationHost(createMockHostImports({
      conversationGetHistory: () => JSON.stringify([{ messageId: "msg-3" }]),
    }));
    expect(getConversationHistory("sess-1")).toHaveLength(1);
  });

  it("conversationSecureDecrypt returns plaintext JSON unchanged", () => {
    const payload = new TextEncoder().encode('{"ok":true}');
    expect(conversationSecureDecrypt("sess-1", payload)).toEqual(payload);
  });

  it("endConversation is a no-op", () => {
    expect(() => endConversation("sess-1")).not.toThrow();
  });
});
