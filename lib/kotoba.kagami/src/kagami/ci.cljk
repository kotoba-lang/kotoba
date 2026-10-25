(ns kagami.ci
  "Native CI for fleet-vcs (ADR-2607160005): content-addressed, signed
  verification receipts, modelled on kotobase code_graph's execution-receipt
  (put-execution-receipt!) — provenance whose CID authenticates the record
  and whose verdict is `required ⊆ passed` (the same shape as that layer's
  `required-effects ⊆ granted-effects`). This replaces the ephemeral GitHub
  Actions log with a durable, queryable attestation on the same kotobase
  IStore stream substrate the delta op-log uses.

  A receipt records: which checks ran over a subject (a repo pin, or the
  fleet-db head), which are REQUIRED, which PASSED, the overall outcome, and
  who signed it. Content-addressed (sha256 of the canonical payload) + signed
  (fleet ed25519). Pure cljc; crypto/hash injected."
  (:require [kotoba.lang.text :as str]))

(def ^:const stream "kagami/ci-receipts")

(defn canonical-str
  "Deterministic signing payload. Field order is protocol."
  [{:ci/keys [subject checks required passed outcome policy at parent]}]
  (pr-str ["fleet-ci/v1" subject
           (mapv (juxt :name :outcome) checks)
           (vec (sort required)) (vec (sort passed))
           outcome policy at parent]))

(defn verdict
  "Overall outcome from checks + the required set: :pass iff every required
  check passed (required ⊆ passed), else :fail. Mirrors execution-receipt's
  capability check (required-effects ⊆ granted-effects)."
  [checks required]
  (let [passed (into #{} (comp (filter #(= :pass (:outcome %))) (map :name)) checks)
        missing (remove passed required)]
    {:passed passed :missing (vec missing)
     :outcome (if (empty? missing) :pass :fail)}))

(def ^:const gate-detail-max 240)
(def ^:const gate-detail-lines 3)

;; A failing check gets a bigger budget than a passing one, and the asymmetry is
;; the whole point rather than a tuning choice.
;;
;; A passing check's detail is confirmatory -- `Ran 23 tests, 0 failures` is the
;; last line, and three lines carry it. A FAILING check's detail is the only
;; artifact anyone acts on, and the old budget provably did not carry it: the
;; runner harness appends its own epilogue after the diagnosis, so the last
;; three lines are the epilogue and the cause is always just above the cut.
;;
;; Measured 2026-08-19, amu-native-fuzz on fleet node simeon. The whole receipt
;; said:
;;
;;   exit 1 — FLEET-CI: native fuzz exited 1 | FLEET-CI-EXIT: 1 |
;;            FLEET-CI: gate did not report success on simeon
;;
;; Three lines, all of them saying THAT it failed, none saying why. The cause --
;; a UBSan report naming the file, the line and the two frames -- had been
;; printed by the gate four lines earlier and was cut. Diagnosing it required
;; shipping the tree to that node over ssh and re-running by hand. The
;; superproject's own gates.edn had already named this: "an error body that is
;; discarded is the same defect class as a check that cannot answer."
;;
;; Receipts stay small where it matters: they only grow when something is wrong.
(def ^:const gate-detail-max-failed 1200)
(def ^:const gate-detail-lines-failed 12)

(defn gate-detail
  "`exit <code> — <last meaningful output lines>`, capped so a receipt stays a
  receipt (not a log). Keeps the LAST lines because test runners print their
  summary there -- and keeps MORE of them when `code` is non-zero, because a
  failing runner prints its epilogue after the diagnosis, putting the cause just
  above a three-line cut. Whitespace-collapsed for one-line EDN readability."
  [code out]
  (let [failed? (not= 0 code)
        keep-lines (if failed? gate-detail-lines-failed gate-detail-lines)
        keep-chars (if failed? gate-detail-max-failed gate-detail-max)
        lines (->> (str/split-lines (str/trim (str out)))
                   (map str/trim)
                   (remove str/blank?))
        tail (str/join " | " (take-last keep-lines lines))
        tail (str/replace tail #"\s+" " ")
        tail (if (> (count tail) keep-chars)
               (str "…" (subs tail (- (count tail) keep-chars)))
               tail)]
    (if (str/blank? tail)
      (str "exit " code " — (no output)")
      (str "exit " code " — " tail))))

(defn make-receipt
  "Build an unsigned receipt over a subject and its checks.
  subject: {:repo .. :pin ..} | {:fleet-head cid}.
  checks:  [{:name kw :outcome :pass|:fail :detail any}].
  required: #{check-name ...} (checks that MUST pass)."
  [{:keys [subject checks required policy at parent]}]
  (let [{:keys [passed outcome]} (verdict checks (or required #{}))]
    {:ci/subject subject
     :ci/checks (vec checks)
     :ci/required (or required #{})
     :ci/passed passed
     :ci/outcome outcome
     :ci/policy policy
     :ci/at at
     :ci/parent parent}))

(defn receipt-cid [hash-fn receipt] (hash-fn (canonical-str receipt)))

(defn sign-receipt
  "-> {:receipt r :cid .. :signature .. :signer ..} (sign-fn injected)."
  [hash-fn sign-fn signer receipt]
  {:receipt receipt
   :cid (receipt-cid hash-fn receipt)
   :signature (sign-fn (canonical-str receipt))
   :signer signer})

(defn verify-receipt
  "Recompute the CID, verify the signature, and re-derive the verdict from the
  recorded checks — a receipt cannot claim :pass if a required check failed.
  -> {:ok? bool :reasons [..]}"
  [hash-fn verify-fn {:keys [receipt cid signature signer]} pubkey]
  (let [reasons
        (cond-> []
          (not= cid (receipt-cid hash-fn receipt)) (conj :cid-mismatch)
          (not (verify-fn pubkey (canonical-str receipt) signature)) (conj :bad-signature)
          (not= (:ci/outcome receipt)
                (:outcome (verdict (:ci/checks receipt) (:ci/required receipt))))
          (conj :outcome-inconsistent-with-checks))]
    (if (seq reasons) {:ok? false :reasons reasons} {:ok? true :reasons []})))
