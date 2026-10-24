# kotoba DSL core

[![CI](https://github.com/kotoba-lang/dsl-core/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/dsl-core/actions/workflows/ci.yml)

Shared validation contracts authored as sovereign, bounded `.kotoba` source.
JVM Clojure is a compiler/test host only and is not a production runtime.

Current surface:

- `kotoba.dsl.problem` — canonical namespaced validation problem documents and
  `errors` / `warnings` / `valid?` helpers.

Problem collections contain at most 32 entries, strings retain the 64 KiB UTF-8
budget, and malformed documents or unsupported severities fail closed.

This repo is intentionally small. Domain libraries such as `statechart`,
`states`, `sigma`, `policy`, and `torch` keep their own model and execution
semantics while sharing stable validation result conventions.

```sh
kbb -M:test
```
