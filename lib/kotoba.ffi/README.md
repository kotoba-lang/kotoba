# kotoba-lang/ffi

`kotoba.ffi` — declared foreign-function bindings and native memory as a
**host capability**. On the JVM it is `java.lang.foreign` (the FFM API); on
the kbb engine (SCI on Node) there is no FFI and every host call refuses by
name.

It exists so that the `java.lang.foreign.*` → `kotoba.*` migration can reach
100%: the fleet files that used FFM directly (`aiueos.vfio`, `aiueos.hvt`,
`aiueos.pid1`, `aiueos.launcher`, their tests, and
`kotodama.inference.host.native-kdot`) call this namespace instead.

## Why a capability

Kotoba is a safe application language: the boundary is the absence of
ambient authority, not purity. Calling a C symbol is the most ambient
authority there is — it can do anything the process can. So the library is
split:

| Half | Runs on | What it is |
|---|---|---|
| **pure** | kbb and JVM | C type keywords and their LP64 sizes/alignments, `signature` data + validation, C struct layout math, the declared binding table |
| **host** | JVM only | linker, symbol lookup, downcalls, arenas, memory segments |

A binding table (`library`) declares every symbol and its signature up
front; `bind` refuses a symbol that was not declared
(`:undeclared-symbol`) *before* any native lookup happens, on both hosts.

## Contract (`kotoba.ffi`)

Types: `:i8 :u8 :i16 :u16 :i32 :u32 :i64 :f32 :f64 :ptr :void` (LP64:
`:ptr` and `:i64` are 8 bytes). Unsigned types share the FFM layout of their
width; `fetch` and `invoke` return them zero-extended.

| fn | JVM equivalent |
|---|---|
| `(signature ret args)` / `(signature-void args)` | data `{:kotoba.ffi/ret :kotoba.ffi/args}`; `(descriptor sig)` → `FunctionDescriptor/of` / `ofVoid` |
| `(layout t)` | `ValueLayout/JAVA_INT` … `ADDRESS` |
| `(native-linker)` `(default-lookup l)` `(loader-lookup)` `(library-lookup path arena)` `(load-library! path)` | `Linker/nativeLinker` `.defaultLookup` `SymbolLookup/loaderLookup` `SymbolLookup/libraryLookup` `System/load` |
| `(find-symbol lk name)` / `(find-symbol! lk name)` | `.find` → segment or nil / `:symbol-not-found` |
| `(downcall linker sym sig)` `(invoke h & args)` `(invoke-list h args)` `(method-handle h)` | `.downcallHandle` + `.invokeWithArguments`, args coerced to the declared C type |
| `(confined-arena)` `(shared-arena)` `(auto-arena)` `(global-arena)` | `Arena/ofConfined` … `Arena/global` (closeable with `with-open`) |
| `(alloc arena t)` `(alloc-bytes arena n [align])` `(c-string arena s)` | `.allocate` / `.allocateFrom` (UTF-8, NUL-terminated) |
| `(put! seg t off v)` `(fetch seg t off)` | `.set` / `.get` with the type's layout |
| `(byte-size s)` `(copy-from! dst src)` `(of-array arr)` `(reinterpret s n [arena])` `(address s)` `(null-segment)` `(segment-string s)` `(as-slice s off n)` | `.byteSize` `.copyFrom` `MemorySegment/ofArray` `.reinterpret` `.address` `MemorySegment/NULL` `.getString 0` `.asSlice` |
| `(map-file arena path off n)` | `FileChannel.map(READ_ONLY, off, n, arena)` |
| `(bind lib linker lookup name)` | declared-only downcall |
| `(segment? x)` `(arena? x)` | `instance?` (false on kbb) |

Pure: `type?` `type-size` `type-align` `check-value` `signature?`
`struct-layout` `library` `declared` `error-reason` `host` `host-fns`.

### Errors

