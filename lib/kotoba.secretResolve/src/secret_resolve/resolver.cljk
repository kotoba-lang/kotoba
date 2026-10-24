(ns secret-resolve.resolver
  "Pure, portable (.cljc — JVM/ClojureScript/nbb/SCI) ordered-fallback
  resolution: given a map of {source-key (fn [ref] value-or-nil)} and a
  spec {:order [source-key ...] source-key ref ...}, try each source in
  order and return the first non-nil result. No I/O of its own — the host
  (secret-resolve.core, secret-resolve.sources) supplies the concrete
  source functions (env var lookup, `op read`, macOS Keychain, or fakes for
  testing).

  This is the generalized shape already used by this workspace's
  `manifest/repos.edn` `:b2 :credentials` (env → 1password → keychain) —
  extracted here so it has exactly one implementation instead of being
  hand-copied per consumer (it had already been copied into at least two
  places before this library existed)."
  (:require [kotoba.lang.text :as str]))

(defn resolve1
  "sources: {source-key (fn [ref] value-or-nil)}.
  spec: {:order [source-key ...] source-key ref, ...} — `ref` is whatever
  shape that source's fn expects (a plain string env-var name / op://
  path, or a map for keychain). Returns the first non-nil, non-blank
  result, or nil if every source in :order returned nothing. A source fn
  that throws is treated as \"unavailable\", not fatal — resolution falls
  through to the next source."
  [sources spec]
  (some (fn [source-key]
          (when-let [f (get sources source-key)]
            (let [ref (get spec source-key)]
              (when (some? ref)
                (try
                  (let [v (f ref)]
                    (when-not (and (string? v) (str/blank? v)) v))
                  (catch #?(:clj Exception :cljs :default) _ nil))))))
        (or (:order spec) (keys (dissoc spec :order)))))

(defn resolve-map
  "fields: {field-key spec}. Returns {field-key value} for every field that
  resolved. Throws ex-info (never partial secret material — only which
  field/order failed) for the first field that could not be resolved from
  any of its configured sources."
  [sources fields]
  (into {}
        (map (fn [[field spec]]
               (let [v (resolve1 sources spec)]
                 (when (nil? v)
                   (throw (ex-info (str "secret-resolve: could not resolve " field
                                        " (checked " (str/join "→" (map name (or (:order spec) [])))
                                        ")")
                                    {:field field :order (:order spec)})))
                 [field v])))
        fields))
