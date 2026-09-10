(ns kotoba.doctor
  "The repairs `kotoba doctor` applies to a converted tree, as portable code.

   The owner's Q9 procedure is rename FIRST and fix afterwards with the
   toolchain. `kotoba adl convert` does the renaming half. This is the other
   half: given what `amu check` says about a module, produce the edited source
   that removes that class of failure -- or say why it cannot.

   Portable `.cljc` on purpose. Deciding what a module publishes and rewriting
   its `ns` form is a source transform over a CST and needs no host: only the
   driver in `bin/kotoba_doctor.cljs` walks directories and runs amu, and only
   because nbb is what can do those things here. Keeping the transform out of
   the driver is what makes the controls in `test/kotoba/doctor_test.cljc`
   possible at all -- a repair buried in a CLI can only be tested by running
   the CLI, and then every control also depends on amu being installed.

   Two rules the repairs are built on, both of them measured rather than
   assumed (2026-09-10, against amu 94e9c29b):

     A repair NEVER narrows the module's public surface to satisfy a check.
     `(:export [])` would pass amu's presence test while publishing nothing,
     and a module that links because it exports less than its source did is
     the shape Q9's whole-component rule exists to forbid.

     A repair is JUDGED BY amu, not by having been written. That check lives
     in the driver, because it is the part that needs a subprocess."
  (:require [kotoba.adl.reader :as r]
            [clojure.string :as str]))

(def export-missing
  "amu's message for the class `repair-missing-export` targets.

   Keyed on amu's own words. If the message is reworded upstream the repair
   stops matching and the class reappears in the work list -- visible, and
   preferable to a repair that keeps firing on a rule that has moved."
  "project module requires an explicit :export vector")

(defn ns-node
  "The (ns ...) form of a CST, or nil."
  [nodes]
  (some (fn [n]
          (when (and (= :coll (:t n)) (= :list (:kind n)))
            (let [fs (r/forms (:children n))]
              (when (= "ns" (some-> (first fs) :s)) n))))
        nodes))

(defn- private-form?
  "A def/defn the module does not publish.

   `defn-` and a `^:private` metadata node both mean private. The metadata
   case is read off the CST rather than by scanning text: `^:private` inside a
   docstring is a string, and a text scan cannot tell those apart."
  [head second-node]
  (or (contains? #{"defn-" "def-"} head)
      (and second-node
           (= :meta (:t second-node))
           (some #(= ":private" (:s %)) (r/forms (:children second-node))))))

(defn public-definitions
  "What this module publishes, split into functions and non-function values.

   The split is not cosmetic. amu requires every export to name a declared
   FUNCTION and says so precisely -- measured 2026-09-10:

     namespace exports must name declared public functions: answer is a def
     constant, not a function; export a function that returns it: write
     (defn answer [] 42) in place of (def answer 42)

   so a public `def` of a value cannot go in the vector. It is returned rather
   than dropped, because exporting only the functions would produce a module
   that links while publishing less than its source did."
  [nodes]
  (reduce
   (fn [acc n]
     (if-not (and (= :coll (:t n)) (= :list (:kind n)))
       acc
       (let [fs (r/forms (:children n))
             head (str (some-> (first fs) :s))
             nm (second fs)]
         (cond
           (not (contains? #{"defn" "defn-" "def" "def-"} head)) acc
           (private-form? head nm) acc
           (nil? nm) acc
           :else
           (let [sym (if (= :meta (:t nm)) (last (r/forms (:children nm))) nm)
                 s (:s sym)]
             (if (str/blank? (str s))
               acc
               (update acc (if (= "defn" head) :functions :values) conj s)))))))
   {:functions [] :values []}
   nodes))

(defn- export-clause-node [names]
  {:t :coll :kind :list
   :children [{:t :atom :kind :keyword :s ":export"}
              {:t :ws :s " "}
              {:t :coll :kind :vector
               :children (vec (interpose {:t :ws :s " "}
                                         (map (fn [s] {:t :atom :kind :symbol :s s})
                                              names)))}]})

(defn insert-export
  "NODES with (:export [...]) added to the ns form, or nil if there is none.

   The edit is made on the CST and printed back, so every byte outside the ns
   form is carried across untouched -- `print-cst` is the identity on what
   `read-cst` read. The caller checks that on the file in hand rather than
   taking the docstring's word for it."
  [nodes names]
  (when-let [nsn (ns-node nodes)]
    (let [kids (vec (:children nsn))
          last-form-idx (last (keep-indexed (fn [i n] (when-not (r/trivia? n) i)) kids))]
      (when last-form-idx
        (let [kids* (into (subvec kids 0 (inc last-form-idx))
                          (concat [{:t :ws :s "\n  "} (export-clause-node names)]
                                  (subvec kids (inc last-form-idx))))]
          (mapv #(if (identical? % nsn) (assoc nsn :children kids*) %) nodes))))))

(defn fidelity-ok?
  "Does the CST round-trip this source byte for byte?

   A repair relies on that for every byte it did not mean to touch, so it is
   checked on THIS file rather than assumed from `print-cst`'s docstring."
  [txt]
  (try (= txt (r/print-cst (r/read-cst txt :source))) (catch #?(:clj Exception :cljs :default) _ false)))

(defn repair-missing-export
  "Add the :export vector this module needs, or say why not.

   {:text .. :names [..]} on success, {:skip <reason>} otherwise. It never
   returns an empty vector: see this namespace's docstring."
  [txt]
  (let [nodes (try (r/read-cst txt :source) (catch #?(:clj Exception :cljs :default) _ nil))]
    (cond
      (nil? nodes) {:skip :unparseable-source}
      (nil? (ns-node nodes)) {:skip :no-ns-form}
      :else
      (let [{:keys [functions values]} (public-definitions nodes)]
        (cond
          (seq values) {:skip :public-def-is-not-a-function}
          (empty? functions) {:skip :no-public-definitions}
          :else
          (if-let [nodes* (insert-export nodes functions)]
            {:text (r/print-cst nodes*) :names functions}
            {:skip :ns-form-not-editable}))))))

(def repairs
  "amu's message -> the repair for that class."
  {export-missing repair-missing-export})

(defn repair-progressed?
  "Did the repair remove the class it targets FROM THIS FILE?

   Not `did the file come out clean`. Measured 2026-09-10: judging on
   cleanliness kept ZERO of fourteen correct repairs. Adding `(:export
   [union])` to kotoba.set.union does admit the clause, and amu then refuses
   the module further in for a variadic parameter -- a second, unrelated
   defect the export repair was never going to reach. Requiring a clean file
   means only modules with exactly one defect can ever be repaired, which is
   not fixing forward.

   What keeps that honest is the other arm: if the finding is unchanged, the
   edit did nothing and the driver undoes it.

   ⚠ `:source` is necessary and NOT sufficient. In project mode amu links the
   whole graph, so a module is refused because a module it REQUIRES is
   refused -- and measured the same day, the diagnostic then names the ENTRY
   amu was asked about, not the module actually missing its vector. So this
   predicate cannot untangle ordering, and the driver does not ask it to:
   every repair is applied before any of them is re-checked."
  [before after this-file-basename]
  (or (true? (:ok? after))
      (not= (:message after) (:message before))
      (let [s (:source after)]
        (and (some? s) (not= s this-file-basename)))))
