# koe-clj (声)

Reusable **voice-session kernel** in portable Clojure — every namespace is `.cljc`,
designed for **Clojure-on-WASM hosts** (SCI, ClojureScript, GraalVM, kotoba-clj) as
well as the JVM. The shared library behind voice agents: it defines the **ports**
(telephony / STT / dialog / TTS / booking) and the **dialog loop** that binds them,
with every concrete capability **injected by the host** — no telephony SDK, no model,
no credentials live here.

Built alongside [langgraph-clj](https://github.com/com-junkawasaki/langgraph-clj) /
[langchain-clj](https://github.com/com-junkawasaki/langchain-clj). Sibling of
[godaddy-dns-clj](https://github.com/com-junkawasaki/godaddy-dns-clj) and
[browser-use-clj](https://github.com/com-junkawasaki/browser-use-clj).

## Why a shared library (org placement)

Per the three-way rule, the **reusable** kernel lives in **com-junkawasaki**, while
**public-benefit actor instances** that consume it live in **etzhayyim**, and any
**business/private deployment** lives in **gftdcojp**. The first consumer is the
`denwaban` (電話番) voice-receptionist actor (etzhayyim, ADR-2606271930), which injects
`twilio-compat` (telephony), `whisper-compat` (STT), `elevenlabs-compat` (TTS) and
`yotei` (booking) into these ports.

## What lives here now (2026-08-15)

`koe` was the ports and the turn loop. It now also carries the telephony side
that every voice actor needs and none of them should re-implement:

| namespace | |
|---|---|
| `koe.ports` | the five host-injected ports |
| `koe.session` | one turn: utterance → reply, booking always delegated |
| **`koe.media`** | the carrier's frame protocol, G.711 μ-law, where an utterance ends, the WAV header a speech engine takes |
| **`koe.carrier`** | inbound webhook admission (signature verification, arrival description, the answer document) |
| **`koe.arrival`** | whether the presented caller ID is the caller's — forwarded calls are the normal case |
| **`koe.bridge`** | a whole call as a fold over frames: barge-in, when to speak, when it ends |

Moved out of `cloud-itonami/denwaban`, where they were written: none of it is
about restaurants. denwaban keeps what is — the reservation dialog, the booking
delegation to `yotei`, its own lines and consent sentence.

**Still no SDK, no socket, no credential.** `koe.bridge` returns the work to be
done (`:koe/transcribe`, `:koe/say`) rather than doing it, so the host's socket
loop is the twenty lines that read a message and write the answers, and every
decision a live call makes is testable without a telephone.

## Ports (`koe.ports`)

```
ITelephony  answer / say / hangup        — twilio-compat | vonage | kotoba-net/webrtc
ISTT        transcribe / stream          — whisper-compat
IDialog     step (utterance → reply+act) — kotoba-llm
ITTS        synth                        — elevenlabs-compat
IBooking    propose / confirm            — yotei  (confirm is member-signed; never server-side)
```

The dialog loop (`koe.session/converse`) is a pure fold over these ports: STT in →
dialog step → optional booking action → TTS out, with **barge-in** (a new partial
transcript interrupts in-flight TTS). Booking is always **delegated** — the kernel
never confirms a booking itself.

The closed booking-delegation shape gate also has a native, capability-free
`.kotoba` implementation for restricted JavaScript and Wasm. Dialog state,
utterances, TTS/audio, slot proposal, cryptographic signature verification,
confirmation, and all host ports remain CLJC/host responsibilities.

```
kbb -X:test
```
