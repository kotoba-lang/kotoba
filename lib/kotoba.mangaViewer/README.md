# manga-viewer

Portable `.cljc` manga viewer — normalized work model, RTL pagination logic,
CSS string, and pure-hiccup views (works index grid + reader). Zero runtime
dependencies; the consumer owns all state and event wiring. ADR-2607070500.

The reader UX mirrors the `manga.gftd.ai` public reader: 作品一覧 card grid →
見開き (RTL spreads: cover alone, then pairs with the higher page number on the
left) / 単頁 / 縦読 modes, tap zones (left = next, RTL), page counter.

## Namespaces

| ns | role |
|---|---|
| `manga-viewer.model` | work model `{:manga/id :manga/title … :manga/pages [{:page/number :page/images […]}]}` + adapters `from-mangaka-data` (manga.gftd.ai reader `DATA` shape) and `from-gh-manga-tx` (aozora `:gh.manga/*` projection tx) + `validate` |
| `manga-viewer.pagination` | `units` (spread/single/scroll), `supported-modes` (spread only when every page is a single composed image), `clamp-unit`, `unit-for-page`, `unit-label` |
| `manga-viewer.style` | `(css)` → plain CSS string (`manga-viewer__*` classes, themed via `--manga-viewer-*` custom properties; dark reader defaults) |
| `manga-viewer.render` | `works-grid`, `reader` — plain hiccup (no reagent-specific forms), state `{:mode :unit}` and handlers `{:on-prev :on-next :on-mode :back-href :bar-extra}` injected by the consumer |

## Consumer contract

The library renders; you own the state machine:

```clojure
(require '[manga-viewer.render :as mv]
         '[manga-viewer.pagination :as mp]
         '[manga-viewer.style :as mvs])

;; reagent example
(defonce state (r/atom {:mode :single :unit 0}))

(defn reader-page [work]
  (let [{:keys [mode unit]} @state
        units (mp/units (count (:manga/pages work)) mode)]
    [:div
     [:style (mvs/css)]
     (mv/reader work @state
                {:on-next #(swap! state update :unit (fn [u] (mp/clamp-unit units (inc u))))
                 :on-prev #(swap! state update :unit (fn [u] (mp/clamp-unit units (dec u))))
                 :on-mode (fn [m]  ; keep the reading position across mode switches
                            (let [page (first (get units (:unit @state)))]
                              (reset! state {:mode m
                                             :unit (mp/unit-for-page
                                                    (mp/units (count (:manga/pages work)) m)
                                                    page)})))
                 :back-href "/manga"})]))
```

An SSR consumer renders the same hiccup to HTML and adds its own keyboard /
fullscreen enhancer. Known consumers: `gftdcojp/app-aozora` (`/manga` index +
`/manga/ghosthacker` reader, reagent SPA).

## Dev

```bash
kbb -M:test
```

Pure `.cljc`, no interop — runs on cljs and JVM (per the repo-wide runtime
priority rule there is no kototama execution path yet; no `#?(:kototama …)`
branches are written).
