# Kotoba-route port harness (machine_ir / aarch64)

Bootstrap tooling for ADR 0089. The Kotoba side always runs as natively compiled
code (aarch64 `.kexe` executed by amu's `tools/kexe_loader.c`); the JVM is the
bootstrap-reference host that records what the host reading answers.

Work directory: `KR_WORK` (default `/tmp/kotoba-route`). It holds `host/` (pristine
host files), `twins/` (Kotoba twins), `ov/` (overlay), `guest/` (differential guest),
`cases/` (host recordings), `dxout/`, `cp-ov.txt` / `cp-guest.txt` (the wall classpath
with `wt-D-kotoba-native/src` replaced by `$KR_WORK/ov/src` / `$KR_WORK/guest/src`)
and `kexe-loader` (`cc tools/kexe_loader.c -std=c11 -O2`).

| script | what it does |
|---|---|
| `merge.py HOST TWINS OUT` | twins beside the verbatim host forms; `(nil-twin ..)`, `(folded-twin ..)`, `(kotoba-exports [..])` |
| `hostview.py PRISTINE MERGED` | the host reading of MERGED equals PRISTINE, top-level form by form |
| `ov.py ledger/rows/overlay` | ledger counts; an overlay that hides unported host forms so `amu check` reaches the ported ones |
| `ledger.py FILE ROOT..` | per-definition TSV with differential coverage (`docs/kotoba-route-ledger.tsv`) |
| `build.sh` / `tbuild.sh` | merge + overlay + native check; `tbuild` turns `reject!` into a trap so a type error the abort inference swallows is reported with its span |
| `jvm-start.sh`, `j.sh`, `jvm-sync.sh`, `mi.clj` | a persistent JVM (socket REPL on 5791) with the current host sources reloaded; `mi/compile-guest`, recording (`wrap!`, `compile-corpus!`, `write-cases!`) |
| `rec.sh FN..` | record host calls of machine-ir FN over the corpus |
| `gen-guest.py ROOT FN[:a]..` | the guest: the Kotoba reading of ROOT (machine_ir or aarch64) plus a case dispatcher; modules not natively linkable become stubs |
| `dx.sh FN[:a]..` (`ROOT=aarch64`, `DX_INPUTS=file`, `NOCOMPILE=1`) | compile the guest, run every case, tally OK / ERR-OK / DIFF / ERR / MISS / TRAP |

Typical loop: edit `twins/machine_ir.cljk`, `build.sh`, then
`dx.sh lower-kir-module:a compile-gmir:a encode-mc-module:a` and
`ROOT=aarch64 dx.sh emit-program:a`.
