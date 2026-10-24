# jp-hiroshiba-voicevox

Portable (`.cljc`) client for a [VOICEVOX Engine](https://github.com/VOICEVOX/voicevox_engine)
HTTP server -- the `audio_query` -> `synthesis` flow, a style_id/emotion
catalog, and commercial-use credit-line rendering. Named for
[Hiroshiba Kazuyuki](https://github.com/Hiroshiba), VOICEVOX's creator,
following this org's `jp-<author>-<project>` convention for individually
authored (non-corporate) Japanese open-source projects, distinct from the
`com-<vendor>` reverse-domain convention used for company APIs
(`com-cloudflare`, `com-youtube`, ...).

## Why this exists

`ai-gftd-project-yukkuri`'s `clj/src/yukkuri/voicevox.cljc` already ported
VOICEVOX's style_id catalog, emotion -> style switching table, and credit-
line logic faithfully from the original `lg/lg_yukkuri/voicevox_client.py`
-- but deliberately as a **plan-only** port (that project's `clj/README.md`
design: no external HTTP calls in that runtime). This repo is the real
execution half: an actual `audio_query`/`synthesis` HTTP client any project
needing real VOICEVOX-synthesized audio can depend on, instead of
re-deriving the two-step call sequence per project.

## Design

```text
voicevox.client      -- audio_query!/synthesis!/version! (injectable :http-fn, JVM-only default transport)
voicevox.speakers    -- style_id catalog, emotion->style table, resolve-style-id, credit-lines
voicevox.synthesize  -- synthesize! : {:text :style-id :speed :pitch} -> WAV bytes (combines the two)
```

Query/response shaping and the speaker catalog are pure `.cljc`. The
actual HTTP call is JVM-only by default (`java.net.http`) but every client
function takes an injectable `:http-fn` (`{:url :method :headers :body} ->
{:status :body-bytes}`, the same convention `kotoba-lang/com-cloudflare`/
`kotoba-lang/com-youtube` use) -- tested with a stub, never only against a
live engine. `/synthesis` returns raw WAV bytes (`:body-bytes`, a byte[]);
JSON endpoints (`/audio_query`, `/version`) are decoded by the caller via
`client/read-json` (accepts a byte[] directly).

Default engine URL: `VOICEVOX_URL` env var, else `http://localhost:50021`
(the engine's own default listen address) -- override per-call via
`{:base-url "..."}`.

## Usage

```clojure
(require '[voicevox.speakers :as speakers]
         '[voicevox.synthesize :as synth])

(def style-id (speakers/resolve-style-id "left" "happy" {:emotion-style? true}))
;; => 0  (四国めたん, happy)

(def wav-bytes
  (synth/synthesize! {:text "こんにちは" :style-id style-id :speed 0.95}))

(speakers/credit-lines [2 3])
;; => ["VOICEVOX:四国めたん" "VOICEVOX:ずんだもん"]
```

## Testing without a live engine

```clojure
(def stub-http-fn
  (fn [{:keys [url]}]
    (if (str/includes? url "/audio_query")
      {:status 200 :body-bytes (.getBytes "{\"speedScale\":1.0}" "UTF-8")}
      {:status 200 :body-bytes (byte-array [0 1 2])})))
(synth/synthesize! {:text "hi" :style-id 2} {:http-fn stub-http-fn})
```

Run tests:

```sh
kbb -M:test
```
