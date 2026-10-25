(ns shitsuke.reagent.core
  "Host-independent reagent seam (mirrors shitsuke.re-frame.core).

  Views are written as plain hiccup data in .cljc (no reagent import), so they
  serve double duty: reagent renders them live in the browser (cljs) and
  shitsuke.hiccup/->html renders the identical data for SSR (clj). This ns is
  the thin mount/escape hatch that picks the host impl.

    :cljs → real reagent 1.2.0 (rdom/render, as-element)
    :clj  → shitsuke.hiccup/->html (SSR string; render writes the page)

  `kotoba-view` adds a third source for the SAME hiccup data: a view function
  written in Kotoba and compiled by amu. It returns a document, this turns it
  into hiccup, and both renderers above take it unchanged -- the guest needs
  no renderer of its own."
  (:require [shitsuke.kotoba.guest :as guest])
  #?(:cljs (:require [reagent.core :as r]
                     [reagent.dom :as rdom])
     :clj  (:require [shitsuke.hiccup :as hic])))

(defn kotoba-view
  "Render a Kotoba guest's `view` of `db` as hiccup.

  Host-independent on purpose: the result is the same hiccup value a cljs view
  function would have returned, so reagent renders it live and
  `shitsuke.hiccup/->html` renders it for SSR."
  [g db]
  (guest/document->hiccup (guest/view g db)))

#?(:clj
   (do
     (defn as-element
       "SSR: hiccup data is already the element form; identity."
       [hic]
       hic)
     (defn render
       "SSR: render hiccup to an HTML string (caller writes it to the response)."
       [hic]
       (hic/->html hic)))
   :cljs
   (do
     (def as-element r/as-element)
     (defn render
       "Browser: render hiccup into the element identified by id-or-node."
       ([hic] (rdom/render hic))
       ([hic node] (rdom/render hic node)))))
