# FS2: complete native filesystem path framing

Tracking: [JUN-241](https://linear.app/kotobalabs/issue/JUN-241),
[JUN-201](https://linear.app/kotobalabs/issue/JUN-201),
[JUN-202](https://linear.app/kotobalabs/issue/JUN-202).

Source candidate only. No implementation, generator, assembler, compiler,
filesystem operation, native admission, emitted artifact, syscall, runtime or
test was executed. This does not enable CDCI or qualify a provider.

## Why the native boundary needs a version

The former wire-34 listing writes raw names separated by TAB/LF, so different
directory contents can serialize identically. Wire 35 scans the whole request
for ASCII `*_SEP` tokens, so literal path/content bytes can participate in form
selection. Splitting, trimming, restricting filenames or adding client-only
quoting cannot represent the complete native string-path domain.

FS2 uses the existing string/string capabilities and existing grants:
`:fs/browse` wire 34 and `:fs/app-data` wire 35. Wire 36 remains the separately
owned `:fs/browse-dir`; it is not reassigned. No provider number, handler id,
profile mapping, syscall authority or sealed decision API changes here.

## Exact request and response

`NUL` is byte zero. The five-byte marker is `NUL F S 2 NUL`.

```
request  = marker + form-letter + path + NUL + tail
response = marker + operation-answer
```

The path is a nonempty valid UTF-8 native path with no NUL. TAB, LF, Unicode
and every former separator token are ordinary path bytes. This does not
claim arbitrary non-UTF-8 filename or raw-file-byte I/O through a string API.
The first NUL after the form letter uniquely ends the path. The tail is the
remaining admitted string span and may include NUL for write/append content.
The owning path and per-form implementation still validates it as required.

| Letter | Form | Tail | Unwrapped answer |
| --- | --- | --- | --- |
| A | 0 read | empty | complete file text |
| B | 1 write | content | written content |
| C | 2 append | content | appended content |
| D | 3 exists | empty | `0` or `1` |
| E | 4 range | decimal offset:length | selected text |
| F | 5 stat | empty | mode size blocks is-dir, or empty |
| G | 6 mtime | empty | unsigned seconds, or empty |
| H | 7 chmod | octal mode | `0` or `1` |
| I | 8 mkdir | empty | `0` or `1` |
| J | 9 unlink | empty | `0` or `1` |
| K | 10 rmdir | empty | `0` or `1` |
| L | 11 rename | destination path | `0` or `1` |
| M | 12 fsync | empty | `0` or `1` |
| N | 13 make-temp-dir | prefix | full path, or empty |
| O | 14 no-follow stat | empty | mode size blocks kind, or empty |
| P | 15 owner | empty | uid and euid, or empty |

Browse accepts only A with an empty tail. Its unwrapped answer is zero or
more `name + NUL + ASCII 0/1 + NUL` records, preserving every name in the
existing stable unsigned-byte sort. A directory flag is still one only for
DT_DIR; DT_UNKNOWN is not promoted to a proved file/directory classification.
Traversal must ask no-follow metadata before descending.

Every FS2 response, including empty directories/absent metadata, has the
marker. The Amu codec requires it. An old provider's empty response is an
explicit protocol error and cannot become successful absence or an empty
tree. An initial NUL with a bad marker, out-of-range form, missing path
terminator, empty path or forbidden tail refuses before filesystem dispatch.

## Native mechanism and budgets

`linux_static_fs_protocol.kotoba` supplies the complete request parser and
one shared response routine. C3 composes it once for both handlers. The
original request span is unchanged; private state at data+1608/1616/1624
holds the frame mode and admitted tail span within the reserved header page.
Every filesystem call resets those fields. No later handler consumes stale
framing state. Request family labels and the response reader have distinct
prefixes. Both Linux ISAs use the existing typed instruction IR and syscalls.

FS2 app-data calls the owning implemented-form and occurrence decisions,
then the complete existing sixteen operation bodies with the explicit path
and tail spans. The body does not scan tokens in FS2 data. Range/chmod/temp,
rename destination resolution and all result/errno decisions remain real.

Browse charges name length plus three framing bytes for every record,
including the first. The existing names/index capacity remains sufficient;
no entry-count or filename-character subset is introduced. Legacy responses
retain their previous raw layout until those callers are ported and retired.
Canonical Amu callers require FS2 and never fall back to that ambiguous form.

The shared response routine validates the actual result handle/text, checks
length+5 without overflow, asks owning op 6 for the additional complete framed
span, proves remaining pool room, copies into a disjoint new pool tail, and
allocates a checked unvalidated pair. Common C3 finish then validates it.
It does not invent a successful default after a resource/provider refusal.
The framing and result pair consume real budgets; existing filesystem
operations remain nontransactional when a later failure occurs.

## Remaining whole-provider and caller acceptance

C1 grants, root/path normalization, openat2 no-follow/beneath confinement,
descriptor ownership and actual operation bodies remain required. This
framing change does not establish their runtime behavior. In particular,
the [complete scope-absence source](linux-static-scope-absence.md) now
distinguishes C1 scope denial from invalid state and supplies all sixteen
absent answers through new owning decision op 48. Both rename operands are
checked before target access. Actual no-leak/kernel behavior and the newly
compiled matching decision artifact remain unqualified.

Amu's paired complete six-export fs-tree source uses this protocol, typed
errors, recursive parents and no-follow deletion, including root file/link
unlink. Whole resolver/materializer/package-authoring caller ports and the
ambiguous legacy decoder's retirement remain open. Raw-byte I/O/digest,
required general runtime helpers/ABI, source/type/native admission, emitted
bytes/Definition CIDs, filesystem/error/resource/race evidence, reviewed
owning mains/pins and complete compiler self-rebuild remain required.

No C-loader pin, generated C header, hosted oracle, CLJK sugar or KBB-first
step supplies that evidence. This source changes no workflow/protection,
live service or production route.
