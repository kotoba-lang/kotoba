# kotoba.jsonrpc candidate

This stages the pure codec and NDJSON implementation from
`kotoba-lang/org-jsonrpc` at
`f1920b9b6436196ced37e621e54540abc3faf235` for consolidation in Kotoba.
The module retains the `org.jsonrpc` namespace and all 32 original exports.
Its source bytes are unchanged; only its path becomes `src/org/jsonrpc.kotoba`
for module resolution. Network transports, clocks and filesystem access stay
with their respective hosts.

**This package is not registered in `lib/catalog.edn`.** `candidate.edn`
records its proposed dotted ID and compatibility aliases. Public import/CLI
resolution, signed release, native qualification and source-repository
retirement are pending. Existing catalog and integrated-repository counts
are unchanged.

`imports.json` maps all 12 tracked files to their source commit and digests.
`local-changes.json` records text normalization. The complete public main
and merged PR #1 head history are in
`maintenance/library-candidates/2026-10-22/org-jsonrpc/public-history.bundle`
at the repository root; `preservation.json` records standalone restoration
and fsck. Local branches, stashes and WIP are excluded from that public bundle.
Apache-2.0 and the vendored protocol-vector copyright notice are retained.

The original scripts, workflow, README, examples and fixtures are under
`provenance/org-jsonrpc/`. Their historical v0.7.2 / Node execution claims do
not qualify this candidate. No old workflow or hosted build is activated.

`test/native/kotoba/jsonrpc/fixture.kotoba` uses a real `org.jsonrpc` import
and retains all 24 original test assertions. Public calls are qualified with
`rpc/`; the five non-exported inspection helpers are copied into the test
namespace with unchanged bodies. They are not added to the library API.
Run every test export in a fresh instance/context with fuel 512, expecting
integer 1 for each. A reduced corpus or aggregate result does not replace
these individual results. The examples likewise use module imports rather
than concatenating the library into a single compilation unit.

Before merge, record actual Amu selfhost-built compiler provenance and
compilation, native module linking, public `kotoba compile`, all 24 execution
results, applicable refusal/fuel cases, and import/CLI alias checks.
`merge-gate.json` tracks those requirements. Host executables, C loaders,
flattened inputs or ignored locks must not be substituted to obtain a pass.
Absent compiler functionality keeps the draft and source repository open.

The original codec implements a documented JSON subset: objects, arrays,
strings, integers, booleans and null, with quote, backslash, newline, tab and
carriage-return escapes. Floats, Unicode escapes and escaped slash are not
supported. Source parity and the 24 historical vectors are not a claim of
complete JSON or JSON-RPC conformance. Review unsupported document encoding
and parser escaping/refusal behavior during runtime qualification.
