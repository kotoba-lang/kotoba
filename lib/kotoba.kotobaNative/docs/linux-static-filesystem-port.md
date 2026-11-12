# Canonical Linux-static fs/app-data handler source

Update: [FS2 framing](linux-static-filesystem-framing.md) supplies explicit
form/path/tail spans for all sixteen forms and mandatory response
acknowledgement, bypassing ambiguous token scanning for canonical callers.
The token protocol below remains only as native migration inventory until
its callers are retired. Initial source digest/counts below are provenance;
they do not identify or qualify the updated source.

Tracking: [JUN-201](https://linear.app/kotobalabs/issue/JUN-201),
[JUN-200](https://linear.app/kotobalabs/issue/JUN-200).

`src/kotoba/native/linux_static_filesystem.kotoba` ports the complete sixteen-form
C3 fs/app-data mechanism from `linux_static.cljk`, owning main
`535ca0a3e7ec1c4b4496c8ea12b18436838cbb47`, blob
`0ab7132ae38f4fd6fb75b107909c1854559160cf`. It imports canonical Kotoba path,
syscall/decision IR, and pool-pair fragments, with no host filesystem API,
shell, FFI, C loader, Node or JVM dependency. Both Linux ISAs are retained.

This is a source candidate. No generator, assembler, compiler build, native
admission, filesystem operation, artifact, syscall or runtime code was executed.
No test was added or run. Source SHA-256:
`0594885fea5dec08bcd794a130a2bf9b9f3c83b9364815c4169ac28a2f8566a4`.
Static inventory: 567 lines / 63 functions, balanced delimiters, own/import call
arities after structural thread expansion, known heads and no local value used
as a function. Source token/state/register, retry, bounds and result dataflow
were read; native type admission, emitted bytes and behavior remain unqualified.

## API and authority

`routine [isa source-plan layout]` returns `:linux.static.fs/result` with `code`,
`binding` and `error`. Only `error=:ok` permits consuming its code; binding is
`:ls.cap/fs-app-data`, handler id 7. Failure has empty code and binding `:none`.
The C3 candidate composes this body and the [process body](linux-static-spawn-port.md);
no existing handler body remains external to that source candidate.

The caller must first admit the full sealed native plan, narrowed grants,
context ABI, ISA-matched compiled decision exports and exact image layout.
Local region/offset/arithmetic checks do not attest documents, mappings or
grant authority. All per-context handler calls remain serialized. Entry follows
the C1 gate and complete UTF-8 request admission with s0=image data and the
existing request state. Results use shared byte/cell admission and the common
C3 result-handle/UTF-8 finish path; direct entry grants no authority.

The fifteen ASCII separator tokens keep their non-overlapping occurrence counts
and first indices. The presence mask and WRITE/APPEND first-index ordering go
to real owning handler decision op 1. Implemented-form and occurrence policy
stay with ops 2 and 17. Full path normalization, dual root spelling, C1 scope
admission and openat2/parent opening come from the shared path component.
No alternate unscoped open or inline replacement policy is introduced.

## All forms

| Form | Operation and retained answer |
| --- | --- |
| 0 | Read complete file into the admitted pool, including EOF probe at capacity |
| 1 | Write/create/truncate mode 0644; return content after WRITE_SEP |
| 2 | Append to an existing file, without O_CREAT; return appended content |
| 3 | Exists, with `1`/`0`, including the existing scope-refusal-to-`0` behavior |
| 4 | Exact decimal offset:length range using pread64; refuse short EOF/shrink |
| 5 | Stat: mode, size, blocks, directory flag; empty when absent |
| 6 | Mtime seconds as unsigned decimal; empty when absent |
| 7 | Chmod from 1..6 octal digits; boolean answer |
| 8 | Mkdir through admitted parent fd; boolean answer |
| 9 | Unlink through admitted parent fd; boolean answer |
| 10 | Rmdir through admitted parent fd and AT_REMOVEDIR; boolean answer |
| 11 | Rename between two admitted parent fds; boolean answer |
| 12 | Fsync, with owning retry/negative handling; boolean answer |
| 13 | Make temporary directory, returning full path or empty when exhausted |
| 14 | Stat final component itself with O_PATH/O_NOFOLLOW; mode,size,blocks,kind |
| 15 | Owner of final component itself: uid and geteuid; empty when absent |

Metadata offsets retain each ISA's reference struct layout; mode/uid loads
are narrowed to 32 bits. A private unsigned formatter has the complete 64-bit
decimal range and uses the existing 32-byte context scratch, with bounded
256-byte metadata answers. There is no host number/string formatting call.

Owning op 12 continues to decide kernel errno proceed/retry/negative/named
outcomes at each operation's reference stage. Decimal range, octal modes,
stat classification and temporary-name policy stay with real ops 3, 6, 16,
20..30. The temp loop retains owning attempt and suffix limits, exact native
entropy, owning suffix mapping and mode. Entropy unavailability uses the
shared named refusal, with no fallback entropy source.

## Mechanism corrections and remaining evidence

The reference closes parent fds before asking op 12 whether mkdir/unlink/rmdir
or rename should retry. This candidate holds those fds through that decision,
closes them after success/negative outcome, and closes the first rename parent
if opening the second fails. Retrying therefore does not reuse a closed fd.

Additional arithmetic/refusal guards check separator suffix spans, complete
write/read return windows, remaining pool capacity, metadata-answer capacity,
all seven needed scratch spans and their pairwise separation. The eventual
temp answer path is bounded inside its 4096-byte buffer before mkdirat can
create the directory. Prefix+suffix+NUL and entropy scratch are bounded too.
These changes do not claim identical malformed-input diagnostic precedence
or native fd/resource parity. Fatal paths use the existing non-returning traps.

Full native positive/negative behavior, Definition CIDs, byte/ABI parity,
sealed decision placement, full [prelude/context](linux-static-prelude-port.md) integration and ELF
construction, owning hash routing/profile, reviewed dependency pins and whole
compiler self-rebuild remain open. The hosted packager does not call these
candidates. This source port enables no CDCI, service or production route.
