# ADR-0078 — The hosted daily shell is one DADS document the session process itself can drive

Date: 2026-08-22

## Status

Accepted and executable **for the hosted JVM profile, P1 of root
`adr-2608221625-aiueos-chromeos-cloud-desktop`**. `kbb -M:session smoke`
serves `apps/session` (jp-go-dds, one HTML document, fragments `#session`
`#desktop` `#setup` `#manage` `#devices`) and, from **that same process**, GETs a known
CID on `https://kotobase.net` and completes a `murakumo-main` infer.

Not executable, and stated here rather than at the end:

- **This is not the compositor.** ADR-0009's virtio-gpu / framebuffer shell
  is where it was. The named-partial compositor process is ADR-0079, a later
  unit; P1 remains HTTP + live kotobase/murakumo from this document.
- **This is not bare-metal.** Nothing in `os/aiueos/` changed here. The
  guest still cannot speak HTTP. Phone bind remains a hosted helper with
  QEMU `-display none`.
- **`kbb -M:cloud-live check` does not green this gate.** That CLI
  proved the authorities. P1 is that the *session* invoked them.
- **itonami (P4) and a real machine (P5) are not this change.**
- **Guest apps (P3) are ADR-0080.** This ADR remains the P1 document +
  kotobase/murakumo legs. `kbb -M:session smoke` does not execute the
  guest; `kbb -M:session guest` does.

## Context

Root ADR-2608221625 P1 is a Chrome OS-shaped daily face: phone-sized
viewport, one document, DADS, live kotobase read and murakumo infer from
the shell. The P1b proving slice had already landed a headless Mac VM bind
(`kbb -M:phone-bind smoke`) but its HTML was a temporary `--hig-*`
string, not `apps/session`, and `apps/` was absent.

A second document, or a CLI that already talked to kotobase, would have
looked green while the operator still had no daily shell.

## Decision

Generate one jp-go-dds page at `apps/session` (`page/->page`,
`tokens/skin-css` for `--hig-*`, inlined `client.js`). Phone-bind's HTTP
helper serves that document at `GET /`. The same helper answers
`POST /api/session/read-cid` and `POST /api/session/infer` by calling
`aiueos.session.live`, which uses `aiueos.provider.cloud` and the live
policy. Model identity is the alias `murakumo-main`; no other model id is
hardcoded.

`kbb -M:session smoke` is the P1 gate (HTTP only, no QEMU).
`kbb -M:phone-bind smoke` remains the P1b gate and must still exit 0
against this document (`-display none`).

## Consequences

Operators can open a phone-sized URL, bind without guest VGA, read a
CID, and run an inference without leaving the document. The Chrome OS
goal is not complete: compositor (ADR-0079 named partial), guest apps
(ADR-0080), itonami, and a physical chassis are later units.
