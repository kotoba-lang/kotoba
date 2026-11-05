# Render closure and size budget for the shared cssom/browser (JUN-854, C1)

Measured 2026-11-05 on kotoba main `ca6a880d4`. Source modules are `.cljk` unless noted; none of the cssom modules is canonical `.kotoba` yet.

## 1. Render closure (from `browser.surface` downward; QuickJS, net and session excluded)

| module | lines | bytes | note |
| -- | --: | --: | -- |
| browser.surface | 328 | 13,317 | root |
| browser.text-edit (`.kotoba`) | 312 | 14,851 | already canonical |
| cssom.layout | 18,815 | 1,084,089 | 67 `#"` literals |
| cssom.core | 11,282 | 603,564 | requires text, wasm.dom, host.color, bounded-regex |
| kotoba.wasm.dom (domGpu; `.cljk` 259 + `.kotoba` 50) | 309 | 11,058 (`.cljk`) | |
| kotoba.wasm.host.color | 433 | 18,248 | |
| kotoba.lang.bounded-regex (`.kotoba`) | 749 | 31,372 | already canonical |
| kotoba.lang.text (`.kotoba` 203 + `.cljk` 900) | 203 | n/a | `.kotoba` already canonical |
| **closure total (excl. text .cljk)** | **about 32.4k** | **about 1.78 MB** | |

htmldom (`htmldom.core`, 2,114 lines, 114,107 B) is needed only if documents are parsed in the kernel; it requires cssom.core and wasm.dom. With it the closure is about 34.5k lines, 1.89 MB of source.

`browser.surface` itself requires only `browser.text-edit`, `cssom.layout` and `kotoba.wasm.dom`.

## 2. Calibration (measured, from the ML-DSA stage builds, kernel-v3 text segment)

Text segment (PT_LOAD flags R+X) of `KERNEL.ELF`:

| build | modules in graph | text bytes | delta |
| -- | --: | --: | --: |
| keccak/ntt (stage 2) | 336 files, 55,235 lines | 2,151,680 | |
| + mldsa-sample (stage 3) | 338, 55,491 | 2,204,672 | +52,992 for +256 lines (+15,456 source B) |
| + mldsa-verify (stage 4) | 340, 55,729 | 2,259,456 | +54,784 for +238 lines (+13,475 source B) |

* Dense arithmetic kernel code costs 207-230 text B per line, i.e. **3.4-4.1 text bytes per source byte** (52,992 / 15,456 and 54,784 / 13,475; source bytes are the stage's module plus its entry file).
* Whole module graph: 2,982,010 source bytes in 340 files produce 2,259,456 text bytes, **0.76 text bytes per source byte** (about 41 B/line). Most of the graph is tables and strings that are cheap per source byte.

The two figures bracket the range: 0.76 (graph average) to 3.4-4.1 (dense code) text bytes per source byte.

## 3. Budget

* kernel-v3 text cap: 2,621,440 B (2.5 MiB). Text now 2,259,456; **margin 362 KB** (2,621,440 - 2,259,456).
* cssom closure source 1.78-1.89 MB. Even at the graph average 0.76 B/B it is about 1.35-1.44 MB, 3.7-4x the margin. At the dense-code ratio it is 6-8 MB.
* Conclusion: the full shared cssom does not fit under the current cap, by any estimate in the measured range. Options (owner decision, not taken here): raise the cap again (amu `kp-text-cap`, as amu#1825 did 2 -> 2.5 MiB), or render outside the kernel image (separate domain/object), or shrink the renderer to a subset.

## Method and limits

Line and byte counts: `wc -l` / `wc -c` on the files above. Text size: program header parse of `KERNEL.ELF` from the stage 2/3/4 QEMU builds (Amu Mac compiler c126449b). The deltas include each stage's entry module. cssom has not been compiled in the kernel dialect, so its real ratio is unmeasured; the range above is an estimate, not a result. A measured figure needs the first slice of JUN-855 (C2).
