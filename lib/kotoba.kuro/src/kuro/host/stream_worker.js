// kuro-stream-worker.js — the guest-execution Worker for
// kuro.host.stream-browser (S3 convergence slice).
//
// Splits the responsibility the S3 E2E put on the page: THIS worker owns
// fetching the guest component bytes and instantiating them;
// kuro.host.stream-browser (page side) keeps the kuro.terminal / kuro.stream
// decision logic. The wire contract mirrors kuro.host.opfs's shape:
// plain string keys, request/reply with correlated ids, closed ops.
//
// Main -> Worker:
//   {"kuro.stream/type": "request", "kuro.stream/id": n,
//    "kuro.stream/op": "start" | "stdin" | "cancel",
//    "kuro.stream/payload": {...}}
//
// Worker -> Main (multiple, in order):
//   {"kuro.stream/type": "chunk", "kuro.stream/stream": "stdout"|"stderr",
//    "kuro.stream/text": "..."}
//   {"kuro.stream/type": "exit", "kuro.stream/exit-code": n,
//    "kuro.stream/started-at": ms, "kuro.stream/finished-at": ms}
//
// start payload: {guest: "<url-or-cid>", args: [..]} — the guest is a wasm
// module exporting `run(args...) -> i32`; its stdout text is written to
// linear memory at offset 2048 by the guest itself and read back here as a
// chunk. Exit code = the guest's i32 return.
//
// The worker has NO ambient authority: fetch is limited to the guest bytes
// URL the page passed (resolved same-origin), and the only other effect is
// WebAssembly.instantiate over those bytes.

const CHUNK_OFFSET = 2048;

async function instantiateGuest(guestUrl) {
  const resp = await fetch(guestUrl);
  if (!resp.ok) throw new Error("guest fetch " + resp.status);
  const bytes = new Uint8Array(await resp.arrayBuffer());
  return WebAssembly.instantiate(bytes, {});
}

function readChunk(memory, ptr) {
  const mem = new Uint8Array(memory.buffer);
  // The guest wrote UTF-8 text bytes; decode them as such. Building the
  // string with String.fromCharCode per byte would mangle every non-ASCII
  // character (each UTF-8 byte becomes its own Latin-1 code point) - the
  // same class of bug fixed in kuro.host.stream-node's pipe path (#96).
  let end = ptr;
  while (end < mem.length && mem[end] !== 0) end++;
  try {
    return new TextDecoder("utf-8").decode(mem.slice(ptr, end));
  } catch (e) {
    // No TextDecoder in this host - fall back to per-byte so we never drop
    // bytes; matches the pre-fix behaviour for pure-ASCII guests.
    return String.fromCharCode.apply(null, mem.slice(ptr, end));
  }
}

async function handleStart(payload, startedAt) {
  const obj = await instantiateGuest(payload.guest);
  const exports = obj.instance.exports;
  const args = payload.args || [];
  // call run with the args as i32s (the S3 guest fixture takes i32s)
  const code = Number(exports.run(...args.map(Number)));
  const text = readChunk(exports.memory, CHUNK_OFFSET);
  if (text.length > 0) {
    self.postMessage({"kuro.stream/type": "chunk",
                      "kuro.stream/stream": "stdout",
                      "kuro.stream/text": text});
  }
  self.postMessage({"kuro.stream/type": "exit",
                    "kuro.stream/exit-code": code,
                    "kuro.stream/started-at": startedAt,
                    "kuro.stream/finished-at": Date.now()});
}

self.onmessage = async (ev) => {
  const msg = ev.data;
  const op = msg["kuro.stream/op"];
  const startedAt = msg["kuro.stream/started-at"];
  const payload = msg["kuro.stream/payload"] || {};
  try {
    if (op === "start") {
      await handleStart(payload, startedAt);
    }
    // stdin / cancel: a completed sync-run guest has nothing to receive
    // them — they are accepted and dropped here, and the page side already
    // no-ops them after exit (kuro.stream's state gate). Recorded honestly:
    self.postMessage({"kuro.stream/type": "ack", "kuro.stream/op": op});
  } catch (e) {
    self.postMessage({"kuro.stream/type": "exit",
                      "kuro.stream/exit-code": 1,
                      "kuro.stream/started-at": startedAt,
                      "kuro.stream/finished-at": Date.now(),
                      "kuro.stream/error": String(e && e.message || e)});
  }
};
