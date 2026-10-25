(ns kisekae.build
  "spec -> VrmDocument -> .vrm bytes, via kotoba-lang/org-vrmc-vrm's engine
   (ADR-2607071610). This namespace is the bridge between the editor's small
   EDN spec and the real VRM pipeline:

     docs-by-url (caller fetches)          kisekae.spec
            \\                                /
             `-> effective-sources <--------'      (pure selection)
                       |
                 vrm.compose/compose               (skeleton unification, engine)
                       |
              apply-material-edits, apply-meta     (pure doc transforms)
                       |
                 vrm.export/export-glb             (bytes, engine)

   Everything here is pure GIVEN the fetched documents — `docs-by-url` is
   `{url VrmDocument}`, resolved by the caller (browser `fetch` + `vrm.parse`
   in an app; a fixture map in tests). No I/O in this namespace, matching the
   engine's own zero-dep discipline and keeping the whole build path in the
   interop-free .cljc subset (runtime-priority note in kisekae.spec).

   Missing anything (an unfetched URL, a donor VRM with no part of the
   requested kind) THROWS ex-info — a build that silently substitutes parts
   would hand the user a character they didn't design."
  (:require [kisekae.spec :as spec]
            [vrm.part :as part]
            [vrm.compose :as compose]
            [vrm.export :as export]
            [vrm.vrm-types :as vt]))

(defn- doc-for [docs-by-url url]
  (or (get docs-by-url url)
      (throw (ex-info "kisekae: document not fetched" {:url url}))))

(defn- find-part [parts kind url]
  (or (first (filter #(= kind (:category %)) parts))
      (throw (ex-info "kisekae: donor VRM has no part of requested kind"
                      {:kind kind :url url :available (mapv :category parts)}))))

(defn effective-sources
  "spec + docs-by-url -> {:sources [{:part VrmPart :doc VrmDocument} ...]
                          :skeleton-base <index into :sources>}

   Dress-up resolution: the base avatar contributes every part EXCEPT the
   kinds the spec overrides; each override contributes exactly the matching
   part from its donor document.

   Skeleton anchor: every part decomposed from the SAME base document already
   references that document's one shared armature, so ANY base part can be the
   `:skeleton-base` compose unifies onto — it does not have to be `:body`. An
   earlier version required a `:body` part and threw when none existed; that
   was wrong for real avatars whose body skin classifies as `:other` rather
   than `:body` (found against VRM Consortium's Seed-san, whose meshes
   decompose to hair/face/other/outfit with no `:body` — net-babiniku M6
   slice-2 compose probe, 2026-07-07). We now prefer the `:body` part as the
   anchor when present (the most natural silhouette root) and otherwise use
   the first base part; the only hard requirement is that the base contributes
   at least one part (else it anchors nothing)."
  [s docs-by-url]
  (let [base-url (get-in s [:spec/base :vrm/url])
        base-doc (doc-for docs-by-url base-url)
        base-parts (part/decompose base-doc)
        overridden (spec/overridden-kinds s)
        kept-base (vec (remove #(contains? overridden (:category %)) base-parts))
        _ (when (empty? kept-base)
            (throw (ex-info "kisekae: base VRM decomposed to no usable parts"
                            {:url base-url :decomposed (mapv :category base-parts)})))
        base-sources (mapv (fn [p] {:part p :doc base-doc}) kept-base)
        donor-sources (mapv (fn [{:part/keys [kind source]}]
                              (let [url (:vrm/url source)
                                    d (doc-for docs-by-url url)]
                                {:part (find-part (part/decompose d) kind url) :doc d}))
                            (:spec/parts s))
        sources (into base-sources donor-sources)]
    {:sources sources
     ;; prefer a :body base part as the anchor, else the first base part (index 0 —
     ;; base-sources always lead `sources`, and are non-empty per the guard above).
     :skeleton-base (or (first (keep-indexed
                                (fn [i {:keys [part doc]}]
                                  (when (and (identical? doc base-doc) (= :body (:category part))) i))
                                sources))
                        0)}))

(defn apply-material-edits
  "Apply the spec's material edits onto a composed VrmDocument. Indices are
   into the COMPOSED document's material vector (what the editor preview
   showed the user), glTF-standard baseColorFactor [r g b a]."
  [doc edits]
  (reduce (fn [d {:material/keys [index base-color]}]
            (when-not (get-in d [:gltf :materials index])
              (throw (ex-info "kisekae: material edit index out of range"
                              {:index index :materials (count (get-in d [:gltf :materials]))})))
            (assoc-in d [:gltf :materials index :pbrMetallicRoughness :baseColorFactor]
                      base-color))
          doc
          edits))

(defn apply-meta
  "Stamp the spec's name/authors/license into the document's VRM meta —
   the user's character carries THEIR meta, not the base model's (the base's
   own license must still permit this; that's a spec-authoring concern the
   consuming app surfaces, not something build can check)."
  [doc s]
  (assoc doc :meta (vt/vrm-meta {:name (:spec/name s)
                                 :authors (get-in s [:spec/meta :meta/authors])
                                 :license-url (get-in s [:spec/meta :meta/license-url])})))

(defn apply-expression-edits
  "Persist editor expression defaults as glTF extras. VRM expression bindings
   remain owned by the source documents; realtime CLJS preview applies these
   weights to the VRM expression manager without rewriting morph targets."
  [doc edits]
  (assoc-in doc [:gltf :extras :kisekaeExpressionDefaults]
            (into {} (map (juxt (comp name :expression/name) :expression/weight)) edits)))

(defn build-document
  "spec + docs-by-url -> composed, edited VrmDocument."
  [s docs-by-url]
  (let [ps (spec/problems s)]
    (when (seq ps) (throw (ex-info "kisekae: invalid spec" {:problems ps})))
    (let [{:keys [sources skeleton-base]} (effective-sources s docs-by-url)]
      (-> (compose/compose sources {:skeleton-base skeleton-base})
          (apply-material-edits (:spec/material-edits s))
          (apply-expression-edits (:spec/expression-edits s))
          (apply-meta s)))))

(defn export-bytes
  "VrmDocument -> .vrm (GLB) bytes, via the engine's exporter."
  [doc]
  (export/export-glb doc))
