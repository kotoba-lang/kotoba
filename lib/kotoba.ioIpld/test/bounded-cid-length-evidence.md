# AWAI-531 bounded CID input length reference, 2026-11-14

Bounded IPLD reads now reject a non-string, empty or greater-than-128-character CID before invoking the CID parser or provider. The supported canonical raw and DAG-CBOR sha2-256 CIDv1 profile is shorter than this limit. The caller/provider still owns input acquisition and the allocation of the string itself.

A local JVM negative control against prior head `970b5954f3145e27d82a2d8c79b7261303719b82` passed a 100001-character CID with an instrumented parser and observed one parser call. The candidate test asserts the same input is rejected with zero parser and provider calls. On macOS OpenJDK 21.0.1 / Clojure 1.12.5, the relevant CBOR/IPLD suites passed 35 tests / 178 assertions; compiled ClojureScript 1.11.132 / Node 26.0.0 passed 8 tests / 56 assertions. Source staging and the existing local dependency overlay match `bounded-cid-preflight-evidence.md`; no downloads. This is hosted evidence, not Native or CI qualification.
