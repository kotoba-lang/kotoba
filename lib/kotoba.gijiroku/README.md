# gijiroku

議事録 — a **Zoom / Google Meet / Microsoft Teams meeting-record actor**: it
accesses each platform's official recording + transcript API, drafts minutes
(summary / decisions / action items), and keeps an append-only audit ledger of
every consent, draft, and distribution — but it **never distributes anything
itself**. It is a sealed-intelligence ⊣ independent-governor StateGraph, built
on this workspace's
[`langgraph-clj`](https://github.com/com-junkawasaki/langgraph-clj) runtime —
the same pattern as
[`kekkai`](../kekkai) (coord-LLM ⊣ TailnetGovernor),
[`robotaxi-actor`](../robotaxi-actor) and
[`ai-gftd-itonami`](../../gftdcojp/ai-gftd-itonami) (ops-LLM ⊣ CertGovernor).
Here it is **scribe-LLM ⊣ PrivacyGovernor**.

> Charter: **(G1)** access → draft-minutes only, no distribution actuation —
> the actor proposes minutes, a human-approved Distributor port sends them;
> **(G2)** distributing minutes is **always a human call** (high-stakes,
> whatever the phase); **(G3)** consent is a ground fact, never inferred —
> silence ≠ consent, commit is blocked without a recorded `:consent/record`;
> **(G4)** raw audio/video never enters the store or git — only an
> `:asset-ref` (object storage key / platform URL) is recorded.

Common infrastructure in `kotoba-lang` (language-substrate, consumed by all
orgs) — the primary consumers today are
[`cloud-itonami`](https://github.com/gftdcojp/cloud-itonami) and
[`cloud-manimani`](https://github.com/gftdcojp/cloud-manimani).

## The core contract

```
Zoom / Google Meet / Teams (Platform port)
        │  fetch-recording / fetch-transcript / verify-webhook
        ▼
meeting facts (meeting/consent/recording/transcript)
        │  ingest = durable ground facts (observe; always on)
        ▼
   ┌───────────┐  proposal: summary/    ┌──────────────────┐
   │ scribe-LLM │  decisions/action-    │ PrivacyGovernor   │  (independent system)
   │ (sealed)   │  items/cites/redact  │  consent · tenant  │
   └───────────┘ ─────────────────────▶│  · redaction · no- └────────┬─────────┘
                            commit ◀───────actuation────────┼──▶ hold (no consent /
                                │                            │      unredacted sensitive
                          minutes/draft                 escalate    cite / cross-tenant
                          auto-commits when                │        recipient / bad
                          clean + confident            request-approval  effect;
                          (phase 2/3)                  (ALWAYS human    human cannot
                                                        for distribute)  override)
```

## Files

| | |
|---|---|
| `src/gijiroku/model.cljk` | canonical data model — meeting/consent/recording/transcript/minutes |
| `src/gijiroku/platform.cljk` | `MeetingPlatform` port + `mock-platform` (default) |
| `src/gijiroku/zoom.cljk` | Zoom Cloud Recording API client (S2S OAuth) + webhook HMAC verify |
| `src/gijiroku/google_meet.cljk` | Google Workspace Meet REST API v2 client |
| `src/gijiroku/teams.cljk` | Microsoft Graph (onlineMeetings recordings/transcripts) client |
| `src/gijiroku/consent.cljk` | pure consent/tenant/redaction evaluation (no I/O) |
| `src/gijiroku/scribellm.cljk` | scribe-LLM — sealed intelligence, proposal only |
| `src/gijiroku/governor.cljk` | **PrivacyGovernor** — independent censor over proposals |
| `src/gijiroku/phase.cljk` | **Phase 0→3** — observe-only → assisted → supervised (distribute always human) |
| `src/gijiroku/store.cljk` | `Store` protocol — `MemStore` ‖ `DatomicStore` |
| `src/gijiroku/operation.cljk` | **MeetingRecordActor** — langgraph-clj StateGraph; ingest vs assess flows |
| `src/gijiroku/cacao.cljk` | agent-side **CACAO self-mint** (JVM Ed25519 + did:key + CBOR) |
| `src/gijiroku/kotoba.cljk` | wire `DatomicStore` to a kotoba-server pod (kotobase.net XRPC) |
| `src/gijiroku/bot_join.cljk` | **bot-join `MeetingPlatform`** — headless-browser join, no OAuth app needed (`:bot-join` alias) |
| `src/gijiroku/transcriber.cljk` | `Transcriber` port + `mock-transcriber` (bot-join has no native transcript) |
| `src/gijiroku/whisper.cljk` | Whisper-compatible STT client for bot-join audio |
| `src/gijiroku/sim.cljk` | demo driver |
| `test/gijiroku/*_test.clj` | privacy contract · store parity (Mem≡Datomic) · platform (mock + VTT/HMAC) · bot-join (join-URL/selectors) · Whisper (multipart) · CACAO |

## Recording acquisition: two Platform implementations

Two approaches were weighed (ADR-2607031100): pulling recordings/transcripts
from each platform's **official cloud API** after the host enables native
recording, vs. a **headless-browser bot** that joins as a participant and
records/transcribes itself. `MeetingPlatform` is a protocol precisely so both
can coexist without touching `gijiroku.operation`/`gijiroku.governor`:

- **`gijiroku.zoom` / `gijiroku.google-meet` / `gijiroku.teams`** (default) —
  official cloud APIs. More ToS-compliant, less implementation surface,
  platform-native transcripts (with speaker attribution). Requires an OAuth
  app registered per platform (Zoom S2S OAuth app, Google Workspace
  service account, Entra ID app) with admin consent, and the host must have
  native recording/transcription enabled.
- **`gijiroku.bot-join`** (`:bot-join` alias, ADR-0002) — a headless browser
  joins with just the meeting URL, **no OAuth app / admin consent needed**.
  Trade-offs: needs an Xvfb+PulseAudio+ffmpeg host rig, join-flow selectors
  are UI heuristics that can break, no speaker diarization (STT-only
  transcript), and some platforms restrict unattended bots under their ToS
  — evaluate per org before enabling.

```clojure
;; bot-join: add the alias, then
(require '[gijiroku.bot-join :as bj] '[gijiroku.platform :as p])
(def pf (bj/bot-join-platform {:tenant "cloud-manimani"}))  ; default mock-transcriber
(bj/register-meeting! pf {:external-id "abc-defg-hij" :platform :google-meet
                          :tenant "cloud-manimani" :participants []})
(p/fetch-recording pf "abc-defg-hij")   ; BLOCKING — joins live, captures until the call ends
```

## PrivacyGovernor — independent censor

The scribe-LLM has no notion of consent law, tenant boundaries, or the
no-actuation charter, so a **separate system** evaluates every proposal:

```clojure
(governor/check request proposal store)
;; => {:ok? bool :violations [..] :confidence c :hard? bool :escalate? bool :high-stakes? bool}
```

HARD (unoverridable, even by a human sign-off):

1. **consent-required** — `:consent/record` must exist, recording announced,
   legal basis on file. No record at all is NOT treated as consent.
2. **protected-content redaction** — every cited segment tagged `:sensitive`
   (health/legal/financial…) must be covered by a declared redaction.
3. **tenant-isolation** (`:minutes/distribute`) — every recipient must be a
   participant of the meeting; no cross-tenant/cross-meeting leak.
4. **no-actuation** — a proposal's `:effect` must be `:minutes` (a data
   record); the actor never sends/posts/attaches anything itself.

SOFT: confidence floor → escalate. `:minutes/distribute` is **always
high-stakes** — a human signs off on every distribution, clean or not.

## Phase 0→3

`gijiroku.phase`: 0 observe-only (ingest facts, no drafting) → 1 assisted
(draft allowed, distribute always human) → 2 assisted-draft (clean drafts
auto-commit) → 3 supervised (same, **distribute never enters `:auto` at any
phase** — the charter rule, not a phase knob).

## Consuming from cloud-itonami / cloud-manimani

```clojure
;; deps.edn
io.github.kotoba-lang/gijiroku {:local/root "../../kotoba-lang/gijiroku"}
```

```clojure
(require '[gijiroku.store :as store] '[gijiroku.operation :as op])
(def st (store/seed-db))                 ; or store/datomic-store for a real backend
(def actor (op/build st))
(g/run* actor {:request {:op :minutes/draft :meeting-id "m-123"}
              :context {:phase 3}} {:thread-id "m-123"})
```

Or read/write the actor's own `kotobase.net` graph over XRPC without a
local checkout:

```clojure
(require '[gijiroku.kotoba :as k] '[gijiroku.cacao :as cacao])
(def me    (cacao/load-or-create-identity! ".gijiroku/identity.edn"))
(def store (k/kotoba-store {:url "https://kotobase.net" :identity me
                            :json-write json/write-str
                            :json-read #(json/read-str % :key-fn keyword)}))
```

Product-specific UI, notifications, and calendar integration are each app's
own responsibility — gijiroku provides the common "access · record ·
transcribe · draft minutes" core only.

## 本番バックエンド（injection）

`DatomicStore` は `langchain.db` の `:db-api` マップ越しにのみ喋る。
`langchain.db/api`（in-process）と `langchain.kotoba-db/kotoba-api`
（kotoba-server XRPC）は同じマップを実装するので、同じ record が backend を
選ばず動く（`store_contract_test` で保証）。同様に Platform port も
`mock-platform` と実クライアント（Zoom/Meet/Teams）が同一契約に従う。

不正・破損 LLM 応答は confidence 0 / noop に落ち、**PrivacyGovernor が必ず
hold/escalate** する（LLM の幻覚や取りこぼしが「配布」に直結する経路は構造的に
無い）。

## Status

設計実装まで完了。runnable（`kbb -M:dev:run`）+ 契約テスト（`clojure
-M:dev:test:bot-join` — privacy contract · store parity · platform
mock/VTT/HMAC · bot-join join-URL/selectors · Whisper multipart · CACAO
offline、**30 tests / 92 assertions**）、lint clean（`kbb -M:bot-join:lint`）。

Zoom/Google Meet/Teams の実クライアントは正しい API 形状で実装済みだが、各社の
OAuth app 登録・admin consent が前提のため **live 結合は未検証**（kekkai の
kotobase.net 522 と同種の「オフライン契約は保証、live は creds 到着後」の
既知状況）。bot-join（ADR-0002）は join-URL 構築・host-caps 契約はオフライン
検証済みだが、実会議での join + 音声キャプチャは Xvfb/PulseAudio/ffmpeg ホスト
が本環境に無いため同様に未検証。

残り: 各社 OAuth app 登録後の live 結合、bot-join の Xvfb/PulseAudio/ffmpeg
ホスト構築 + 実会議での live 結合、実 LLM/実 STT（一般 API key）、
kotobase.net origin 復帰時の live 結合、cloud-itonami/cloud-manimani 側の
実際の consumer 配線（deps.edn 追加 + UI）、Distributor port の実装
（メール/Slack 等、承認後のみ呼ばれる）。
