# murakumo-generation

The shared client for **murakumo.cloud's public generation API** — the fleet
that owns every GPU step of a production: the moving image (`:video`), the
narration (`:voice`), the music bed (`:music`) and the one-shot cues (`:sfx`).

Portable `.cljc`, no dependencies. The same code runs under nbb operator
scripts and on the JVM, because the `-ka` repos are split across both and a
second copy would drift.

```
murakumo.generation          request bodies, accepted ranges, response parsing,
                             retry classification — pure
murakumo.generation.digest   sha2-256 hex -> raw CIDv1
murakumo.generation.client   submit -> poll -> fetch -> verify, transport injected
```

## Why this is a library and not four copies

Written from the documented shape alone, a caller fails on first contact in
four separate ways, and each one costs a round trip against a live GPU fleet
to discover. All four were measured on 2026-07-29 and are encoded here:

1. **Wrong host.** `api.murakumo.cloud` 401s a generation-scope token. The
   gate that accepts it is `generation.murakumo.cloud` — different Workers,
   different signing secrets, not interchangeable.
2. **The advertised artifact URL is unusable as given.** Status and artifact
   URLs come back pointing at `murakumo.cloud` whichever host accepted the
   job, so following them verbatim 401s on every fetch. `rebase-host` keeps
   the job-id path and speaks to the host you authenticated to.
3. **Geometry and frame counts are constrained.** `params.width must be a
   multiple of 32 in 256..1280` — a vertical short's own 720 is a 400.
   `params.frames must be 8n+1 in 9..121`, which caps one clip near 5s at the
   fleet's 24fps, so a longer shot has to hold or loop on your side.
4. **`params.locale` wants BCP-47.** `"ja"` and `"ja_JP"` are both rejected;
   it is `ja-JP`.

Plus one that only shows up in production: generation functions **scale from
zero**, so the first job after an idle period races the GPU worker's boot and
fails with the service unable to reach its backend (`[Errno 111] Connection
refused`, then `[Errno 104] Connection reset by peer` mid-boot). Both times
the very next job ran to completion. Degrading scheduled work to a fallback
because it happened to be the job that woke the fleet is a bug, so those
signatures retry while a real refusal — bad params, out of vram — still fails
fast.

## One name across compute and storage

The API states an artifact's integrity as `contentHash: "sha256:<hex>"`, and
kotobase names archive objects by exactly that digest. So the fleet's content
hash **is** the storage CID: no re-hash, no second naming scheme, and
re-storing identical bytes is a no-op. `artifact-cid` gives you that name, and
the client verifies the download against the digest before handing it back —
a truncated file is discarded rather than muxed into a production and stored
under a name that does not describe it.

## Models are not pinned

Omit `:model` and murakumo resolves the function's own `:default` from
`murakumo.edn`, so a fleet-side model swap reaches every consumer without a
release here — the murakumo-main rule (ADR-2607173100) applied to generation.
Pin one explicitly only when a specific model is the point.

## Use

```clojure
(require '[murakumo.generation.client :as gen])

(def opts
  {:base   (murakumo.generation/endpoint (System/getenv "MURAKUMO_GENERATION_URL"))
   :token  (System/getenv "MURAKUMO_GENERATION_TOKEN")   ; scope: generation
   :request!   my-json-http      ; (fn [method url body-map token] -> {:status :body})
   :download!  my-download       ; (fn [url out token] -> truthy)
   :sha256-hex my-file-digest    ; (fn [path] -> lowercase hex)
   :delete!    my-delete         ; (fn [path] -> nil)
   :sleep!     #(Thread/sleep %)})

(gen/video!     {:prompt "…" :seconds 7 :width 720 :height 1280 :seed 0} "shot.mp4" opts)
(gen/narration! {:text "…" :voice "ja-narrator-female"}                  "line.wav" opts)
(gen/music!     {:prompt "…" :seconds 30 :model "ace-step" :seed 2652}   "bgm.wav"  opts)
(gen/sfx!       {:prompt "…" :seconds 2 :model "musicgen-small" :seed 7} "cue.wav"  opts)
;; -> {:file … :cid "bafkrei…" :job-id …} | nil (warned, with the reason)
```

Four host primitives are injected because JSON codecs, file digests and
sleeping differ between the JVM and nbb — everything that was expensive to
learn stays here.

**Nothing throws at the caller.** An unreachable fleet, a missing token, a
failed job or a digest mismatch all return `nil` after saying which on stderr,
so a scheduled producer degrades instead of losing the night's work. What it
will not do is degrade *quietly*: every `nil` is warned with its reason,
because a fallback that reads as success is how a pipeline ships placeholders
for two weeks without anyone noticing.

## Test

```bash
kbb -M:test            # JVM
kbb --backend sci --classpath src …      # loads unchanged under nbb
```

## References

- ADR-2607299960 — dougaka の生成計算を murakumo.cloud に、保管を kotobase.net に
- ADR-2607173100 — murakumo-main alias（モデル id を焼かない）
- ADR-2607171330 — `:video` の第一経路は murakumo fleet の self-hosted OSS モデル
