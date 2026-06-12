// conversation.ts — Conversation protocol helpers.

import type {
  ConversationSession,
  ConversationMessage,
  HostImports,
} from "./types.js";

let _host: HostImports | null = null;

export function setConversationHost(host: HostImports): void {
  _host = host;
}

function host(): HostImports {
  if (!_host) throw new Error("kotodama-host-sdk: conversation host not initialized");
  return _host;
}

export function conversationSecureGroupEnvelope(sessionId: string, plaintext: Uint8Array): Uint8Array {
  const groupId = `conv:${sessionId}`;
  try {
    return host().signalSessionGroupEncrypt(groupId, plaintext);
  } catch {
    return plaintext;
  }
}

export function conversationSecureDecrypt(sessionId: string, recordJson: Uint8Array): Uint8Array {
  if (recordJson.length === 0) return recordJson;
  if (recordJson[0] === 0x7b || recordJson[0] === 0x5b) return recordJson;

  try {
    const pt = host().signalSessionGroupDecrypt(`conv:${sessionId}`, recordJson, "");
    if (pt.length > 0 && (pt[0] === 0x7b || pt[0] === 0x5b)) return pt;
  } catch {
    // Fall through to the original payload when decryption is unavailable.
  }

  return recordJson;
}

export function startConversation(topic: string, participantNanoids: string[]): ConversationSession {
  const json = host().conversationCreateSession(topic, JSON.stringify(participantNanoids));
  return JSON.parse(json) as ConversationSession;
}

export function say(sessionId: string, content: string): ConversationMessage {
  const plaintext = new TextEncoder().encode(content);
  const payload = conversationSecureGroupEnvelope(sessionId, plaintext);
  const json = host().conversationSendMessage(sessionId, new TextDecoder().decode(payload));
  return JSON.parse(json) as ConversationMessage;
}

export function reply(sessionId: string, content: string, _replyToMessageId: string): ConversationMessage {
  const plaintext = new TextEncoder().encode(content);
  const payload = conversationSecureGroupEnvelope(sessionId, plaintext);
  const json = host().conversationSendMessage(sessionId, new TextDecoder().decode(payload));
  return JSON.parse(json) as ConversationMessage;
}

export function getConversationHistory(sessionId: string): ConversationMessage[] {
  const json = host().conversationGetHistory(sessionId);
  return JSON.parse(json) as ConversationMessage[];
}

export function endConversation(_sessionId: string): void {
  // Session close is handled server-side.
}
