# Canonical Linux-static directory browse handler

Update: [FS2 framing](linux-static-filesystem-framing.md) adds a complete
NUL-framed native listing and mandatory response acknowledgement. The raw
TAB/LF layout described below remains only for legacy requests pending caller
retirement. The recorded initial source digest/counts below are provenance;
they do not identify or qualify the updated source.

Tracking: [JUN-201](https://linear.app/kotobalabs/issue/JUN-201),
[JUN-200](https://linear.app/kotobalabs/issue/JUN-200).

`src/kotoba/native/linux_static_browse.kotoba` ports the complete C3 fs/browse
handler from `linux_static.cljk`, owning main
`535ca0a3e7ec1c4b4496c8ea12b18436838cbb47`, blob
`0ab7132ae38f4fd6fb75b107909c1854559160cf`. It reuses canonical rooted paths,
typed syscall/decision IR and checked pool-pair allocation. Both Linux ISAs
are retained; no host directory API, C/FFI, shell, runtime sorting or filename
conversion is imported.

This is a source candidate. No generator, assembler, compiler build, native
admission, directory operation, syscall or artifact/runtime code was executed.
No test was added or run. Source SHA-256:
`228876a997fcff0492d24c946608811ea975a122e0a4c3a848618f500e41ae2a`.
Static source inventory: 238 lines / 29 functions, balanced delimiters,
own/import call arities after structural thread expansion, known heads and
no local data-as-function calls. Source record-window, register/state,
sorting, budget and result dataflow were reviewed; emitted bytes and native
positive/refusal behavior remain unqualified.

## API and composition

`routine [isa source-plan layout]` returns `:linux.static.browse/result` with
`code`, `binding` and `error`. Only `error=:ok` permits consumption; its binding
is `:ls.cap/fs-browse`, handler id 8. Failure has empty code and binding `:none`,
with named ISA/handler/index/layout/scratch or shared path/context errors.
The C3 candidate imports and composes this body, so fs/browse is no longer a
missing handler external. The [filesystem component](linux-static-filesystem-port.md)
also supplies fs/app-data; the [process component](linux-static-spawn-port.md)
supplies spawn. The C3 source candidate now composes all existing handler bodies.

The caller must admit the complete artifact, native plan, narrowed grants,
decision code, context, ISA and exact computed layout. This component's bounds
checks do not attest supplied documents or actual memory mappings. Entry is
only after the C1 gate and UTF-8 request admission, with s0=image data and the
request pointer/length in the existing C3 state protocol. The result is stored
as a handle and transferred to the common UTF-8-validated C3 finish path.
Standalone direct entry does not carry that authority.

## Complete listing path

The handler resolves the request under the admitted scope through the shared
path component, then opens the directory beneath the captured root using
openat2 with the reference directory/no-follow/close-on-exec flags. Owning
outcome op 12 handles open/read retry and refusal. No unscoped directory or
alternate open is substituted.

getdents64 fills the reference's 32768-byte batch region. Its record layout
is the kernel's [linux_dirent64 definition](https://github.com/torvalds/linux/blob/master/include/linux/dirent.h)
and [documented ABI](https://man7.org/linux/man-pages/man2/getdents.2.html).
The candidate checks positive batch size within capacity, remaining fixed
record header, record length within the batch, NUL termination within that
record and nonempty name. Thus a malformed record cannot drive an unbounded
strlen or an unchecked offset increment. These additional refusal guards
are not a claim of identical malformed-input diagnostic precedence.

Dot and dot-dot classification still asks owning op 18 to skip the entry.
Other names are copied without normalization/escaping into the names arena;
each index entry retains offset, byte length and the reference's directory
flag (1 only for d_type=DT_DIR, otherwise 0, including DT_UNKNOWN). This
preserves its existing output convention rather than claiming that an unknown
type was independently resolved. No ASCII-only or small-entry-count subset
is introduced; invalid UTF-8 still fails the common result contract.

The complete insertion sort compares raw unsigned name bytes and lengths,
with the same stable less-or-equal disposition. Output is name, tab, ASCII
0/1, with a newline before each row except the first and no final newline.
Names containing tab/newline retain the reference's raw bytes; this patch
does not silently introduce a different serialization or escaping contract.
An empty directory produces an allocated empty-string handle.

## Resource and ownership invariants

Owning op 6 admits each accumulated listing-byte charge, then the final pool
charge. The names/index scratch follow the complete plan: names need at most
the byte budget, and the index has `2 + floor(bytes/3)` entries of 24 bytes.
The candidate checks that capacity/product and all region spans fit signed
i64/image memory, plus remaining names/index/pool capacity before writes.
It keeps all batches and entries up to those owning budgets; no arbitrary
replacement limit is used. Scratch/layout disjointness and stable context
ownership remain the full image/verifier caller's responsibility.

After EOF the directory fd is closed, names are sorted, and the complete
listing is emitted once into the admitted pool. Only actual result bytes
advance pool-used. The shared pool-pair fragment performs checked cell
allocation without copying or charging bytes twice; C3 admits the result
handle/UTF-8. Per-context calls must remain serialized. Full native fd/resource,
ordering, error, directory-type and UTF-8 behavior still needs qualification.

The [prelude/context candidate](linux-static-prelude-port.md) now composes these
bodies. Remaining closure includes full image integration,
sealed decision placement, hash routing/profile, ELF construction, native
verification/Definition CIDs, reviewed pins and compiler self-rebuild. Neither
hosted CDCI nor a native filesystem release is enabled by this source port.
