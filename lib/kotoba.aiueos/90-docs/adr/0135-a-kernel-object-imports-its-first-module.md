# ADR 0135: a kernel object imports its first module

- Status: accepted
- Date: 2026-09-02

## Decision

`hkdf-sha256.kotoba` no longer contains SHA-256. It requires
`aiueos.lib.sha256-core`, which lives at
`os/aiueos/kotoba/aiueos/lib/sha256_core.kotoba`, and the object is built
through amu's project route:

```
amu compile os/aiueos/kotoba/hkdf-sha256.kotoba \
    --source-path os/aiueos/kotoba --unpinned \
    --target x86_64-aiueos-kernel-v1 --output hkdf-sha256.o --jvm-free
```

The object still exports exactly one symbol, imports nothing, and carries one
relocation. `verify-kotoba-kernel-object.py` says so:

```
AIUEOS_KOTOBA_OBJECT_OK target=x86_64-aiueos-kernel-v1
  export=kotoba_aiueos_hkdf_sha256 imports=0 relocations=1
```

The bytes changed — `d1330d6f…a646a7e2` → `75a9857d…a30c4b59`, 13,056 → 13,128
— because the linked unit routes the export through a wrapper. Say so rather
than round it off: this is a different object, produced from the same rounds.

## Why it was inlined, and what changed

The file said why itself:

> SHA-256 is INLINED rather than required from `aiueos.sha256`. Measured
> 2026-09-02 against amu b1fdaad2: a namespace that declares `(:require ...)`
> is a multi-module project, and `amu compile` refuses to package one for
> `x86_64-aiueos-kernel-v1` at all […] That is why `cid-v1-admit.kotoba` has no
> committed `.o` beside it.

`tls13-record.kotoba` records the same cause for its own copy. amu#742
(`bb51dc14`) removed the refusal by moving amu's project resolver out of the
Wasm driver, where it had been written, into a namespace both drivers require.
Nothing about a kernel target had made it single-file.

## What was actually duplicated — the brief was one file off

Measured before touching anything, by the SHA-256 round constant:

| file | carries a SHA-256 core |
|---|---|
| `sha256.kotoba` | yes |
| `hkdf-sha256.kotoba` | yes |
| `value-runtime-sha256.kotoba` | yes — and it is `sha256.kotoba` **verbatim**, differing only in its `ns` form |
| `tls13-record.kotoba` | **no** — its copied block is AES-GCM, from `aes128-gcm.kotoba` |

So there were three SHA-256 copies, not two-plus-`tls13-record`, and the
`tls13-record` duplication is a different function with the same cause.

Only `hkdf-sha256`'s copy is extracted here. `sha256.kotoba` and
`value-runtime-sha256.kotoba` share a *different* core: the same rounds against
a separate 512-byte workspace region, where hkdf's is re-based into a
caller-owned 800-byte context at offset 448 and bounded at 192 message bytes
instead of 12,288. Sharing across that boundary needs the window length and the
workspace base to become parameters, which changes what the object admits and
therefore needs its own vectors. It is not done here and the new module says so
in its header.

## The 6 objects that never existed

The stronger measurement, taken while looking for the duplication: **eight
sources under `os/aiueos/kotoba` declare `(:require ...)`, and six of them have
no committed `.o` at all** — `cid-v1-admit`, `value-runtime-cas-verify`,
`value-runtime-dispatch`, `value-runtime-entry`,
`value-runtime-provider-policy`, `value-runtime-provider-transport`. They are
not unfinished; they could not be packaged. `hkdf-sha256` and `tls13-record`
have objects precisely because they refused to import and copied instead.

Those six are **not built here.** They resolve `aiueos.value-runtime-sha256`,
and amu's resolver maps a namespace to a path (`.` → `/`, `-` → `_`), so it
looks for `aiueos/value_runtime_sha256.kotoba` while the file sits flat as
`value-runtime-sha256.kotoba`. Measured: `required module is missing from the
explicit source paths`. Giving those modules namespace-shaped paths is a rename
across the repository's build scripts and belongs in its own change.

