(ns tedai.cells.social-post.state-machine
  "Phase state machine for the tedai social_post cell — the publication membrane that
  lets the actor self-publish observations to the mesh/AT-proto WITHOUT a server-held key.
  ADR-2606272355 (actor self-publication seed). Auto-seeded R0 (mirrors
  danjo.cells.social-post.state-machine / keizu's social_post membrane).

  A record enters; it is DRAFTED into a dry-run post ONLY if:

    source-provenance — \u2265 2 citations are present;
    non-adjudicating — the post is a mirror, opening with the observational disclaimer;
    no-server-key — server-held-key is false;
    R0-gate — the status is dry-run (a 'published' request REFUSES).

  Self-contained. Stdlib only. Deterministic."
  (:require [kotoba.lang.text :as str]))

(def disclaimer
  "【観測ミラー / accountability map — NOT a verdict, NOT advice, 非断定】")

(def phase-init "init")
(def phase-drafted "drafted")
(def phase-refused "refused")

(def state-defaults
  {"phase"            phase-init
    "subject"          ""
    "sources"          []
    "requested_status" "dry-run"
    "server_held_key"  false
    "payload"          {}
    "refusal"          ""})

(defn- cell-state [state]
  (merge state-defaults (get state "cell_state" {})))

(defn- lstrip-colon [s]
  (str/replace (str s) #"^:+" ""))

(defn transition-to-drafted
  "Drive one record toward a dry-run post payload, or refuse with the failed invariant.
  Pure: (state) -> {\"cell_state\" {…}}."
  [state]
  (let [cs0 (cell-state state)
        cs  (assoc cs0
                   "subject"          (get state "subject" (get cs0 "subject"))
                   "sources"          (get state "sources" (get cs0 "sources"))
                   "requested_status" (lstrip-colon (get state "requested_status" (get cs0 "requested_status")))
                   "server_held_key"  (boolean (get state "server_held_key" (get cs0 "server_held_key"))))
        refuse (fn [msg]
                 {"cell_state" (assoc cs "refusal" msg "phase" phase-refused)})]
    (cond
      (< (count (get cs "sources")) 2)
      (refuse "source-provenance: a post needs \u2265 2 citations")

      (get cs "server_held_key")
      (refuse "no-server-key: server-held-key must be false; the actor self-signs in its mesh runtime")

      (not= (get cs "requested_status") "dry-run")
      (refuse "R0-gate: only dry-run posts; live publication is Council Lv6+ + operator + member/actor-signature gated")

      :else
      (let [payload {":post/subject" (get cs "subject")
                       ":post/body" (str disclaimer " " (get cs "subject"))
                       ":post/status" ":dry-run"
                       ":post/is-mirror" true
                       ":post/non-adjudicating-notice" true
                       ":post/server-held-key" false
                       ":post/sources" (get cs "sources")}]
        {"cell_state" (assoc cs "payload" payload "refusal" "" "phase" phase-drafted)}))))
