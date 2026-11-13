# AWAI-174 policy/query basis race — 2026-11-13 UTC

At kotoba base `426ddd2a635b6714ad60a8d7852f4f802e3e54b6`, a request
resolved the row policy using one graph head, then the query fetched the head
again. A deterministic test changes the returned head between those calls.
The first basis is public and contains no secret; the second adds both a
protected-prefix policy and a secret. Under the old code the vector query and
Datalog join each return the new secret under the old policy. The candidate
captures one graph head and supplies it to both policy resolution and dispatch.
The test also verifies that the current protected policy denies an anonymous
reader and grants a reader with the existing read-protected capability.

Local reference oracle on macOS arm64: Clojure CLI 1.12.5.1654 / Temurin
OpenJDK 21.0.1+12. The previous AWAI-174 v6 oracle classpath was copied, `.cljk`
inputs staged as `.cljc`, and missing local source dependencies added. Existing
`:kotoba/export` ns attributes in copied dependencies were quoted for this
oracle. The browser-only trampoline was truncated after `ex-data-chain` for
JVM loading; SPARQL, Cypher and unrelated query-exec functions were replaced
with throwing stubs. None of these stubs is called by the tested paths. The
complete staged candidate classpath hashes are in `inputs.json`; scratch source
mapping and baseline/candidate outputs are retained in `.agent-output/oracle`.
This is an adapted local reference measurement, not a Native, deployed or
full-server compatibility test.

The candidate handler and test SHA-256 are respectively
`a2d3c16bd55f07e374a6347c4feae45d8fd587300f48698421a63df25ad2d7ea` and
`6a2574aea8968b473ce0fcc34f595ace5b1647b1f8b5bccdc5dc7c153957627c`.
The old handler bytes are `83d7f14306e485e9fd124f6dd47a4952e337d0472463fe106f72eb5d74d80e71`.

With the same staged regression test, old handler: 1 test, 8 assertions pass,
4 fail (both query shapes reveal the new secret and both read the head twice).
Candidate: targeted race, transact/query round trip and unknown method tests:
3 tests, 26 assertions pass, no failures or errors. The local command was
`clojure -Sdeps '{:paths [".agent-output/oracle/base"]}' -M -e ...`, with
individual test vars selected by `clojure.test/test-vars`; full exact commands
and outputs remain in the task scratch. No dependencies were downloaded for
this run. Signed basis, revocation freshness, durable receipt and Native query
remain open; a pinned read basis alone establishes none of them.
