(ns sdc.path-exception
  "SDC `set_false_path`/`set_multicycle_path` command model. Part of the
  kotoba-lang org-<vendor>-<spec> reverse-domain naming initiative
  (ADR-2607072500, com-junkawasaki/root).")

(defn false-path
  "Build a `set_false_path -from <a> -to <b>` entry: {:type :false-path
  :from :to :multiplier nil}. A nil `:from`/`:to` means \"any\" (matches
  every pin), mirroring SDC's behavior when -from/-to is omitted."
  [{:keys [from to]}]
  {:type :false-path :from from :to to :multiplier nil})

(defn multicycle-path
  "Build a `set_multicycle_path <n> -from <a> -to <b>` entry: {:type
  :multicycle-path :from :to :multiplier}. `:multiplier` defaults to 1
  (the setup-check multiplier SDC assumes when none is given)."
  [{:keys [from to multiplier] :or {multiplier 1}}]
  {:type :multicycle-path :from from :to to :multiplier multiplier})

(defn- endpoint-matches?
  "A nil `spec` is a wildcard (matches any pin); a collection `spec` is a
  set of alternatives; otherwise it's matched by equality."
  [spec pin]
  (or (nil? spec)
      (= spec pin)
      (and (coll? spec) (contains? (set spec) pin))))

(defn applies-to?
  "True if the path-exception `entry` covers a timing path that starts at
  `from-pin` and ends at `to-pin`."
  [entry from-pin to-pin]
  (boolean
    (and (endpoint-matches? (:from entry) from-pin)
         (endpoint-matches? (:to entry) to-pin))))
