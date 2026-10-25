# Shell binding — kotoba-shell iOS / Android

Cheat sheet for products that ship a shinkansen app as an iOS / Android app
through [`kotoba-lang/shell`](https://github.com/kotoba-lang/shell). It is
the mobile sibling of [`HOST-BINDING.md`](HOST-BINDING.md): that file is for
a Worker in front of the bytes, this one is for a phone that **carries** the
bytes. Same contracts, one different fact — there is no edge between the
reader and the document.

Status: **declared** (2026-10-11). No product drives this binding end to end
yet; the consumers below are designs. The measured map stays
`src/shinkansen/maturity.cljk` — a row moves there when a product requires
the contracts from a shell build, not when this file names it.

Kotoba only. No Tauri, Capacitor, React Native or Flutter host: kotoba-shell
is the native host on both platforms, and these products retire any other
mobile host rather than keeping one beside it.

## 0. The shape

    shinkansen documents ──adapter/adapt──▶ dist/ + receipts ──app scaffold──▶ .app / .apk
           (CID each)          (gate)        (carried bytes)      (kotoba-shell)

    in the app:  WKWebView / android.webkit.WebView
                 origin  kotoba-webbundle://app  |  https://appassets.androidplatform.net
                 reads   fetch → product edge (HTTPS)
                 writes  POST {edge}/v1/invoke  (shinkansen.invoke envelope)
                 effects window.kotobaShell.invoke  (policy-gated, deny-all by default)

The kotoba-shell host is the host in SPEC §1.3's sense: it owns every effect.
The bundle is inert documents plus the shinkansen runtime fragments.

## 1. Identity — the bundle is a set of CIDs, the scheme is a name

- Every document in `:web/dist-dir` goes through `shinkansen.adapter/adapt`
  (the publish gate) **before** `app scaffold`. A document the gate refuses
  does not ship; a bundle built without the gate is not a shinkansen bundle.
- The bundle carries `/.well-known/shinkansen/receipts.json`. The app's
  version shown to a reader is the entry document's CID, not only
  `:app/version` — two builds with the same version string and different bytes
  are different apps, and the receipt says so.
- `kotoba-webbundle://app/…` and `https://appassets.androidplatform.net/…` are
  **names** (SPEC §1.7). They differ per platform and resolve to the same CIDs.
  Nothing in the bundle may treat either origin as identity or authority.
- The `:document` rule is unchanged and matters more here: a document that
  fetches its own runtime from a CDN is not self-contained, and on a phone it
  is also a document that breaks offline. Fonts, CSS (`dds.css`) and the
  runtime fragments are in the bundle.
- `app scaffold` copies `dist/` wholesale and does not clean its output
  (measured in cloud-itonami-app ADR-0087). The receipt set is the allowlist:
  a file in `dist/` with no receipt and no asset entry is a build failure,
  not a passenger.

## 2. Viewport — `:xs` is the main band, not the edge case

- `shinkansen.viewport/audit` must pass with **`:host :kotoba-shell`**; it is
  the same gate `adapt` runs. The shell host adds `:safe-area-incomplete`,
  which names each side whose `env(safe-area-inset-*)` no CSS reads. The
  cloud-itonami-app iOS run found a design system that covered three sides;
  the nav sat under the Dynamic Island, clipped and untappable.
- A document with no phone layout of its own carries
  `viewport/phone-band-style` (the framework `:xs` band, max-width 480px): all
  four insets, no horizontal scroll, 16px form controls (below that iOS zooms
  on focus), 44px targets. It satisfies `:no-xs-band` and the shell check.
  Collapsing rows to one column stays the product's call.
- No hover-only affordance. Touch targets follow the design system's minimum.

## 3. Theme — unchanged

`shinkansen.theme` as in HOST-BINDING §2: `localStorage["kotoba-theme"]`,
`<html data-theme>`, `theme/head-script` in `<head>`. In a WebView `system`
follows the OS appearance through `prefers-color-scheme`; nothing native is
needed. WebView storage is per origin, so the choice survives relaunch and
does not cross platforms.

## 4. Locale — the bundle carries the variants, the boot document negotiates

On the web the edge negotiates before bytes (SPEC §2.3). A carried bundle has
no edge, so:

- Build every locale with `locale/document-variants` (one route → N
  documents, N CIDs), translated by `locale/substitute :exact?`. All variants
  ship.
- The entry document is a small boot document that negotiates with the same
  precedence as `locale/negotiate` — explicit > cookie/storage >
  `navigator.languages` (the OS locale, in the `:hint` seat) > `:default` —
  and navigates to the variant. It renders nothing itself.
- **Gap:** the browser runtime (`locale/runtime-fragment`) has `get` / `set` /
  `format` / `lang` and no `negotiate`. The first consumer adds it there,
  driven by the same `:supported` / `:default` data as the cljc function, so
  the two cannot disagree. A per-product copy in the boot document is the
  thing this rule exists to prevent.
- `locale/set` writes the preference and reloads, as on the web. It never
  re-renders in place.

## 5. Reads — plain fetch to the edge

- Reads use the WebView's `fetch` to the product's edge over HTTPS.
- **Do not grant `http/fetch` to escape CORS.** The bridge policy names
  commands, not destinations; that grant lets the page reach any host.
- A credential-less public read may answer `Access-Control-Allow-Origin: *`
  (ADR-0087 rule 5). A route that reads a session must allowlist exactly the
  two shell origins above, never `*`.
- Live data uses `shinkansen.live` frames over the same fetch. When the app is
  backgrounded the stream closes; on resume the runtime reconciles from a
  fresh snapshot rather than trusting a stale cursor.

## 6. Writes — one envelope, the key stays in the keychain

- Every write is a `shinkansen.invoke` envelope POSTed to the product's
  `/v1/invoke`. The bundle never puts `:principal` or `:grant` in `:input`;
  the host side reads them from the session, as for MCP.
- Principal: a DID whose key is held by the shell (`keychain/*`, scoped by
  `kotoba.shell.native-bridge/keychain-service` = the bundle id). Grant: a
  Biscuit from `auth.kotoba.cloud/v1/biscuit/token`. Granting `keychain/*` in
  `shell-policy.edn` is a decision recorded with the slice that needs it.
- **Passkeys are macOS-only in kotoba-shell today.** A write that requires a
  Passkey to be present is declined on iOS / Android **by the client first**,
  with its own sentence, not a 404 (the cloud-itonami-app terminal pane
  pattern). It does not become allowed because the phone lacks the ceremony.
- OAuth on a phone must not run in the embedded WebView (RFC 8252). kotoba-
  shell's `open-authorization-url` (ASWebAuthenticationSession) is macOS-only
  today; until iOS / Android equivalents land, a product either signs in
  through a device-paired token or does not offer sign-in on mobile.

## 7. Interaction — the one runtime, inlined

`shinkansen.interaction/runtime`, `theme/runtime-fragment`,
`locale/runtime-fragment` and `live/runtime-fragment` are inlined once into
the bundle (they are strings). Controls use `data-action`; handlers register
with `shinkansen.on`. No second event layer for "native" controls — a shell
command is just an effect the handler asks the host for.

## 8. Effects — deny-all until a slice names one

`shell-policy.edn` starts as `{:allow [] :deny ["*"] :audit true}`. Each
command added (`clipboard/*`, `fs/*`, `keychain/*`, `notify/show`) is one
string plus the reason. `notify/show` is a local notification only; remote
push (APNs / FCM) does not exist in kotoba-shell and is not implied.

## 9. Not on the device

- MCP (`shinkansen.mcp`) — an agent reaches the product's edge, not a phone.
- `shinkansen.serve` / `shinkansen.host` — the phone serves files through the
  shell's scheme handler; there is no shinkansen HTTP host in the app.

## 10. Verification ladder

Each rung is a different claim; a lower rung passing says nothing about a
higher one.

| rung | claim |
|---|---|
| `kbb -M:test` (view, every phase) | the view is right as data |
| `adapter/adapt` with the viewport audit | every shipped document passed the gate, receipts written |
| headless Chromium at 390×844 | the bundle mounts and reads the edge |
| `app check --target ios --target android` | the manifest and bundle scaffold, `:placeholder? false` |
| `app build --execute` | simulator `.app` / debug `.apk` exist |
| booted Simulator / Emulator | it renders real data (wait for the named state, not a timeout: first paint took 13 s on a loaded machine) |
| `app package` | **refuses** until `:apple/team-id` and a Gradle keystore are set — signing is a separate decision |

## 11. Consumers (designs, 2026-10-11)

| product | repo | app id | design | status |
|---|---|---|---|---|
| itonami | `cloud-itonami/cloud-itonami-app` | `cloud.itonami.app` | ADR-0087, ADR-0143 | built and run before this binding; `app check` ready (ios+android). Bundle failed `viewport/audit` with `:no-xs-band` (only a 768px query); fix = carry `phone-band-style` |
| itonami (operator) | `network-awai/cloud-itonami` | — (macOS client only) | ADR-0071 | Tauri mobile host retired; its approval/ledger UI becomes a pane of `cloud.itonami.app` |
| murakumo | `network-awai/cloud-murakumo` | `cloud.murakumo.app` | `docs/adr-mobile-kotoba-shell-shinkansen.md` | design; placeholder bundle, `app check` ready. Slice 1 reads `api.murakumo.cloud` public endpoints. No on-device inference |
| aozora | `network-awai/app-aozora-appview` | `app.aozora` | ADR-2610111600 | design; placeholder bundle, `app check` ready. Slice 1 reads `appview.aozora.app` XRPC (feed/profile reads 500 in production on 2026-10-11) |

**Recorded departure (aozora, §6):** AT Protocol record writes go to the
user's PDS as XRPC, not to a product `/v1/invoke`. The envelope rule still
holds for anything aozora itself authorizes; a PDS write is the PDS's
authority, and the bundle must not dress it up as a shinkansen invocation.

**Gaps every consumer hit:** iOS/Android `open-authorization-url` and
passkeys in kotoba-shell (§6); `negotiate` in the locale runtime (§4); no
remote push (§8); store signing is per-product and deferred.
