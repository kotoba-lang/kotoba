# kotoba-lang/org-ieee-which — BSD `which`, as a Kotoba command binary

`which(1)` — `which NAME...`, `-s`, `-a` — written in `.kotoba` and
compiled to a standalone native executable.

```sh
./which ls            # /opt/homebrew/opt/coreutils/libexec/gnubin/ls
./which -a ls         # every ls on PATH, in PATH order
./which -s nope       # nothing printed; exit 1
```

## Measured, 2026-09-16

1,495 invocations in 1,268,018 Bash calls across 558 agent transcripts
(superproject ADR-2609161710), all but a handful `which NAME`.

## Where it looks

Where the caller's shell looks: PATH comes from `:env/read` (wire 33), and
the packaged scope is the single entry **`$PATH`**, which the loader expands
at start to the caller's PATH directories (amu #1021) — the one deliberate
exception to a packaged command ignoring its environment, and the caller's
choice the way standard input and `/dev/fd` are. Under those directories
`which` probes with wire 35's `EXISTS_SEP` (a readable regular file) and
`STAT_SEP` (an execute bit). It reads nothing else: a directory that PATH
does not name is not in scope, so a `which` that could not be fooled into
probing the filesystem at large is what the packaging says, not what the
program promises.

## Measured against the system utility

`test/which_test.cljk` compiles the guest, packages it, **runs the binary**,
and compares stdout, stderr and exit status against `/usr/bin/which` under
a PATH the suite controls: two directories it owns plus `/usr/bin`, a name
in both (first wins; `-a` lists both, in PATH order both ways), a name
without an execute bit (skipped), a group-only execute bit, a directory of
that name (skipped), a name with a slash (tried as given, not searched),
several names with one missing (exit 1, the others still printed), empty
PATH entries, and the usage error. 23 cases, all byte-identical.

## What this is not

An empty PATH entry (`::`) means the working directory to a shell; a
packaged command has no scope for it, so it holds nothing here (pinned by
comparison — `/usr/bin/which` agrees for the suite's case). Capabilities:
`:cli/args` (38), `:env/read` (33), `:fs/app-data` (35), `:io/write` (37),
`:io/write-error` (39).
