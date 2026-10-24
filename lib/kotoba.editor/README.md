# editor

`editor` is a portable **structural EDN editor** — the data model behind "no raw
text, no parentheses" editing UIs. It contains no DOM, no re-frame, no host effects;
a consuming app supplies the UI (sliders, color pickers, a click-to-select list) and
the persistence (however the edited EDN gets saved).

```text
editor = editable-paths (walk a map, find editable leaves) + set-value (assoc-in) + color <-> hex
```

## Why

Any app that lets a user edit a document authored as **plain EDN data** (a game
scene, a config, a CAD parameter set) eventually needs a "simple mode": don't make
the user edit text, walk the document and surface every number/colour as a control.
That walk-and-surface logic doesn't depend on what the document is *for* — it's the
same problem whether the document is a `network-isekai` game scene, a `kotoba-code`
project config, or anything else authored as EDN. `editor` is that logic, extracted
once so every consumer gets it as a library, not a reimplementation.

## API (`editor.core`)

```clojure
(require '[editor.core :as editor])

(def scene {:world {:speed 600.0 :gravity 26.0}
            :skin  {:torso [0.96 0.82 0.72]}})

(editor/editable-paths scene)
;; => [{:path [:world :speed]   :value 600.0 :kind :number :label "world › speed"}
;;     {:path [:world :gravity] :value 26.0  :kind :number :label "world › gravity"}
;;     {:path [:skin :torso]    :value [0.96 0.82 0.72] :kind :color :label "skin › torso"}]

(editor/set-value scene [:world :speed] 700.0)
;; => {:world {:speed 700.0 :gravity 26.0} :skin {...}}

(editor/color->hex [0.96 0.82 0.72])  ;=> "#f5d1b8"
(editor/hex->color "#f5d1b8")         ;=> [0.9607... 0.8196... 0.7215...]

(editor/slider-bounds 600.0)  ;=> [300.0 1200.0 6.0]   ; [min max step], always usable
```

`editable-paths` matches, in order: a `[r g b]` vector of numbers in `[0,1]` (a
`:color`), then a bare `number?` (a `:number`). It walks maps up to a bounded depth
(3) so it terminates on any real-world document without a schema. Everything else
(strings, keywords, booleans, deeper/irregular structures) is left alone — this is
a numbers-and-colours editor, not a general EDN editor; a consuming app is free to
add its own leaf-kind matchers on top.

## Design

Pure `.cljc` — zero host effects, zero third-party deps, runs on JVM Clojure,
ClojureScript, SCI, and Clojure-on-WASM alike. A consuming UI owns:
- rendering (`editable-paths` → your slider/color-picker components)
- selection state (which path is being edited)
- persistence (what `set-value`'s result gets written to — a re-frame app-db, a
  file, a kotoba fork pin, whatever the host app already uses)

`editor` never touches any of that — same separation `kotoba-lang/kuro` uses for
terminal sessions (portable data model; host provides the effects).

## Tests

```bash
kbb -M:test
```
