# kotoba-composer

[![CI](https://github.com/kotoba-lang/composer/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/composer/actions/workflows/ci.yml)

**AI music composition requests, tracks, stems, style references and
generation/audit events, in pure Clojure.** A
[kotoba-lang](https://github.com/kotoba-lang) capability library modeling
the `ai.gftd.ongakuka.*` lexicon shapes (`compose`/`track`/`stem`/`style`/
`generation`) 1:1, plus a pure pipeline-status reducer, so any composing/
video-producing actor constructs valid requests and interprets responses
without re-deriving the lexicon by hand.

No network, no I/O, no model call. The library models **records, not the
wire format** — the same approach [`kotoba-lang/webrtc`](https://github.com/kotoba-lang/webrtc)
takes for WebRTC signaling. Portable `.cljc` across JVM / ClojureScript /
SCI / GraalVM.

## Naming note

`ai.gftd.ongakuka.compose`'s own internal pipeline is documented as
`lyricist→composer→vocalist‖arranger→mixer→critic` — i.e. ongakuka already
has an internal stage *called* "composer" (the melody/arrangement-skeleton
stage). `kotoba.composer` is **not** a model of that one internal stage —
it models the **outer** composition request/track/stem/generation contract
that any external caller (yukkuri or otherwise) uses to talk to ongakuka as
a whole.

## Scope

This library **does not** call `ai.gftd.ongakuka.compose`/`regenerate`
itself — no network I/O, no auth, no retries. It models the request/
response records and the pipeline's status transitions; the app-level actor
that owns the deployment (e.g. yukkuri's
`did:web:yukkuri.gftd.ai:actor:composer`) supplies the actual XRPC dispatch
and executes the effects `kotoba.composer.pipeline/apply-event` returns —
the same separation of concerns `kotoba.webrtc.session` uses for
call-signaling negotiation (host injects every concrete capability).

## Contract

```clojure
(require '[kotoba.composer :as composer]
         '[kotoba.composer.track :as track]
         '[kotoba.composer.stem :as stem]
         '[kotoba.composer.style :as style]
         '[kotoba.composer.generation :as generation]
         '[kotoba.composer.pipeline :as pipeline])

;; compose-request — mirrors ai.gftd.ongakuka.compose's input schema
(composer/compose-request {:title "Cyber Yukkuri Theme"
                            :lyrics "line one\nline two"
                            :style "synthwave, driving, upbeat"
                            :duration-sec 120})

;; track / stem / style / generation records — mirror the response-side
;; lexicons (ai.gftd.ongakuka.track/.stem/.style/.generation)
(def t (track/track {:title "Cyber Yukkuri Theme" :lyrics "..." :style "synthwave" :status :queued}))
(stem/stem {:track-uri "at://.../track/1" :kind :vocal :blob-key "..." :mime-type "audio/wav"})
(style/style {:name "80s synthwave" :kind :prompt :prompt "driving arpeggios, gated reverb"})
(generation/generation {:target-uri "at://.../track/1" :stage :compose :model-id "diffrhythm-1.2-ja" :status :ok})

;; pipeline reducer — host executes the returned :effects
(pipeline/apply-event t {:type :start-lyric})
;; => {:track {... :composer.track/status :lyric ...}
;;     :effects [[:request-lyrics]]}
```

## The copyright gate

`kotoba.composer.style` enforces the same invariant the `ai.gftd.ongakuka.style`
lexicon description states ("embeddings of unknown-license sources MUST NOT
be published as record") and yukkuri's own copyright-invariants section
restates for BGM/SFX:

```clojure
(style/publishable? (style/style {:name "clip A" :kind :embedding
                                   :embedding-blob-key "..." :license :unknown}))
;; => false — an :unknown or absent license never defaults to permitted.
;; A :prompt-kind style (plain text, not derived from copyrighted audio)
;; has no license gate at all.
```

## Pipeline states

```
:queued → :lyric → :compose → :vocal → :mix → :review → :published | :rejected | :failed
```

`:vocal` covers ongakuka's own parallel `vocalist‖arranger` stage —
`{:type :compose-done}` requests both `[:request-vocal]` and
`[:request-arrangement]` at once.

## Test

```sh
kbb -M:test
```

Lint:

```sh
kbb -M:lint
```

## Why

Any composing/video-producing actor (yukkuri's cyber/anime/truecrime/
pachinko channels today; any future gftdcojp/etzhayyim actor that wants a
soundtrack) needs to construct a valid `ai.gftd.ongakuka.compose` request
and interpret `track`/`stem`/`generation` responses. `kotoba-composer` is
the pure-data layer any such actor depends on, instead of re-deriving the
ongakuka lexicon by hand in each one — the actual cross-project XRPC call
stays with the app-level actor that owns the deployment.

## License

Apache License 2.0.
