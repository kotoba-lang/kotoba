# Kotoba guests

Thirteen namespaces in this repository compile as pure Kotoba guests.
`90-docs/adr/0202-first-kernel-guests-are-kotoba-only-and-carry-no-capability.md`
is the decision record; this page is the working reference.

## The guests

| guest | oracle (.cljc) | surface |
|---|---|---|
| `aiueos/topic.kotoba` | `src/aiueos/topic.cljk` | `empty-bus` `publish` `latest` `take-sample` `pending` `topic-count` `tick` `advance` |
| `aiueos/os_update.kotoba` | `src/aiueos/os_update.cljk` | `health-status` `boot-selection` `manifest-local-errors` `artifact-set-error?` |
| `aiueos/model_channel.kotoba` | `src/aiueos/model_channel.cljk` | `continuity-errors` `boot-decision` |
| `aiueos/runtime_update.kotoba` | `src/aiueos/runtime_update.cljk` | `health-status` `manifest-local-errors` `artifact-set-error?` (blue/green) |
| `aiueos/device_auth.kotoba` | `src/aiueos/device_auth.cljk` | `proof-problem` -- the sixteen-refusal decision chain |
| `aiueos/vm.kotoba` | `src/aiueos/vm.cljk` | `plan-errors` -- boot-plan validation decisions |
| `aiueos/hardware_qualification.kotoba` | `src/aiueos/hardware_qualification.cljk` | `qualify` -- fail-closed receipt classification |
| `aiueos/pid1.kotoba` | `src/aiueos/pid1.cljk` | `pid1-argv0?` -- the rdinit=/init contract |
| `aiueos/bare_metal.kotoba` | `src/aiueos/bare_metal.cljk` | `p2-result` -- P2 boot classification |
| `aiueos/virtio.kotoba` | `src/aiueos/virtio.cljk` | interrupt-status decoding, device-type mapping, irq-line validation |
| `aiueos/image.kotoba` | `src/aiueos/image.cljk` | `boot-input-errors` -- which missing/malformed initramfs input is a refusal |
| `aiueos/compositor/ime.kotoba` | `src/aiueos/compositor/ime.cljk` | `lookup` + `convert-buf` -- the romaji conversion core (111-entry mora table in 4 chunk maps) |
| `aiueos/compositor/ime_key.kotoba` | `src/aiueos/compositor/ime.cljk` | `handle-key` -- the full branch tree: bypass / escape / backspace / space / enter / compose |

## Building

```bash
amu check aiueos/topic.kotoba
amu compile aiueos/topic.kotoba --target wasm32-browser --output topic.wasm
# same for os_update.kotoba and model_channel.kotoba
```

## Do guests need capabilities? No — measured

A guest that only moves immutable documents **infers** an empty effect row
and compiles with zero capability lines. All eleven guests in the workspace
(org-ietf-{smtp,pop3,imap,ed25519,x25519,ical,cbor}, mail, mailer, and the
thirteen here) landed with `:effects #{}`.

- Effect inference is the default; the row is derived from the body.
- `perform :kind/op v` is the only capability spelling, used only when an
  effect exists; the namespace then declares `:capabilities`. Wire IDs are
  never source vocabulary.
- Under the pure-product profile the declaration is rejected outright.

The rule: **a pure guest is written with zero capability lines; a guest
that touches the world declares exactly the capabilities it uses, through
`perform`, and nothing else.** This is Unison-shaped (the effect row is
statically tracked like an ability) without being Unison-identical
(authority stays a named host boundary, and ambient authority remains
permanently excluded — ADR-2608650000).

## Measured bounds (stated in each guest's header)

| bound | effect |
|---|---|
| `:container-items 32` | a topic queue / topic count caps at 32; the 33rd sample traps `document-vector-too-large` (fail-closed, not a silent drop) |
| `max-parameters 5` | booleans travel as an i64 flags vector; ladder state as a 5-lane vector |
| no `document-is-null` lowering | absence is read as `document-count = 0` |
| no `rem` / `mod` lowering | spelled `quot`-and-subtract |
| CID strings unbounded | the guest receives CID EQUALITY as booleans |
| document-map entry limit (32) | the IME mora table (111 entries, measured) splits into 4 chunk maps scanned in order |

## What stays in the host

Regexes over wire bytes (sha256 / immutable-url / CID patterns), the
`grant.ota` / `grant.update` publisher closures, and the clock. The test
for future ports: if a namespace's decisions are arithmetic and keywords,
it is a guest; if it opens a socket, holds a clock or runs a regex over
wire bytes, it stays in the host until the capability kit for it exists.
