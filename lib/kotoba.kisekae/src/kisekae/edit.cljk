(ns kisekae.edit
  "Pure edit operations over a character spec, plus op-log history
   (ADR-2607071610). Every edit is data — `{:op/type ...}` — applied by one
   pure function, so:

   - undo/redo is a cursor over a vector of spec snapshots (no mutable
     command objects);
   - the op itself is what a collaborative/persistent layer would transact
     (an op-log is append-only, exactly the shape kotobase/datomic likes —
     see kisekae.store's docstring for the datom mapping);
   - a UI (e.g. kotoba-lang/editor's walk-and-surface controls) only ever
     dispatches ops, never touches the spec directly.

   Unknown op types THROW (ex-info), never silently no-op — an editor that
   drops an edit on the floor is corrupting user work; better to fail loudly
   (same honest-failure convention as vrm.compose's part errors).

   .cljc: pure, interop-free — see kisekae.spec's ns docstring for the
   runtime-priority note."
  (:require [kisekae.spec :as spec]))

(defn apply-op
  "spec + op -> new spec. The only way an edit happens."
  [s {:op/keys [type] :as op}]
  (case type
    :op/rename
    (assoc s :spec/name (:name op))

    :op/set-meta
    (update s :spec/meta merge (select-keys (:meta op) [:meta/authors :meta/license-url]))

    :op/set-base
    ;; Body/skeleton replacement is deliberately a base-avatar change, not a
    ;; normal part override. Compose will anchor and rebind every skin to it.
    (assoc s :spec/base {:vrm/url (:url op)})

    :op/add-part
    ;; One override per kind: adding a part for an already-overridden kind
    ;; replaces it (dress-up semantics — you wear one hair at a time).
    (let [{:part/keys [kind] :as p} (:part op)]
      (when-not (contains? spec/overridable-kinds kind)
        (throw (ex-info "kisekae: part kind not overridable" {:op op})))
      (update s :spec/parts
              (fn [parts] (conj (vec (remove #(= kind (:part/kind %)) parts)) p))))

    :op/remove-part
    (update s :spec/parts
            (fn [parts] (vec (remove #(= (:kind op) (:part/kind %)) parts))))

    :op/set-base-color
    ;; One edit per material index, latest wins — same replace-not-stack
    ;; shape as :op/add-part.
    (let [{:keys [index color]} op]
      (update s :spec/material-edits
              (fn [edits]
                (conj (vec (remove #(= index (:material/index %)) edits))
                      {:material/index index :material/base-color color}))))

    :op/set-expression
    (let [{:keys [expression weight]} op]
      (update s :spec/expression-edits
              (fn [edits]
                (conj (vec (remove #(= expression (:expression/name %)) edits))
                      {:expression/name expression :expression/weight weight}))))

    (throw (ex-info "kisekae: unknown op type" {:op op}))))

(defn apply-ops [s ops] (reduce apply-op s ops))

;; --- history: snapshot vector + cursor -------------------------------------------------
;; Pure value the UI holds in its app-db. `push` truncates any redo tail
;; (standard editor semantics: editing after an undo discards the undone
;; future). Snapshots, not diffs — specs are small EDN values; simplicity
;; over cleverness until profiling says otherwise.

(defn new-history [initial-spec] {:snapshots [initial-spec] :cursor 0})

(defn current [{:keys [snapshots cursor]}] (nth snapshots cursor))

(defn push
  "Apply `op` to the current spec and record the result."
  [{:keys [snapshots cursor] :as _h} op]
  (let [kept (subvec snapshots 0 (inc cursor))
        next-spec (apply-op (peek kept) op)]
    {:snapshots (conj kept next-spec) :cursor (inc cursor)}))

(defn can-undo? [{:keys [cursor]}] (pos? cursor))
(defn can-redo? [{:keys [snapshots cursor]}] (< cursor (dec (count snapshots))))

(defn undo [h] (if (can-undo? h) (update h :cursor dec) h))
(defn redo [h] (if (can-redo? h) (update h :cursor inc) h))
