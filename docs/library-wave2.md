# Bootstrap, I/O and state library review (JUN-196)

The second wave selects eleven standard libraries: `kotoba.text`, `kotoba.test`,
`kotoba.edn`, `kotoba.io`, `kotoba.fs`, `kotoba.process`, `kotoba.async`,
`kotoba.scheduler`, `kotoba.store`, `kotoba.fmt`, and `kotoba.log`. Their complete
same-family dependency closures include the historical `kotoba-io-*` names.
All current-default source snapshots, licenses, tests and file modes are kept
in `imports.json`; changes are explained and hashed in `local-changes.json`.

The catalog now contains 21 package IDs and 58 exact aliases. Dotted IDs select
packages; they do not rename Lisp source symbols, define field paths, grant
capabilities, or start event subscriptions. Lexicon events remain the accepted
design described by the ADR, without a new transport implementation here.

## Bootstrap and namespace ownership

Text, test and the compatibility EDN reader resolve from bundled source. Old
self-dependencies in text/EDN/I/O are removed, and the library test resolver
bootstraps from checked-in text with JVM commands blocked. External dependencies
remain pinned. EDN interoperability does not change `.kotoba` as the format for
new normative Kotoba specifications.

`kotoba.lang.text` and `kotoba.text` retain their existing APIs and alias identity.
`kotoba.string` belongs to its already bundled canonical definition facade.
Text's duplicate old `kotoba.string` facade is kept under `provenance/text/src`,
outside active source paths. The text/string behavioral parity tests remain;
the text alias identity check now applies to `kotoba.text`. Classpath order
must not select between two definitions of the same host namespace. The canonical
string facade also forwards the old text alias's `re-quote`; the JVM suite checks
that every legacy text export remains available alongside canonical `spec-re`.

## Effects and state

I/O protocols and memory buffers, filesystem paths and memory implementations,
process argument validation, bounded channel/scope transitions, tick scheduling,
KV composition and structured log records are standard-library source.
Injected handles, clocks and sinks remain explicit. Host filesystem/process
namespaces retain their existing behavior, including existing ambient JVM/Node
compatibility APIs. Bundling them grants no new sandbox or app capability.

Store now uses `read-bytes`/`write-bytes` rather than the filesystem text face.
The former combination corrupted binary data. Both the legacy implementation
and canonical definition facade have a regression test over all 256 byte values.
The WIT policy authority stays external; `with-policy` remains a host-side
composition helper and is not an unforgeable authorization boundary.

Amu, kototama, aiueos, osaho, ABI, compiler/language, security and protocol owners
remain separate. `num` includes GPU backends and retains its independent release
boundary. `atom` is Atom feeds, not mutable state. The native memory hash kernel
needs compiler-specific review. `math` and `i64` are held for missing licenses.

## Unintegrated branch decisions

[`branch-reviews.json`](../lib/branch-reviews.json) records immutable tips and
file-level decisions. Bytes branch `5a9dcec` supplies the two SHA1/SHA256
dual-runtime modules exactly; main's byte core/base64 fixes are retained. Host
digest/HMAC vectors pass, and both closed module graphs pass the CLI's pinned
Amu admission. Admission alone is not native execution qualification.

JSON branch `3b2ffc7` passes the host suite, but the current pinned Amu rejects
`json.core/decode` with `kotoba.error/abort-unhandled-export`. Its old claim of
admission is not current proof. The branch is held pending an explicit
result/abort API design and native tests. Current main's JSON implementation
stays in use, and its source repository remains writable.

Other unreviewed remote branches, local branches, WIP or stashes hold their
source repositories from archive. Copying main alone does not retire novel work.

## Verification and limits

The test registry lists every imported suite. The portable driver runs all
portable suites with JVM bootstrap blocked. The JVM driver runs original JVM
oracles and current bytes admission. Async's native oracle uses its original
test-only Amu `c3be07f` in `lib/async-test`, isolated from the launcher graph:
today's CLI compiler reserves `take` and has different abort export rules.
Passing the historical oracle does not qualify async on today's compiler.
The original channel tests still execute KIR, JavaScript and typed Wasm;
generated probe data goes through stdin within existing process argument limits.

Public `bin/kotoba` tests resolve every canonical ID and alias, execute all eleven
new packages with deterministic injected handles, and assert source paths under
their monorepo subtrees. Merged-main CI and the same public CLI are verified
before archive; exact receipts and outstanding work are tracked in
[JUN-196](https://linear.app/com-junkawasaki/issue/JUN-196).
