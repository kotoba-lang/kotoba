# ADR-0036 — The JVM packager is elf64.clj, and it is an allowlist

- **Status:** Accepted
- **Date:** 2026-08-26
- **Owner:** `kotoba-lang/kotoba-native`

## Decision

`package-kernel-object` in `src/kotoba/native/elf64.clj.cljk` refuses an
`aiueos-*` export that is not in `kernel-object-entries`. It does not
hand that object the probe symbol.

Clojure on the JVM loads `.clj` before `.cljc`. `elf64.cljc` already
refused unlisted names (amu#626 / aiueos ADR-0054). That refusal was
dead on the compiler's JVM path because `.clj` still defaulted missing
names to `kotoba_aiueos_probe`. nbb portable tests exercise `.cljc`.
amu's `aiueos-target-test` exercises `.clj`.

This ADR does not delete `.clj` or merge live-boot into `.cljc`. The
live-boot GDT/TSS shim stays in `.clj`. The two files remain a twin;
the JVM file must not be a weaker allowlist than the portable one.

## Evidence

`elf64-test` must throw `no admitted symbol` and name
`aiueos-not-in-the-table` in `:unlisted-exports` for a sealed kernel
object that exports that name. A source that exports only `main` still
packages as `kotoba_aiueos_probe`.

The same JVM file places kernel RW context at file offset `0x8000` for
a small image. Tests that still look at `0x10000` are reading the
`.cljc` layout.
