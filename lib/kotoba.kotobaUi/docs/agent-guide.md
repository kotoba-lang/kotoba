# kotoba-ui agent guide — the paved road for building frontends

Read this **before** writing any frontend on this stack. It exists because a
real consumer (net-babiniku) ended up hand-writing **400+ lines** of ad-hoc
page CSS — layout, hero, nav, specificity fights, invented hex colors —
that this stack now provides in one call. Every "don't" below is a real
production failure, not a hypothetical.

## 1. The stack

```
css/html primitives
  └─ shitsuke            hiccup dual-render contract + HIG token layer (shitsuke.hig:
     │                   11 text styles, semantic colors light/dark, system palette,
     │                   4pt spacing, radius, hairline — all as --hig-* vars)
     └─ liquid-glass-ui  glass material skin: tokens + style + 29 components
        └─ kotoba-ui     ← YOU REQUIRE THIS. single entry: aliases + shell + theme + ->page
           ├─ appkit     desktop/dense-data defaults on top
           └─ uikit      touch/card-first defaults on top
              └─ app     your code: views + unlayered app CSS (always wins)
```

**The require rule:** apps require `kotoba-ui.core` (plus `appkit.core` for
desktop-dense UIs or `uikit.core` for touch/card UIs) — **never**
`liquid-glass.*` or `shitsuke.*` directly. Everything those layers export
for app use is re-exported by `kotoba-ui.core`.

## 2. The 8 non-negotiable rules

1. **Single entry.** Require `kotoba-ui.core` only (see the require rule
   above). If something you need isn't re-exported, add the alias to
   kotoba-ui — don't reach around it.
2. **No raw hex, no raw `px` font-size, no `font-family` in app code.**
   Colors come from the theme map and the `--hig-*` / `--liquid-glass-*`
   tokens; type comes from the 11 HIG text styles. If you're typing `#`,
   stop.
3. **Never fight specificity.** All library CSS lives inside
   `@layer kotoba.hig, kotoba.glass` — *unlayered* app CSS always wins over
   it, regardless of source order or selector weight. Compound selectors
   against `liquid-glass__*` classes are dead weight; a plain class selector
   in your own stylesheet is enough.
4. **Layout starts from shell.** `app-shell` / `hero` / `section` / `grid` /
   `stack` / `spacer` — no hand-written `.layout` / `.hero` / `.nav-wrap`
   CSS. The shell already handles sticky nav, sidebar collapse, readable
   measure, and the `min-width: 0` overflow guards. Need an id / class /
   data-attr on a scaffold (JS targeting, app-CSS hook, aria)? Every
   scaffold's opts map takes `:id` / `:class` (string or vector — merged
   with the shell class) / `:attrs` (any other attribute map) — **don't
   mirror shell CSS in app CSS** just to get a selectable element (a real
   consumer duplicated the grid rules for a `#business-grid` hook before
   this existed). `:attrs` can't clobber the component's own
   :class/:style; on `page` these land on `<body>`.
   Building an **editor** rather than a document — a canvas, timeline or
   tree that should consume the leftover space instead of extending the
   page? `(ui/app-shell {:fill true :nav … :sidebar …} canvas)`. The frame
   becomes bounded, panes stretch and scroll inside themselves, and your
   app CSS stays at zero lines. It is structure only (height / overflow /
   align-items / min-height), so a filled shell is themed identically to
   an unfilled one. It fills its **container**, so a full-page editor
   still adds `html, body { height: 100% }` — the one thing only the page
   can know.
5. **Theme = one map.** `{:accent "#RRGGBB" :accent-dark "#RRGGBB"
   :appearance :auto|:light|:dark :hig {...} :glass {...}}` passed to
   `->page` (or `theme-css`). That is the *only* place a hex color is
   legitimate in app code.
