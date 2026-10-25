(ns vhdl.parser
  "Simplified line-based parser for a tiny textual subset of VHDL: entity
  declarations (`entity <name> is` / `port ( ... );` / `end entity`) and
  architecture bodies (`architecture <name> of <entity> is` /
  `signal <name> : <type>;` / `process(<sensitivity list>)` /
  `end process` / `end architecture`).

  Not a general VHDL parser: one statement per line, no nested blocks
  beyond a single port/process region, no expressions or statement
  semantics."
  (:require [kotoba.lang.text :as str]))

(defn- blank-or-comment?
  [line]
  (or (str/blank? line) (str/starts-with? line "--")))

(defn- source-lines
  [text]
  (->> (str/split-lines text)
       (map str/trim)
       (remove blank-or-comment?)))

(def ^:private entity-open-re #"(?i)^entity\s+(\S+)\s+is\b")
(def ^:private entity-end-re #"(?i)^end\s+entity\b")
(def ^:private port-open-re #"(?i)^port\s*\(")
(def ^:private port-close-re #"^\)\s*;")
(def ^:private port-decl-re #"(?i)^(\S+)\s*:\s*(in|out|inout|buffer)\s+([^;]+);")

(defn parse-entity
  "Parse a simplified VHDL entity declaration into
  {:name ... :ports [{:name :mode :type} ...]}. Text may contain other
  constructs (e.g. an architecture body); non-entity lines are ignored."
  [text]
  (:result
   (reduce
    (fn [{:keys [in-ports? done?] :as acc} line]
      (cond
        done? acc

        (re-find entity-end-re line)
        (assoc acc :done? true :in-ports? false)

        (re-find entity-open-re line)
        (assoc-in acc [:result :name] (second (re-find entity-open-re line)))

        (re-find port-open-re line)
        (assoc acc :in-ports? true)

        (and in-ports? (re-find port-close-re line))
        (assoc acc :in-ports? false)

        (and in-ports? (re-find port-decl-re line))
        (let [[_ pname mode type] (re-find port-decl-re line)]
          (update-in acc [:result :ports] (fnil conj [])
                     {:name pname
                      :mode (keyword (str/lower mode))
                      :type (str/trim type)}))

        :else acc))
    {:result {:name nil :ports []}}
    (source-lines text))))

(def ^:private arch-open-re #"(?i)^architecture\s+(\S+)\s+of\s+(\S+)\s+is\b")
(def ^:private arch-end-re #"(?i)^end\s+architecture\b")
(def ^:private signal-re #"(?i)^signal\s+(\S+)\s*:\s*([^;]+);")
(def ^:private process-open-re #"(?i)^(?:(\S+)\s*:\s*)?process\s*\(([^)]*)\)")
(def ^:private process-end-re #"(?i)^end\s+process\b")
(def ^:private begin-re #"(?i)^begin\b")

(defn- split-sensitivity-list
  [s]
  (->> (str/split s #",")
       (map str/trim)
       (remove str/blank?)))

(defn parse-architecture
  "Parse a simplified VHDL architecture body into
  {:name ... :entity-name ... :signals [...] :processes [...]}. Text may
  contain other constructs (e.g. an entity declaration); non-architecture
  lines are ignored."
  [text]
  (:result
   (reduce
    (fn [{:keys [in-process done?] :as acc} line]
      (cond
        done? acc

        (re-find arch-end-re line)
        (cond-> (assoc acc :done? true)
          in-process (-> (update-in [:result :processes] conj in-process)
                         (dissoc :in-process)))

        (re-find arch-open-re line)
        (let [[_ aname ename] (re-find arch-open-re line)]
          (-> acc
              (assoc-in [:result :name] aname)
              (assoc-in [:result :entity-name] ename)))

        (re-find signal-re line)
        (let [[_ sname stype] (re-find signal-re line)]
          (update-in acc [:result :signals] (fnil conj [])
                     {:name sname :type (str/trim stype)}))

        (re-find process-open-re line)
        (let [[_ pname sens] (re-find process-open-re line)]
          (assoc acc :in-process {:name pname
                                   :sensitivity-list (split-sensitivity-list sens)
                                   :statement-count 0}))

        (and in-process (re-find process-end-re line))
        (-> acc
            (update-in [:result :processes] (fnil conj []) in-process)
            (dissoc :in-process))

        (and in-process (re-find begin-re line))
        acc

        in-process
        (update-in acc [:in-process :statement-count] inc)

        :else acc))
    {:result {:name nil :entity-name nil :signals [] :processes []}}
    (source-lines text))))

(defn parse-design
  "Parse a text containing both an entity declaration and an architecture
  body into {:entity {...} :architecture {...}}."
  [text]
  {:entity (parse-entity text)
   :architecture (parse-architecture text)})
