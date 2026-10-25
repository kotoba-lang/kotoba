(ns sdc.io-delay
  "SDC `set_input_delay`/`set_output_delay` command model. Part of the
  kotoba-lang org-<vendor>-<spec> reverse-domain naming initiative
  (ADR-2607072500, com-junkawasaki/root).")

(defn- io-delay
  [direction {:keys [port delay clock rise? fall? max? min?]}]
  {:direction direction
   :port port
   :delay delay
   :clock clock
   ;; SDC: an entry with neither -rise nor -fall given applies to both edges.
   :rise? (if (or rise? fall?) (boolean rise?) true)
   :fall? (if (or rise? fall?) (boolean fall?) true)
   ;; an entry with neither -max nor -min given applies to both corners.
   :max? (if (or max? min?) (boolean max?) true)
   :min? (if (or max? min?) (boolean min?) true)})

(defn input-delay
  "Build a `set_input_delay` entry map: {:direction :input :port :delay
  :clock :rise? :fall? :max? :min?}."
  [opts]
  (io-delay :input opts))

(defn output-delay
  "Build a `set_output_delay` entry map: {:direction :output :port :delay
  :clock :rise? :fall? :max? :min?}."
  [opts]
  (io-delay :output opts))

(defn- corner-key [mode]
  (case mode :max :max? :min :min?))

(defn effective-delay
  "Given a collection of io-delay entries for a single port and a mode
  (`:max` or `:min`), return the delay value that applies. Prefers an
  entry explicitly tagged for that corner; falls back to a generic entry
  (one that applies to both corners); falls back to whatever single entry
  exists, mirroring SDC's behavior where a delay specified only for one
  corner is also used for the other when it has no entry of its own."
  [entries mode]
  (let [k (corner-key mode)
        specific (first (filter #(and (k %) (not= (:max? %) (:min? %))) entries))
        generic (first (filter #(= (:max? %) (:min? %)) entries))]
    (:delay (or specific generic (first entries)))))