6. **Typography = the 11 HIG text styles only.** `.hig-large-title`
   `.hig-title1` `.hig-title2` `.hig-title3` `.hig-headline` `.hig-body`
   `.hig-callout` `.hig-subheadline` `.hig-footnote` `.hig-caption1`
   `.hig-caption2` — plus the element defaults (h1–h4, body, small) that
   already map onto them.
7. **Accessibility is part of "refined".** Keep the stack's ARIA attributes,
   `:focus-visible` outline, and `prefers-reduced-motion` handling intact;
   maintain ≥ 4.5:1 text contrast (the tokens already pass — that's another
   reason not to invent colors).
8. **SSR-first, dual-render, pure `.cljc` views.** The same hiccup renders
   via `->page`/`->html` (SSR/nbb) and via reagent in the browser. No
   host-specific view code.

## 3. Worked example — a complete refined page

Hero + card grid + a form section with text-field + toolbar nav, dark
appearance, custom accent. **This is the whole app view** — it replaces what
used to take 400+ lines of hand-written CSS:

```clojure
(ns my-app.page
  (:require [kotoba-ui.core :as ui]))

(def theme {:accent "#FF3CAC" :appearance :dark})

(defn feature-card [title body]
  (ui/panel [[:h3 title] [:p {:class "hig-callout"} body]]))

(defn view []
  (ui/app-shell
   {:nav (ui/nav-bar "Babiniku"
                     {:leading  [(ui/icon-button "☰" {:act :menu})]
                      :trailing [(ui/button "Sign in" {:act :sign-in})]})}
   (ui/hero {:title   "Become the character"
             :tagline "Real-time avatar puppeteering, in the browser."
             :actions [(ui/button "Start now" {:act :start})
                       (ui/button "Watch demo" {:act :demo})]})
   (ui/section {:title "Why babiniku" :wide true}
     (ui/grid
      (feature-card "Zero install" "Camera to character in one tab.")
      (feature-card "Your look"    "Accent + appearance from one theme map.")
      (feature-card "Private"      "Frames never leave the device.")))
   (ui/section {:title "Get updates"}
     (ui/stack {:gap :3}
       (ui/text-field {:placeholder "you@example.com" :aria-label "Email"})
       (ui/stack {:direction :horizontal :gap :3}
         (ui/spacer)
         (ui/button "Subscribe" {:act :subscribe}))))))

(defn render-page []
  (ui/->page {:title "Babiniku" :description "Browser avatar puppeteering."
              :theme theme}
             (view)))
```

`render-page` returns a complete `<!doctype html>` document: HIG typography
and semantic colors, dark appearance, accent-tinted hero wash, glass nav and
controls, responsive grid — zero app CSS written.

## 4. Measure it — an unmeasured page is theater

