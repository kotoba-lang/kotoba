(ns custody.model
  "Threshold custody: who has to agree before a sealed secret can be opened,
  and whether that agreement means anything.

  `custody.shamir` splits a secret so that `m` of `n` shares reconstruct it.
  That is arithmetic. This namespace is the part that decides whether a
  given split is *worth* anything, because m-of-n is only as strong as the
  independence of the people holding the shares — three shares held by one
  operator is a 1-of-1 wearing a costume, and nothing in the algebra
  notices. `independence` is therefore not a helper here; it is the point.

      {:deal/id            \"deal:itonami/recovery/2026-07\"
       :deal/version       1
       :deal/secret-id     \"envelope:drv:abc123#recovery\"
       :deal/epoch         0
       :deal/threshold     3
       :deal/total         5
       :deal/digest-alg    :sha-256
       :deal/secret-digest \"base64url…\"
       :deal/custodians    [{:custodian/id      \"did:key:z6Mk…\"
                             :custodian/domain  :operator
                             :custodian/pub     \"base64url…\"   ; X25519
                             :custodian/share-x 1
                             :custodian/wrapped \"base64url…\"}]}

  A share is wrapped to its custodian's X25519 public key with
  `kotoba-lang/envelope`'s recipient machinery — this namespace does no
  crypto, it names the AAD that wrap must bind (`share-aad`) and refuses
  quorums that disagree about which deal and which epoch they belong to.

  Sits under ADR-2607285000 (cloud-itonami sealed plane). It replaces the
  `kotoba-custody` Rust crate that ADR-2607061900 cited, which was removed
  with the rest of the Rust tree (ADR-2607072000); the `GrantedShare` shape
  it describes — epoch, deal binding, per-requester re-wrap — is what
  `share-aad` and `quorum-error` reconstruct in cljc."
  (:require [kotoba.lang.text :as str]
            [custody.shamir :as shamir]))

(def version 1)

(def digest-algs #{:sha-256 :blake3})

;; ------------------------------------------------------------------- deal

(defn deal
  "Describe a split that has already happened. `custodians` is a vector of
  `{:custodian/id :custodian/domain :custodian/pub}`; this assigns the
  share x-coordinates positionally (1-based), matching `shamir/split`'s
  output order, so a caller zips the two without inventing a convention.

  `secret-digest` is over the SECRET, not over any share. It is what makes
  a wrong quorum fail loudly instead of returning a plausible byte vector
  (see `shamir/combine`'s own warning)."
  [id {:keys [secret-id threshold total custodians secret-digest digest-alg epoch]
       :or {epoch 0 digest-alg :sha-256}}]
  {:deal/id id
   :deal/version version
   :deal/secret-id secret-id
   :deal/epoch epoch
   :deal/threshold threshold
   :deal/total total
   :deal/digest-alg digest-alg
   :deal/secret-digest secret-digest
   :deal/custodians (vec (map-indexed (fn [i c] (assoc c :custodian/share-x (inc i)))
                                      custodians))})

(defn deal-error
  [{:keys [:deal/id :deal/threshold :deal/total :deal/custodians
           :deal/secret-digest :deal/digest-alg :deal/epoch] :as d}]
  (let [xs (mapv :custodian/share-x custodians)
        ;; the (m, n) rules are the split's, not a second copy of them here —
        ;; a divergent copy is how a deal becomes constructible but unopenable.
        split-err (shamir/split-error [0] threshold total)]
    (cond
      (not (map? d)) :not-a-map
      (not (and (string? id) (seq id))) :missing-id
      (not= version (:deal/version d)) :bad-version
      (not (nat-int? epoch)) :bad-epoch
      split-err split-err
      (not (contains? digest-algs digest-alg)) :unknown-digest-alg
      (not (and (string? secret-digest) (seq secret-digest))) :missing-secret-digest
      (not= total (count custodians)) :custodian-count-mismatch
      (not= (count xs) (count (set xs))) :duplicate-share-x
      (not (every? :custodian/id custodians)) :custodian-missing-id
      (not (every? :custodian/domain custodians)) :custodian-missing-domain
      :else nil)))

(defn valid? [d] (nil? (deal-error d)))

;; -------------------------------------------------------------------- AAD

(defn share-aad
  "What the wrap of one custodian's share must authenticate.

  Binds the wrapped share to the deal, the epoch, the secret it is a share
  OF, the custodian, and the x-coordinate. Each element is there because
  without it a specific substitution works: without the epoch, a share
  released under a retired generation can be replayed into the current one;
  without the custodian id, two custodians can swap wraps and each open the
  other's; without x, a share can be presented at a different coordinate
  and silently move the interpolation to a different secret.

  A string, UTF-8 encoded by the sealing layer — same convention as
  `envelope.model/wrap-aad`."
  [{:keys [:deal/id :deal/version :deal/epoch :deal/secret-id]} custodian-id share-x]
  (str/join "|" ["kotoba/custody/share" version id epoch secret-id
                 custodian-id share-x]))

;; ------------------------------------------------------------ independence

(defn- domain-counts [{:keys [:deal/custodians]}]
  (frequencies (map :custodian/domain custodians)))

(defn min-domains-to-open
  "The fewest distinct domains that together hold `threshold` shares.

  1 means one party can open the secret alone and the threshold is
  decorative."
  [{:keys [:deal/threshold] :as d}]
  (let [counts (sort > (vals (domain-counts d)))]
    (loop [n 0 acc 0 [c & more] counts]
      (cond
        (>= acc threshold) n
        (nil? c) nil                     ; not enough shares to reach threshold at all
        :else (recur (inc n) (+ acc c) more)))))

(defn captured-by
  "The domain that holds `threshold` or more shares by itself, or nil."
  [{:keys [:deal/threshold] :as d}]
  (some (fn [[dom n]] (when (>= n threshold) dom)) (domain-counts d)))

(defn can-deny
  "Domains that can make reconstruction impossible by refusing, i.e. that
  hold more than `total - threshold` shares.

  Reported but NOT part of `sound?`: this is availability, not
  confidentiality. A tenant that can deny its own recovery is often exactly
  what you want; an operator that can is a hostage situation. The library
  will not guess which one you meant."
  [{:keys [:deal/threshold :deal/total] :as d}]
  (let [slack (- total threshold)]
    (into #{} (keep (fn [[dom n]] (when (> n slack) dom))) (domain-counts d))))

(defn independence
  "Whether this deal's threshold means what it looks like it means.

  `:independence/sound?` is the invariant worth gating on: no single domain
  can reach the threshold, and opening genuinely requires more than one
  party. Everything else in the map is reported so a caller can explain a
  refusal instead of just returning false."
  [d]
  (let [counts (domain-counts d)
        min-doms (min-domains-to-open d)
        captured (captured-by d)]
    {:independence/domains counts
     :independence/distinct-domains (count counts)
     :independence/min-domains-to-open min-doms
     :independence/captured-by captured
     :independence/can-deny (can-deny d)
     :independence/sound? (boolean (and (nil? captured)
                                        min-doms
                                        (>= min-doms 2)))}))

;; --------------------------------------------------------------- releases

(defn release
  "One custodian handing back one unwrapped share, with the context that
  makes it checkable. `reason` is free text and is not validated — it is
  there so the ledger says why, and a ledger that cannot say why is an
  audit trail in name only."
  [d {:keys [:custodian/id :custodian/share-x]} share {:keys [at reason]}]
  {:release/deal-id (:deal/id d)
   :release/epoch (:deal/epoch d)
   :release/secret-id (:deal/secret-id d)
   :release/custodian-id id
   :release/share-x share-x
   :release/share share
   :release/at at
   :release/reason reason})

(defn quorum-error
  "Why these releases do not constitute a quorum for `d`, or nil.

  Order matters: structural disagreement is reported before insufficiency,
  so a caller collecting shares sees `:mixed-epoch` immediately rather than
  `:below-threshold` until the last share arrives and then a sudden
  mismatch."
  [{:keys [:deal/id :deal/epoch :deal/secret-id :deal/threshold :deal/custodians] :as _d}
   releases]
  (let [known-x (into #{} (map :custodian/share-x) custodians)
        by-cust (into {} (map (juxt :custodian/id :custodian/share-x)) custodians)
        xs (mapv :release/share-x releases)]
    (cond
      (not (sequential? releases)) :releases-not-sequential
      (empty? releases) :no-releases
      (some #(not= id (:release/deal-id %)) releases) :foreign-deal
      (some #(not= epoch (:release/epoch %)) releases) :mixed-epoch
      (some #(not= secret-id (:release/secret-id %)) releases) :foreign-secret
      (some #(not (contains? known-x (:release/share-x %))) releases) :unknown-share-x
      (some (fn [r] (let [x (get by-cust (:release/custodian-id r))]
                      (and x (not= x (:release/share-x r)))))
            releases) :custodian-share-mismatch
      (not= (count xs) (count (set xs))) :duplicate-share
      (some #(not= (:release/share-x %) (:share/x (:release/share %))) releases)
      :share-x-disagreement
      (< (count releases) threshold) :below-threshold
      :else nil)))

(defn verify-secret
  "Compare a reconstructed secret against the deal's digest.

  Split out of `open` because the digest is async on the runtimes that have
  a real one (Web Crypto has no synchronous SHA-256), so `custody.seal`
  computes it, awaits it, and calls this — rather than reimplementing the
  comparison and drifting from it."
  [d secret digest]
  (if (= digest (:deal/secret-digest d))
    {:custody/opened? true :custody/secret secret}
    {:custody/opened? false
     :custody/reason :digest-mismatch
     :custody/computed-digest digest}))

(defn open
  "Reconstruct the secret from `releases`, verifying the result against the
  deal's digest.

  Returns `{:custody/opened? …}`. A wrong-but-well-formed quorum is an
  expected condition, not an exception: a custodian can hand back a stale
  share in good faith, and the caller needs to say which one rather than
  catch a throw. Structural misuse (a malformed deal) still throws.

  `digest-fn` takes the reconstructed byte vector and returns the digest in
  whatever encoding `:deal/secret-digest` uses. It is injected for the same
  reason `shamir/split` injects randomness: this namespace runs on runtimes
  that do not agree on how to hash."
  [d releases digest-fn]
  (when-let [e (deal-error d)]
    (throw (ex-info "invalid custody deal" {:custody/error e})))
  (if-let [e (quorum-error d releases)]
    {:custody/opened? false :custody/reason e}
    (let [secret (shamir/combine (mapv :release/share releases))]
      (verify-secret d secret (digest-fn secret)))))

;; --------------------------------------------------------------- rotation

(defn rotate
  "Begin a new epoch for the same secret-id.

  Returns the deal shell for the next generation — the caller must re-split
  and re-wrap, because that is the only thing that actually retires the old
  shares. Bumping the epoch alone stops old shares from being *accepted*;
  it does not stop a custodian who already unwrapped one from having it,
  exactly as `envelope.model/revoke` says about a deleted wrap. A rotation
  that does not re-split is bookkeeping."
  [d]
  (-> d
      (update :deal/epoch inc)
      (assoc :deal/custodians [])
      (dissoc :deal/secret-digest)))
