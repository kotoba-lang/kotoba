(ns kagami.reach
  "Signed reachability receipts (ADR-2607160005): make pin reachability a
  REPLICATED, SIGNED attestation instead of a per-node clone. One node that
  has verified a pin (via reach-local-git) signs a receipt; other fleet nodes
  fetch it over p2p and trust it (signer ∈ trust set, fresh enough) — so they
  need NEITHER a clone NOR the gh API. This is kagami.ci's receipt shape
  applied to reachability, and it removes the last per-node GitHub touch the
  clone-based provider still had.

  Pure cljc; sign/verify/hash injected. A receipt attests: repo, pin,
  default-branch tip observed, reachable?, value-advance?, at, signer."
  (:require [kotoba.lang.text :as str]))

(defn canonical-str
  [{:reach/keys [repo pin default-tip reachable? value-advance? at]}]
  (pr-str ["fleet-reach/v1" repo pin default-tip reachable? value-advance? at]))

(defn make-receipt [{:keys [repo pin default-tip reachable? value-advance? at]}]
  {:reach/repo repo :reach/pin pin :reach/default-tip default-tip
   :reach/reachable? reachable? :reach/value-advance? value-advance? :reach/at at})

(defn sign-receipt [sign-fn signer receipt]
  {:receipt receipt :signature (sign-fn (canonical-str receipt)) :signer signer})

(defn js->ms
  "ISO-8601 -> epoch ms (host-agnostic). 0 on parse failure so :stale never
  falsely fires."
  [iso]
  #?(:cljs (let [n (js/Date.parse iso)] (if (js/isNaN n) 0 n))
     :clj (try (.toEpochMilli (java.time.Instant/parse iso)) (catch Exception _ 0))))

(defn verify-receipt
  "Trust a peer's reachability receipt iff: signer ∈ trust, signature valid,
  it's for the pin we're asking about, and it's fresh (within max-age-ms of
  `now`). Returns {:ok? bool :reachable? :value-advance? :reasons [..]}."
  [{:keys [receipt signature signer]}
   {:keys [trust verify-fn did->pubkey repo pin now max-age-ms]}]
  (let [reasons
        (cond-> []
          (not (contains? trust signer)) (conj :untrusted-signer)
          (not= repo (:reach/repo receipt)) (conj :wrong-repo)
          (not= pin (:reach/pin receipt)) (conj :wrong-pin)
          (not (try (verify-fn (did->pubkey signer) (canonical-str receipt) signature)
                    (catch #?(:clj Exception :cljs :default) _ false)))
          (conj :bad-signature)
          (and now max-age-ms (:reach/at receipt)
               (> (- now (js->ms (:reach/at receipt))) max-age-ms))
          (conj :stale))]
    (if (seq reasons)
      {:ok? false :reasons (vec (distinct reasons))}
      {:ok? true :reachable? (:reach/reachable? receipt)
       :value-advance? (:reach/value-advance? receipt) :reasons []})))
