# kotoba-lang/org-ieee-mkdir — POSIX `mkdir`, as a Kotoba command binary

```sh
./mkdir DIR...        create each directory
./mkdir -p DIR...     create missing parents too, silent about what exists
```

Fourteen cases agree with `/bin/mkdir` on stdout, stderr, exit status **and
the resulting directory tree** — mkdir writes nothing on success, so an
output-only comparison would pass an implementation that created nothing.

## The diagnostics name the parent, not the operand

Measured against `/bin/mkdir` 2026-09-10:

```
mkdir x/y/z      ->  mkdir: x/y: No such file or directory     (not x/y/z)
mkdir one        ->  mkdir: one: File exists
mkdir -p af/below->  mkdir: af: Not a directory                (af is a file)
```

The wire answers only `1` or `0`, so which message applies is decided by
asking `EXISTS` about the operand and then its parent — that is what the
EXISTS form is for. Collapsing the two into one message fails **3** cases.

For `-p`, the component that refused is the first ancestor that already
existed, and the walk is the only thing that knows which one that is, so it
owns the message rather than the caller.

## Why `-p` climbs instead of descending

It cannot walk **downward** from the root creating as it goes: an out-of-scope
path answers `EXISTS` `0`, which is indistinguishable from absent, so the walk
would try to create `/private` and trap on the grant. Climbing and stopping at
the first ancestor that exists terminates inside the grant, because the scope
root exists and answers `1`.

A `-p` whose ancestors lie outside the grant therefore traps rather than
reporting. A packaged command is given a scope its operands live under, and
the depth bound (64) is there so a path the grant does not contain fails
instead of recursing forever.

Removing the parent-creation makes `-p` fail 4 cases, including `-p taken`,
which must succeed silently over a directory that already exists.

## Capabilities

`:cli/args` (38), `:fs/app-data` (35), `:io/write-error` (39). Nothing on
stdout at all.

The `MKDIR_SEP` request form is new; it is a new **request form on wire 35**,
not a new capability, so nothing in the catalog or `kotoba-sema` moved.

## What this is not

No `-m` (mode) — a new directory takes `0777` masked by the umask, which is
what `mkdir(1)` does, but the mode cannot be set. No `-v`.
