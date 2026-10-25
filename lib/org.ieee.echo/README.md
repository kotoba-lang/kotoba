# kotoba-lang/org-ieee-echo — POSIX `echo`, as a Kotoba command binary

`echo` from IEEE Std 1003.1, written in `.kotoba` and compiled to a
standalone native executable. Named `org-ieee-echo` because IEEE publishes
POSIX — the same `org-<body>-<spec>` pattern as
[`org-ieee-tar`](https://github.com/kotoba-lang/org-ieee-tar),
`org-ieee-verilog` and `org-ieee-vhdl`.

```sh
amu compile echo/core.kotoba --target aarch64-macos --jvm-free \
  --policy policy.edn --output echo.kexe            # {:allow #{[:cap/call 37] [:cap/call 38]}}
amu extract-native echo.kexe --symbol main --output echo.bin
nbb <amu>/scripts/package-command.cljs --code echo.bin --offset <reported> \
  --isa aarch64 --allow 37,38 --output ./echo

./echo hello world      # hello world
./echo -n hi            # hi
```

## Measured against the system utility

`test/echo_test.cljk` does not assert that the guest compiles. It compiles
it, packages it into a standalone binary, **runs that binary**, and compares
bytes and exit status against `/bin/echo` — because `:ok true` from a
compiler means the artifact was built, not that it is right.

```
AMU_HOME=<amu checkout> kbb --backend sci test/echo_test.cljk
```

Nine cases, all byte-identical:

| argv | answer |
|---|---|
| `hello world` | `"hello world\n"` |
| `one` | `"one\n"` |
| `a b c d e` | `"a b c d e\n"` |
| *(none)* | `"\n"` |
| `x "" y` | `"x  y\n"` |
| `-n hi` | `"hi"` |
| `-n` | `""` |
| `--code /etc/passwd` | `"--code /etc/passwd\n"` |
| `-n a b` | `"a b"` |

Each case separates a right implementation from a wrong one that passes the
others. Removing the `-n` handling fails exactly three of them; writing the
separator *after* each argument instead of *between* fails four; neither
change fails a case it should not.

**Arguments are passed as a vector, never through a shell.** zsh does not
word-split an unquoted variable, so `cmd $args` hands the whole string over
as **one** argument — which silently turns a multi-argument test into a
single-argument one. Measured 2026-09-09: exactly that made `-n hi` and
`a b c d e` appear to pass before `-n` existed.

## Capabilities

`:cli/args` (wire 38) to see the arguments and `:io/write` (wire 37) to
answer. Nothing else: `echo` reads no file, so it is granted no filesystem
scope and could not use one if it had it. `./echo --code /etc/passwd` prints
that text — a packaged command has no argument that selects what it runs or
what it may do, because the code and the grant are constants of the binary.

## Two things the source works around, and why

Both capabilities carry `:string -> :string`, because those are the generic
type pairs `kotoba.kir`'s native gate admits for `typed-cap-call` (with i64,
option-i64 and result-i64). So numbers travel as **decimal text** in both
directions and the guest has no `text->number` builtin: the walk counts up
and compares the *rendered* index against the rendered count.

And the loop does not stop at the first empty answer. An index past the end
answers the empty string — but an **empty argument is legal** and answers the
same thing, so `echo x "" y` would stop after `x`. The count comes from the
empty *request*, which no index can collide with.

## What this is not, yet

The binary is a Mach-O executable that runs from anywhere, but building it
still takes three commands. There is no `amu build-command` that goes from
`.kotoba` to `./echo` in one step, and no cross-compilation: the packager
links for the host it runs on.
