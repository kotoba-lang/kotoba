# x402-directory

**Vendor-neutral HTML directory-page renderer for any [x402](https://blog.cloudflare.com/monetization-gateway/)-compliant facilitator's `GET /catalog` response, in pure Clojure/ClojureScript (`.cljc`).**

x402 facilitators already serve a JSON `/catalog` so autonomous agents can
discover what they can pay for (seller, price, gateway URL). This library
renders that same data as a human-readable HTML page (and, since
2026-07-10, an [llms.txt](https://llmstxt.org) plain-markdown summary) —
so a facilitator operator doesn't have to hand-write either. Extracted
2026-07-10 from [`gftdcojp/nexus-x402`](https://x402.nexus)'s production
directory page (that facilitator's own live demo) into a reusable,
branding-agnostic component, then (same day) adopted back into
nexus-x402 as its actual dependency (vendored, same convention as
`kotoba-lang/pay`/`treasury`) — `nexus.directory` there is now a thin
branding layer on top of this package's `page`/`llms-txt`, not a second
copy of the renderer.

```clojure
(require '[x402.directory :as directory])

(directory/page
 {:origin "https://your-facilitator.example"
  :items [{:seller "murakumo" :method "POST" :path-prefix "/v1/messages"
           :price {:usd "0.01" :asset "USDC" :network "base"}
           :description "LLM inference, per request"}]
  :branding {:title "your-facilitator"
             :tagline "Self-hosted x402 payment facilitator."
             :pitch-html "<strong>No waitlist. Live today.</strong>"
             ;; optional: jump-nav, extra <section>s (e.g. a quickstart),
             ;; extra footer links -- all omitted unless supplied
             :nav-links [{:href "#resources" :label "Resources"}]
             :extra-sections-html ["<section id=\"docs\"><h2>Docs</h2><p>...</p></section>"]
             :extra-links [{:href "/catalog" :label "Catalog (JSON)"}
                           {:href "/health" :label "Health"}]}})
;; => "<!doctype html>..." — a complete, self-contained HTML page string

(directory/llms-txt
 {:origin "https://your-facilitator.example"
  :items [...]  ; same shape as above
  :branding {:title "your-facilitator"
             :llms-summary "Self-hosted x402 payment facilitator."
             :llms-links [{:href "/catalog" :label "Catalog"
                           :note "JSON menu of every gated resource."}]}})
;; => "# your-facilitator\n\n> Self-hosted x402...\n\n## API\n..." — plain markdown
```

## What's in scope / out of scope

- **In scope**: rendering `{:seller :method :path-prefix :price :description}`
  items (the shape any x402 `/catalog` already returns) as an HTML page
  and an [llms.txt](https://llmstxt.org) markdown summary, with
  caller-supplied branding (title/tagline/pitch/nav/extra sections/links/
  CSS) and an honest empty state in both formats.
- **Out of scope**: fetching `/catalog` itself (the host does that — a
  Cloudflare Worker, a static-site build step, whatever), payment
  verification, and the facilitator/gateway logic itself (see
  [`kotoba-lang/pay`](https://github.com/kotoba-lang/pay) and
  [`kotoba-lang/treasury`](https://github.com/kotoba-lang/treasury) for
  that layer).

## Default CSS — generated from the kotoba-lang HIG design system

The default page CSS sits on the kotoba-lang HIG design system: its palette
block (`--bg/--fg/--muted/--border/--surface/--accent/...` custom
properties, light + dark via `prefers-color-scheme`) is **generated from
[`kotoba-lang/shitsuke`](https://github.com/kotoba-lang/shitsuke)'s
`shitsuke.hig` semantic tokens** (Apple-HIG semantic colors, SF Pro/SF Mono
font stacks, 0.5px hairline, radius scale), and the layout CSS uses the HIG
text-style scale (17px/22px body, 13px/18px footnote, 34px/41px
large-title, ...) and 4pt-grid spacing, with zero raw hex outside the
generated palette block (test-enforced).

The generated result is **checked in** (`default-palette-css` in
`src/x402/directory.cljk`, between the `;; gen:begin`/`;; gen:end`
markers), so the library itself keeps **zero runtime deps** — shitsuke is a
dev-time dependency of the generator only, pinned by `:git/sha` in
`deps.edn`'s `:gen` alias (currently `35099a7`). Regenerate after a
shitsuke token change with:

```bash
kbb -M:gen           # rewrites the palette block + prints a WCAG report
kbb -M:gen --check   # CI-style verification that the palette is current
```

Two derivations go beyond a straight token copy (both WCAG-AA-verified by
the generator, which fails if they regress): `--muted` raises HIG
secondary-label's alpha 0.6 → 0.73 (Apple's own value is ~3.4:1 on white,
below AA for small text), and `--accent` keeps the x402 **brand cyan**
rather than HIG's systemBlue tint — light `#0E7490` (the historical
`#0891b2` darkened same-hue to pass AA on white), dark `#22C3E6`
(unchanged). Hosts can still replace the whole stylesheet via
`:branding :css`.

The page also covers the mobile/page axes out of the box (2026-07-13,
scored 100/100 by the deterministic
[`kotoba-lang/design-quality`](https://github.com/kotoba-lang/design-quality)
HIG/WCAG audit): `viewport-fit=cover`, a media-gated
`<meta name="theme-color">` pair derived from the generated palette's own
`--bg` values (overridable/omittable via `:branding :theme-color`),
`env(safe-area-inset-*)` body padding, an `overflow-x` guard on html/body,
`:focus-visible` rings, and a `<=480px` breakpoint that stacks the
resources table into labeled cards (`td[data-label]`) — a host replacing
`:css` takes those axes over too.

## Never fabricates

Renders exactly what `:items` says — no placeholder stats, testimonials, or
customer counts. An empty registry renders an honest empty state, not a
lie. A directory page's only value is that it's true; this library treats
that as a hard constraint, not a style preference (see the test suite's
`page-never-fabricates-when-registry-is-empty`).

## Live demo

[`x402.nexus`](https://x402.nexus) — [gftdcojp/nexus-x402](https://github.com/gftdcojp/nexus-x402)'s
self-hosted facilitator — runs this package (vendored, see above) in
production (content-negotiated: browsers get HTML, API/agent clients
hitting the same URL without an `Accept: text/html` header get the
unchanged JSON `/catalog` pointer; `GET /llms.txt` always returns
markdown).

## Test

```bash
kbb -M:test          # 23 tests
kbb -M:lint           # clj-kondo (src + test + scripts)
```

Apache-2.0.
