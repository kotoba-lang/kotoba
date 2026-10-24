(ns knp
  "KNP: KAMI Network Protocol — custom UDP-based multiplayer protocol.
  Zero-dep portable CLJC root namespace.

  Restored from the legacy kami-engine/kami-knp Rust crate (deleted in PR
  #82) as part of ADR-2607010930 (com-junkawasaki/root, kami-engine
  Rust-workspace restoration to CLJC). Original crate root (`lib.rs`) was
  just Rust module wiring (`pub mod` / `pub use` glue with `#[cfg]`
  platform gates) with no logic of its own; this namespace plays that role
  for the CLJC port, re-exporting the portable public surface.

  Ported (this repo, all pure state-machine / wire-format logic, no I/O):
    - knp.packet  — wire packet header (5B post-session) + payload framing
    - knp.channel — 4-channel send/receive/retransmit bookkeeping
    - knp.session — handshake state machine + hello/welcome messages

  Excluded (native-only, no portable logic — stay Rust/native, not ported):
    - crypto.rs        — ChaCha20-Poly1305 AEAD via the `ring` crate; only
                          real encrypt/decrypt operations, no data format
                          of its own (nonce is a trivial counter, not worth
                          a module).
    - socket.rs         — raw UDP socket syscalls / platform socket traits.
    - client.rs          — async I/O event loop driving a real socket.
    - server.rs          — async I/O event loop driving a real socket.
    - webtransport.rs    — wasm_bindgen browser WebTransport API bindings.
  See this repo's README.md for the full file-by-file rationale."
  (:require [knp.packet :as packet]
            [knp.channel :as channel]
            [knp.session :as session]))

;; Re-export the portable public surface (Rust `pub use` equivalent).

(def make-header packet/make-header)
(def make-packet packet/make-packet)
(def packet->bytes packet/packet->bytes)
(def bytes->packet packet/bytes->packet)
(def header->bytes packet/header->bytes)
(def bytes->header packet/bytes->header)
(def header-channel packet/header-channel)
(def header-flags packet/header-flags)
(def header-sequence packet/header-sequence)
(def header-ack packet/header-ack)
(def wire-size packet/wire-size)

(def channel-manager channel/channel-manager)

(def session-manager session/session-manager)
(def make-hello session/make-hello)
(def make-welcome session/make-welcome)
(def parse-welcome session/parse-welcome)
(def is-hello? session/is-hello?)