That rule is why the new module is at `aiueos/lib/sha256_core.kotoba` and not
at the `lib/sha256-core.kotoba` this work was asked for: the hyphen and the
missing package segment are both unresolvable. The *entry* module is exempt —
it is named explicitly rather than discovered — so `hkdf-sha256.kotoba` stays
where it is.

## Two receipts had to learn about modules

**`verify-admissions.cljs`** mapped a module namespace to a flat hyphenated
filename. It now tries amu's munged path first and falls back to the flat
spelling. Both are needed: every pre-existing module is flat, and no
namespace-shaped module is reachable without the munged rule. A verifier that
disagrees with the compiler about which bytes a namespace names verifies a
different program than the one that ships.

**`build-k16-pure-native.cljs --emit-provenance`** recorded one `:source` and
one `:source-sha256` per object. For a project that is a receipt that reports
"unmodified" for an input it never looked at: `sha256_core.kotoba` could change
and the manifest would not move. It now walks the entry's requires
transitively and records `:modules {namespace {:source :source-sha256}}`.
A module that resolves to neither path is a hard stop
(`reason=module-source-absent`, exit 2) — shown red by hiding the module file,
green with it restored.

## The vectors ran, and this section used to say they had not

They finished after this ADR first landed and they pass, so the claim is
replaced rather than annotated.

`verify-admissions os/aiueos/contracts/hkdf-sha256-v1.edn`, run twice on the
same current toolchain — once against a pristine `origin/main` worktree
(de48542, the unmodified single-module source) as the control, once against
this split:

| | vectors | traps | memory assertions | observed reasons | verdict |
|---|---|---|---|---|---|
| control (inlined) | 18 | 0 | 11 | `0 1 2 3 4 5 6` | `:passed` |
| this change (imported) | 18 | 0 | 11 | `0 1 2 3 4 5 6` | `:passed` |

The 11 memory assertions are the derived bytes themselves — the key schedule's
output, not merely its reason code — so this is the statement that matters:
**importing the core did not change what the object derives.** Both runs are
`{:jvm false}`. Elapsed 864,607 ms and 869,970 ms; the header's note that the
CLJS interpreter runs SHA-256 about ten times slower than the JVM is not
decoration.

And the committed object is reproducible from the landed compiler:
rebuilding `hkdf-sha256.o` with amu `bb51dc14` gives
`75a9857d…a30c4b59`, byte-identical to what is committed.

### The blocker that made the earlier claim true

Running them at all required a classpath other than this repository's own.
With aiueos's pinned closure, `verify-admissions` on this contract fails —
**including on a pristine `origin/main`, on the unmodified single-module
source** — with `source reader rejected input {:phase :read}` out of the pinned
`kotoba-sema` `244765d4`: `project/link-source` prints a linked source its own
reader then refuses. That is the BigInt printer defect this repository's own
verifier header calls "fixed upstream" while the pin still predates the fix.

So the contract is unrunnable on the pinned toolchain and green on a current
one, and it was already unrunnable before this change. **Advancing the
amu/kotoba-sema pin is the next change**, and until it lands, a green
`verify-admissions` for this contract requires passing a current closure
explicitly. That is a real gap: the repository's default invocation cannot
check this object.

## Not done

- `sha256.kotoba` / `value-runtime-sha256.kotoba` still hold a verbatim copy of
  each other.
- `tls13-record.kotoba` still holds a copy of `aes128-gcm.kotoba`.
- The six multi-module sources still have no objects (namespace-shaped paths).
- `qualification/jvm-free-object-parity.edn` still lists 66 objects and does not
  cover `hkdf-sha256`; regenerating it is a separate measured run.
- The amu/kotoba-sema pin (`244765d4`) predates the linked-source printer fix,
  so `verify-admissions` cannot check this contract with the repository's own
  closure. Advancing it is the next change.
