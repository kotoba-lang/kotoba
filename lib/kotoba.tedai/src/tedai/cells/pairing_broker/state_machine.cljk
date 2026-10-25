(ns tedai.cells.pairing-broker.state-machine
  "Phase state machine for the tedai 手代 pairing_broker cell.
  1:1 port of cells/pairing_broker/state_machine.py (ADR-2606101400). Brokers access to the MEMBER's
  OWN paired device with NO platform-held key; read ops allowed, mutating ops member-signature-gated,
  :outward ops held at the Council outward gate even WITH a member signature.
  G1 member-principal/own-device-only · G3 no-server-key · G5 read-default/mutate-gated/outward-held."
  (:require [kotoba.lang.text :as str]))

(def member "member")
(def encref-prefix "encref:")
(def read- "read")
(def outward "outward")

(def state-defaults
  {"phase" "init" "device" "member-laptop" "principal" member "device_owner" member "paired" true
   "server_held_key" false "pairing_ref" "encref:com.etzhayyim.encrypted/member-laptop-pairing"
   "op_safety" read- "member_sig" "" "server_sig" "" "payload" {}})

(defn- cell-state [state] (merge state-defaults (get state "cell_state" {})))

(defn transition-verify-owner [state]
  (let [cs (cell-state state)
        cs (assoc cs "principal" (get state "principal" (get cs "principal"))
                  "device_owner" (get state "device_owner" (get cs "device_owner"))
                  "paired" (get state "paired" (get cs "paired")))]
    (when (not= (get cs "principal") member)
      (throw (ex-info "G1 violation: principal must be the member (member-principal)" {:gate "G1"})))
    (when (not= (get cs "device_owner") member)
      (throw (ex-info "G1 violation: tedai operates only the member's OWN device; third-party-device control is refused (N3: structurally not a RAT)" {:gate "G1"})))
    (when-not (get cs "paired")
      (throw (ex-info "G1 violation: the device must be physically paired (consent ceremony); an unpaired device is refused" {:gate "G1"})))
    {"cell_state" (assoc cs "phase" "verified_owner") "next_node" "grant_built"}))

(defn transition-build-grant [state]
  (let [cs (cell-state state)
        cs (assoc cs "pairing_ref" (get state "pairing_ref" (get cs "pairing_ref")) "server_held_key" false)]
    (when-not (str/starts-with? (get cs "pairing_ref") encref-prefix)
      (throw (ex-info "G3 violation: the grant may carry only an encrypted-envelope ref (com.etzhayyim.encrypted.*); a plaintext pairing key is never stored" {:gate "G3"})))
    (let [cs (assoc cs "phase" "grant_built"
                    "payload" (assoc (get cs "payload") "grant"
                                     {"device" (get cs "device") "principal" member "deviceOwner" member
                                      "paired" true "serverHeldKey" false "pairingRef" (get cs "pairing_ref")}))]
      {"cell_state" cs "next_node" (if (= (get cs "op_safety") read-) "read_allowed" "awaiting_member_sig")})))

(defn transition-read-allowed [state]
  (let [cs (cell-state state)]
    (when (not= (get cs "op_safety") read-)
      (throw (ex-info "G5 violation: read_allowed reached for a mutating op" {:gate "G5"})))
    {"cell_state" (assoc cs "phase" "read_allowed" "payload" (assoc (get cs "payload") "mutateGate" "read-allowed"))
     "next_node" "end"}))

(defn transition-authorize-mutate [state]
  (let [cs (cell-state state)
        cs (assoc cs "member_sig" (get state "member_sig" "") "server_sig" (get state "server_sig" ""))]
    (when (= (get cs "op_safety") read-)
      (throw (ex-info "G5 violation: authorize_mutate reached for a read op" {:gate "G5"})))
    (when (seq (get cs "server_sig"))
      (throw (ex-info "G3 violation: server signature refused (no-server-key, ADR-2605231525)" {:gate "G3"})))
    (when-not (seq (get cs "member_sig"))
      (throw (ex-info "G5 violation: member signature required to authorize a mutating op" {:gate "G5"})))
    (if (= (get cs "op_safety") outward)
      (let [cs (assoc cs "phase" "awaiting_outward_gate"
                      "payload" (assoc (get cs "payload")
                                       "mutateGate" "awaiting-member-sig-and-outward-gate"
                                       "outwardGate" {"memberSigned" true "authorized" false "requires" "council-outward-gate"}))]
        {"cell_state" cs "next_node" "end"})
      (let [cs (assoc cs "phase" "authorized"
                      "payload" (assoc (get cs "payload") "mutateGate" "authorized"
                                       "authorization" {"authorizedBy" member "serverSigned" false "actuationGated" true}))]
        {"cell_state" cs "next_node" "end"}))))

(defn solve [_input-state]
  (throw (ex-info "tedai R0 scaffold: activate pairing_broker via Council ADR (post-2606101400 ratification)" {:scaffold true})))
