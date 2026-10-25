# 0085 — the AArch64 kernel arms return the operands they borrowed

Status: accepted
Date: 2026-09-18
Base: `origin/main` `a9f8a3c`

## Context

`a64-kernel-dot-f32` and `a64-kernel-dequant-dot` (Q8_0) ran their loops IN
their operand registers: the two bases advanced, the count counted down, the
`length` register became the group counter and `second-length` the fp16 sign
temporary. The comment beside the bindings said the five operands "arrive on
the call-argument tier with nothing live across the instruction, so all five
are scratch here". That sentence describes `kotoba.mir`'s SPILLED lowering,
where each operand is `load-value`d into c0..c4 immediately before and the
result stored from c0 immediately after. It does not describe a LEAF
allocation, where a parameter stays in x0..x4 for the whole function and a
let-bound block count sits in x5 — and the arm is emitted on exactly those
registers.

Measured 2026-09-18 on the M1 (superproject ADR-2609182300), a `.kotoba`
program compiled by amu to an AArch64 kexe and run through amu's own
`tools/kexe_loader.c`, no JVM and no Deno anywhere on the path:

    (defn after [wbase :i64 wlen :i64 xbase :i64 xlen :i64 spec :i64]
      (let [blocks (bit-and spec 65535)
            k (kernel-dequant-dot-q8-0 wbase wlen xbase xlen blocks)]
        (- <one operand> (bit-and k 0))))

| read after the call | x86-64 answered | AArch64 answered |
|---|---|---|
| `wlen` | 34 | **0** |
| `xlen` | 128 | **0** |
| `blocks` | 1 | **0** |
| `xbase - wbase` | 34 | **128** (both pointers one block further on) |

The dot product itself was right on both (528.0f, 0x44040000). A counted
loop calling the kernel once per row — the shape every matrix-vector product
has — therefore computed row 0 correctly and folded ZERO blocks for every
row after it, while agreeing with itself and with the byte goldens. The x86
arm never had the defect: it walks r10/r11 and pushes what else it touches
(`x86-kernel-dequant-dot`, "rescue the operands, then ask the CPU").

## Decision

Both AArch64 arms save every operand register they mutate right after the
trap checks and restore them right before writing `dst`, through the
existing `a64-saved-frame` (one SP update each way, 16-byte aligned):

- `kernel-dot-f32`: `base`, `second-base`, `count` — `stp`+`str` / `ldr`+`ldp`.
- `kernel-dequant-dot-q8-0`: all five — `stp`,`stp`,`str` / `ldr`,`ldp`,`ldp`.

The answer is formed in s0 and moved to `dst` AFTER the restore, so a `dst`
that aliases a dead operand still receives it. The saves sit after the checks
so a trap leaves SP where the function had it. `(distinct …)` collapses an
operand passed twice.

Verified through the consumer: the five probes above answer 34 / 128 / 1 /
34 / `blocks<<32 | k` on AArch64, and the counted-loop probe folds every
iteration (fuel consumed per iteration, answer unchanged across N).

## Consequences

- Six words on the f32 dot, six on Q8_0, per call. At Nex's row lengths
  (1024–4096 elements) that is below noise; the measured cost of the arm
  is the scalar element loop (~4.9 µs per 400 Q8_0 blocks on the M1).
- `isa-parity-test` moves its positional indices (+2 before the restore, +4
  after) and pins the save/restore words themselves, in order, for both arms.
- The test that would have caught this is an EXECUTING one, and it belongs in
  amu's `isa_execution_test` beside `granted-region-dequant`: read an operand
  after the kernel, on both ISAs, assert equality to the value passed in.
  That fixture lands with amu's pin advance to this commit.
- The lesson is the same one ADR 0066 states from the other side: a byte
  golden says the sequence is the one intended and cannot say what it does
  to the registers around it.
