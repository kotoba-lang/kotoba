(ns fleet.receipt
  "Signed governor decisions: the shape, the sign-off rule, and the published
  ledger.

  Three things that were about to be written three times share one namespace
  because they share one object. A receipt is signed once (`sign`), can be
  required to carry a human approval before it may materialize (`needs-signoff?`
  / `approved?`), and is published so anyone can check it later
  (`append-to-ledger!`). Splitting those across scripts is how the signed thing
  and the published thing drift apart.

  Everything except `append-to-ledger!` is pure, so the rules are testable
  without a network, a key, or a fleet.

  The ledger is append-only ON PURPOSE. The 2026-07-25 policy that documents
  show latest state (ADR-2607257000) explicitly keeps append-only for signed
  event streams — a receipt records that a decision happened at a point in
  time, and rewriting it destroys exactly the thing a signature is for."
  (:require [kotoba.lang.text :as str]
            [fleet.cli :as cli]
            [fleet.github :as gh]
            [fleet.identity :as fid]))

(def ledger-repo "com-junkawasaki/root")
(def ledger-path "manifest/fleet-sandbox.edn")

;; ── shape ───────────────────────────────────────────────────────────────────

(defn body
  "The canonical, signable body of one decision. Deliberately small and
  content-addressed: it names WHAT was decided (work, proposal, verdict), what
  it was decided ABOUT (repo at an exact pin, the patch by digest), and under
  what containment (exec backing, source credential class) — not the patch
  text, which stays in the repo the patch lands in."
  [{:keys [receipt payload work-id node at]}]
  {:fleet.sandbox/work (:receipt/work receipt)
   :fleet.sandbox/work-id work-id
   :fleet.sandbox/proposal (:receipt/proposal receipt)
   :fleet.sandbox/verdict (:receipt/verdict receipt)
   :fleet.sandbox/reason (:receipt/reason receipt)
   :fleet.sandbox/repo (:repo payload)
   :fleet.sandbox/pin (:pin payload)
   :fleet.sandbox/agent (:proposal/agent payload)
   :fleet.sandbox/node (or node (:node payload))
   :fleet.sandbox/model (:model payload)
   :fleet.sandbox/machine (:machine payload)
   :fleet.sandbox/machine-id (:machine-id payload)
   :fleet.sandbox/kcm-contract (:kcm-contract payload)
   :fleet.sandbox/kcm-capabilities (:kcm-capabilities payload)
   :fleet.sandbox/cache (:cache payload)
   :fleet.sandbox/exec-backing (:exec-backing payload)
   :fleet.sandbox/exec-leaked (vec (get-in payload [:exec-probe :leaked]))
   :fleet.sandbox/source-auth (:source-auth payload)
   :fleet.sandbox/tests-exit (get-in payload [:tests :final-exit])
   :fleet.sandbox/patch-sha256 (some-> (:diff payload) fid/sha256-hex)
   :fleet.sandbox/at at})

(defn sign
  "{:receipt body :cid sha256(body) :signature … :signer did}. The cid is what
  is signed, so a verifier re-derives it from the body and never has to trust
  the transport."
  [identity b]
  (let [cid (fid/sha256-hex (pr-str b))]
    {:receipt b :cid cid :signature (fid/sign-hex identity cid) :signer (:did identity)}))

(defn verify
  "True when the signature covers a cid that really is this body's digest."
  [{:keys [receipt cid signature signer]}]
  (and (= cid (fid/sha256-hex (pr-str receipt)))
       (fid/verify-hex signer cid signature)))

;; ── sign-off (C2) ───────────────────────────────────────────────────────────

(defn needs-signoff?
  "Does this patch touch a path the fleet refuses to let an agent land
  unattended? Distinct from a protected path, which is refused outright: these
  are allowed, but only behind a human decision."
  [files signoff-paths]
  (boolean (some (fn [f] (some #(str/starts-with? f %) signoff-paths)) files)))

(defn approval-datoms
  "A sign-off is itself a signed fact in the log, not a flag someone flipped:
  the approver signs the PROPOSAL id, so an approval cannot be moved to a
  different proposal or minted by a key the fleet does not recognise."
  [identity proposal-id t]
  (let [e (str "approval|" proposal-id)]
    [[e :approval/proposal proposal-id t]
     [e :approval/signer (:did identity) t]
     [e :approval/signature (fid/sign-hex identity proposal-id) t]
     [e :approval/t t t]]))

(defn approved?
  "Is there a VALID approval for `proposal-id` from one of `authorized-dids`?
  Re-verifies the signature; an approval datom that does not check out counts
  as no approval at all."
  [datoms proposal-id authorized-dids]
  (let [e (str "approval|" proposal-id)
        ent (reduce (fn [m [de a v]] (if (= de e) (assoc m a v) m)) {} datoms)]
    (boolean
     (and (= proposal-id (:approval/proposal ent))
          (contains? (set authorized-dids) (:approval/signer ent))
          (fid/verify-hex (:approval/signer ent) proposal-id (:approval/signature ent))))))

;; ── published ledger (B1) ───────────────────────────────────────────────────

(defn append-to-ledger!
  "Append one signed receipt to the published ledger, optimistic-locked on the
  file's blob sha: a concurrent appender makes this 409 and retry, so two
  fleets can publish into one ledger without a lock and without either losing
  a line. Returns {:commit sha :line n}."
  [{:keys [token signed repo path retries] :or {repo ledger-repo path ledger-path retries 3}}]
  (loop [attempt 0]
    (let [existing (gh/file-at {:token token :repo repo :path path})
          prior (or (some-> (:text existing) (.toString "utf8")) "")
          line (pr-str signed)
          content (str (str/replace prior #"\n*$" (if (str/blank? prior) "" "\n")) line "\n")
          resp (try
                 {:ok (gh/put-file!
                       {:token token :repo repo :path path
                        :message (str "fleet-sandbox: " (name (:fleet.sandbox/verdict (:receipt signed)))
                                      " " (:fleet.sandbox/work-id (:receipt signed))
                                      " (signed " (subs (:signer signed) 0 20) "…)")
                        :content content :base-sha (:sha existing)})}
                 (catch :default e {:err e}))]
      (cond
        (:ok resp) {:commit (get-in (:ok resp) [:commit :sha])
                    :lines (count (str/split-lines content))}
        (< attempt retries) (do (cli/warn "  ledger: contended, retrying…") (recur (inc attempt)))
        :else (throw (:err resp))))))

(defn read-ledger
  "Parse a ledger blob into signed receipts (one EDN map per line)."
  [text]
  (->> (str/split-lines (or text ""))
       (remove str/blank?)
       (mapv cljs.reader/read-string)))
