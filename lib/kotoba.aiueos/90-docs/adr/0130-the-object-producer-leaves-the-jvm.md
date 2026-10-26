# ADR-0130: The object producer leaves the JVM

## Status

Accepted (2026-08-31)

## Context

Every kernel object in `os/aiueos/kotoba` was produced by `clojure`.  Not
because code generation needed a JVM -- ADR-0129 measured the whole inventory
through a compiler whose native emitters are portable `.cljc` -- but because
`bin/amu` sent the aiueos targets to the JVM entry point and nothing else could
build them.

The reason was one missing step, not a missing capability.
`kotoba.compiler.nbb.cli`, the JDK-free driver, sealed a `:kotoba.kexe/v1`
artifact and wrote it out as EDN.  The JVM CLI does one thing more for the
aiueos target profiles: it hands that same sealed artifact to an ELF64 or PE32+
packager and writes THOSE bytes to `--output`.  `kotoba.native.elf64` and
`kotoba.compiler.packaging.pe32plus` are portable `.cljc` -- measured by loading
both under nbb before writing anything -- and the four aiueos targets reach the
same two ISA emitters as the plain native targets, because `kir.target/backend`
maps all of them to `:x86_64-kotoba-v1` or `:aarch64-kotoba-v1`.

They were absent from the JDK-free route only because admitting them without a
packager would have written artifact EDN to a path named `.o` and reported
`:ok true`.  A wrong answer, delivered quietly.

## Decision

The premise is `amu` native.  `amu compile <src> --target
x86_64-aiueos-kernel-v1 --output foo.o --jvm-free` produces the kernel object.

`--jvm-free` remains a refusal rather than a preference: a command or target
with no JDK-free implementation exits 64 rather than falling back.  That
property is what makes the flag evidence, and this change strengthens it rather
than weakening it -- see the kernel image below.

The producer scripts that pin an older compiler (`reproduce-kotoba-kernel-object.sh`
at amu `9cf3a0a`, `build-kotoba-native-kernel.sh` and `build-kotoba-native-boot.sh`
at `1de9dafe`) are deliberately NOT switched.  Those pins are reproducibility
receipts for objects already committed; against compilers that predate the
packaging step the flag is a refusal, not a route.  They stay as historical
recipes, and new production goes through the JVM-free route.

`measure-object-producer.cljs` takes `--jvm-free` as a pass-through and records
`:route` in its receipt.  "The committed object differs" and "the committed
object differs under a route we did not name" are different claims.

## Result

All 66 aiueos kernel objects: **66 match, 0 differ, 0 could-not-run, 0 failed,
0 reached a JVM, 0 needed a retry.** Receipt:
`qualification/jvm-free-object-parity.edn`, which carries the digest of the
compiler tree it measured (`1ec79803...`) -- taken before the first compile and
again after the last, and equal.

That is the whole inventory reproduced byte-for-byte with `clojure`, `java`,
`javac` and `clj` replaced by stubs that exit 77.

## What is equivalent, and the one thing that is not

Measured on one source rather than assumed.  Of the four aiueos containers, the
kernel object, the CPL3 user image, the UEFI application and the AArch64 kernel
image are byte-identical across both routes.

The **x86-64 kernel image is not**: 65,904 bytes on the JVM-free route against
110,872 through the JVM.  `kotoba.native.elf64` is a twin, and kotoba-native
ADR-0036 keeps the two files apart on purpose -- the live-boot GDT/TSS shim
lives only in the `.clj`, which also lays the kernel RW context at a different
offset.

So that container is refused on the JVM-free route, naming the measurement and
the ADR, rather than served differently.  Producing a materially different
kernel image under a flag whose whole value is that it refuses instead of
falling back would be the exact failure this route was added to remove.

This costs aiueos nothing today: `build-uefi.sh` links committed objects and
does not build the image through this path.

## What the comparison found in the compiler

Three objects -- `ecdsa-p256`, `dhcp-option-u32`, `dhcp-reply-valid` -- came out
different on the two routes, and the JVM was wrong.

`package-kernel-object` picks a fuel immediate from a per-object tier table, and
that table had drifted between the twins the same way the entry table did before
`db7b711`.  The `.clj` had four tier arms and the `.cljc` six, missing
`ecdsa-fuel?` and `dhcp-fuel?`.  On the JVM, `aiueos-ecdsa-p256-sha256-verify`
fell through to RSA's 250,000,000 instead of 2,147,483,647, and both DHCP
objects fell to the 1,024 default -- 64x less than they are built with.

