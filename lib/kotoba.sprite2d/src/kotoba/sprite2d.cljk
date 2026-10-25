(ns kotoba.sprite2d
  "Facade re-exporting `kami.sprite2d` (Canvas2D painter SSoT, ADR-2607102200 addendum 7).
   Layout SSoT remains `kami.sprite2d.layout` in this package."
  (:require [kami.sprite2d :as impl]))

#?(:cljs
   (do
     (def prim!          impl/prim!)
     (def draw-sprite!   impl/draw-sprite!)
     (def draw-2d!       impl/draw-2d!)
     (def draw-portrait! impl/draw-portrait!)
     ;; :image support — consumers reach the cache through this facade, not kami.* directly.
     (def preload-images! impl/preload-images!)
     (def image-states    impl/image-states)))
