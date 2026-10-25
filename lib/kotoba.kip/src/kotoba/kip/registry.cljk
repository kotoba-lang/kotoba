(ns kotoba.kip.registry
  "Integrity of the KIP registry as a whole: numbering, statuses, and the
  references KIPs make to each other.

  Per-document rules live in `kotoba.kip.core`. What is here is everything that
  needs to see more than one document at a time, which is why it cannot be a
  document-level check: a duplicate number is not visible from inside either of
  the two files that share it.

  No IO. `check` takes `[{:path ... :tx-data ...}]` — the caller reads the
  files, which is what lets the same function run under nbb in the gate, under
  the JVM in the test suite, and against a hand-built fixture."
  (:require [kotoba.lang.text :as str]
            [kotoba.kip.core :as core]))

(defn number-from-path
  "kips/kip-0007.edn -> 7. nil when the name does not fit the pattern."
  [path]
  (when-let [m (re-find #"kip-(\d{4})\.edn$" (str path))]
    #?(:clj (Long/parseLong (second m))
       :cljs (js/parseInt (second m) 10))))

(defn- finding [severity kind path m]
  (merge {:severity severity :kind kind :path path} m))

(defn- check-document
  "Rules that need one document. Returns a seq of findings."
  [process {:keys [path kip]}]
  (let [n (number-from-path path)
        status (:kip/status kip)
        track (:kip/track kip)]
    (concat
     (when (nil? n)
       [(finding :error :kip/unnumbered-filename path
                 {:note "must match kips/kip-NNNN.edn"})])
     (when (and n (not= n (:kip/number kip)))
       [(finding :error :kip/filename-number-mismatch path
                 {:filename n :in-document (:kip/number kip)})])
     (when-not (contains? core/state->code status)
       [(finding :error :kip/unknown-status path {:status status})])
     (when-not (contains? core/track->code track)
       [(finding :error :kip/unknown-track path {:track track})])
     ;; A document must satisfy the requirements of the state it *claims*.
     ;; Otherwise a KIP can be written straight into :final with no
     ;; specification, and the transition rules never get a chance to object
     ;; because no transition was ever requested.
     (when (contains? core/state->code status)
       (let [missing (core/missing-fields process kip status)]
         (when (seq missing)
           [(finding :error :kip/missing-required-fields path
                     {:status status :missing (vec missing)})])))
     (when (and (= status :superseded) (str/blank? (:kip/superseded-by kip)))
       [(finding :error :kip/superseded-without-target path {})])
     (when (and (= status :last-call)
                (nil? (core/parse-date (:kip/last-call-started kip))))
       [(finding :error :kip/last-call-start-unparseable path
                 {:value (:kip/last-call-started kip)})])
     ;; Standards track reaching :final without a recorded quorum is the one
     ;; failure that would make the whole process decorative.
     (when (and (= status :final) (= track :standards))
       (let [{:keys [signers]} (core/quorum-signers kip)
             threshold (get-in process [:guards :quorum-met :threshold] 2)]
         (when (< (count signers) threshold)
           [(finding :error :kip/final-below-quorum path
                     {:signers (count signers) :threshold threshold})]))))))

(defn- check-cross-document
  "Rules that need the whole set."
  [entries]
  (let [by-number (group-by #(get-in % [:kip :kip/number]) entries)
        ids (into #{} (keep #(get-in % [:kip :kip/id])) entries)
        numbers (sort (keep #(get-in % [:kip :kip/number]) entries))]
    (concat
     (for [[n dupes] by-number
           :when (and n (< 1 (count dupes)))]
       (finding :error :kip/duplicate-number (mapv :path dupes) {:number n}))
     ;; Dangling references. A KIP may name a successor or a dependency that
     ;; does not exist yet only while it is still a draft; once it is anything
     ;; else, a reference nobody can follow is a broken citation.
     (for [{:keys [path kip]} entries
           :let [target (:kip/superseded-by kip)]
           :when (and (not (str/blank? target))
                      (not (contains? ids target)))]
       (finding :error :kip/dangling-superseded-by path {:target target}))
     (for [{:keys [path kip]} entries
           req (:kip/requires kip)
           :when (and (string? req)
                      (not (contains? ids req))
                      (not= :draft (:kip/status kip)))]
       (finding :error :kip/dangling-requires path {:target req}))
     ;; A gap means a numbered file left the tree. Numbers are never reused, so
     ;; the number itself is still spent — but the record of what it was is
     ;; gone, and that is worth saying out loud rather than silently tolerating.
     (when (seq numbers)
       (for [n (range (first numbers) (last numbers))
             :when (not (contains? (set numbers) n))]
         (finding :warn :kip/number-gap nil {:number n}))))))

(defn check
  "Whole-registry check.

  `entries` is `[{:path \"kips/kip-0000.edn\" :tx-data <parsed edn>}]`.

  Returns `{:scanned n :read-ok m :findings [...]}`. `:scanned` and `:read-ok`
  are the evidence floor: a caller must refuse to report a pass when `:scanned`
  is 0, because \"no documents\" and \"no problems\" produce an identical empty
  `:findings` and only one of them is good news."
  [process entries]
  (let [parsed (for [{:keys [path tx-data]} entries]
                 (let [kip (core/read-kip tx-data)]
                   {:path path :kip kip :error (:kip/error kip)}))
        broken (filter :error parsed)
        good (remove :error parsed)]
    {:scanned (count entries)
     :read-ok (count good)
     :findings
     (vec (concat
           (for [{:keys [path error]} broken]
             (finding :error error path {}))
           (mapcat #(check-document process %) good)
           (check-cross-document good)))}))

(defn errors [result] (filterv #(= :error (:severity %)) (:findings result)))
(defn warnings [result] (filterv #(= :warn (:severity %)) (:findings result)))
