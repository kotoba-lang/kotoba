(ns rtc
  "KAMI RTC — WebRTC SDK for KAMI Engine: room-based real-time
  communication with WebRTC peer connections (SDP offer/answer, ICE
  candidates), media track management, spatial audio integration, and
  a signaling protocol over a KNP ReliableOrdered channel. Restored
  from the legacy kami-engine/kami-rtc Rust crate (deleted in
  kotoba-lang/kami-engine PR #82 'Remove Rust workspace from
  kami-engine') as part of the clj-wgsl migration (ADR-2607010930,
  com-junkawasaki/root).

  Architecture: browser (WASM) holds the real RTCPeerConnection/
  MediaStream objects; this CLJC layer is the platform-agnostic room/
  peer/track/signaling state machine, mirroring the original's split.

  One namespace per original Rust module:
    rtc.media   — media track types + constraints presets
    rtc.peer    — per-peer connection state machine
    rtc.room    — room management, signal processing, spatialize dispatch
    rtc.signal  — signaling protocol wire format
    rtc.spatial — spatial audio pan/volume calculation

  Zero-dep portable CLJC — pure data + pure functions, no IO/GPU.")