Every refusal is `ex-info` with `:kotoba.ffi/error <keyword>`. The JDK
exceptions FFM throws are **translated** (the original is the cause), so a
caller matches one keyword on either host:

| keyword | from |
|---|---|
| `:out-of-bounds` | `IndexOutOfBoundsException` |
| `:misaligned` | `IllegalArgumentException` "… alignment constraint …" |
| `:read-only` | write to a read-only (e.g. mapped) segment |
| `:scope-closed` | `IllegalStateException` (arena already closed) |
| `:wrong-thread` | `WrongThreadException` (confined arena, other thread) |
| `:unknown-type` `:void-has-no-value` `:void-argument` `:args-not-sequential` | signature / type validation |
| `:value-out-of-range` `:not-an-integer` `:not-a-number` `:not-a-segment` `:arity-mismatch` `:not-a-handle` | `put!` / `invoke` argument checks (before FFM is touched) |
| `:empty-struct` `:duplicate-field` `:bad-field` `:bad-array-length` | `struct-layout` |
| `:undeclared-symbol` `:bad-library` `:bad-signature` `:bad-symbol-name` | binding table |
| `:symbol-not-found` `:library-load-failed` `:negative-size` `:bad-alignment` `:not-a-string` `:not-a-primitive-array` | host |
| `:unsupported-host` (`:host :node`, `:op <fn>`) | every host fn on kbb |

`invoke` coerces each argument by its declared type: FFM's
`invokeWithArguments` refuses a boxed `Long` for an `int` parameter (measured
in the tests), so a Clojure long is range-checked and narrowed; `nil` is
`NULL` for `:ptr`.

## What runs where

- **JVM, JDK 22+**: everything (FFM is final). Measured on JDK 26.0.1.
- **JVM, JDK 21**: everything as well — FFM is a preview API there but loads
  without `--enable-preview` for what this namespace uses; only the String
  helpers were renamed in 22, and `c-string` / `segment-string` pick
  `allocateUtf8String` / `getUtf8String` by `jdk-feature`. Measured on
  Temurin 21.0.1. (The consumers' own raw `allocateFrom` calls needed 22.)
- **kbb (SCI on Node 26)**: the pure half; every host fn throws
  `{:kotoba.ffi/error :unsupported-host :host :node :op <fn>}`.
- Restricted methods (`reinterpret`, `downcall`) print a JDK warning unless
  the JVM runs with `--enable-native-access=ALL-UNNAMED`.

## Tests

```
kbb -M:test
kbb --backend sci scripts/jvm_test.cljk kotoba.ffi-test kotoba.ffi-jvm-test \
    --jvm-opt --enable-native-access=ALL-UNNAMED [--java <jdk22+/bin/java>]
```

Measured 2026-09-25 on darwin/arm64: kbb 7 tests / 162 assertions; JVM
(JDK 26.0.1 and 21.0.1) 15 tests / 234 assertions. The JVM suite calls libc
`strlen`, `getpid` (checked against `ProcessHandle`), `abs` and `labs`, and
compares every answer with the raw FFM call on the same symbol; every type is
written with `put!` and read with raw `MemorySegment.get` (and the reverse)
at its offset; `c-string` is byte-compared with raw `allocateFrom`
(`.mismatch` = -1). Mutating struct padding, the int coercion, the
out-of-bounds translation or the kbb refusal keyword turns the suites red
(checked before landing).

`scripts/jvm_test.cljk` is the fleet JVM oracle runner, extended here with
`--jvm-opt` and `--java`.

## Neighbours

- **`kotoba-native`** is amu's native AOT backend (checked KIR → x86_64 /
  aarch64 machine code). It emits code; it does not call host C libraries.
- **`kototama-native`** is kototama's native host: it loads and runs
  artifacts amu wove, under a capability gate. It is not an FFI to host C
  libraries either.
- **`kotoba.ffi`** is the only one of the three that binds existing C symbols
  of the host process, and it does so only on a host that offers FFI (the
  JVM today).
