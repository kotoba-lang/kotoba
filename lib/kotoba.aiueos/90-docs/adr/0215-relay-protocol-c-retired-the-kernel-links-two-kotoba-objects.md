# ADR-0215 — relay_protocol.c is retired; the kernel links two Kotoba objects for it

- Status: accepted
- Date: 2026-09-11
- Completes ADR-0213 (the first kernel conversion is a retirement). Executes
  step 1 of ADR-0212's order. Root authority for the direction: ADR-0013
  (C-free hard flip), root ADR-2607241100 (C is mechanism, Kotoba judges).

## What changed

`os/aiueos/kernel/relay_protocol.c` and its header are deleted. `pci.c`'s two
call sites (`rtl8125_build_relay_hello`, `rtl8125_relay_ack_valid`) call two
compiler-emitted kernel objects instead, and `build-uefi.sh` links them with
their digests pinned like every other object:

| C symbol (gone) | Kotoba object | export | bytes |
|---|---|---|---|
| `aiueos_relay_hello_payload` | `kotoba/relay-hello-payload.kotoba` | `kotoba_aiueos_relay_hello_payload` | 3,536 |
| `aiueos_relay_ack_payload` + `_valid` | `kotoba/relay-ack-payload-valid.kotoba` | `kotoba_aiueos_relay_ack_payload_valid` | 2,312 |

The kernel is 31 → 30 C files; `os/aiueos/kernel` is 21,457 → 21,391 lines of
C, assembly and headers (measured with `wc -l` over `*.c *.S *.h`, before and
after, same tree). Small. It is the first file to leave, and what it cost to
leave is the substance of this record.

## Why not the module ADR-0213 pointed at

ADR-0213 found the HELLO line already written in `native/relay_line.kotoba` +
`native/relay_text.kotoba` and said the C should be retired in favour of it.
That pair was not linked. It writes into a 4 KiB frame page and reads the MAC
out of RTL8125 MMIO registers, because it serves `debug_link.kotoba`, which
owns the NIC. `pci.c` hands the C a 160-byte stack buffer and a six-byte MAC
it already holds. Wiring the template pair in would have meant either giving
`pci.c` a frame page and an MMIO base to pass, or changing the pair's
signature and with it its two existing callers. A new object with the C's
shape changes one symbol and two nonce halves at the call site and nothing
else. The template pair stays, the parity gate now compares it against the
retired C's recorded line (below), and the two Kotoba implementations are
held to the same bytes the way the C and the template were.

## The nonce crosses as two 32-bit halves

`rtl8125_boot_nonce` is a raw `rdtsc`. Bit 63 can be set. Words are signed on
the guest side — `relay_line.kotoba` says so and masks its nonce to 60 bits
where it draws it — so a 64-bit nonce parameter would format wrongly for the
top half of the range, and the C never masked. `(out capacity nonce-hi
nonce-lo mac)` keeps every operand below 2^32. This is why the object's
arity is 5 rather than 4, and why the ACK validator's is 4 rather than 3.

`:hello-top-bit` in the contract is that case: nonce `0xffffffffffffffff`,
and the object's line agrees with the C's.

## What the toolchain needed first (three repos, measured red before each)

None of this compiled at the start of the day, for reasons that had nothing
to do with relay lines.

1. **amu's JVM-free route was gone.** The 2026-09-11 `.cljk` rename (amu #934)
   updated text that named a renamed *path* but not strings that build a path
   from a basename: `bin/amu` looked for `scripts/print-classpath.cljs` and
   `x86_64_cli.cljs`, and its pinned stock nbb could not resolve `.cljk`
   sources at all. Every `amu compile … --jvm-free` exited 70. Fixed forward
   in amu #935: 42 basename strings in 28 files, `package.json` → the
   org-babashka-nbb fork root already pins, `deps-lock.edn` regenerated.
2. **The export table did not know the symbols.** A kernel object has one
   public symbol, chosen from `kernel-object-entries` in kotoba-native; the
   sources compiled through the frontend and were refused only at the
   packager: *declares an aiueos export with no admitted symbol*. Added in
   both twins (`elf64.clj.cljk`, `elf64.cljc.cljk`) — the first attempt
   touched only the JVM twin and changed nothing on the nbb route, which is
   the drift the twin-parity test exists for. kotoba-native #174; amu's pin
   5f2717c2 → ece7257a.
