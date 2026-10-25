(ns kagami.pin
  "Phase 1 (ADR-2607160005): signed pin head records + the admission gate.

  A pin advance is no longer a generated line in a YAML file — it is a signed,
  parent-covering head record admitted (or rejected) by a pure decision
  function. The three admission invariants that verify-west-pins.cljs + CI +
  convention emulate today become preconditions of the transaction itself:

    1. authority     — the signer holds a pin-advance grant covering the repo
    2. monotonicity  — :pin/sequence strictly increases; rollback is rejected
                       in the same layer as signature verification
    3. reachability  — :pin/value is reachable from the upstream default
                       branch (checked server-side; injected here)

  Parent-covering (the Radicle 1.7.0 sigrefs-replay CVE lesson, day 1):
  the signed payload includes the hash of the *previous accepted record*,
  so an old valid record cannot be replayed as a new head.

  Pure cljc: crypto is injected as fns — {:verify-fn (fn [pubkey bytes sig])
  :hash-fn (fn [s] hex)} — nbb wires node:crypto, JVM wires ed25519-clj.
  Signer ids are \"ed25519:<pubkey-hex>\" in Phase 1; migrating ids to
  did:key via kotoba-lang ed25519/did libs is Phase 2 (identity plane).

  The admission judgement (`covers?` + the reason/verdict fold in `admit`)
  also exists as a Kotoba decision core, `src/kagami/pin_core.kotoba`,
  parity-bound to this namespace by `kagami.pin-kotoba-parity-test` (compiled
  at test time; test-only deps). This cljc is still what runs — the core's
  header records why the authority move is a separate slice."
  (:require [kotoba.lang.text :as str]))

;; ---------------------------------------------------------------------------
;; record shape + canonical bytes

(defn canonical-str
  "Deterministic signing payload: a fixed-order vector printed with pr-str.
  Field order is part of the protocol; changing it is a format version bump."
  [{:pin/keys [name value sequence parent valid-until]}]
  (pr-str ["fleet-pin/v1" name value sequence parent valid-until]))

(defn record-hash
  "Hash of an accepted record (canonical bytes + signature) — what the next
  record's :pin/parent must equal."
  [hash-fn record signature]
  (hash-fn (str (canonical-str record) "|" signature)))

(defn make-record
  [{:keys [repo value sequence parent valid-until]}]
  {:pin/name repo
   :pin/value value
   :pin/sequence sequence
   :pin/parent parent
   :pin/valid-until valid-until})

;; ---------------------------------------------------------------------------
;; grants (Phase 1 keyring; CACAO delegation chains replace this in Phase 2)

(defn covers?
  "Trailing-* wildcard path grant, same convention as cacao-clj resources."
  [grant path]
  (if (str/ends-with? grant "*")
    (str/starts-with? path (subs grant 0 (dec (count grant))))
    (= grant path)))

(defn authorized?
  "keyring: {:keys {\"ed25519:<hex>\" {:grants #{\"orgs/kotoba-lang/*\" ...}}}}"
  [keyring signer repo-path]
  (boolean (some #(covers? % repo-path)
                 (get-in keyring [:keys signer :grants]))))

;; ---------------------------------------------------------------------------
;; admission gate

(defn admit
  "Pure admission decision for a proposed signed pin advance.

  proposal: {:record r :signature hex :signer \"ed25519:<hex>\"}
  ctx:      {:repo-path   path of the repo entity (grant subject)
             :current     nil | {:record r :signature hex} — last accepted
             :keyring     see `authorized?`
             :verify-fn   (fn [pubkey-hex payload-str sig-hex] -> bool)
             :hash-fn     (fn [s] -> hex)
             :reachable?  true | false | :unknown  — server-side judgment,
                          computed by the caller (GitHub API), never local
                          shallow ancestry
             :value-advance? true | false | :unknown — is :pin/value ahead of
                          the current record's value (verify-west-pins Rule 2:
                          behind = silent pin regression, diverged = wrong
                          lineage; both reject). true when there is no current.}

  -> {:verdict :accept | :warn-accept | :reject, :reasons [kw ...]}
  Fail-open only on unverifiable reachability (matching verify-west-pins);
  every other failure rejects."
  [{:keys [record signature signer] :as _proposal}
   {:keys [repo-path current keyring verify-fn hash-fn reachable? value-advance?]
    :or {value-advance? true}}]
  (let [pubkey  (when (and signer (str/starts-with? signer "ed25519:"))
                  (subs signer (count "ed25519:")))
        cur-rec (:record current)
        reasons
        (cond-> []
          (not pubkey)
          (conj :malformed-signer)

          (not (authorized? keyring signer repo-path))
          (conj :unauthorized-signer)

          (and pubkey (not (verify-fn pubkey (canonical-str record) signature)))
          (conj :bad-signature)

          (and cur-rec (<= (:pin/sequence record) (:pin/sequence cur-rec)))
          (conj :sequence-rollback)

          (and (nil? cur-rec) (not= 1 (:pin/sequence record)))
          (conj :genesis-sequence-not-1)

          (and cur-rec
               (not= (:pin/parent record)
                     (record-hash hash-fn cur-rec (:signature current))))
          (conj :parent-mismatch)

          (and (nil? cur-rec) (some? (:pin/parent record)))
          (conj :genesis-has-parent)

          (false? reachable?)
          (conj :unreachable-from-upstream-default-branch)

          (and cur-rec (false? value-advance?))
          (conj :value-regression))]
    (cond
      (seq reasons) {:verdict :reject :reasons reasons}
      (or (= :unknown reachable?) (= :unknown value-advance?))
      {:verdict :warn-accept
       :reasons (cond-> []
                  (= :unknown reachable?) (conj :reachability-unverifiable-fail-open)
                  (= :unknown value-advance?) (conj :value-advance-unverifiable-fail-open))}
      :else {:verdict :accept :reasons []})))

(defn accepted-event
  "Ledger event for an accepted (or warn-accepted) signed pin advance."
  [{:keys [record signature signer]} verdict seq-no at]
  {:event/seq seq-no
   :event/type :pin/advance-signed
   :event/at at
   :event/verdict (:verdict verdict)
   :event/signer signer
   :pin/record record
   :pin/signature signature})
