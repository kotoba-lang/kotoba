(ns kuro.browser-base
  "Shared module base for the fs-browser build's two independent page
  bundles (fs-cap.js, fs-demo.js).

  shadow-cljs :simple needs a common dependency a module can hang off when
  more than one top-level entry exists. Both page demos require the pure
  kuro.fs model, so hosting it here gives the base a real payload and lets
  the two E2E bundles share it instead of each re-shipping goog/base alone."
  (:require [kuro.fs :as fs]))