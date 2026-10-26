# ADR-0142 — SHA-256 stops being a whole-message primitive

Status: accepted
Date: 2026-09-02

## The gap three streams found separately

Every SHA-256 in this repository was a WHOLE-MESSAGE primitive with a small
hard cap.

| where | ceiling |
|---|---|
| `os/aiueos/kotoba/sha256.kotoba` (`aiueos-sha256`) | refuses input above **12,288** bytes |
| `os/aiueos/kotoba/aiueos/lib/sha256_core.kotoba` (ADR-0135) | **192** bytes, from a fixed offset inside the caller's 800-byte context |

Three streams reached those ceilings:

- **ADR-0137** wrote `aiueos-device-worker-canonical` and reserved
  `device-worker-digest`, then could not write it. The Murakumo device-P256
  worker's `input-sha256` is taken over `4*(count+2)` bytes and the protocol
  admits 32,768 tokens, so the widest canonical input is **131,080 bytes** —
  ten times the first ceiling and six hundred times the second. That object's
  "Not done" says so.
- The UEFI loader cannot hash a 1 MiB kernel with a Kotoba object, so
  `verify-kotoba-native-boot`-style integrity stays in C (`uefi/main.c:390`
  is the only C SHA-256 left in this tree).
- `aiueos-hkdf-sha256` is under diagnosis for a native fuel anomaly in the
  re-based 800-byte shape (ADR-0134/0135). **Nothing here touches that
  object**, and this ADR makes no claim about it.

**Raising a constant cannot close this.** A whole-message object has to see
its message through ONE bounded-memory window, and the widest window
kotoba-native has is 65,536 bytes (`kir-kernel-memory-ops`, the `-64k` tier
MEMWIDTH landed). 131,080 is not reachable at any tier.

## Decision

A streaming core, plus three objects that expose it.

### `os/aiueos/kotoba/aiueos/lib/sha256_stream.kotoba`

The shared module, in the project-route layout amu#742 made possible
(`aiueos.lib.sha256-stream` → `aiueos/lib/sha256_stream.kotoba`, hyphen to
underscore). It exports `sha-init`, `sha-absorb`, `sha-block`, `sha-blocks`,
`sha-final`, and the four state-region accessors the three objects need.

The state region is **512 bytes the caller owns**, and the 512 is a LITERAL
inside `sl`/`ss` exactly as `sha256_core`'s 800 is — the ABI admits five
arguments and threading a length through every helper spends one forever. The
consequence is stated rather than hidden: a caller with a differently sized
region cannot share the module, and every entry checks `st-len` itself.

```
offset  bytes  words    what
     0    256   0-63    W[0..63], the message schedule
   256     32  64-71    H[0..7], the chaining state
   288     32  72-79    a..h
   320     32  80-87    the round's shifted copy
   352      8  88,89    message length in BYTES, high word then low
   360     64           block assembly buffer (the tail; and, for a caller
                        that synthesises its bytes, any block)
   424     32 106-113   the digest, RAW, big-endian
   456      4    114    token count      (device-worker-digest)
   460      4    115    max-tokens       (device-worker-digest)
   512                  end
```

512 is also the CHEAPEST memwidth tier, so every access is a base
`kernel-load-u8` / `kernel-store-u8`.

### The API, and its bounds

| call | arity | bound |
|---|---|---|
| `sha-init st` | 1 | — |
| `sha-block st blk` | 2 | `blk` is a 64-byte region |
| `sha-absorb st blk` | 2 | as above, and advances the length by 64 |
| `sha-blocks st src src-len i full` | 5 | `full` iterations, `full` derived from the caller's length |
| `sha-final st src src-len` | 3 | `src-len` in 0..63 |

`:kotoba.error/max-parameters` is 5 and it applies to EVERY `defn`, not just
the export — which is why `sha-blocks` is exactly at the limit and why
`device-worker-digest` puts `max-tokens` in the state region instead of in the
fifth argument.

### Every loop that can be a jump is a jump

kotoba-native turns a self-call in tail position into a jump only when the
call sits at the function's own frame baseline —
`(and tail? (= op function-name) (zero? temp-depth))` in `emit-call`,
`x86_64.cljc`. **A self-call written from inside a `let` body is still in tail
position but is no longer at that baseline**, so it emits an ordinary CALL and
the native stack grows once per iteration.

