# kotoba Genome

[![ci](https://github.com/kotoba-lang/genome/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/genome/actions/workflows/ci.yml)

Open-source genomics workflow workbench as EDN data + portable CLJC pipeline model.

This repository follows the kotoba industrial-app pattern:

- `resources/genome/domain.edn` is the data registry.
- `src/kotoba/genome/core.cljk` is the pure portable domain engine.
- `src/kotoba/genome/runner.cljk` is a conservative host dry-run runner.
- `docs/index.html` is the GitHub Pages workbench.

Pages: https://kotoba-lang.github.io/genome/

## Scope

This is an OSS workbench skeleton for 遺伝子/バイオインフォマティクス. It does not claim proprietary compatibility with commercial systems. It focuses on open artifact registries, policy-gated runners, coverage/maturity scoring, and EDN handoff.

## Test

```sh
kbb -M:test
kbb -M:lint
```

`test/kotoba/genome/` covers the domain engine (`core.cljc`: scoring,
artifact classification, runner-plan construction, coverage/maturity
review), the host dry-run runner (`runner.clj`: executable whitelist
enforcement, dry-run-by-default safety), and the pure Hiccup/CSS UI
helpers (`ui.cljc`).

## Verify

```sh
kbb -M -e '(load-file "src/kotoba/genome/core.cljk") (println :ok)'
python3 -m http.server 8765 --directory docs
```
