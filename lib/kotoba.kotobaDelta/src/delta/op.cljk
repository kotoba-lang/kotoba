(ns delta.op
  "kotoba-delta — datom-native operation log for agent edits
  (ADR-2607161325; the 'Datomic-for-code-edits' answer to DeltaDB).

  Design stance vs DeltaDB (researched 2026-07-16, ADR-2607160005 P4):
  - Writers are agents emitting DISCRETE ops (Edit/Write/Remove), not human
    keystrokes — so no character-level text CRDT. Ordering comes from the
    log (transactor-style total order); convergence is by construction.
  - Conflicts are EXPLICIT (an :edit whose :op/old no longer matches is a
    first-class conflict value), never silent CRDT convergence — semantic
    conflicts can't be merged away, so surfacing beats converging.
  - Every op is Ed25519-signed by a did:key actor and parent-covering
    (op chain = tamper-evident; replay of an old op is structurally
    impossible) — the authorization layer DeltaDB says nothing about.
  - Admission rejects secret material (the 'op logs archive API keys'
    liability raised against DeltaDB) BEFORE it enters the log.
  - Conversation linkage: :op/turn ties an op to the agent conversation
    turn that produced it — provenance from prompt to line.

  Pure cljc; crypto injected ({:sign-fn :verify-fn :hash-fn}) like fleet.pin."
  (:require [kotoba.lang.text :as str]))

;; ---------------------------------------------------------------------------
;; canonical form + identity

(defn canonical-str
  "Deterministic payload (signed; :op/id = hash of this). Field order is
  protocol; changing it is a format version bump. v2 adds :op/anchor — the
  structural anchor (delta.anchor) of the definition the edit touches, so
  provenance survives code motion, not just a file path."
  [{:op/keys [parent actor at kind file old new turn anchor]}]
  (pr-str ["kotoba-delta/v2" parent actor at (name kind) file old new turn anchor]))

(defn op-id [hash-fn op] (hash-fn (canonical-str op)))

(defn make-op
  [{:keys [parent actor at kind file old new turn anchor]}]
  (cond-> {:op/parent parent :op/actor actor :op/at at
           :op/kind kind :op/file file}
    (some? old)    (assoc :op/old old)
    (some? new)    (assoc :op/new new)
    (some? turn)   (assoc :op/turn turn)
    (some? anchor) (assoc :op/anchor anchor)))

(defn log-head
  "The op-log head = the id of the last op (or nil for an empty log). This is
  what folds into the signed fleet head (ADR-2607160005): a fleet head over
  fleet-db content + the op-log head certifies the manifest AND the edit
  provenance together."
  [hash-fn ops]
  (when (seq ops) (op-id hash-fn (last ops))))

;; ---------------------------------------------------------------------------
;; admission (secrets redaction + signature + chain)

(def secret-patterns
  "Reject-before-log patterns. Deliberately conservative — false positives
  are cheaper than archiving a credential in an append-only log."
  [#"-----BEGIN [A-Z ]*PRIVATE KEY-----"
   #"AKIA[0-9A-Z]{16}"
   #"ghp_[A-Za-z0-9]{36}"
   #"sk-[A-Za-z0-9_-]{20,}"
   #"xox[baprs]-[A-Za-z0-9-]{10,}"
   #"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*[\"']?[A-Za-z0-9+/_-]{20,}"])

(defn secret-material? [s]
  (boolean (and s (some #(re-find % s) secret-patterns))))

(defn admit
  "Admission for a signed op proposal {:op .. :sig ..}.
  ctx: {:head {:op .. :sig ..} | nil   — last accepted op (whole log head)
        :verify-fn (fn [pubkey-hex payload sig] bool)
        :hash-fn (fn [s] hex)
        :actor-pubkey hex               — resolved from :op/actor did by caller
        :grant-ok? bool}                — does the actor hold an edit grant
  -> {:verdict :accept|:reject :reasons [..]}"
  [{:keys [op sig]} {:keys [head verify-fn hash-fn actor-pubkey grant-ok?]}]
  (let [reasons
        (cond-> []
          (not grant-ok?) (conj :unauthorized-actor)
          (not (verify-fn actor-pubkey (canonical-str op) sig)) (conj :bad-signature)
          (not= (:op/parent op)
                (when head (op-id hash-fn (:op head)))) (conj :parent-mismatch)
          (or (secret-material? (:op/new op))
              (secret-material? (:op/old op))) (conj :secret-material))]
    (if (seq reasons) {:verdict :reject :reasons reasons}
        {:verdict :accept :reasons []})))

;; ---------------------------------------------------------------------------
;; replay (explicit conflicts, deterministic)

(defn apply-op
  "files (map path->content) + op -> files' | {:conflict {..}}.
  :edit requires :op/old to occur EXACTLY ONCE (Edit-tool semantics);
  zero or many occurrences is an explicit conflict, never a guess."
  [files {:op/keys [kind file old new] :as op}]
  (case kind
    :write (assoc files file new)
    :remove (if (contains? files file)
              (dissoc files file)
              {:conflict {:op op :reason :file-not-found}})
    :edit
    (let [content (get files file)]
      (if (nil? content)
        {:conflict {:op op :reason :file-not-found}}
        ;; occurrence count via index-of walk (no regex surprises)
        (let [occ (loop [i 0 c 0]
                    (if-let [j (str/index-of content old i)]
                      (recur (long (inc j)) (inc c)) c))]
          (cond
            (zero? occ) {:conflict {:op op :reason :old-not-found}}
            (> occ 1)   {:conflict {:op op :reason :ambiguous-old :occurrences occ}}
            :else (assoc files file (str/replace-first content old new))))))))

(defn replay
  "Deterministic fold of ops over an initial files map.
  -> {:files .. :applied n} | {:files .. :applied n :conflict {..}} (stops)."
  [files ops]
  (loop [files files [op & more] ops n 0]
    (if (nil? op)
      {:files files :applied n}
      (let [r (apply-op files op)]
        (if (:conflict r)
          {:files files :applied n :conflict (:conflict r)}
          (recur r more (inc n)))))))

(defn ops-by-actor
  "Return ops in log order whose :op/actor equals `actor`."
  [ops actor]
  (filter #(= (:op/actor %) actor) ops))

(defn content-hash
  "Deterministic hash of a whole files map (projection identity):
  hash of sorted [path hash-of-content] pairs."
  [hash-fn files]
  (hash-fn (pr-str (into [] (map (fn [[p c]] [p (hash-fn c)]))
                         (sort-by first files)))))
