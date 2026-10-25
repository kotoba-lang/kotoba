# kotoba-lang/org-ieee-stat — BSD `stat -f`, as a Kotoba command binary

The `-f FORMAT` form of `stat(1)`, written in `.kotoba` and compiled to a
standalone native executable.

```sh
./stat -f %z FILE            # size in bytes
./stat -f %m FILE            # modification time, seconds since 1970
./stat -f '%N: %z bytes' A B # %N name, %p mode (100644 / 40755), %% literal
```

## Measured, 2026-09-16

267 invocations in 1,268,018 Bash calls across 558 agent transcripts
(superproject ADR-2609161710): `-f %Sm` 61, `-f %m` 23, `-f %z` 18, GNU
`-c %Y` 18. `%m` needed a loader form — wire 35's STAT answers mode, size,
blocks and is-dir, and `org-ieee-du` reads its fourth field to the end of
the string, so mtime became its own `MTIME_SEP` form (amu #1017) rather
than a fifth field that would have turned every directory into a file for
`du`.

## Measured against the system utility

`test/stat_test.cljk` compiles the guest, packages it, **runs the binary**,
and compares stdout, stderr and exit status against `/usr/bin/stat` on 20
cases over files with *known* sizes, modes and mtimes (set with `utimes`,
so `%m` is a number the suite predicts): each conversion alone and mixed,
a directory (`%p` → `40755`), several operands, a missing operand among
readable ones (reported, exit 1). All byte-identical. Five named
divergences: `%Sm` (and any `%S…`), other conversions, the default line
without `-f`, `-c`, and `-f` without a file — each refused with a message,
exit 1.

## What this is not

No `%Sm` / local times (zone database), no default line (uid names, device
numbers, local times), no `-L`, `-x`, `-r`, `-s`, no symbolic-link
reporting (the loader opens with `O_NOFOLLOW`). Capabilities: `:cli/args`
(38), `:fs/app-data` (35), `:io/write` (37), `:io/write-error` (39).