3. **This repository's own tooling had the same rename holes.** `build-uefi.sh`
   called `image-freshness.cljs`; the UEFI smoke could not build. And
   `build-k16-pure-native.cljk --emit-provenance` looked for
   `verify-admissions.cljs` and `test/aiueos/*.clj`, found neither, and
   **demoted all 23 `:kir-vectors` objects to `:attested-unverified` in one
   run, exit 0**. That generator now refuses when the runner is absent. 117
   stale basename strings across 46 executable/data files were rewritten
   (contracts, the installer bundle builders, the QEMU smokes, the K16 tools),
   and the bundle builder's classpath scan now takes `.cljk` -- on main
   `:install-bundle-test` was 15 failures out of 34 (the bundle named scripts
   that no longer exist), after this it is 34/34, with `:install-chain-test`
   22/22, `:provision-record-test` 6/6, `:node-installer-test` 63/63 and
   `:guided-install-test` 53/53. A first scan skipped lines beginning with
   `#` as comments and so missed `#js ["guided-install.cljs"` -- in a `.cljk`
   only `;;` opens a comment. C-source prose, `90-docs/` and
   `tools/kbb-migration-gaps.edn` were left as the records they are. The
   nbb tree an install USB is built with (`--nbb-dir`) must now be the
   org-babashka-nbb fork: it is the only nbb that resolves `.cljk`, and a
   stick built with stock nbb dies at the first `require` -- ADR-0209's shape.

A fourth, found while attesting: `reproduce-kotoba-objects.cljk --attest
--objects a,b` wrote a manifest containing only a and b. 98 receipts gone,
exit 0. It merges now, and the run that found it is described in the file.

## Evidence

**Executed, not only built.** `os/aiueos/contracts/relay-hello-v1.edn` (6
vectors) and `relay-ack-valid-v1.edn` (8 vectors) run the objects' sources in
the `kotoba.kir` oracle (`verify-admissions.cljk`, format
`:aiueos.relay-line/v1`, task `:relay-line-verify`, under a second). Every
expected byte and verdict in them was printed by the C — built standalone
with `cc -O2` at e45724e7, the last commit to touch it — not typed from the
protocol description:

- HELLO: the ADR-0213 vector, the top-bit nonce, the zero nonce with an
  all-`ff` MAC, capacity exactly 91 admits, capacity 90 refuses **without a
  byte written** (the first 26 bytes are asserted still zero), a nonce half
  ≥ 2^32 refuses.
- ACK: two accepted lines, wrong low nibble, wrong high half, one byte short,
  one byte long, a banner byte flipped, the last state byte flipped.

Both contracts turned red for the named reason when broken: the last byte of
one expected line changed → `memory mismatch` on exactly that vector; one
refusal's expected verdict inverted → `vector mismatch`, actual 0.

**Linked and booted.** `smoke-qemu-uefi.sh` builds the image with the two
objects linked and boots it: `AIUEOS_UEFI_SMOKE_OK`, 76 distinct `_OK`
markers on serial, image fresh against the tree. `kernel.map` carries
`kotoba_aiueos_relay_hello_payload` (731 bytes) and
`kotoba_aiueos_relay_ack_payload_valid` (469 bytes) and no C relay symbol.

**Drift alarm kept.** `:relay-parity` compares `relay_text.kotoba`'s template
against the C's recorded line in the HELLO contract, masking the two variable
spans, and still proves its own discrimination on every run.

## What this does not claim

- **The relay path did not run.** `rtl8125_build_relay_hello` is reached
  only on a physical RTL8125 under the relay-qualification profile; QEMU
  does not emulate that NIC. The boot proves the objects link and the image
  still boots with them; the KIR oracle proves the objects' *sources* produce
  the C's bytes; what is not proved is the emitted machine code producing
  them on the K16. That is the next physical relay qualification's job, and
  `qualification/jvm-free-object-parity.edn` is where such a measurement is
  recorded, per object, when it happens.
- **The compiler pin for these two objects is amu d9033ad0** (the #935 branch
  head, reachable from main once it merges), with kotoba-native ece7257a. The
  other 91 recorded objects keep their 6c245f69 / 9cf3a0ac receipts; nothing
  here regenerates them. `:kernel-object-digests --check` was already
  `COULD-NOT-RUN object-variable-unresolved kotoba_rt_dispatch_plan_object`
  on main before this change and is unchanged by it.
- **The JVM suites did not run.** `test/aiueos/native_pxe_test.cljk` was
  repointed at the Kotoba sources and the ACK contract, but `.cljk` does not
  load on stock Clojure since the rename (owner decision; recovered per
  component). Its assertions were re-read by hand, which is not the same.
- **ADR-0212's order is otherwise untouched.** Step 2 (`tls_aes_gcm.c`) and
  the pointer question that gates the 840 lines behind it stand as written.
