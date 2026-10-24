# kotoba-ip

[![CI](https://github.com/kotoba-lang/ip/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/ip/actions/workflows/ci.yml)

**Chip IP block domain in pure Clojure: bus protocol RTL generation,
clock-domain-crossing (CDC) analysis, IP-XACT component catalog/export, and
network-on-chip (NoC) topology synthesis.** A
[kotoba-lang](https://github.com/kotoba-lang) capability library, ported
from [`kami-engine`](https://github.com/kotoba-lang/kami-engine)'s
`kami-ip` Rust crate as part of the
[kotoba runtime SDK `.cljc` migration](../../../90-docs/adr/2607010000-kotoba-runtime-sdk-cljc-migration.md)
(kami-engine's Rust workspace is being retired in favor of pure Clojure
authority repos).

No network, no I/O, no GPU in the domain namespaces — pure data
transformation and string generation, portable `.cljc` across JVM /
ClojureScript.

## Maturity

| | |
|---|---|
| Role | capability |
| Tests | 30 assertions, all green |
| Lint | clj-kondo, 0 errors / 0 warnings |

## Namespaces

```clojure
(require '[kotoba.ip.bus-protocol :as bus])
(require '[kotoba.ip.cdc :as cdc])
(require '[kotoba.ip.ip-xact :as ip-xact])
(require '[kotoba.ip.noc :as noc])
```

### `kotoba.ip.bus-protocol` — AXI4 / APB bus protocol

AXI4 signal catalog (`axi4-signals`, `axi4-signal-groups`) and Verilog RTL
port-list generation for AXI4 master/slave interfaces.

```clojure
(bus/generate-axi4-master (bus/axi-config 32 64 4 0))
;; => "// AXI4 Master — addr=32, data=64, id=4\nmodule axi4_master (\n  ...
```

`apb-config` exists as a constructor (matching the Rust `ApbConfig`
struct), but there is no `generate-apb-*` function — the original Rust
source never implemented one either (only AXI4 master/slave RTL was
generated). Preserved as-is rather than inventing new behavior.

### `kotoba.ip.cdc` — Clock domain crossing analysis

`analyze-cdc` checks signals crossing between clock domains for missing
synchronizers and glitch-prone multi-bit crossings without Gray-code
encoding.

```clojure
(cdc/analyze-cdc
  [(cdc/cdc-signal "req" "clk_100" "clk_200" 1 false nil)]
  [(cdc/clock-domain "clk_100" 100.0) (cdc/clock-domain "clk_200" 200.0)])
;; => {:crossings [...] :violations [{:signal "req" :issue :missing-synchronizer}]}
```

Faithfully ported including a source quirk: the "glitch-prone" check's
FIFO exemption can never trigger, because the crossing type it checks is
always derived as `:single-bit`/`:multi-bit` (never `:fifo-async`) within
`analyze-cdc` itself. Documented in the namespace docstring rather than
silently "fixed", to keep behavioral parity with the Rust original.

### `kotoba.ip.ip-xact` — IP-XACT component catalog + XML export

Component/bus-interface/port/parameter data constructors, catalog lookup
by bus type, and IEEE 1685-2014 XML export.

```clojure
(ip-xact/export-ip-xact-xml
  (ip-xact/ip-xact-component
    {:vendor "gftd" :library "kami" :name "uart_controller" :version "1.0"
     :bus-interfaces [...] :ports [...] :parameters [...]}))
;; => "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<ipxact:component ...
```

### `kotoba.ip.noc` — Network-on-chip topology synthesis

`generate-noc` builds routers and links for mesh / ring / crossbar / fat
tree topologies and estimates area (um²) and worst-case latency (cycles).

```clojure
(noc/generate-noc (noc/noc-config (noc/mesh-topology 4 4) 64 128 :xy))
;; => {:routers [...16 routers...] :links [...] :total-area-um2 ... :estimated-latency-cycles ...}
```

## EDN-for-constants

Hardcoded constants from the Rust source (the AXI4 signal catalog, the
NoC area/latency model's empirical unit costs) are extracted into EDN
resource files under `resources/kotoba/ip/` — the canonical, diff-able
source of truth. The `.cljc` domain namespaces embed the same data as
plain Clojure literals (so they stay usable without resource IO on every
platform, including ClojureScript); a `:clj`-only round-trip test in
`test/` asserts the embedded data and the EDN resource never drift apart.
`kotoba.ip.resources` (plain `.clj`, JVM-only) is the loader, mirroring
`kami-scene-contracts`' `load-edn-resource` pattern.

## What was NOT ported

The Rust `kami-ip` crate (`orgs/kotoba-lang/kami-engine/kami-ip`, recovered
from `kami-engine` git history at the point this repo was created) is
entirely pure domain logic — data structures, string/RTL/XML generation,
and topology math. There is no GPU (`wgpu`), OS, or `wasm-bindgen` FFI
bridge/glue code in this crate to skip: **everything in the source crate
was ported.** The one intentional omission is noted above under
`kotoba.ip.bus-protocol` — `apb-config` has no matching RTL generator
because the Rust source never had one.

Also not carried over: `serde`/`serde_json` (de)serialization derives,
`thiserror` error types, and `glam` (unused in this crate) — these are
Rust-ecosystem plumbing with no meaning in a `.cljc` world; plain Clojure
maps/keywords and `ex-info` fill the equivalent roles natively.

## License

Apache License 2.0.
