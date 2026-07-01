# kotoba

Kotoba host repository for the CLJC/EDN-authoritative public CLI.

The public language and command contract lives in
[`kotoba-lang/kotoba-lang`](https://github.com/kotoba-lang/kotoba-lang). This
repository provides host launchers, packaging, docs, and SDK fixtures that
delegate to that contract instead of defining independent native behavior.

## Install

### Homebrew

```bash
brew tap etzhayyim/kotoba
brew install kotoba
kotoba check --kind cli-contract --json
```

### From Source

```bash
git clone https://github.com/kotoba-lang/kotoba.git
cd kotoba
bin/kotoba-clj check --kind cli-contract --json
```

## Repository Boundary

Current source of truth:

- CLI command schema and behavior: `kotoba-lang/kotoba-lang`
- launcher and package wiring: this repository
- modal/python SDK fixtures: `sdk/kotoba-modal`
- static documentation: `docs/`

Legacy Rust crates, Cargo workspace files, Rust CI, and Rust server deployment
assets have been removed from this repository. Historical Rust implementation
details remain available in git history. New behavior should land first in
CLJC/EDN contracts and only then be hosted by platform-specific adapters when
needed.

## Development

```bash
clojure -M:test
bin/kotoba-clj check --kind cli-contract --json
```

The default CI gates the CLJ launcher and Python SDK package surface.

## Docs

The static docs site is served from `docs/` via GitHub Pages. Some ADRs describe
historical native backends; treat those as migration records unless a current
CLJC/EDN contract references them.
