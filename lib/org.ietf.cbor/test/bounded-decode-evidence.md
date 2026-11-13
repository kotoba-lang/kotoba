# AWAI-531 bounded decode local oracle, 2026-11-14

Source baseline: Kotoba `426ddd2a635b6714ad60a8d7852f4f802e3e54b6`. These are local host reference runs, not Native qualification or a CI gate. The `.cljk` sources and tests were copied to `.cljc` files; the existing unquoted `:kotoba/export` namespace metadata was quoted in the copies for the host reader. No runtime fallback was added.

- JVM: Clojure CLI 1.12.5.1654; `cbor.core-test`, `ipld.core-test`, and both bounded decode test namespaces: 31 tests, 152 assertions, zero failures and errors. Command: `clojure -Sdeps '{:paths [".agent-output/oracle/src" ".agent-output/oracle/test" "<existing-local-dependency-classpath>"]}' -M -e '(require (quote cbor.core-test) (quote ipld.core-test) (quote cbor.bounded-decode-test) (quote ipld.bounded-decode-test)) (apply clojure.test/run-tests (quote [cbor.core-test ipld.core-test cbor.bounded-decode-test ipld.bounded-decode-test]))'`.
- ClojureScript 1.11.132 on Node v26.0.0: the two bounded namespaces, 4 tests, 30 assertions, zero failures and errors. Compiled using `cljs.main` with `:target :nodejs` and `:optimizations :none`, then executed with Node.
- Existing CBOR golden suite, JVM: both the unmodified baseline and this candidate yielded two errors due to pre-existing integer overflow in `cbor.core/write-int` at the minimum signed long. This is not a passing golden suite.
- nbb 1.4.208 / Node v26.0.0: both baseline and candidate fail to load existing `cbor.core` because `Tagged` cannot be resolved. No nbb success is claimed.

Limits in these tests cover oversized input, nesting, item counts, declared container sizes, canonical IPLD rejection, and 10,000 nested arrays. They do not establish Native execution, hostile-input memory ceilings for the full product, or durable storage recovery.
