# Kotoba library IDs, standard-library monorepo, and Lexicon events

Status: **accepted design, 2026-10-21 owner decision**. The source pilot and
development resolver are implemented here. Event transport, generated event
clients, signed monorepo package releases, and native qualification are open.

The decision authority is
[ADR-2610210900](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2610210900-kotoba-library-monorepo-and-lexicon-events.kotoba).
This document explains its implementation in `kotoba-lang/kotoba`.

## Names and authority

The language-owned [Kotoba naming Spec](https://github.com/kotoba-lang/kotoba-lang/blob/main/docs/lang/naming.md)
defines the contexts and Lisp punctuation conventions. Its Kotoba ADL resource
`kotoba/spec/naming.kotoba` ships with the portable import contract;
`kotoba.lang.naming` is the sole validator. The CLI catalog delegates to it.

Bundled libraries have project-local dotted IDs: `kotoba.coll`, `kotoba.spec`,
and `kotoba.json`. Each segment starts with a lowercase ASCII letter and
continues with ASCII letters or digits. Names are case-sensitive. There is no
implicit case folding, hyphen substitution, prefix rewrite, or DNS lookup.
`kotoba.*` is a Kotoba namespace, **not an ATProto NSID or a claim to a DNS
domain**. We do not own `app.kotoba`; it is not the default library namespace.
An ATProto adapter must explicitly project contracts to an NSID whose domain
authority its publisher controls. It must preserve the original contract CID
and must not silently treat the project-local ID as a valid ATProto authority.

`lib/catalog.edn` is the development source inventory. Every package directly
owns a vector of legacy aliases. For example `kotoba-lang/json`,
`io.github.kotoba-lang/json`, and `kotoba.lang.json` resolve to `kotoba.json`.
Alias chains do not exist. Collisions between any canonical ID and alias, or
between aliases, reject the **whole** catalog. Unknown names refuse. Legacy
namespace APIs remain ordinary source namespaces; we do not copy value vars,
protocol identities, macros, or records through a new facade.

Discovery only returns source locations. It performs no network operation and
does not grant link, execution, storage, or publish authority. This catalog is
not a replacement for the signed package registry. Existing signed locks keep
their exact names, repository RID, tree CID, manifest CID, signers, grants,
and definition CIDs. A future release alias must be bound by the same pinned
catalog and resolve to one exact admitted manifest; it must not rewrite an
existing signed manifest or select a floating latest version.

## Physical repository boundaries

`kotoba-lang/kotoba` owns the standard-library source pilot under
`lib/kotoba.{coll,spec,json}`. Each package retains its API, tests, license,
dependency declarations, provenance, and eventual independent release identity.
Its same-family per-definition dependencies are included in that package.
`imports.json` names each original commit, Git tree, and file digest;
`local-changes.json` explains the dependency/configuration changes after import.
These records are provenance, not signature or runtime-qualification evidence.

The imported source and tests are compatibility/portable sources. Moving them
is **not** a `.kotoba` source conversion, a whole-component Q9 migration,
selfhost completion, or a native/Web/Wasm qualification result. Existing
`.kotoba` sources are retained at their original relative paths. Old
repositories remain available to existing pinned consumers; retirement is a
separate consumer-migration and publication task.

Amu, kototama, aiueos, osaho, ABI, the neutral core contracts, protocol codecs,
and the language/CLI contract keep their existing repositories and authority.
Bundling standard libraries does not move any of those implementations here.
Product apps remain separate when deployment, ownership, or release needs it.
Thin vendor API bindings belong to the registry/adapter classification of
JUN-69; this pilot does not bulk-move them.

Co-location follows shared maintenance and frequent coordinated changes.
Separate repos need a real ownership, build, deployment, or release boundary;
one function or one external consumer alone does not require a repo. The
per-definition identity/dependency graph remains useful independently of Git
placement. This supersedes the physical repo-per-library/per-definition rule
for bundled standard libraries, not definition-level identity.

## Identity and cache

Keep four identities separate: a schema/contract CID, a checked definition's
DefCID, immutable data/state CIDs, and a signed package-manifest CID. Reuse
existing canonical encoders and the owning repositories' contracts. No second
hash or admission implementation is introduced by this pilot.

A package release must cover its own source subtree and explicit external
dependency closure. A monorepo HEAD is provenance, not the cache identity of
every library. Renaming a human alias does not change a definition's normalized
code identity. Moving source or renaming a manifest can change package/tree/
manifest identity and requires a new admitted release. Do not claim the old
manifest CID survives the move.

Pure result caches bind DefCID, all argument CIDs, captured state snapshots,
and execution-semantics versions. Code-generation caches also bind compiler,
target, ABI, and options. Impure operations are not memoized or re-executed by
replay. Private values and caches stay scoped to their authorized owner.
Content equality never grants access or execution authority. The checker's
`source-sha256` is a diagnostic digest of a source inventory, **not** a package
CID or a newly qualified DefCID.

## Lexicon-driven publish and subscribe

The machine-readable design is [spec/lexicon-events.edn](../spec/lexicon-events.edn).
It is the **Kotoba Lexicon profile**, inspired by ATProto Lexicon's typed
records/procedures/subscriptions. Its local IDs and event declarations are not
wire-compatible ATProto Lexicon v1 extensions. ATProto, NATS, and other wire
formats are explicit projections. Checked code types, effects, and ABI retain
their existing authorities; a schema does not grant an effect.

An event declaration binds the concrete subject, payload schema CID, allowed
scope kind, resource-key shape, bounded selectors, delivery/retention policy,
and separate `publish`, `subscribe`, `ack`, `unsubscribe` operations. A code
generator can derive typed clients, validation calls, documentation, and a
transport plan from it. The host intersects requested operations with the
declaration, current grants, and supported operations. It starts with none.

The intended syntax is illustrative, not an implemented language/CLI surface:

```clojure
(publish 'kotoba.docs.document.changed
         {:scope cell-ref :resource-id "d42" :schema-cid schema-cid
          :request-id request-id :payload change})

(subscribe 'kotoba.docs.document.changed
           {:scope cell-ref :resource-id "d42" :after cursor :limit 128})
```

`publish` validates and authorizes before storing or sending anything. A
durable event is accepted only with a committed journal record/receipt. A
state-derived event and state transition share an atomic journal/outbox commit;
transport notification follows that commit and can be retried. External
delivery cannot make an uncommitted state transition true. A transient event
is explicitly transient and must never be represented as durable.

The immutable event envelope binds contract/schema CID, concrete subject,
scope, producer identity, resource key, payload CID, causal parents, and a
unique action/request identity. Two occurrences with identical payloads can
therefore be distinct events. EventCID uses the existing boundary's canonical
bytes. Transport sequence, retry count, consumer cursor, and signatures are
separate from the immutable payload identity; signing/admission follows the
existing classical-plus-PQ floor. An idempotency key is scoped to producer and
scope: repeating it with different content refuses, and repeating the same
request returns the same committed event/receipt.

Subscriptions are handles scoped to one principal, cell, contract revision,
filter, and bounded lifetime. A subject alone is not a global resource address.
Resource IDs, field paths, and tenant/cell scope are separate fields, never
concatenated into unescaped subject tokens. Publish takes a concrete subject;
wildcards are subscription selectors only. The Kotoba selector grammar uses
`*` for exactly one segment and terminal `>` for one or more remaining
segments. Patterns are expanded/intersected with declared event subjects and
the caller's grants; they never broaden authority. ATProto's NSID glob grammar
is different and must not be reused as this matcher.

The naming Spec defines dotted field paths as shorthand for relative string
keys, and typed vectors for exact keys and array indices. For example,
`body.display-name` means `["body" "display-name"]`, while `["body" "display.name"]`
keeps the dot inside one literal key. No implicit code lookup, data access,
publication or subscription is added by dotted spelling. The design gate checks
the event example with the language-owned validator and runs its normative
positive/negative examples through the actual ADL reader. Transport and grant
checks remain separate gates.

Durable delivery assumes at-least-once, not exactly-once business effects.
Consumers deduplicate by committed EventCID/action identity, commit their
processing before ack, and use their own atomic outbox when processing creates
a further effect. Ordering is per declared journal/partition; timestamps or a
shared subject imply no cross-cell total order. A cursor binds stream epoch,
scope, filter/contract revision, and position. Resuming checks current grants,
including revocation. Expired retention or incompatible cursors return an
explicit `cursor-expired`/`cursor-incompatible` response and require a fresh
snapshot, never an implicit switch to "from now". Snapshot read returns an
atomic journal watermark; catch-up starts after that watermark and transitions
to live delivery without a read/subscribe gap.

Limits bound payload bytes, queue bytes/messages, in-flight deliveries, replay
batch size, ack timeout, retry count, subscription lifetime, and retention.
Overflow is explicit; a durable stream cannot silently drop old messages.
Dead-letter/quarantine is an explicit scoped destination. Unsubscribe and ack
are declared operations too, not authority inherited from subscribe.

The default host can be local/browser-side. NATS/JetStream is an optional
transport adapter; no central broker becomes language or state authority.
Remote subscribe, reconnect, replay, publish, ack, unsubscribe, or resource
creation must map to exact approved external operations through the canonical
`kotoba.app.client-runtime.v1` broker. State the service, endpoint, operation,
and data categories and obtain fresh operation-specific consent. A local
subscription handle or browser permission is not remote-operation approval.
Reconnection cannot silently reuse an old approval. If the broker has no
reviewed support for a streaming/WebSocket/browser operation, that adapter is
blocked; do not create a product-local consent gate or an app-origin proxy.
Application origins continue to serve static artifacts only.

## Verification and remaining work

- `node scripts/check-libraries.mjs`: import bytes, modes, licenses, local
  changes, source digests, and complete portable test inventory.
- `node scripts/test-libraries.mjs`: the declared dependency closure and all
  portable imported suites with implicit workspace stdlib disabled and JVM
  executables blocked. `KBB_ENGINE` may select the installed SCI engine.
- `scripts/library-catalog.cljk`: real development lookup and classpath
  resolution through canonical IDs and old aliases.

The public source import/CLI contract now resolves these IDs and aliases via
`library import` and explicit `run --runtime sci --library`; see
[source imports](library-source-import.md). Checked/native package imports are
not provided by that compatibility route. Next gates are signed subtree
package publication/admission, checked/native import integration, event schema
compiler/codegen, journal/host implementations, browser/transport qualification,
and eventual consumer migration. None is completed by accepting this ADR or
passing portable compatibility tests.

References: [ATProto Lexicon](https://atproto.com/specs/lexicon),
[NATS subjects](https://docs.nats.io/concepts/subjects),
[JetStream](https://docs.nats.io/concepts/jetstream),
[Unison content-addressed code](https://www.unison-lang.org/docs/the-big-idea/),
[package publication](ADR-kotoba-library-publish-cli.md).
