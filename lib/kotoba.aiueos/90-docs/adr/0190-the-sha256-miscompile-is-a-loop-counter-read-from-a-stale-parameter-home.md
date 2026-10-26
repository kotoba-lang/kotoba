# ADR-0190 — the `sha256.o` miscompile is a loop counter read from a stale parameter home

- Status: accepted
- Date: 2026-09-03
- Answers the open item ADR-0150 left: "The next step is a bisect of amu
  `9cf3a0ac..7e8f06d7` against `smoke-qemu-uefi.sh`; this ADR bounds the window
  and supplies the reproducer but does not name the commit."
- Amends ADR-0150's Consequences: `unattested = 0` **is** reachable now, and the
  rebuild it withdrew can be retried. It does not supersede ADR-0150 — the
  decision that attesting means recording the revision that produced the bytes,
  not rebuilding at whatever is current, still stands.

## The commit

| revision | `sha256.o` | boot |
|---|---|---|
| amu `9cf3a0ac` | 17,792 B `af378b06…` | `AIUEOS_UEFI_SMOKE_OK` |
| amu `886e9408` | 10,368 B `b118a3a7…` | good (static) |
| amu `0df9d992` | 9,912 B `db5effa8…` | **`#UD`** |
| kotoba-native `3dab370e`, amu held at `886e9408` | 10,368 B | good (static) |
| **kotoba-native `da3b56b`**, amu held at `886e9408` | 9,952 B | **bad (static)** |

