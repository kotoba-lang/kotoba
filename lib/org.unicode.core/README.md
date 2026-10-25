# org-unicode

**Clean-room Unicode Standard corpus — the UTF-8 encoding/decoding state machine
and the normalization-form algorithm model, in portable `.cljc`.**

Spec-first like [`org-ietf-tcp`](https://github.com/kotoba-lang/org-ietf-tcp)
and [`org-freedesktop-wayland`](https://github.com/kotoba-lang/org-freedesktop-wayland):
no ICU, no tables vendored from upstream, no locale machinery. What is here is
the **algorithm** the Standard specifies, written from the specification, with
each function citing its section.

## What is here

| namespace | subject | spec |
|---|---|---|
| `unicode.utf8` | UTF-8 encode/decode as an explicit state machine, overlong/surrogate rejection | Unicode §3.9 (UTF-8), Table 3-7 |
| `unicode.normalize` | the four normalization forms as a composition of canonical ordering + decomposition classes | Unicode §3.11 (Normalization Forms), §3.12 |

## The part worth a state machine

UTF-8 decoding is where encoding bugs live. §3.9 D92 distinguishes a *valid*
sequence from a *well-formed* one, and the two-byte prefix `0xC0`/`0xC1` is
excluded **by definition** (every sequence it starts is overlong). `decode`
returns `[:error reason pos]` instead of U+FFFD-substituting silently — the
caller decides what a malformed byte means.

## What honest extraction means here

Unicode is **table-driven**: canonical class, decomposition mapping, and
composition exclusions are per-character data this repo does not ship.
`normalize` therefore takes a `char-db` argument (the lookup surface) and the
algorithms are tested against a **minimal fixture database** covering the
documented behavior classes. Growing real tables is data work, gated behind
the same clean-room rule — and marked with their Unicode version when added.

## Not here

Locale collation, case mapping, bidi, East Asian width. Each is its own
corpus sized by its table mass.

## Provenance

Transcribed from The Unicode Standard, Version 15.0.0 — **by description**.
No upstream data file is checked in; fixture characters name their code point
in a comment so a reviewer can check the Standard directly.