Building the page is not the last step; **scoring it is** (ADR-2607132300:
an unmeasured metric is theater — "looks refined to me" is an opinion, the
audit is a number). [kotoba-lang/design-quality](https://github.com/kotoba-lang/design-quality)
scores the ACTUAL rendered HTML + inline CSS against a deterministic
HIG/WCAG/mobile-first rubric (viewport, safe-area, tap targets,
focus-visible, reduced motion, contrast, ...) — no LLM, no browser.

After you build a page, render it and score it:

```bash
# in your app: spit the ->page output, then (from a design-quality checkout)
kbb -M:score rendered.html --min 95        # exits 1 below --min — CI-gate ready
kbb --backend sci -m design-quality.cli score dist/  # same report on Node
```

Or as a deftest, the way this repo gates itself
(`test/kotoba_ui/design_quality_gate_test.cljk` — three representative
`->page` pages, full 12-axis rubric, floors set from measured scores):

```clojure
(let [{:keys [overall findings]}
      (dq/audit {"home" (my-app.page/render-page)} {:extra-axes dq/extra-axes})]
  (is (>= overall 95) (pr-str findings)))
```

Pages built purely from this stack currently measure **~87–92**; the gap to
100 is two known upstream liquid-glass-ui findings (`:tap-targets` — no
explicit `min-height: 44px` on buttons; `:input-zoom` — a 13px
checkbox-glyph rule the heuristic reads as a field font), not anything you
control from app code. Set your app's `--min` from *your* measured score
minus a small margin, fix the findings the report names before shipping,
and raise the floor as upstream fixes land — never lower it to make a
regression pass.

## 5. Do / don't (each "don't" shipped as a real failure)

| Do | Don't |
|---|---|
| Put app CSS anywhere, unlayered — the cascade layers guarantee it wins | Inject library CSS after app CSS and try to out-specify it with compound selectors (`.liquid-glass__toolbar.app-toolbar` — ~100 dead lines in production) |
| Use `ui/text-field` etc.; report/fix upstream if a component misbehaves | Hand-roll `<input>` because a component "seems broken" — the reagent keystroke-loss bug that prompted this is **FIXED** in `text-field` |
| Use the system palette for status: `var(--hig-palette-green)` / `-orange` / `-red` / … | Invent hex status colors (`#4caf50`-style greens that match nothing) |
| Use token colors for text on washes/gradients — they already pass ≥ 4.5:1 | Write white-on-gradient text without checking contrast |
| Use shell (`grid`/`app-shell`/`stack`) — `min-width: 0` + `overflow-wrap` are built in | Forget `min-width: 0` on grid/flex children (a long URL in `<main>` blew the page width in production) |
| Reach for `app-shell {:fill true}` when the content is a canvas/editor | Re-derive the editor frame (`height:100dvh` + `overflow:hidden` + `align-items:stretch` + `min-height:0`) in app CSS — four rules every editor was rewriting until `:fill` existed |
| Dark mode via tokens: `:appearance` + `--hig-*` vars flip everything | Hand-maintain a second palette behind your own `@media (prefers-color-scheme: dark)` |

## 5.5 Backdrops

`liquid-glass` is a material designed to have something behind it. That
something is `kotoba-lang/byoubu` — a catalog of backdrops as data, reachable
from core like everything else:

```clojure
(kotoba-ui/theme-css {:backdrop :purple-desert})     ; accent + ink + chrome
(kotoba-ui/backdrop {:backdrop :purple-desert
                     :assets-base "/assets"}          ; tier-1 poster; optional
  content)
```

Naming a `:backdrop` in the theme map is enough: accent, label ink,
`data-appearance` and `<meta theme-color>` all come from that backdrop's
*measured* palette, and the plate stylesheet is appended to the bundle. Your
explicit keys still win. Do not derive a text colour for a backdrop by hand —
`(kotoba-ui/backdrop-facts :purple-desert)` already knows it, and knows it per
delivery tier.

Without `:assets-base` the plate is CSS gradients only: about a kilobyte, first
frame, no network. That is a complete page, not a degraded one.

## 6. Browser mount

The same view hiccup mounts live in the browser through shitsuke's reagent
seam — `shitsuke.reagent.core/render`, with state via
`shitsuke.re-frame.core`. `->page` is the SSR/nbb path; both consume
identical hiccup (the dual-render contract), so a view written for one is
already written for the other.

## 7. Review checklist

- [ ] App requires only `kotoba-ui.core` (+ `appkit.core`/`uikit.core`)
- [ ] No raw hex / `px` font-size / `font-family` in app code — theme + tokens only
- [ ] No compound selectors against `liquid-glass__*`/`kotoba-shell__*`; app CSS unlayered
- [ ] Layout built from shell components, not hand-written `.layout`/`.hero` CSS
- [ ] All styling routed through one theme map
- [ ] Typography only via the 11 `.hig-*` text styles / element defaults
- [ ] ARIA, `:focus-visible`, reduced-motion intact; ≥ 4.5:1 contrast
- [ ] Views are pure `.cljc` hiccup, dual-render clean (SSR `->page` + reagent)
- [ ] **Measured**: rendered output scored with design-quality (`kbb -M:score
      rendered.html --min <your floor>` or the deftest pattern in §4) and the
      report's findings addressed — an unmeasured page is theater
      (ADR-2607132300)