`0df9d992` is "Merge co-scientist iteration 49: count lever lands, metrology
tightens", and its entire source diff is one line: the kotoba-native pin
`3dab370e` -> `3162d868`. Inside that range the bad commit is kotoba-native
`da3b56b`, **"Optimize x86 direct self reentry" (#94)** — five changed lines in
`machine_ir.cljc` that give `:mc/recur` an `:x86-64/jmp-rel32` back edge, plus a
kotoba-mir pin to `3aea0acc`, where `x86-direct-reentry?` turns that allocator
path on for x86-64.

Attribution was measured, not inferred: the last two rows hold amu at one
revision and move only its kotoba-native pin.

## The mechanism, and what ADR-0150 saw

kotoba-mir's `store-at-definition` splices a spill store at the value's
definition, and says why: *a definition dominates every use of its value, because
the program is in SSA form.* `:mir/recur` is the one edge that breaks it — it
redefines the parameter homes and branches back to `:mir/reentry`, which sits
after the entry plan. The store therefore runs once, before the loop; the body's
reloads run every iteration.

In `round-block`, which recurs on `(workspace, i)` and reads `i` twice per
iteration:

```
1998: movq %rsi, %r12          ; i -> its parameter home
199b: movq %r12, 0x60(%rsp)    ; the ONE store, before the loop header
19a3: <loop header>            ; :mir/reentry
19a8: cmpq %rax, %r12          ; (= i 64) -- register, correct
1d29: movq 0x60(%rsp), %r13    ; (+ i 1)  -- slot, ALWAYS the entry value 0
1da4: movq %rdx, %r12          ; so the next i is 1, forever
1db7: jmp 0x19a3
```

`(= i 64)` never holds. The object does not compute a wrong hash and it does not
return — **it spins**, and dies at whichever fuel guard is executing when the
10,000,000-decrement budget in `.data+8` reaches zero.

Reproduced here, on an image with only `sha256.o` swapped: `RIP 0x165075`, which
resolves against the object's `.text` in `KERNEL.ELF` to offset `0x175` — the
`ud2` of the fuel guard in a `rotr` helper. **It is a guard, and it is fuel.**
ADR-0150 concluded the opposite from two true observations about a *different*
image (the 9,936 B object linked with 68 other rebuilt objects): the trap moved
when the fuel immediate was raised, and neither address it saw was a `ud2`. Both
are what a non-terminating loop looks like when the counter is large enough to
run out somewhere else each time. Patching the immediate to `2^31-1` in this
object does not move the trap — it removes it, and the image **hangs**: three
600-second QEMU attempts, no exception.

## What was fixed

kotoba-mir #54 / `0bb174c8` (ADR 0038): an entry-plan value's definition position
is one instruction later when the function has a direct reentry edge, so the
store lands at the top of the loop body. kotoba-native #132 / `d7105581`
(ADR 0076) pins it; amu #759 advances to that.

The fix's regression test is red on **both** targets. Nothing about this was
x86-only — AArch64 escaped because it has enough registers that no shipped aiueos
object had spilled a parameter home.

## The rebuild ADR-0150 withdrew now works

All objects recompiled at amu `ed78ffd1` (kotoba-native `d7105581`), digests
synced into `build-uefi.sh`, and the image booted — measured in this tree and
then reverted, because the objects are the attestation stream's to land.

```
REPRODUCE scanned=93 match=0 drift=0 differs=76 receipt-mismatch=0
          unrecorded=17 could-not-run=0
ATTESTED  objects=93 rewritten=76
SYNCED    objects=86 rewritten=71
```

| gate | scanned | kotoba | stubs | foreign | unattested |
|---|---|---|---|---|---|
| committed tree | 80 | 40 | 0 | 0 | **40** (`compiler-unrecorded`) |
| all objects rebuilt at the fixed amu | 80 | **80** | 0 | 0 | **0** |

`AIUEOS_K16_PURE_NATIVE_OK scanned=80 kotoba=80 stubs=0 foreign=0 unattested=0`,
`kernel=linked`. The profile still exits 3 — `REFUSED foreign-code: uefi/main.c`,
`loader=refused` — which is the loader blocker and not this one.

The production image with those same objects: `AIUEOS_UEFI_SMOKE_OK`, exit 0,
with `AIUEOS_INITRAMFS_RECOVERY_ADMISSION_OK`, `AIUEOS_X25519_OK`,
`AIUEOS_AES_GCM_OK`, `AIUEOS_ECDSA_P256_OK`, `AIUEOS_TLS13_RECORD_OK`,
`NIC-PARITY ok`, `DEVCLIENT-PARITY canonical ok` and `SHA-STREAM-PARITY ok` all
present.

`device-worker-canonical.o` compiles now: the symbol ADR-0150 found missing
landed in kotoba-native `24f43e21`, which the advanced pin includes.

## Four committed objects already have it

Looking for the shape in the artifacts rather than in the compiler found it in
the tree, today, in objects nobody had suspected:

```
$ kbb --backend sci os/aiueos/scripts/verify-loop-parameter-homes.cljk
KNOWN-STALE-PARAMETER-HOME  cid-v1-admit.o             function=0x1971 slot=0x60(%rsp) …
KNOWN-STALE-PARAMETER-HOME  hkdf-sha256.o              function=0x18ea slot=0x60(%rsp) …
KNOWN-STALE-PARAMETER-HOME  qwen35-vocab-index-build.o function=0xcfb  slot=0x20(%rsp) …
KNOWN-STALE-PARAMETER-HOME  value-runtime-cas-verify.o function=0x1971 slot=0x60(%rsp) …
SCANNED 93  self-tail-loops=278  findings=4  known=4  new=0  baseline-cleared=0
```

- **`hkdf-sha256.o` is the one that was already known to be broken and not
  understood.** `build-uefi.sh:157` excludes it with "it does not return on this
  machine", and ADR-0136 (TLS-DIAG anomaly 2) measured it trapping at a fuel
  guard inside `copy-round` and ruled out fuel tier, block count, memory range,
  callee-saved clobbers, out-of-frame references and unbalanced epilogues. It is
  this. `copy-round` is a `round-block`-shaped self-tail loop and the object was
  built by a compiler inside the bad window.
- **`cid-v1-admit.o` and `value-runtime-cas-verify.o` carry the identical
  `round-block` at the identical offset**, because they import `aiueos.sha256`.
  `build-uefi.sh` builds and shape-verifies both (lines 878, 881) and does **not**
  link either — checked by searching `KERNEL.ELF` for their `.text`, which is not
  there. So they are two more copies of the same defect sitting in the tree,
  waiting for whoever links them.
- **`qwen35-vocab-index-build.o` IS linked** — its `.text` is in `KERNEL.ELF` at
  `0x15f4c0` — and its defect is a different function and a different slot, so
  the shape is not a property of the sha256 source. It is the same shape all the
  way down:

  ```
   d2e: movq %r15, 0x20(%rsp)   ; the one store, before the loop label
   d36: <loop label>
   d3b: cmpq %rax, %r15         ; the exit test -- register, correct
  1068: movq 0x20(%rsp), %r15   ; the next counter -- slot, frozen at entry
  1070: subq %rcx, %r15         ; so it is (initial - 1) forever
  1080: jmp 0xd36
  ```

  Called with a count above 1 this function does not terminate. The image boots,
  so at boot it is either not reached or reached with a count that exits on the
  first test — **which of those was not measured here.**

All four clear when rebuilt at amu `ed78ffd1`: `SCANNED 4 self-tail-loops=47
findings=0`.

## The check that found them

`os/aiueos/scripts/verify-loop-parameter-homes.cljk` reads the emitted objects,
not the sources — nothing in `.kotoba` says where a spill goes — and refuses an
object whose self-tail loop reloads a frame slot written exactly once, outside
the loop. Its baseline is `os/aiueos/contracts/loop-parameter-home-baseline.edn`,
which names those four and nothing else.

Four exit paths, each measured:

| exit | direction | measured with |
|---|---|---|
| 0 | the committed tree | `SCANNED 93 … known=4 new=0 baseline-cleared=0` |
| 3 | a NEW object with the shape | the pre-fix `sha256.o` -> `new=1` |
| 4 | the baseline has gone stale | the four rebuilt at the fixed amu -> `baseline-cleared=4` |
| 2 | measured nothing | `--objects digest-equal.o` -> `self-tail-loops=0`, refused rather than passed |

A `--objects` run reports `baseline-cleared=n/a-subset-run`: a baseline entry a
run never opened is unmeasured, not cleared. It is registered nowhere as a fleet
gate — that is the orchestrator's call, and it needs a disassembler on the node
(it exits 2, naming the reason, when there is none).

## Decision

1. The regression is closed upstream. Anyone advancing amu for aiueos kernel
   objects needs a pin at or past kotoba-native `d7105581`.
2. **ADR-0150's rule stands and is the reason this was findable.** Attestation
   compares bytes against the revision a receipt names. It is the only check in
   this tree that looks at the producer, and it is what turned "the objects are
   older than the compiler" into a measurable claim.
3. This ADR lands **no object bytes**. The rebuild above was performed and
   reverted; the attestation stream owns landing it.

## Consequences

- **A non-terminating kernel object is indistinguishable from a QEMU flake
  today.** The raised-fuel run printed `warning: QEMU hung on attempt 1/3 (known
  flake kotoba-lang/aiueos#108); retrying` three times and then reported a
  timeout. A real hang is absorbed by that retry loop. Nothing in this ADR fixes
  it; it is recorded so the next hang is not read as #108.
- **17 objects are still `UNRECORDED`** in the manifest even after the rebuild
  drives `unattested` to 0 — the gate counts an object attested once the receipt
  names the amu that produced its bytes, which `--attest` writes for all of them;
  the 17 are the ones that had no *prior* recipe to carry forward. They are:
  `broker-admit`, `device-worker-digest`, `ime-romaji`, `qwen35-activation`,
  `qwen35-dequant-row`, `qwen35-detokenize`, `qwen35-dot-f32`,
  `qwen35-gguf-header-valid`, `qwen35-matvec`, `qwen35-norm`, `qwen35-tokenize`,
  `rtl8125-link-up`, `rtl8125-rx-poll`, `scanout-bind`, `session-restore`,
  `sha256-region`, `sha256-stream`.
- `hkdf-sha256.o` changes bytes at the new pin (`75a9857d…` -> `cc03dd62…`, same
  13,128 B) and the rebuilt object is clean. **ADR-0136's anomaly 2 (TLS-DIAG)
  is explained and should be closed against this pin rather than investigated
  further.** Whether the rebuilt object also RETURNS has not been measured here:
  it is not in the link list, so no boot exercised it.