Every existing SHA-256 here is written that way. That is *why* they are
capped: `sha256.kotoba` at 12,288 bytes recurses 192 frames deep in
`process-blocks` alone, and a megabyte would be 16,384 frames.

So each loop here is split in two — a `-step` function that holds the
bindings, and a loop whose only body is
`(if done 1 (loop … (+ i 1 (* 0 (step …)))))` with no `let` around it. That is
the baseline shape, so it is a jump. **The native stack cost of hashing a
megabyte is the same as hashing 64 bytes: one `-step` frame at a time.**

The `(* 0 …)` is the ordering idiom the shipped objects use, and kotoba-native
ADR 0049 (STOREFIX) classified `sha256`, `rsa2048` and `x25519` as
ORDERING-ONLY users of it — they thread a store's answer through `(* 0 …)` and
never let it decide anything, which is why those three were correct even while
the backend answered a store with the wrong register. Nothing here decides on
a store's answer either, so this module is correct at 24f43e2 and at 279fbc3.

### Multi-form `let` bodies are available, and are not used for this

`kotoba-sema` `c14ca39` ("a let body is an implicit do, and no pass truncates a
core form") landed 2026-09-02 15:13 and is an ancestor of `e42b74e`, the
kotoba-sema amu `ca869d79` pins — verified with `git merge-base --is-ancestor`.
Multi-form bodies compile. They are not used here because the shape that
matters for this module is the ABSENCE of a `let` around the self-call, which
is the opposite constraint.

### Three objects, one implementation

| symbol | arity | `.o` | result convention |
|---|---|---|---|
| `kotoba_aiueos_sha256_stream` | 5 `(mode st st-len src src-len)` | 11,984 B | 0 done, 1..4 reason |
| `kotoba_aiueos_sha256_region` | 4 `(st st-len src src-len)` | 11,872 B | 0 done, 1..3 reason |
| `kotoba_aiueos_device_worker_digest` | 4 `(st st-len tok tok-count)` | 13,568 B | positive = canonical byte count, -1..-3 reason, **zero never** |

All three verify as ordinary kernel objects —
`AIUEOS_KOTOBA_OBJECT_OK target=x86_64-aiueos-kernel-v1 export=… imports=0
relocations=1` — and all three are linked unconditionally, like
`device-worker-canonical` and for the same reason: the boot self-test runs
them on every UEFI profile.

All three import the shared module, so the compression rounds exist ONCE in
source; the three `.o` files are three instances of it, not three
implementations. A kernel object exports one symbol and cannot call another,
which before amu#742 would have forced three copies.

**Three rather than one, and the reason is fuel.** The prologue's replenish is
a per-CALL budget. Folding them into one symbol would hand the single-block
call — the one a driver makes 16,384 times — the budget a whole-megabyte call
needs, and a runaway single-block call could then spend a megabyte's worth of
steps before the counter noticed. That is not a cost (fuel is not consumed by
being granted); it is a loss of information. It is the same argument
`elf64.cljc` already makes for keeping `canonical` and `body` on separate arms
where their constants agree.

**The two families keep their own result conventions rather than being
harmonised.** The two `sha256` objects take `aiueos-hkdf-sha256`'s (zero is
done) because their output is bytes in a region and there is no length to
return; `device-worker-digest` takes the `aiueos-device-worker-*` one it joins
(positive is the useful number). Both are stated in the contracts.

## Fuel: measured, not copied

Bisected in the `kotoba.kir` interpreter, which charges one unit per Kotoba
call — the same accounting the emitted prologue does. Every bisection reports
both directions: the minimum returns and the minimum minus one does not.

```
region  len=0    15,183     len=64   30,077    len=128  44,971
        len=56   30,182     len=120  45,076
        -> 14,894 per 64-byte block, cross-checked two ways
           (f(128)-f(64) and f(64)-f(0) both give 14,894)
        -> confirmed at 640 bytes: predicted 164,123 returns, 164,122 does not
        -> a 56..63-byte tail costs 14,999 more (the padding needs a 2nd block)

stream  init 54   block 14,895   final(short tail) 15,130
        final(56..63-byte tail) 30,129

digest  n=0 15,291   n=1 15,323   n=16 30,698   n=32 46,105
        -> 15,407 per block; n=32 predicted 46,105 and measured 46,105
```

