# ADR-0283 — Default Itonami apps, the Itonami Apps installer and the update manager

Date: 2026-11-03

## Status

Proposed (owner request 2026-11-03, JUN-805). Install records and a record check are implemented. The native
desktop window, launcher and cores are **not** implemented; the hosted session UI is the only HTML/CSS surface.

## Context

After boot, the native desktop lists four apps (Murakumo, Itonami, Yataverse, Aozora). The request is to add default
apps (browser, yotei, shakai, saifu, bunsho, hyokeisan, zuhyo), system apps (tokei, wifi, bluetooth, settei), an
installer ("Itonami Apps") and an update manager.

Measured in the source (2026-11-03):

- The native desktop is not HTML/CSS. `native/desktop.kotoba` rasterizes the draw list of `kotoba/browser-frame2.kotoba`
  into the GOP framebuffer. That object is a behavior mirror of Browser/CSSOM, not its output (README: the shared
  Browser graph does not link under the Amu selfhost image yet). The HTML/CSS UI is only
  `resources/aiueos/session/index.html`, the hosted session.
- browser-frame2's ABI is fixed: window ids 1..4, title up to 32 and body up to 64 code points, an 8192-byte surface,
  and the renderer refuses a frame past 259 ops (ADR-0282). `desktop.kotoba` hit-tests launcher and dock for ids 1..4
  only, and `app-catalog` has four static cards.
- `native/update.kotoba` and `native/esp.kotoba` already implement a signed-image pull and an ESP swap with a rollback
  copy (AWAI-122), driven by remote commands, not by a user-facing app.

## Decision

1. **Install records.** Every app has `distributions/awai/dapps/<id>.json` (`itonami.dapp.v1`), dock ids 1..17:
   1-4 existing; 5 browser, 6 yotei, 7 shakai, 8 saifu, 9 bunsho, 10 hyokeisan, 11 zuhyo (default); 12 tokei, 13 wifi,
   14 bluetooth, 15 settei, 17 updates (system); 16 itonami-apps (store). New records carry
   `"localCoreState": "planned"` and `"native": {"window": "not-implemented"}` until a core and window exist.
   `scripts/check-dapp-records.py` checks them (`dns: never`, each-operation consent, unique contiguous docks).
2. **Frame ABI v3 (follow-up, native).** Window ids and the dock become data, not four literals: a launcher page
   (grid, paged by 8) and a dock of pinned apps, with the app count read from the installed catalog. The body text
   limit and the 259-op budget stay, so each window still draws under the budget; only one full window is open per
   page of launcher. This needs a native Amu rebuild, the QEMU gates and a new KIR contract, and replaces the
   fixed-size `app-catalog` with a signed one (`app-catalog.sig`).
3. **Itonami Apps installs by digest.** The app lists the signed catalog (offline copy first). Install of an entry
   fetches its artifact only after a fresh each-operation approval naming service, endpoint, operation and data
   (`fetch-catalog`, `download-app`), admits it by CID (`aiueos.cid-v1-admit`) and signature, then records it in the
   draft store. No silent fallback, no app-origin proxy, no DNS resolution by the dapp (ADR-0282).
4. **Updates is a manager, not a daemon.** `distributions/awai/update-policy.json` defines modes `manual`, `notify`
   (default), `auto-stage`, `auto-install` and channels `stable`/`beta`. "Auto" means a schedule that raises a prompt:
   it never contacts a service by itself, and check, download and install each wait for their own approval. Install
   uses the AWAI-122 signed-image path with its rollback copy. App updates apply to catalog entries whose digest and
   signature verify, and the old version stays until the new one is admitted.
5. **Saifu is read and verify only.** It does not sign transactions, broadcast or settle (etzhayyim-exclusive).

## Consequences

- The records are the contract the native work implements against; they grant nothing.
- Update signatures are Ed25519 only, below the post-quantum floor; an ML-DSA-65 verifier is required before
  `auto-install` can be called qualified.
- Hosted session and native desktop are separate surfaces; hosted parity with the native frame stays unqualified.
- Native wi-fi has no driver in the tree (only RTL8168 wired); the wifi app is status-only until one exists.

## Amendment 2026-11-04 — UI is authored once, in kotoba html/css (owner intent, JUN-805)

Itonami OS follows the browser's render, so an Itonami dapp's UI is a `kotoba-lang/html` hiccup document with a
`kotoba-lang/css` sheet (`distributions/awai/dapps/ui/ui.cljk`), not hand-written per-surface code. The hosted session
emits that document as HTML (JUN-809, done: `generated/` spliced by `scripts/dapp-ui.py`), and the native desktop is to
render the same document through the shared browser render (`browser`/`cssom`/`dom-gpu`; JUN-810), which replaces the
`browser-frame2` mirror for dapp windows. Dynamic values and operations are declarative (`data-bind`, `data-action`);
the host supplies them. Native rendering is blocked on JUN-93/JUN-134..137/JUN-353 (cssom typed calc AST, regex in
layout, f64/document ABI, Browser graph link); until then the frame ABI v3 (JUN-811) is an interim, not the target.
The hand-written JS DOM builder from PR #1187 is removed.
