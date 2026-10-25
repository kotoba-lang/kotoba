(ns kotoba.document.style
  "The resolved-style map SHAPE `kotoba-lang/cssom`'s cascade already
   produces per node: a flat map of CSS-property keywords to already-
   resolved values (no more `inherit`/`initial`/cascade-order left to
   resolve -- that work is `cssom.core`'s job, not this contract's).

   Deliberately scoped to the properties this stack's REFERENCE
   implementation (`cssom`) actually supports today, not full CSS -- see
   this repo's own README, \"Non-goals\". `known-properties` below is the
   authoritative allow-list; a future non-Clojure renderer conforms to this
   set, not to CSS's full property grammar. Growing this set (as `cssom`
   itself grows -- text-decoration, text-align, list markers, etc. were all
   added incrementally in earlier work) is an ordinary, expected edit here,
   not a breaking contract change, as long as an ABSENT key keeps meaning
   'unset / use the implementation's own default' rather than a required
   field."
  )

(def known-properties
  "Every resolved-style key `cssom`'s cascade may produce today. Not
   exhaustive of CSS -- exhaustive of what THIS reference implementation
   resolves."
  #{;; box model
    :width :height :margin :padding :border-width :border-color
    :background :display :position :overflow :scroll-left :scroll-top
    ;; flex/grid
    :flex-direction :flex-grow :flex-shrink :justify-content :align-items
    :gap :grid-template-columns :grid-template-rows :grid-template-areas
    :grid-column :grid-row
    ;; text
    :color :font-size :font-weight :font-style :text-decoration
    :text-align :text-transform :white-space :line-height
    ;; misc
    :opacity :list-style})

(defn resolved-style?
  "A resolved style is just a map -- every key present must be one this
   contract knows about, but no key is REQUIRED (an element with zero
   author/inherited styling is a valid, empty resolved style)."
  [x]
  (and (map? x)
       (every? known-properties (keys x))))
