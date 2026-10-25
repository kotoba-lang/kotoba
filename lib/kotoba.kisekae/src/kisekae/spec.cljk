(ns kisekae.spec
  "The character-spec document: what a user chose in the editor, as plain EDN
   (ADR-2607071610). This is the persisted unit — a kisekae character is NOT a
   .vrm file in a bucket; it's this small, diffable, datomic-friendly EDN value,
   from which `kisekae.build` deterministically reproduces the .vrm on demand
   via kotoba-lang/org-vrmc-vrm's decompose/compose/export engine.

   Dress-up semantics: `:spec/base` names a full VRM avatar (by URL); each entry
   in `:spec/parts` overrides ONE part-kind of the base (hair/outfit/accessory/
   face) with the matching part from a donor VRM. `:body` is deliberately NOT
   overridable — the base's body is the canonical skeleton `vrm.compose/compose`
   unifies everything onto (its `:skeleton-base`), and swapping skeletons is a
   rigging problem this editor does not pretend to solve.

   Part kinds come from `vrm.part/part-categories`, not a separate list here —
   the editor's vocabulary and the engine's classifier share one source of
   truth, so a spec can never name a kind `decompose` won't produce.

   .cljc: pure data + pure functions, no platform code, no interop — per the
   repo-wide runtime-priority rule (kototama > cljs > nbb > JVM), everything in
   this namespace stays in the interop-free subset. Executes on cljs today;
   kototama when its runtime lands (no #?(:kototama) exists yet — ADR notes)."
  (:require [vrm.part :as part]))

(def spec-version 1)

(def overridable-kinds
  "Part kinds a spec may override. `vrm.part/part-categories` minus `:body`
   (skeleton stays with the base — see ns docstring) and minus `:other`
   (the classifier's fallback bucket, not a user-meaningful part)."
  (disj part/part-categories :body :other))

(defn new-spec
  "A fresh character spec. `base-vrm-url` is the full avatar the dress-up
   starts from; everything else starts empty."
  [{:keys [id name base-vrm-url]}]
  {:spec/version spec-version
   :spec/id id
   :spec/name (or name "untitled")
   :spec/base {:vrm/url base-vrm-url}
   :spec/parts []
   :spec/material-edits []
   :spec/expression-edits []
   :spec/meta {:meta/authors [] :meta/license-url nil}})

(defn problems
  "Structural validation: spec -> seq of problem keywords (empty = valid).
   A seq (not a boolean) so an editor UI can show every issue at once."
  [{:spec/keys [version id base parts material-edits expression-edits] :as spec}]
  (concat
   (when-not (= spec-version version) [:problem/unknown-spec-version])
   (when-not id [:problem/missing-id])
   (when-not (string? (:vrm/url base)) [:problem/missing-base-url])
   (when-not (map? spec) [:problem/not-a-map])
   (keep (fn [{:part/keys [kind source]}]
           (cond
             (not (contains? overridable-kinds kind)) :problem/part-kind-not-overridable
             (not (string? (:vrm/url source))) :problem/part-missing-source-url
             :else nil))
         parts)
   (keep (fn [{:material/keys [index base-color]}]
           (cond
             (not (nat-int? index)) :problem/material-index-not-nat-int
             (not (and (vector? base-color) (= 4 (count base-color))
                       (every? number? base-color)))
             :problem/material-color-not-rgba
             :else nil))
         material-edits)
   (keep (fn [{:expression/keys [name weight]}]
           (when-not (and (keyword? name) (number? weight) (<= 0 weight 1))
             :problem/expression-invalid))
         expression-edits)))

(defn valid? [spec] (empty? (problems spec)))

(defn overridden-kinds
  "The set of part kinds this spec overrides."
  [spec]
  (into #{} (map :part/kind) (:spec/parts spec)))

(defn part-urls
  "Every VRM URL the spec references (base first, then donors, distinct) —
   the fetch list a caller must resolve into `docs-by-url` before
   `kisekae.build` can run."
  [spec]
  (into [(get-in spec [:spec/base :vrm/url])]
        (distinct (remove #(= % (get-in spec [:spec/base :vrm/url]))
                          (map #(get-in % [:part/source :vrm/url]) (:spec/parts spec))))))
