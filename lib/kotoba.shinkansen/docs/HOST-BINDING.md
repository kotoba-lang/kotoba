# Host binding — kotoba.cloud Workers

Cheat sheet for product hosts (console / docs / blog / auth Workers) that
should **require shinkansen contracts** instead of re-deriving them. UI
markers live in jp-go-dds / cloud-kotoba-dds; this repo owns audit, theme,
locale, and invoke. The measured map is `src/shinkansen/maturity.cljk`
(SPEC §2.5 / §6). Do not invent a second copy.

## 1. Locale — require `shinkansen.locale`

Negotiation is a host/edge seam, not a path fork (SPEC §2.3). Call
`negotiate` with the three seams a product had re-derived in its own
`locale.cljk`:

- `:explicit` — `?lang=` or a legacy locale path the reader just used
- cookie — `defaults` cookie name `shinkansen_locale`
- `:hint` — environment suggestion (e.g. Cloudflare `cf.country` → locale)

Precedence: `:explicit` > cookie > Accept-Language > `:hint` > `:default`.
Unknown values are fail-closed against `:supported`. Serialize Set-Cookie
only through `set-cookie-header` / `:cookie-attrs`. A preference cookie may
set `:domain` to the registrable parent so docs. / blog. / console. share
one choice; **credentials must not** (SPEC §1.8).

## 2. Theme / locale browser contracts — do not fork

Coordinate with jp-go-dds / cloud-kotoba-dds markers. One contract:

| | storage / cookie | attribute | paint-before |
|---|---|---|---|
| theme (`shinkansen.theme`) | `localStorage["kotoba-theme"]` = `light` or `dark`; **absent = system** | `<html data-theme="light">` or `"dark"`; **remove** for system | `theme/head-script` in `<head>` |
| locale (`shinkansen.locale`) | cookie `shinkansen_locale` | `<html lang>` is the negotiated document | host/edge negotiates before bytes; the runtime writes the cookie then navigates/reloads |

CSS is `jp-go-dds.dark/dark-css`. Actions `theme/set` and `locale/set` are
framework-actions. Do not invent `data-appearance` or a second storage key.

## 3. Audit markers at publish

Run `shinkansen.audit` (fitness axes) on **emitted HTML**. Every miss is
named. **Unmeasured ≠ pass** — an axis you did not supply context for
(`:assets`, `:csp`, `:actions`, stylesheets, …) is `:unmeasured` and is
excluded from the mean; it is never a silent green.

`data-behavior` markers are promises kept with the **jp-go-dds.behavior**
runtime (dialog / menu / tabs / disclosure / radiogroup / toast / combobox
/ popover / tooltip / select / slider / table). Markup without that
runtime, or a runtime that cannot find its markup, is a dead control.

## 4. Invoke — one envelope; POST is transport

`shinkansen.invoke` is the one shape every transport carries (SPEC §1.6 /
§2.5):

```
{:artifact cid :principal did :grant … :input {:kind :query|:action|:event …}}
```

`POST …/invoke` (reference host `/invoke`, kotoba.cloud `/v1/invoke`) is
transport only — the URL is not the semantic. Inject `authorize-fn`;
**no authorizer is a refusal** (`:no-authorizer`), not a pass. Principal
and grant come from the session / headers (`principal-fn` / `grant-fn`),
**never from tool arguments** (`invoke/from-mcp` ignores those keys).

## 5. Receipts / ETag — identity headers from the receipt

A Worker that serves bytes via asset binding cannot hand the document to
`host/handle`. Use the seams SPEC §6 product binding already landed:

- `host/document-headers` — **ETag = CID**, `Link: <ipfs://{cid}>; rel="canonical"`, `Cache-Control: no-cache` (a name is mutable)
- `host/not-modified?` — **304 from the receipt alone**, before touching bytes
- `routes/paths->tree` — flat emit → tree; the path is a name, not identity
- adapter receipts at `/.well-known/shinkansen/receipts.json`

See `src/shinkansen/host.cljk` and `src/shinkansen/adapter.cljk`.
