;; config.cljc — shared normalization for configured endpoint URLs.
;;
;; One function, deliberately: it turns a raw configuration value into a usable base URL, or
;; into nil. It never substitutes a host of its own. Deciding what an absent endpoint means
;; belongs to the module that would contact it — llm.cljc and mst_projector.cljc each raise
;; their own error type so callers can keep classifying failures by module.
;;
;; The normalization exists because both call sites build `(str (base-url) "/path")`. A value
;; of "  " used to produce the non-URL "  /xrpc/…", and one with a trailing slash produced a
;; doubled "//" — neither names a host, so both are treated as absent.
(ns etzhayyim-sdk.config
  (:require [kotoba.lang.text :as str]))

(defn normalize-base-url
  "Trim *raw* and strip trailing slashes, returning the resulting base URL.

  Returns nil when *raw* names no host — nil, empty, whitespace-only, or nothing but
  slashes. Pure: callers pass the environment value in, e.g.
  `(normalize-base-url (System/getenv \"ETZHAYYIM_LLM_URL\"))`."
  [raw]
  (some-> raw
          str/trim
          not-empty
          (str/replace #"/+$" "")
          not-empty))
