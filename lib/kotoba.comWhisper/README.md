# Whisper Clean Room Actor

Clean-room, API-compatible implementation of an audio **speech-to-text (STT/ASR)**
platform (OpenAI `audio/transcriptions` + `audio/translations` shape), backed by
Datomic and Py Kotodama WASM.

> **An engine is bound as of 2026-08-15.** `whisper.main` always said the
> in-memory store existed "before a live engine binds"; `whisper.engine` is that
> binding — `whisper-cli` on the murakumo fleet, injected rather than shelled out
> to from here. Measured on a fleet node against **telephony-degraded** Japanese
> (8 kHz μ-law and back): `large-v3-turbo` transcribed 8/8 reservation utterances
> at ~1.45 s, including a full telephone number. See
> [`docs/fleet-measurement.md`](docs/fleet-measurement.md) — including the run
> where a truncated model crashed, exited 0, and returned eight silent callers.

This actor closes the **one missing primitive** identified in
ADR-2606271930: `elevenlabs-compat` gives TTS (speech *out*) but there was no
clean-room STT (speech *in*). `whisper-compat` is the input half of `denwaban`'s
voice I/O.

## Architecture
- **State:** Datomic-backed, immutable/time-travel record keeping (transcripts are
  transient by default — see G1 no-secret-recording in ADR-2606271930).
- **Schema:** `schema/whisper.kotoba`.
- **Execution:** Py Kotodama WASM, intercepting inbound REST + a streaming transcript
  channel (partial → final) for barge-in.

## Status

**R0 scaffold** — socket-free core only. No live audio, no socket. `transcribe`
materializes against the in-memory `*store*`; streaming is fixture-driven. Live
audio ingest is outward-gated (G7) and lands in a later R-cycle.

```
kbb -M:test   # cljc contract test under babashka
```
