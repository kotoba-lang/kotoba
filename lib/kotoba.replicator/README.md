# kotoba-replicator (utsushimi 写身)

[![CI](https://github.com/kotoba-lang/replicator/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/replicator/actions/workflows/ci.yml)

Synthetic data generation + domain randomization — `omni.replicator.core`
API-compat target. Safety-gated `.kotoba` contract derived from the Rust `kami-replicator`
crate (`kotoba-lang/kami-engine`), per ADR-2607010930 (clj-wgsl migration
Phase 4).

**Status**: R1.0 path reservation (ADR-2605261800). No runtime code — in
either the original Rust crate or this port.

## Port scope

The Rust source (`kami-replicator/src/lib.rs`) exports only status
constants; there was no domain logic to port. This library preserves those
values through typed getters compiled for restricted JavaScript and Wasm:

```clojure
(defn kami-name-value [] :string "utsushimi")
(defn nv-compat-target-value [] :string "omni.replicator.core")
```

## Unported (out of scope)

Nothing was skipped — the source crate had no runtime logic (random
pose/light/texture/material distribution, BasicWriter/KittiWriter/CocoWriter,
yatachain attestation) to port yet. When the R1.3 deliverable lands, the
pure-data portions (distribution parameters, writer schemas) belong here.

## Scope (R1.3 deliverable, per original ADR)

- Random pose / light / texture / material distribution
- BasicWriter / KittiWriter / CocoWriter API mirror
- Seed → yatachain attestation for reproducibility (G6 inheritance)

## License

Apache License 2.0.
