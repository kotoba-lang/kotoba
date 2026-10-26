# ADR-0202 — the first kernel-adjacent namespaces are Kotoba guests, and they carry no capability

- Status: accepted
- Date: 2026-09-07
- `aiueos.topic`, `aiueos.os-update` and `aiueos.model-channel` now compile as
  pure Kotoba guests, alongside their `.cljc` oracles.
- The capability question, answered by measurement: a guest that makes no
  effect declares none, writes none, and compiles with `:effects #{}`.

## Decision

Thirteen namespaces whose decisions are arithmetic and keywords, not bytes, are
now **kotoba-only** — the guest is the component, the `.cljc` stays as the
parity oracle:

| guest | oracle | owns |
|---|---|---|
| `aiueos/topic.kotoba` | `src/aiueos/topic.cljk` | the whole topic bus: publish / latest / take-sample / pending / topic-count / tick / advance |
| `aiueos/os_update.kotoba` | `src/aiueos/os_update.cljk` | health-status, boot-selection, non-regex manifest faults |
| `aiueos/model_channel.kotoba` | `src/aiueos/model_channel.cljk` | continuity-errors (the four sequence-history rules), boot-decision |
| `aiueos/runtime_update.kotoba` | `src/aiueos/runtime_update.cljk` | blue/green health-status, manifest faults incl. `:incompatible-runtime-abi` |
| `aiueos/device_auth.kotoba` | `src/aiueos/device_auth.cljk` | the proof-problem chain: all sixteen refusal reasons, in the oracle's order |
| `aiueos/vm.kotoba` | `src/aiueos/vm.cljk` | boot-plan validation (unknown arch / graphics / console, display-requires-graphics) |
| `aiueos/hardware_qualification.kotoba` | `src/aiueos/hardware_qualification.cljk` | fail-closed receipt classification, destructive markers need explicit authority |
| `aiueos/pid1.kotoba` | `src/aiueos/pid1.cljk` | the rdinit=/init argv0 contract, positional scan |
| `aiueos/bare_metal.kotoba` | `src/aiueos/bare_metal.cljk` | P2 boot classification; the :host-fetch-does-not-count gate kept verbatim |
| `aiueos/virtio.kotoba` | `src/aiueos/virtio.cljk` | interrupt-status bit decoding, device-id mapping, irq-line validation |
| `aiueos/image.kotoba` | `src/aiueos/image.cljk` | boot-input refusal decisions (file existence / ELF checks stay in the host) |
| `aiueos/compositor/ime.kotoba` | `src/aiueos/compositor/ime.cljk` | the romaji conversion core: 111-entry mora table split into 4 chunk maps (the 32-entry document-map limit), greedy longest-match conversion |
| `aiueos/compositor/ime_key.kotoba` | `src/aiueos/compositor/ime.cljk` | the handle-key branch tree: bypass red, escape, backspace, space (kanji cycle / convert / kanji-absent), enter commit, compose |

All thirteen compile (`amu compile --target wasm32-browser`), all pass
`amu check`, none declares or calls a capability. The device-auth guest
runs its chain as a linear scan over numbered checks -- each a small
(state, flags, method) function -- so the refusal order can be diffed
against the oracle's cond line by line.

## The capability question, measured

The question this ADR answers directly: **does kotoba-only migration now
require writing capabilities?** No — and this is not a loosening, it is the
language working as specified:

1. **Effect inference is the default.** `infer-effects` derives the effect
   row from the body. A namespace that only moves immutable documents
   infers `:effects #{}` — measured on all three guests and on the nine
   earlier guests across org-ietf-{smtp,pop3,imap,ed25519,x25519,ical,cbor},
   mail, mailer.
2. **Capability syntax appears only when an effect exists.** `perform
   :kind/op v` desugars to `cap-call`; the namespace must then declare
   `:capabilities`. Wire IDs are never source vocabulary.
3. **The pure-product profile forbids the declaration outright** — a guest
   compiled under it that declares `:capabilities` is rejected
   (`pure-product profile rejects :capabilities (guest must be effect-free)`).
4. **Unison-shaped, not Unison-identical**: the effect row is statically
   tracked like an Unison ability, but authority stays a named host boundary
   (`:cap/kind` / `:cap/resource` / `:cap/holder`), not a first-class
   ability value. Ambient authority remains permanently excluded
   (ADR-2608650000).

The practical rule this ADR records: **a pure guest is written with zero
capability lines; a guest that touches the world declares exactly the
capabilities it uses, through `perform`, and nothing else.**

## The measured bounds that shaped the port

Each is stated in the guest's own header so the next reader does not
re-derive it:

- `:container-items 32` — a topic queue and the topic count cap at 32; the
  33rd sample traps `document-vector-too-large`, fail-closed, not a silent
  drop. The oracle's EDN maps are unbounded; this is the one honest
  difference, and it is the same bound org-ietf-pop3 states for its body
  channel.
- `max-parameters 5` — booleans travel as an i64 flags vector beside the
  sequences; ladder state travels as one 5-lane vector.
- `document-is-null` has no admitted lowering — absence is read as
  `document-count = 0`.
- CID strings cannot be bounded guest values — the guest receives CID
  EQUALITY as booleans; the sha256 / immutable-url / CID regexes stay in
  the host, where the grant.publisher admission owns them.
- `rem` / `mod` have no admitted lowering — spelled `quot`-and-subtract.

## What stays in the host, deliberately

- `grant.ota/admit`, `grant.update/advance`, `grant.update/rollback-required?`
  — closures over publisher state and clocks. Mechanism.
- `sha256-pattern`, `immutable-url-pattern`, CID/IPNS patterns — regexes.
  A pattern that can match the wire shape can match a great deal else; the
  positions that matter are checked where the bytes live.
- The clock, the socket, the disk — as before.

## Consequences

- The three guests are compiled artifacts with definition CIDs; their
  oracles remain the executable spec, checked by parity, not deleted.
- The bus the runtime executes (`aiueos.execute.cljc`'s `topic-*` host
  functions threading `aiueos.topic`'s atom) is unchanged; the guest now
  speaks the same semantics the host's bus implements, so a component and
  the kernel share one topic vocabulary instead of two hand-copied ones.
- Future ports follow the same test: if a namespace's decisions are
  arithmetic and keywords, it is a guest; if it opens a socket, holds a
  clock or runs a regex over wire bytes, it stays in the host until the
  capability kit for it exists.


## 適用記録 (2026-09-07 closing)

この ADR が初めて全 13 guest として着地したのは main `4ca9496` (merge of
`agent/kotoba-guests-imekey`)。検証は 2 段階:

1. **compile 実測** — 全 guest が `amu check` と
   `amu compile --target wasm32-browser` を通過 (wasm 2.3KB〜8.0KB)。
   `:effects #{}` と `:admission {:required #{}}` は全件の check 出力で確認。
2. **capability ゼロの確認** — 全 13 ファイルに `perform` も `cap-call` も
   `:capabilities` 宣言も含まれない (上記 1-3 の規則の正の実例)。

テーブルが書いた通りに動いた実例: mora テーブル 111 エントリが
document-map の 32-entry limit に当たり、4 chunk map への分割という
機構解で通った (13 番目の guest)。limit を「推定」ではなく「実測」として
扱ったから、分割は最初から設計に含まれた。

未着手 (次の最初の一手): `phone_bind` / `hvt` / `launcher` / `cloud_live`
は JVM/FFM/chicory 直結が本体で、capability kit 設計が前提。
`compositor` 本体の残部は string-heavy で、IME と同じ slice 単位で
続けられる — `feed` と `latin-leaked?` が次の 2 つ。
