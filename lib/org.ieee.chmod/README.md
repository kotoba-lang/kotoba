# kotoba-lang/org-ieee-chmod — POSIX `chmod`, the octal form

```sh
./chmod MODE FILE...
```

Fourteen cases agree with `/bin/chmod` on stdout, stderr, exit status **and
the resulting modes** — chmod writes nothing on success, so the tree snapshot
carries each entry's permission bits and that is what the comparison rests on.

## Octal only

The symbolic form (`u+x`, `go-w`, `a=r`) is a small language of its own — a
who-list, an operator and a perm-list applied against the file's current mode.
It is not implemented. Same kind of boundary
[`org-ieee-grep`](https://github.com/kotoba-lang/org-ieee-grep) draws at `-F`:
what is here is exact, and what is absent is named rather than half-done.

`0755` and `755` are the same request — the mode travels to the host as the
octal **text** it arrived as, so neither side re-renders it.

## Setuid, setgid and the sticky bit are not settable

The host masks to the twelve permission bits, because a grant to write a
file's bytes is not a grant to make it run as someone else. `chmod 4755` sets
`0755` here and `4755` under `/bin/chmod`.

## The mode is validated here, not at the host

A mode that is not octal makes the host **trap**, and a command must never
provoke that — a trap cannot be caught and cannot be reported. So the digits
are checked in the guest and refused the way chmod refuses them
(`chmod: Invalid file mode: 9999`, exit 1). Removing that check fails exactly
the two invalid-mode cases.

Reporting success without actually changing anything fails **8** — every case
that should have moved a mode.

## Its usage differs from its siblings, and was measured

Two lines, a literal **tab** after `usage:` and at the start of the second,
and exit **1** — not the 64 that `rm` and `mv` use for the same mistake. Each
utility was measured on itself.

## Capabilities

`:cli/args` (38), `:fs/app-data` (35), `:io/write-error` (39). Nothing on
stdout.

`CHMOD_SEP` is a new **request form on wire 35**, not a new capability, and it
opens the file with `O_NOFOLLOW` and proves the descriptor is inside the grant
before touching it — the same confinement reading and writing use.

## What this is not

No symbolic modes, no `-R`, `-f`, `-h`, `-v`. Symlinks are not followed.
Operands must be absolute paths inside the packaged scope.
