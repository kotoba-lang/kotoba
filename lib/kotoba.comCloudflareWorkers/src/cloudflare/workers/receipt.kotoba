(ns cloudflare.workers.receipt
  "Audit receipts for every admission attempt.

  `kotoba-lang/kotoba-lang`'s `lang/capability-semantics.edn` requires
  `:receipt/cap`, `:receipt/at`, `:receipt/call`, `:receipt/outcome` on every
  receipt and states `:attempt-always-receipted true` -- denials are receipted
  exactly like grants. An unreceipted denial is the failure mode where an
  operator sees a quiet, working system and never learns that a guest has been
  probing keys outside its scope for a week.

  `at` is a parameter, never read from a clock. A pure core that reaches for
  the current time has taken an authority nobody granted it, and it also stops
  being testable without freezing time. The provider passes the Worker's
  request time down."
  (:require [kotoba.lang.text :as str]))

(defn receipt
  "Build one receipt.

  Required: `:cap` (capability kind or nil when the command never got far
  enough to need one), `:at`, `:call`, `:outcome` (`:granted` / `:denied`).
  Optional: `:resource`, `:reason`, `:detail`, `:binding`, `:index`."
  [{:keys [cap at call outcome resource reason detail binding index]}]
  (cond-> {:receipt/cap cap
           :receipt/at at
           :receipt/call call
           :receipt/outcome outcome}
    (some? resource) (assoc :receipt/resource resource)
    (some? reason) (assoc :receipt/reason reason)
    (some? detail) (assoc :receipt/detail detail)
    (some? binding) (assoc :receipt/binding binding)
    (some? index) (assoc :receipt/index index)))

(defn granted
  [m]
  (receipt (assoc m :outcome :granted)))

(defn denied
  [m]
  (receipt (assoc m :outcome :denied)))

(defn failed
  "A command that was *admitted* and then failed in the provider (a D1 error,
  an R2 outage). Distinct from `denied` on purpose: conflating \"you were not
  allowed to\" with \"it did not work\" hides both an authorization bug and an
  availability one."
  [m]
  (receipt (assoc m :outcome :failed)))

(defn denial?
  [r]
  (= :denied (:receipt/outcome r)))

(defn complete?
  "True when R carries the four keys `capability-semantics.edn` mandates.

  `:receipt/cap` may legitimately be nil (a malformed command is denied before
  any capability is identified), so this checks key presence, not truthiness."
  [r]
  (and (map? r)
       (every? (fn [k] (contains? r k))
               [:receipt/cap :receipt/at :receipt/call :receipt/outcome])))

(defn summarize
  "One-line, log-safe rendering of R.

  Deliberately omits values and SQL: a receipt line ends up in `console.log`
  and then in a log sink, so it carries who/what/where and never payloads."
  [r]
  (str/join " "
            (remove nil?
                    [(name (:receipt/outcome r))
                     (str (:receipt/call r))
                     (when-let [c (:receipt/cap r)] (str c))
                     (when-let [res (:receipt/resource r)] res)
                     (when-let [reason (:receipt/reason r)] (str "reason=" reason))
                     (str "at=" (:receipt/at r))])))