`digest` is 513 fuel per block dearer than `region` because every canonical
byte goes through `cb` rather than being read straight out of the token
region. That is the cost of not special-casing the blocks that happen to be a
contiguous slice of `tok`; the optimisation is named as not done, below.

### The two numbers the brief asked for

- **per 64-byte block: 14,894** (region), **15,407** (device-worker-digest).
- **for a 131,080-byte input: 30,518,095** (region), **31,568,827**
  (device-worker-digest at 32,768 tokens with a max-tokens suffix).

The brief said 131,076 for a 32,768-token prompt. 131,076 is the OUTPUT
canonical form (`4*(n+1)`); the input form is `4*(n+2)` = **131,080**. Both are
measured here and the QEMU self-test hashes both.

### The tiers, and why the region ceiling is 1 MiB

```
region  1,048,576 bytes = 16,384 blocks -> 244,038,584 worst case
        tier 2,147,483,647   margin 8.80x
stream  30,129 for the dearest single call
        tier 262,144         margin 8.7x
digest  131,080 canonical bytes = 2,048 blocks -> 31,568,827
        tier 250,000,000     margin 7.9x
```

`2,147,483,647` is not just the tier chosen for `region`; it is **the largest
tier any object can have**, because the replenish is
`mov qword [r9+8], imm32` and the immediate is 32 bits. At 14,894 per block
that pays for about 144,181 blocks — **8.80 MiB**. So a 2^32-byte ceiling
would be the failure this repository keeps naming: an argument the object
accepts and then `ud2`s partway through, surfacing as an unexpected vector 6
that reads as a protocol bug rather than a fuel bug. 1 MiB is the largest
round ceiling the largest possible tier covers with margin, and raising it is a
fuel re-measurement rather than an edit to one number.

**No tier here is copied from another object.** `elf64.cljc`'s own comment
records what copying cost last time: `aiueos-hkdf-sha256` took
`aiueos-sha256`'s tier because a tighter one "would be a 9x margin on an
estimate, not a measurement", and then did not return on the machine. A
borrowed tier is where that hid.

## Parity

### Off-target, executed (`verify-admissions.cljs`)

```
CONTRACT :aiueos.device-worker-digest/v1 vectors=11 traps=0 memory=7
         observed=-3,-2,-1,4,8,12,16,24,88,260   ms=39276
CONTRACT :aiueos.sha256-stream/v1        vectors=5  steps=34 traps=0 memory=4   ms=41880
CONTRACT :aiueos.sha256-region/v1        vectors=12 traps=0 memory=9
         observed=0,1,2,3                        ms=55277
CONTRACTS 3      {:host :nbb, :jvm false, :amu-sha "ca869d79…", :status :passed}
```

Twenty memory assertions, which is what matters: these three objects write
their answer into the caller's region and return a constant on success, so a
vector that checked only the return value would be checking the part that does
not matter. Every declared reason of the two contracts that have reasons was
produced by some vector.

Three new contracts, and `verify-admissions.cljs` grew a builder for each.
`run-stepped` also grew `:expect-memory` — it had only ever compared reason
codes, which for a streaming object whose success value is the constant 0 is a
pass over the part that does not matter. `run-single` has had this since
ADR-0132; the step runner did not.

Red direction for that new check: one nibble of the
`:one-thousand-in-seventeen-calls` digest gives

```
FAILED: memory mismatch
  {:vector [:one-thousand-in-seventeen-calls 16], :region :digest, :offset 424,
   :expected [… 115 126 164], :actual [… 115 126 163]}
```

— the vector, the step index, the region and the byte.

The `:verify-admissions` alias pin moved from amu `0085e138` to `ca869d79`.
ADR-0135's "Not done" named advancing it as the next change; this is it. On
the old pin these three contracts cannot be linked at all — they are two-module
projects and that pin predates amu#742. The two contracts most likely to be
disturbed by either change were re-run on the new pin and pass unchanged:

```
CONTRACT :aiueos.value-handle-arena/v1 vectors=2  steps=11 traps=0 memory=0 ms=2152
CONTRACT :aiueos.cid-v1-admit/v1       vectors=14 traps=1  memory=0
         observed=0,1,2,3,4,5,6,8                                   ms=313909
```

