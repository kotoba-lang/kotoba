# ADR-0080 — One grant-limited Kotoba guest is visible in the hosted daily shell

Date: 2026-08-22

## Status

Accepted and executable **for the hosted JVM profile, P3 of root
`adr-2608221625-aiueos-chromeos-cloud-desktop`**. `kbb -M:session guest`
serves the same `apps/session` DADS SPA, runs `:app/notes` through
`grant` + `aiueos.execute` (Chicory Wasm, WAT in `examples/apps/notes.wat`),
lists it on `#session` / `#desktop`, and a deny grant answers **403** with
`:unresolved-capability` rather than a generic 500.

Not executable, and stated here rather than at the end:

- **This is not a second JS runtime.** The guest is the existing notes
  fixture plus log_write Wasm. `examples/apps/notes.cljk` is not the product
  face.
- **POSIX `:fs/open` is not the store.** On-disk notes.edn still declares
  that import; the hosted allow path drops it. Local-disk-only write is P3
  red. Kotobase round-trip is the session process. A write without a
  credential is `:write-unauthorized` (or unmeasured), never a successful
  store.
- **This is not P2 / P4 / P5.** Bare-metal net, itonami, and a real machine
  remain later units. Full WM / IME / virtio-gpu 2D create/flush remain
  later than the named-partial compositor (ADR-0079).
- **`kbb -M:session smoke` stays P1.** Guest execute is `guest`, not
  folded into smoke. The P1 document must still *list* the guest chrome.

## Context

ADR-0078 landed the DADS SPA and live kotobase/murakumo from the session
process. ADR-0079 landed a named-partial compositor. Root P3 is a
capability guest in that same shell: grant is why it runs, and it is
visible to the operator, not only a CLI fixture or a WAT file on disk.

`grant` already decides. `examples/apps/notes.edn` already names
`:app/notes`. The missing product was the session HTTP API and the same
document rendering the guest identity.

## Decision

1. `aiueos.session.guest` admits `:app/notes` through `aiueos.execute`.
   Allow overlays kernel `:log/write` only. Deny uses the on-disk import
   set so `:fs/open` is `:unresolved-capability`.
2. Same helper as P1 (`aiueos.phone-bind`) answers
   `GET /api/session/guests` and `POST /api/session/guest` with
   `{"grant":"allow"}` / `{"grant":"deny"}`. Running guests are `:guests`;
   a deny is `:refused` with the grant kind. HTTP 403, not 500.
3. The one DADS document grows a notes card on `#session` (run/deny
   buttons, `#guest-out`) and a named status on `#desktop`
   (`#guest-desktop-out`). Not a second HTML document. Not an anonymous
   compositor iframe.
4. Gate: `kbb -M:session guest`. P1 / P1b / compositor smokes stay
   green, including headless bind (`-display none`).

## Consequences

Operators can see `:app/notes` in the daily shell when grant admits it,
and see a named refusal when it does not. The Chrome OS-shaped desktop
goal is not complete: P2 bare-metal net, P4 itonami, P5 a real machine,
and full WM/IME/virtio-gpu 2D remain.
