(ns brep.assembly
  "Assembly management: part instances, constraints, BOM extraction.
  Restored from kami-cad's `assembly` module (deleted PR #82). A world
  transform (`DAffine3` in the original) is opaque data here — assembly
  `solve` only validates constraint instance references, it never reads
  transform contents (matches the original: the constraint solver itself
  is a documented TODO, iterative Newton-Raphson on 6-DOF transforms).")

(defn affine3-identity [] :identity)

(defn part-ref [solid-id name] {:solid-id solid-id :name name})

(defn part-instance [id part-ref transform name]
  {:id id :part-ref part-ref :transform transform :name name :suppressed false})

;; AssemblyConstraint variants
(defn mate-constraint [instance-a face-a instance-b face-b]
  {:kind :mate :instance-a instance-a :face-a face-a :instance-b instance-b :face-b face-b})
(defn align-constraint [instance-a face-a instance-b face-b]
  {:kind :align :instance-a instance-a :face-a face-a :instance-b instance-b :face-b face-b})
(defn insert-constraint [instance-a face-a instance-b face-b]
  {:kind :insert :instance-a instance-a :face-a face-a :instance-b instance-b :face-b face-b})
(defn angle-constraint [instance-a face-a instance-b face-b angle]
  {:kind :angle :instance-a instance-a :face-a face-a :instance-b instance-b :face-b face-b :angle angle})
(defn distance-constraint [instance-a face-a instance-b face-b distance]
  {:kind :distance :instance-a instance-a :face-a face-a :instance-b instance-b :face-b face-b :distance distance})

(defn bom-entry [part-name quantity] {:part-name part-name :quantity quantity})

(defn assembly
  "A fresh, empty assembly named `name`."
  [name]
  {:name name :instances [] :constraints [] :next-instance-id 1})

(defn add-instance
  "Add a part instance at `transform`. Returns `[id assembly']`."
  [asm part-ref transform name]
  (let [id (:next-instance-id asm)]
    [id (-> asm
            (update :instances conj (part-instance id part-ref transform name))
            (update :next-instance-id inc))]))

(defn add-constraint [asm constraint] (update asm :constraints conj constraint))

(defn- constraint-instances [c] [(:instance-a c) (:instance-b c)])

(defn solve
  "Validate all constraints reference existing instances. Returns
  `[:ok asm]` or `[:error msg]` (asm unchanged — matches the original:
  validation only, no actual transform solving yet)."
  [asm]
  (let [ids (into #{} (map :id (:instances asm)))]
    (loop [constraints (:constraints asm)]
      (if (empty? constraints)
        [:ok asm]
        (let [[a b] (constraint-instances (first constraints))]
          (cond
            (not (ids a)) [:error (str "instance " a " not found")]
            (not (ids b)) [:error (str "instance " b " not found")]
            :else (recur (rest constraints))))))))

(defn get-bom
  "Bill of materials: non-suppressed instances aggregated by part name,
  sorted alphabetically."
  [asm]
  (let [counts (reduce (fn [m inst]
                          (if (:suppressed inst)
                            m
                            (update m (:name (:part-ref inst)) (fnil inc 0))))
                        {} (:instances asm))]
    (vec (sort-by :part-name (map (fn [[name qty]] (bom-entry name qty)) counts)))))

(defn instances [asm] (:instances asm))
(defn constraints [asm] (:constraints asm))
(defn active-count [asm] (count (remove :suppressed (:instances asm))))

;; ---------------------------------------------------------------------------
;; Translation-only constraint solving (2026-07-27).
;;
;; `solve` above validates that constraints reference existing instances and
;; nothing else — the namespace docstring is explicit that "the constraint
;; solver itself is a documented TODO, iterative Newton-Raphson on 6-DOF
;; transforms". That is honest, but it means adding constraints to an assembly
;; changes nothing geometrically, so a caller can believe an assembly is
;; constrained when it is not.
;;
;; A full 6-DOF solver is a real project. What is added here is the subset that
;; covers axis-aligned mechanical assembly — the case that actually occurs when
;; parts bolt to a chassis: **translation only, along one coordinate axis, with
;; explicit numeric targets.** Rotation is untouched and explicitly refused.
;;
;; Constraint semantics implemented (all take `:axis` 0|1|2 and operate on
;; `{:translate [x y z]}` transforms):
;;   :distance  — instance-b's axis coordinate is set to a's plus `:distance`
;;   :mate      — coincident along the axis (distance 0)
;;   :align     — same as mate here; a distinct meaning needs face geometry
;;
;; Solving is Gauss-Seidel sweeps over the constraint list: each pass moves the
;; dependent instance to satisfy its constraint, repeated until the largest
;; correction falls under `tol` or `max-iters` is hit. For a consistent,
;; non-cyclic set this converges in one pass; cycles either converge to a
;; compromise or hit the iteration cap, and the cap being hit is REPORTED, not
;; swallowed — an unconverged solve returns `:unconverged` with the residual.
;; ---------------------------------------------------------------------------

(defn- translate-of [inst]
  (let [t (:transform inst)]
    (if (and (map? t) (vector? (:translate t))) (mapv double (:translate t)) nil)))

(def solvable-kinds
  "Constraint kinds `solve-translations` understands. Anything else present in
  the assembly makes the solve refuse rather than ignore it."
  #{:mate :align :distance})

(defn solve-translations
  "Solve axis-aligned translation constraints. Returns
  `{:status :ok|:unconverged|:error :assembly asm' :iterations n :residual r
    :message msg}`.

  Requirements, each of which produces `:error` rather than a quiet skip:
  - every instance transform is `{:translate [x y z]}` (`:identity` is not a
    translation this solver can move — make it explicit)
  - every constraint kind is in `solvable-kinds`
  - every constraint carries an `:axis` of 0, 1 or 2

  Rotation is never modified. `:angle` and `:insert` constraints are refused
  by the kind check above, because honouring them needs orientation."
  ([asm] (solve-translations asm 1e-9 64))
  ([asm tol max-iters]
   (let [insts (:instances asm)
         ids (into #{} (map :id insts))
         bad-tf (remove translate-of insts)
         cs (:constraints asm)
         bad-kind (remove #(solvable-kinds (:kind %)) cs)
         bad-axis (remove #(#{0 1 2} (:axis %)) cs)
         missing (remove (fn [c] (and (ids (:instance-a c)) (ids (:instance-b c)))) cs)]
     (cond
       (seq bad-tf)
       {:status :error :assembly asm
        :message (str "solve-translations: instance(s) "
                      (mapv :id bad-tf)
                      " have no {:translate [x y z]} transform")}

       (seq missing)
       {:status :error :assembly asm
        :message (str "solve-translations: constraint references unknown instance: "
                      (first missing))}

       (seq bad-kind)
       {:status :error :assembly asm
        :message (str "solve-translations: unsupported constraint kind(s) "
                      (vec (distinct (map :kind bad-kind)))
                      " — only " (vec (sort solvable-kinds))
                      " are solvable (rotation is not implemented)")}

       (seq bad-axis)
       {:status :error :assembly asm
        :message "solve-translations: every constraint needs :axis 0, 1 or 2"}

       :else
       (loop [pos (into {} (map (juxt :id translate-of)) insts)
              iter 0]
         (let [[pos' worst]
               (reduce
                (fn [[p w] c]
                  (let [a (:instance-a c) b (:instance-b c)
                        ax (:axis c)
                        d (double (case (:kind c) :distance (or (:distance c) 0.0) 0.0))
                        target (+ (nth (p a) ax) d)
                        cur (nth (p b) ax)
                        delta (- target cur)]
                    [(assoc p b (assoc (p b) ax target))
                     (max w (Math/abs delta))]))
                [pos 0.0] cs)]
           (if (or (<= worst tol) (>= iter max-iters))
             {:status (if (<= worst tol) :ok :unconverged)
              :iterations (inc iter)
              :residual worst
              :message (if (<= worst tol)
                         "converged"
                         (str "hit max-iters " max-iters " with residual " worst
                              " — the constraint set is likely cyclic or"
                              " over-determined"))
              :assembly
              (assoc asm :instances
                     (mapv (fn [i] (assoc i :transform {:translate (pos' (:id i))})) insts))}
             (recur pos' (inc iter)))))))))
