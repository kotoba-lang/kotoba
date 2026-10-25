# kotoba-lang/org-ieee-shasum — `shasum -a 256`, as a Kotoba command binary

The SHA-256 form of `shasum(1)`, written in `.kotoba` and compiled to a
standalone native executable.

```sh
./shasum -a 256 FILE...     # <64 hex>  FILE, one line per operand
... | ./shasum -a 256       # <64 hex>  -
```

## Measured, 2026-09-16

832 invocations in 1,268,018 Bash calls across 558 agent transcripts
(superproject ADR-2609161710): `shasum -a 256` 612, bare `shasum` (SHA-1)
211. Only SHA-256 is here — it is the digest the capability catalog names
(`:hash/sha256`, wire 3), and the loader gained a real provider for it the
same day (amu #1016; before that the wire fell through to identity and a
guest asking for a digest got its input back).

## Measured against the system utility

`test/shasum_test.cljk` compiles the guest, packages it, **runs the
binary**, and compares stdout, stderr and exit status against
`/usr/bin/shasum` on 14 cases: the FIPS vectors, block boundaries (55, 56
and 64 bytes — the two-block padding edge), a 1 MB file, multi-byte text,
several operands, a missing operand among readable ones (reported, skipped,
exit 1), and standard input. All byte-identical. Three named divergences:
`-a 1`, a bare `shasum`, and no arguments are refused with a message, where
the system answers SHA-1.

The digest is computed by the host: the file's bytes are the request and
the 64 hex characters the answer, so the guest's own work is the walk over
operands.

## What this is not

No SHA-1 / 224 / 384 / 512, no `-c` (check mode), no `-b`/`-t`, no `-p`.
Capabilities: `:cli/args` (38), `:fs/app-data` (35), `:io/read` (41),
`:hash/sha256` (3), `:io/write` (37), `:io/write-error` (39).
