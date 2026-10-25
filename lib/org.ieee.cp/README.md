# kotoba-lang/org-ieee-cp — POSIX `cp`, as a Kotoba command binary

The single-source `cp` from IEEE Std 1003.1, written in `.kotoba` and
compiled to a standalone native executable.

```sh
./cp SRC DST     # copy SRC's contents to DST
./cp SRC DIR     # copy SRC into DIR, under its own name
```

Eighteen cases agree with `/bin/cp` on stdout, stderr, exit status **and the
resulting directory tree, each file as `[mode, sha256]`** — plus seven
mode-and-umask cases run at four different umasks.

## The tree is the test

A copy tool that printed nothing and exited 0 would pass an output-only
comparison completely. So after each case both implementations' directories
are walked and compared file by file.

That is not a precaution, it is load-bearing, and it has been measured in both
of its halves:

- replacing the copied content with a constant fails twelve cases, every one
  of them with **`exit [0 0]` and `err=["" ""]`** and an *identical mode* —
  differing only in the content hash. It flips the invalid-UTF-8 divergence
  check too, since bytes that never cross cannot trap;
- removing the `chmod` that follows the write fails five cases the mirror way
  — identical status, identical stderr, identical content hash, differing only
  in the mode — and **dropping the mode back out of the snapshot makes all
  eighteen pass again** with the guest still not setting one. Each half of the
  pair is the only thing catching its own class of bug.

Both implementations run in the *same* directory, one after the other, with
the fixtures rebuilt in between. The diagnostics contain absolute paths, so
two parallel trees would differ in stderr for reasons unrelated to the
behaviour under test.

## A new destination takes the source's mode — masked by the umask

This used to be a named divergence: a newly created destination came out 0644
whatever the source was, because 0644 is what the host's write form passes to
`open(2)`, and an executable lost its executable bit. The host has since grown
a `STAT` form and a `CHMOD` form on the same wire, and the divergence is
closed.

Closing it turned out to be more than "copy the source's mode". Measured
2026-09-10, five umasks × thirteen source modes, sixty-five rows:

| umask | source | `/bin/cp` gives |
|---|---|---|
| 022 | 755 | 755 |
| 022 | 777 | **755** |
| 022 | 666 | **644** |
| 077 | 755 | **700** |
| 002 | 777 | **775** |
| 027 | 711 | **710** |

`/bin/cp` never chooses this; `open(2)` does, because the mode it is handed is
masked by the process umask. Copying the source's mode verbatim agrees for
755, 700 and 600 — the three modes it is tempting to test — and then hands out
a **world-writable file** for a 666 or 777 source, which `/bin/cp` does not.

The guest cannot read the umask; no wire form answers it. So it **measures**
it: the host's `MKDIR` form passes 0777 and lets the umask apply, exactly as
`mkdir(1)` does, so a directory created right now comes back at `0777 & ~umask`
— which is `~umask` itself in the nine bits that matter. The probe directory is
created **at the destination path**, which has just been shown not to exist, so
no name is invented and no name can collide; it is removed before the copy is
written. All sixty-five measured rows are reproduced by
`(source mode) AND (probe mode)`.

The suite runs that at umask 022, 077, 002 and 027 and checks both against
`/bin/cp` *and* against a written-down expectation, so a run in which both
implementations drifted the same way is still a failure. Chmod-ing to the
source's mode without the mask fails six of those seven and two of the
eighteen tree cases.

Two conversions are written out in the guest because there are no formatting
builtins: the stat form answers the mode in **decimal**, the chmod form wants
**octal text**, and the AND is done a bit at a time with `quot` — there is no
`bit-and` on the wire and none is needed. Reversing the octal digit order
(0755 → 0557, still a valid octal string the host accepts) fails ten of the
eighteen and all seven umask cases.

*Overwriting* an existing destination changes no mode at all, under either
implementation, and not by luck — `open(2)` ignores its mode argument when the
file already exists. The probe and the chmod are skipped on that path, so a
600 destination stays 600 even when the source is 755.

## Two named divergences, each asserted to still be true

The suite does not avoid these; it checks each one still diverges exactly as
described, because a divergence that quietly stops being true is as much a
finding as one that appears.

**1. Bytes that are not valid UTF-8 cannot be copied.** The content crosses
as a guest *string*, and the host validates every string result as canonical
UTF-8. `/bin/cp` copies such a file fine; this refuses — exit 120, **with no
destination written**. It does not truncate and it does not write mangled
bytes. `cp` is otherwise a byte copier, so this is a real restriction of
domain. A byte-typed result would close it.

**2. Three or more operands are unsupported.** `/bin/cp` treats the last as
a target directory; this prints the usage and exits 64.

## Copying a file onto itself

`cp x x` is refused, matching `/bin/cp`'s message and exit 1. `/bin/cp`
decides this by identity (device and inode); the stat form now answers a size
and a mode but still no inode, so this compares the resolved paths as strings.
It catches `cp x x`; it does not catch `cp x ./x` or a copy through a symlink.

It is worth checking rather than skipping: without it the destination is
truncated before being written back.

## A path's kind is read from its parent

The stat form could answer "is this a directory" directly now, but it is still
answered by browsing the path's **parent** — the browse wire answers
`NAME<TAB>D` per entry, and keeping it that way is what has the two commands
reading a tree the same way. That is the same technique
[`org-ieee-find`](https://github.com/kotoba-lang/org-ieee-find) uses to walk a
tree.

This is what keeps the write form from ever being handed a directory, and
what turns a missing destination parent into a diagnostic: without that
check the case exits **120 with `KEXE_TRAP {:kind :signal :signal :SIGILL}`**
instead of `cp: …: No such file or directory`.

## Capabilities and size

`:cli/args` (38), `:fs/app-data` (35), `:fs/browse` (34), `:io/write-error`
(39). No `:io/write` — `cp` writes nothing to stdout. The stat, chmod, mkdir
and rmdir forms are all wire 35, so preserving the mode widened no grant.

The whole file is held in one guest string, so `--string-pool` must exceed
the largest file copied.

## What this is not

No `-R`, `-p`, `-f`, `-i`, `-n`, `-a`, `-v`. One source operand. No copying
of directories, devices, symlinks or hard links. Operands must be absolute
paths inside the packaged scope.

A destination the process may not write **traps** — measured 2026-09-10, exit
120 with `SIGILL` against `/bin/cp`'s `Permission denied` and exit 1, with no
destination written and nothing left behind by either. That is the write
form's behaviour on any refusal and predates the mode work; it is not one of
the two divergences above because it is not specific to `cp`.
