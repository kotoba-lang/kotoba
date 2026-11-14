# AWAI-531 structural value decoding: host oracle, 2026-11-14

`decode-structurally-bounded` and `verify-value-cid-structurally-bounded` reuse the opt-in CBOR byte, depth and item limits before constructing a value; canonical re-encoding and CID verification still apply. The existing `decode-bounded` remains a byte-only API. Fetching the bytes and allocating the input buffer are outside this limit.

On macOS, local staged `.cljc` copies (namespace export attribute quoted for host readers): JVM Clojure tests for `ipld.value-test`, `kotoba.value.value-cid-test`, `ipld.canonical-value-bytes-test`, and `ipld.structural-value-test`: 28 tests, 195 assertions, zero failures/errors. ClojureScript 1.11.132 compiled for Node, same namespaces: 28 tests, 196 assertions, zero failures/errors. The tests include canonical values, mismatched CID, a noncanonical encoding with its own matching CID, invalid limits, truncated input, a 10,000-level CBOR nesting, and an enormous claimed array. Compilation and test output are in the local worktree `.agent-output/oracle/`.

This is hosted evidence only. It does not qualify native artifacts, provider fetch allocation, persistent index integration, or performance.
