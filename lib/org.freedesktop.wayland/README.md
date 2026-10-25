# org-freedesktop-wayland

**Clean-room Wayland core protocol — the interface/request/event datom model and
the object-lifecycle state machine, in portable `.cljc`.**

Spec-first like [`org-ietf-tcp`](https://github.com/kotoba-lang/org-ietf-tcp):
no sockets, no file descriptors, no actual display. `wire-step` takes an object
table and one decoded message and returns the next object table; the caller
supplies everything environmental. The protocol's *sequencing discipline* is
the subject — that part is pure and testable without a compositor.

## Why a clean-room corpus

ADR-2809050100 fixes the OS stack's display surface to Wayland and measured
the corpus as having zero Wayland repos (2026-09-05, three-index check). The
rule for filling it is extraction, not regeneration: **upstream is read, never
copied**; every datom carries its spec citation. This repo models what
`wayland.xml` *says*, written from the specification.

## What is here

| namespace | subject | spec |
|---|---|---|
| `wayland.model` | interface/request/event descriptors as EDN datoms | wayland core protocol §2 (Interfaces and requests) |
| `wayland.objects` | object table + id allocation discipline | wayland core protocol §2.4 (Object creation) |
| `wayland.wire` | message ordering rules, `wl_display` error protocol | wayland core protocol §2.5/§2.6 |

## The part worth a state machine

An object id is dead, live, or pending destruction. Requests to a dead object
are the bug class every Wayland client hits: the id stays valid-looking in the
table after the server sent `wl_registry` teardown. `wire-step` enforces:

- requests to unknown ids are protocol errors (`:invalid-object`)
- destroying an object twice is a protocol error, not a silent no-op
- ids are monotonic (server-assigned ≥ 0xff000000, client-assigned below it)
- new ids may not be reused within the same connection

## Not here

A compositor, a client, shared memory, or rendering. Those are host effects
and belong elsewhere; this repo is the contract the future display stack
validates against.

## Corpus provenance

Extracted from the public `wayland.xml` protocol definition (freedesktop,
MIT) **by description, not by copying**: interface names, request/event
shapes, and lifecycle rules are transcribed as EDN with per-interface
`:spec/source` citations. No upstream source text is vendored.
