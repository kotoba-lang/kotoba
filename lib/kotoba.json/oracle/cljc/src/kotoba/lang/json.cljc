(ns kotoba.lang.json
  "Compatibility namespace for the foundational JSON API.

  Oracle file (JUN-1024): a .cljc twin of the .cljk facade for hosts that
  cannot read .cljk (stock nbb, Basilisp). Each name is the `kotoba.json.twin`
  engine function itself on every runner (the host aliases `json.core`, which
  Basilisp cannot load: top-level `json` resolves to Python's stdlib). The
  {:kotoba/export [...]} ns metadata of the .cljk is intentionally absent:
  Basilisp rejects unknown ns metadata keys at load. Never a build, gate,
  runtime or fallback input -- one-off measurement oracle only (ADR 0026 D18)."
  (:require [kotoba.json.twin :as json]))

(def encode "See kotoba.json.twin/encode." json/encode)
(def decode "See kotoba.json.twin/decode." json/decode)
(def json "See kotoba.json.twin/json." json/json)