`value-handle-arena` is the only other stepped contract, so it is the one the
`run-stepped` change could have broken; `memory=0` there is correct — it
declares no `:expect-memory` and no floor.

### A second implementation, on the JVM

`test/aiueos/sha256_stream_parity_test.cljk` re-derives **every** digest the
three contracts assert, from the message each contract describes, using
`sha2.core` from `kotoba-lang/org-nist-sha2` — a pure `.cljc` SHA-256 sharing
no code, no author and no representation with `aiueos.lib.sha256-stream`.

That answers a question `verify-admissions` cannot: it compares the object
against the contract, which says nothing about whether the CONTRACT is right,
and a contract is where a transcription error lands.

It also checks the two 64-character digests `kernel/main.c` carries as C string
literals inside `worker_canonical_v3_expected` — transcribed by hand under
ADR-0137 because nothing on the device could compute them — against the
server's published byte form.

`5 tests, 34 assertions, 0 failures`, with `SCANNED` lines of 9 / 4 / 7 / 4 / 2.
Red direction: one nibble of the `:one-thousand` digest changed
(`…9737ea3` → `…9737ea4`) gives exactly one failure, naming the vector and
saying the contract's digest is not the SHA-256 of the message the contract
describes.

### On a CPU (QEMU boot self-test)

`SHA-STREAM-PARITY`, in `kernel/main.c` beside `DEVCLIENT-PARITY`, ten cases.

**The oracle is the object this kernel already trusts.** There is no C SHA-256
in this kernel and has not been since ADR-0015 — every kernel hash already goes
through `kotoba_aiueos_sha256`. So cases 4 and 5 hash **12,288 bytes, the
largest input that object accepts**, with the old object and with both new ones
and compare the 32 bytes. Two independent Kotoba implementations, both running
as x86-64 machine code, agreeing on the same input is a stronger statement than
either against a literal.

Past 12,288 bytes nothing else here can answer, so cases 6 and 9 pin the digest
as a literal — and those literals are the ones the JVM test re-derives.

Cases 7 and 8 are the point of the whole stream: the two digests they compute
are ALREADY IN THAT FILE as hand-transcribed literals. Now they are computed.

**The self-test's buffers live in `.high_bss`, and that was measured rather
than chosen.** 131,080 bytes is 13% of the whole low kernel/user budget
(`kernel/linker.ld` asserts `aiueos_low_end <= 0x1f4000`), and putting them in
ordinary `.bss` linked fine on the tree this branch started from and then
failed — `ld.lld: error: low kernel/user layout overlaps process-private
aperture` — the moment `origin/main` was merged in with the RTL8125 and
Qwen3.5 objects. The 4..6 MiB window is what that section is for, and
`device_result.c`, `tls13.c` and `qwen35_infer.c` already put theirs there.
Anything that wants to hash at this size in the kernel has the same
constraint.

Green, on the serial console (`smoke-qemu-uefi.sh`, q35 + OVMF, isa-debugcon
0xe9), verbatim:

```
SHA-STREAM-PARITY ok fips-abc fips-448 one-block region-vs-sha256-12288 stream-192-blocks region-131080 dwd-input-4 dwd-output-3 dwd-input-32768 refusals
```

and the whole gate ends `AIUEOS_UEFI_SMOKE_OK`.

**The deliberate break.** One character in the shared module: `sha-final`'s

```clojure
r (if (< src-len 56) (final-short st bits) (final-long st bits))
```

became `(< src-len 8)`. That is the FIPS 180-4 5.1.1 rule for whether the
0x80, the zero padding and the 8-byte length fit in one more block, and moving
the threshold to 8 mis-pads exactly the messages whose tail is 8..55 bytes.
Every earlier case has a tail of 0, 3 or 56 bytes and is unaffected; case 6's
131,080 bytes has a tail of 8. The three objects were recompiled from the
broken module and the image rebuilt:

```
SHA-STREAM-PARITY mismatch case=6
```

Restoring the 56 and recompiling gives objects that are **byte-identical** to
the ones committed here — `fdf5b3ac…`, `5306967e…`, `496d285c…`, the same
three sha256s `build-uefi.sh` pins — and the `ok` line above.

## What this does not claim

