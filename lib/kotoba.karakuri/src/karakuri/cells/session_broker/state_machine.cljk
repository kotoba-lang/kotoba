(ns karakuri.cells.session-broker.state-machine
  "Phase state machine for the karakuri session_broker (絡繰) cell.
  1:1 Clojure port of cells/session_broker/state_machine.py (ADR-2606039200 / ADR-2606160842).

  The defining karakuri skill: broker access to the MEMBER's OWN service session WITHOUT the platform
  ever holding secret material, allow read ops freely, and route every mutating op to a member
  signature. The gates are pure, unit-tested transitions; the cell's .solve() raises until Council
  activation.

  Invariants enforced:
    G1 — member-principal / own-account-only: the principal AND the account owner are the member;
         a third-party account is refused.
    G3 — no-server-key: the grant carries serverHeldKey=false and an encrypted-envelope REFERENCE
         only (never plaintext credentials); a server signature is refused (ADR-2605231525).
    G5 — read-default / mutate-gated: :read ops are allowed at R0; any :create/:update/:delete op
         awaits a member signature before it can be authorized.

  Conventions: the dataclass BrokerState → a plain map with the SAME string field keys the Python
  `cs.__dict__` round-trips; phase enum values stay strings; ValueError → ex-info."
  (:require [kotoba.lang.text :as str]))

;; G1: only the member's own account is operable.
(def MEMBER "member")

;; G3: a secret reference must be an encrypted-envelope ref, never inline plaintext.
(def ENCREF-PREFIX "encref:")

;; G5: read ops are allowed at R0; everything else awaits a member signature.
(def READ "read")

;; ── BrokerPhase (enum — Python value identities preserved) ──
(def broker-phases
  {:init                "init"
   :verified-owner      "verified_owner"
   :grant-built         "grant_built"
   :read-allowed        "read_allowed"
   :awaiting-member-sig "awaiting_member_sig"
   :authorized          "authorized"})

(def phase-init                (:init broker-phases))
(def phase-verified-owner      (:verified-owner broker-phases))
(def phase-grant-built         (:grant-built broker-phases))
(def phase-read-allowed        (:read-allowed broker-phases))
(def phase-awaiting-member-sig (:awaiting-member-sig broker-phases))
(def phase-authorized          (:authorized broker-phases))

;; ── BrokerState (dataclass → plain map, string keys + field defaults) ──
(def state-defaults
  {"phase"           phase-init
   "service"         "squarespace"
   "principal"       MEMBER                 ; G1: always the member
   "account_owner"   MEMBER                 ; G1: the member's OWN account
   "server_held_key" false                  ; G3: always false
   "secret_ref"      "encref:com.etzhayyim.encrypted/squarespace-session"
   "op_safety"       READ                   ; :read / :create / :update / :delete
   "member_sig"      ""
   "server_sig"      ""                      ; G3: must remain empty
   "payload"         {}})

(defn- cell-state [state]
  (merge state-defaults (get state "cell_state" {})))

(defn transition-verify-owner
  "G1: the principal and the account owner must both be the member; refuse a third-party account."
  [state]
  (let [cs (cell-state state)
        cs (assoc cs
                  "principal" (get state "principal" (get cs "principal"))
                  "account_owner" (get state "account_owner" (get cs "account_owner")))]
    (when (not= (get cs "principal") MEMBER)
      (throw (ex-info "G1 violation: principal must be the member (member-principal)" {:gate "G1"})))
    (when (not= (get cs "account_owner") MEMBER)
      (throw (ex-info (str "G1 violation: karakuri drives only the member's OWN account; "
                           "third-party-account access is refused (N1 no scraping/surveillance)")
                      {:gate "G1"})))
    (let [cs (assoc cs "phase" phase-verified-owner)]
      {"cell_state" cs "next_node" "grant_built"})))

(defn transition-build-grant
  "G3: build a server-keyless grant holding only an encrypted-envelope ref — never plaintext."
  [state]
  (let [cs (cell-state state)
        cs (assoc cs
                  "secret_ref" (get state "secret_ref" (get cs "secret_ref"))
                  "server_held_key" false)]   ; G3 invariant
    (when-not (str/starts-with? (get cs "secret_ref") ENCREF-PREFIX)
      (throw (ex-info (str "G3 violation: the grant may carry only an encrypted-envelope ref "
                           "(com.etzhayyim.encrypted.*); plaintext credentials are never stored")
                      {:gate "G3"})))
    (let [cs (assoc cs
                    "phase" phase-grant-built
                    "payload" (assoc (get cs "payload")
                                     "grant" {"service" (get cs "service")
                                              "principal" MEMBER
                                              "accountOwner" MEMBER
                                              "serverHeldKey" false
                                              "secretRef" (get cs "secret_ref")}))
          ;; G5: route based on the op's safety class.
          nxt (if (= (get cs "op_safety") READ) "read_allowed" "awaiting_member_sig")]
      {"cell_state" cs "next_node" nxt})))

(defn transition-read-allowed
  "G5: a :read op needs no signature; it is allowed at R0 (still dry-run / G6 downstream)."
  [state]
  (let [cs (cell-state state)]
    (when (not= (get cs "op_safety") READ)
      (throw (ex-info "G5 violation: read_allowed reached for a mutating op" {:gate "G5"})))
    (let [cs (assoc cs
                    "phase" phase-read-allowed
                    "payload" (assoc (get cs "payload") "mutateGate" "read-allowed"))]
      {"cell_state" cs "next_node" "end"})))

(defn transition-authorize-mutate
  "G3/G5: authorize a mutating op on a MEMBER signature only; refuse any server signature."
  [state]
  (let [cs (cell-state state)
        cs (assoc cs
                  "member_sig" (get state "member_sig" "")
                  "server_sig" (get state "server_sig" ""))]
    (when (= (get cs "op_safety") READ)
      (throw (ex-info "G5 violation: authorize_mutate reached for a read op" {:gate "G5"})))
    (when (seq (get cs "server_sig"))
      (throw (ex-info "G3 violation: server signature refused (no-server-key, ADR-2605231525)" {:gate "G3"})))
    (when-not (seq (get cs "member_sig"))
      (throw (ex-info "G5 violation: member signature required to authorize a mutating op" {:gate "G5"})))
    (let [cs (assoc cs
                    "phase" phase-authorized
                    "payload" (assoc (get cs "payload")
                                     "mutateGate" "authorized"
                                     "authorization" {"authorizedBy" MEMBER
                                                      "serverSigned" false
                                                      "outwardGated" true}))]   ; G6
      {"cell_state" cs "next_node" "end"})))

(defn solve
  "R0 scaffold: .solve() raises until Council activation (ADR-2606039200 §Decision)."
  [_input-state]
  (throw (ex-info "karakuri R0 scaffold: activate session_broker via Council ADR (post-2606039200 ratification)"
                  {:scaffold true})))