The shipped objects settle it.  At file offset 75, `ecdsa-p256.o` carries
`ffffff7f` and both DHCP objects carry `00000100`: the `.cljc` values, in all
three cases.  Rebuilding them through the JVM would have quietly weakened them,
and a tight fuel bound fails as a prologue `ud2`, surfacing as an unexpected
vector 6 that reads as a protocol bug rather than a fuel bug.

Fixed in kotoba-native `0daafbf`, with the tier comparison added to
`elf64_twin_parity_test`.

**It could not have been found from inside either runtime.**  Clojure loads
`.clj` for that namespace and nbb loads `.cljc`, so no single runtime can call
both packagers.  A behavioural comparison has to run them under two runtimes and
compare the bytes -- which is what having two routes made possible for the first
time.

## Evidence

`os/aiueos/scripts/verify-jvm-free-object-parity.cljk` compiles every kernel
source both ways in one pass and compares the two digests directly, so the
answer never depends on a previously recorded run of the other route.

The JVM-free side is not asked to be JVM-free, it is prevented from reaching
one: `clojure`, `java`, `javac` and `clj` on its PATH are stubs that exit 77 and
say so.  Without that the run would measure the flag's intent rather than its
effect, and a silent fallback would report a clean parity -- a JVM-built object
obviously matches a JVM-built object.  Reaching a poisoned tool is its own
verdict, never a plain failure.

`scripts/jdk-free-native-conformance.cljs` in amu asserts on the container bytes
-- ELF64 `ET_REL`/`ET_EXEC` with the right `e_machine`, `MZ` for the PE32+ image
-- rather than on exit status, because the failure guarded against is not a
crash.  Shown in both directions: with the packager returning nil it reads
`got "{:fo" -- artifact EDN written where a container belongs`, and green with
it restored.  It also asserts that the divergent kernel image is refused, that
the refusal names why, and that no output file is left behind -- likewise for an
unknown `--artifact`.

## What this does not claim

No object is linked into `KERNEL.ELF` by this change.  The advance ADR-0129
measured -- 62 objects regenerated and every pinned digest in `build-uefi.sh`
moved -- is still deferred, and still wants boot evidence.  This changes who can
produce an object, not which objects ship.

`package-aiueos-boot` is a separate command and still runs on the JVM.

That sentence used to end "its only JVM-specific line is a `Files/readAllBytes`;
the packager it calls is the same portable `pe32plus`", which read as *this is
three lines away*.  It was measured, and it is not.

Implemented on the JDK-free route, **the two routes produce different boot
images**: 129,024 bytes each, differing in exactly two, inside an eight-byte run
the JVM writes as `AIUEBOOT` and ClojureScript as `\0HUEBOOT`.  Read as one
little-endian word the two differ by 321.  Both routes report the same
`:kernel-sha256`, so both read the same input; the divergence is inside
`pe32plus/package-embedded-kernel`, a file with **zero reader conditionals**.

`pe32plus/package-efi` -- the UEFI target -- is byte-identical across both
routes, so this is one function rather than the namespace.  The implementation
was reverted rather than shipped: serving a different boot image under a flag
whose value is that it refuses instead of falling back is the same silent wrong
answer this ADR exists to remove.

A file having no reader conditionals is not evidence that it is portable.  It is
evidence that nobody wrote one.

## Two measurements discarded, and why

**Contaminated.**  The first parity run reported two objects as `differs` that
are byte-identical when either route is run alone.  The compiler worktree it was
reading from was edited mid-run -- by the break/unbreak of the packager that
produced the conformance evidence above -- so two of its comparisons were
between two different compilers.

This is the same failure ADR-0129 records, in the same session, by the same
hand.  Remembering it did not prevent it.  The parity script now takes one
digest over the compiler's `src`, `bin` and `deps-lock.edn` before the first
compile and again after the last, and refuses with its own exit code when they
differ, naming both digests.  A run that can be silently disturbed will be.

**Misclassified.**  The second run reported `ipv4-checksum` as FAILED.  It
compiles, and matches, when run alone; the JVM frontend had failed to load under
a machine at load average 76.  `measure-object-producer.cljs` already retries
for exactly this and records `:could-not-run` as its own verdict -- and this
script shipped without either, so it reported "could not answer" as "answered
no" on its first full run.  Retry and the distinct verdict are now in both.

The first diagnostic line is kept rather than the last: a Java stack trace ends
in `... 1 more`, which names nothing.
