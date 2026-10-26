(ns kototama.membrane
  "kototama.membrane — the shared OUTWARD self-publication membrane for atproto actors +
  artificial organisms (generalized from danjo/keizu/kosatsu/iriai `social_post`). A record
  (a readout summary) enters; it is DRAFTED into a DRY-RUN post ONLY if every charter gate
  holds (kototama.gates), else REFUSED with the failed invariants. A live post is outward-gated
  (Council Lv6+ + member/actor signature) — `build-live` refuses by construction at R0.

  Pure + deterministic; the actual signing + AT-proto broadcast are the HOST's job (the
  actor self-signs with its own did:key via actor:host/sign — see kototama.host — the server
  never holds a key). This namespace only shapes + gates the post record."
  (:require [kototama.gates :as gates]))

(def phase-drafted :drafted)
(def phase-refused :refused)

(defn draft
  "Drive one record toward a dry-run post, or refuse with the failed gates.
  `record` = {:subject :body :sources :cash :server-held-key :sim-only :author :disclaimer}.
  Returns {:phase :drafted :post {…}} or {:phase :refused :refusal [<gate-kw>…]}."
  [{:keys [subject body sources author disclaimer]
    :or {sources [] disclaimer ""}
    :as record}]
  (let [refusal (gates/why-refused record)]
    (if (seq refusal)
      {:phase phase-refused :refusal refusal :subject subject}
      {:phase phase-drafted
       :post {":post/subject" subject
              ":post/body" (str disclaimer (when (seq disclaimer) "\n\n") body)
              ":post/status" ":dry-run"        ; published is unrepresentable at R0
              ":post/server-held-key" false    ; no-server-key
              ":post/sim-only" true            ; narrates, never actuates
              ":post/author" (or author "")    ; member/actor DID (for a gated live post)
              ":post/sources" (vec sources)}})))

(defn drafted? [m] (= phase-drafted (:phase m)))
(defn refused? [m] (= phase-refused (:phase m)))

(defn build-live
  "Live posting is outward-gated. Refuses by construction at R0; the live signature is the
  actor's OWN did:key (present-only via actor:host/sign), never a server-held key, under
  Council Lv6+ + operator + member/actor-signature (a §1.12 outward-action gate)."
  [& _]
  (throw (ex-info (str "actor R0: live broadcast is Council Lv6+ + member/actor-signature gated; "
                       "only dry-run posts are producible offline (the actor self-signs in its "
                       "own runtime, never with a server key)")
                  {:actor/outward-gated true})))
