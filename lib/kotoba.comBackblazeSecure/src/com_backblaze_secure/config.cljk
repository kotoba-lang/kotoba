(ns com-backblaze-secure.config
  "Bucket allowlist + capability gate. Pure data/validation, no I/O — the
  host (com-backblaze-secure.server) reads config/*.edn and hands this ns
  the parsed EDN map. A bucket that is not present in `(:buckets config)`,
  or a capability not present in that bucket's `:capabilities` set, must
  never reach com-backblaze-secure.b2-cli — every call site checks
  `require-capability!` BEFORE spawning a `b2` subprocess.")

(def capabilities #{:list :read :write :delete})

(defn bucket-config [config bucket]
  (get-in config [:buckets bucket]))

(defn capability-granted?
  [config bucket capability]
  (contains? (:capabilities (bucket-config config bucket) #{}) capability))

(defn allowed-buckets
  "Set of bucket names that grant `capability` (or all configured buckets
  if capability is nil)."
  ([config] (allowed-buckets config nil))
  ([config capability]
   (into (sorted-set)
         (keep (fn [[bucket cfg]]
                 (when (or (nil? capability)
                           (contains? (:capabilities cfg) capability))
                   bucket)))
         (:buckets config))))

(defn require-capability!
  "Returns nil if `bucket`/`capability` is allowlisted in `config`, or a
  human-readable error string otherwise. Never throws — callers check the
  return value before doing anything with side effects."
  [config bucket capability]
  (cond
    (not (contains? capabilities capability))
    (str "unknown capability: " (pr-str capability))

    (not (bucket-config config bucket))
    (str "bucket not allowlisted: " (pr-str bucket))

    (not (capability-granted? config bucket capability))
    (str "capability " capability " not granted for bucket " bucket)

    :else nil))