- **`hkdf-sha256` is untouched.** Its native fuel anomaly is TLS-DIAG's, and
  nothing here changes that object, its module, or its tier.
- **The wire protocol is unchanged.** The device still speaks protocol 2;
  ADR-0137's stream owns that flip. This adds the object that computes the two
  v3 digest fields, and nothing calls it outside the boot self-test.
- **`sha256.kotoba` is not replaced.** Ten call sites use `aiueos-sha256` and
  none of them moved. What this adds is the sizes it refuses.
- **The UEFI loader still hashes in C.** Linking a kernel object into
  `BOOTX64.EFI` is a separate change with its own link set.
- **The digest is RAW, not hex.** Hex is a total injective encoding —
  mechanism, in ADR-0015's sense — and the C callers that need it already own a
  hex writer for the model digest.
- **No interpreter vector hashes 100,000 bytes, let alone 1,000,000.** The
  1,000-byte vector (16 loop iterations) already costs minutes in a
  ClojureScript interpreter; 1,563 blocks would be hours and 15,625 blocks
  would exhaust node's stack in `prepare`'s host frames long before fuel ran
  out. The large sizes are the QEMU self-test's job, and it hashes 131,080
  bytes twice.
- **`device-worker-digest` assembles every block byte by byte.** Blocks 1..k of
  a canonical form are a contiguous slice of the token region at offset
  `64b-4` and could be read with one `kernel-subregion`; only block 0 and the
  last one are mixed. That is a measured 513 fuel per block, not done.

## Roster and provenance

`build-k16-pure-native.cljs --emit-provenance` regenerated
`os/aiueos/kotoba/provenance.edn`: **objects=77 recorded=47 unrecorded=30**
(74/47/27 before). All three new objects are recorded, and each records the
`aiueos.lib.sha256-stream` module in its `:modules` closure — the transitive
recorder ADR-0135 added, without which `sha256_stream.kotoba` could change and
three receipts would still report "unmodified".

`build-uefi.sh` gained three `AIUEOS_KOTOBA_*_OBJECT` variables, three
`verify-kotoba-kernel-object.py` lines pinning the sha256 and the export
symbol, and three entries in the link list — the `# sha-stream:` set:

```
sha256-stream.o          fdf5b3ac388982cdcc851817a7414f638a821420f70650df4dc8985491281abc
sha256-region.o          5306967ed079f62c37e906095e75a5d0d3cf1e7b0df741a4219d40515e851f0e
device-worker-digest.o   496d285c78f906e2de996fc392212fc6ed01c770fa7d05c813db07833f830ca2
```

`aiueos.kotoba-object-reachability-test` needs no entry for the three sources:
they are built by a script, which is the question it asks.

## Not done

- The six multi-module sources ADR-0135 named still have no objects.
- `value-runtime-sha256.kotoba` is still a verbatim copy of `sha256.kotoba`;
  neither has been moved onto this core.
- `qualification/jvm-free-object-parity.edn` covers 66 objects and does not
  cover these three (nor `hkdf-sha256`, nor `device-worker-canonical`);
  regenerating it is a separate measured run.
- `aiueos-sha256-region`'s 1 MiB ceiling is a fuel fact, not a limit of the
  core. A caller that needs more drives `aiueos-sha256-stream` itself, and the
  10.9 GiB model file needs exactly that.

## Housekeeping

**FIVE ADR numbers are duplicated on aiueos `main`**, and the count grew while
this branch was open. 0134, 0135, 0136, 0137 and 0140 each name two files
written by two streams that landed within minutes of each other. This one was
drafted as 0139 — the next free number when it was written — and 0139 was
taken by `a-prompt-becomes-token-ids-without-leaving-kotoba` before this
branch could merge, so it is renumbered to **0142** here rather than becoming
the sixth collision. The ten existing duplicate files are left alone:
renumbering a landed ADR breaks every reference to it.

That is the sixth time in two days, so it is a property of the process and not
of any stream: a filename chosen at authoring time cannot be unique when N
branches are open, because the number is picked from a `main` that moves. The
fix is not a rule about looking harder. It is either a number allocated at
merge time or an identity that is not a number at all, which is what the
superproject's own `:adr/id` slug form already decided (root
AGENTS.md, "`:adr/id` は slug 形").
