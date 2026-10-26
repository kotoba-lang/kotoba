# aiueos-image-route-node-free-20261022

Kernel IMAGE route (EFI/GPT packaging inputs) moved off NBB/Node, measured
against the nbb originals. JUN-31 acceptance: no C, NBB/Node, JVM or GraalVM
path in the accepted build; Python is orchestration only.

## What changed

* `os/aiueos/scripts/edn_lite.py` (new) — minimal EDN reader/writer for the
  two tools. Refuses reader tags / regex / char literals rather than guessing.
* `os/aiueos/scripts/k16-pure-native-gate.py` (new) — port of
  `k16-pure-native-gate.cljk`. Same exit codes (0 admitted / 2 could-not-answer
  / 3 refused), same marker lines, same pinned reason literals, receipt
  compared as an EDN value.
* `os/aiueos/scripts/image-freshness.py` (new) — port of
  `image-freshness.cljk`. Same three exits (0 fresh / 3 could-not-run /
  4 refused), `IMAGE-RECEIPT` / `IMAGE-FRESH` / `SCANNED` markers.
* `os/aiueos/scripts/check-image-route-node-free.py` (new) — parity harness.
  Runs BOTH implementations (nbb original = dev-time oracle, never on the
  build path) over the same fixtures and compares exit codes, marker lines,
  receipt EDN values, cross-reads receipts in both directions, and proves the
  ports complete with node/nbb absent from PATH.
* `os/aiueos/scripts/build-uefi.sh` — the two nbb calls (K16 gate, freshness
  `record`) replaced by `python3` on the ports; `command -v nbb` refusals
  became `command -v python3`.
* `os/aiueos/scripts/smoke-qemu-uefi.sh`, `smoke-qemu-firmware-matrix.sh` —
  freshness `assert` moved to the port the same way.

## Measured (2026-10-22, this tree)

`python3 os/aiueos/scripts/check-image-route-node-free.py --out <receipt>`:
**21/21 AGREE, 0 disagreements** (receipt:
`docs/evidence/aiueos-image-route-node-free-20261022/parity-receipt.json`).
G1–G11 gate scenarios (admit-all over the 116 committed objects with the
committed manifest, empty/absent inputs, receipt-missing/mismatch, undefined
symbol, wrong section set, real `zig cc` C object with a truthful and with a
lying receipt, receipt value equality, clojure.edn reading the port's
receipt), F1–F9 freshness scenarios (record/assert/cross-assert/no-artifacts/
receipt-missing/tampered artifact/moved tree/cross-show/real git tree), and
N1 (node/nbb absent from PATH; both ports complete).

The receipt text is deliberately NOT byte-compared (cljs pr-str is hash-ordered,
the port is insertion-ordered); equality is by EDN value, which is what every
reader sees.

## Boundary (no rounding)

* The nbb originals remain in the tree as the dev-time oracle only. They are
  not invoked by `build-uefi.sh` or the smoke scripts any more.
* Harness fixture note: `synthesized_receipt` now takes each object's `:source`
  name from the committed `provenance.edn` (not every object's source is named
  after it — e.g. `model-mapping-plan.o`), and G11 reads the receipt via
  `node:fs` because nbb's `-e` has no `slurp`.
* This is the IMAGE-route INPUT tooling. The QEMU/OVMF boot proof (log +
  screenshot) and the EFI/GPT packaging itself are tracked separately and are
  NOT claimed here.
