(ns ddl.ddl
  "CREATE TABLE SQL ⇄ DDL-as-EDN schema. Zero third-party deps, portable .cljc.

  parse-str handles one or more ';'-terminated CREATE TABLE [IF NOT EXISTS] statements
  with:
    - '--' line comments (stripped before parsing)
    - Column defs: name TYPE [NOT NULL] [PRIMARY KEY] [DEFAULT <lit>]
    - Types with precision/scale: VARCHAR(255), NUMERIC(10,2)
    - Table-level: PRIMARY KEY (cols), FOREIGN KEY (cols) REFERENCES t (cols)
    - Case-insensitive SQL keywords

  emit-str generates portable CREATE TABLE SQL that round-trips through parse-str."
  (:require [kotoba.lang.text :as str]))

;; --- internal: character access portable across JVM and CLJS ---

(defn- ch
  "Character at position i as a single-char string — portable across JVM and CLJS."
  [s i]
  (subs s i (inc i)))

;; --- strip line comments ---

(defn- strip-comments
  "Remove -- … end-of-line comments from sql."
  [sql]
  (str/replace sql #"--[^\n]*" ""))

;; --- find matching closing paren ---

(defn- find-body-end
  "Return the index of the ')' that closes the '(' at open-idx, accounting for nesting.
  Returns nil if the string ends before the match."
  [s open-idx]
  (loop [i (inc open-idx) depth 1]
    (when (< i (count s))
      (let [c (ch s i)]
        (cond
          (= c "(") (recur (inc i) (inc depth))
          (= c ")") (if (= depth 1) i (recur (inc i) (dec depth)))
          :else      (recur (inc i) depth))))))

;; --- split body by top-level commas ---

(defn- split-top-level
  "Split string s by commas that are not inside parentheses.
  Returns a vector of trimmed, non-empty parts."
  [s]
  (loop [i 0 depth 0 start 0 parts []]
    (if (>= i (count s))
      (let [part (str/trim (subs s start))]
        (if (seq part) (conj parts part) parts))
      (let [c (ch s i)]
        (cond
          (= c "(") (recur (inc i) (inc depth) start parts)
          (= c ")") (recur (inc i) (dec depth) start parts)
          (and (= c ",") (= depth 0))
          (let [part (str/trim (subs s start i))]
            (recur (inc i) depth (inc i)
                   (if (seq part) (conj parts part) parts)))
          :else (recur (inc i) depth start parts))))))

;; --- column definition parser ---

(def ^:private col-re
  "Matches: colname TYPE[(n)] rest  or  colname TYPE[(n,m)] rest"
  #"(?i)^(\w+)\s+([\w]+(?:\s*\(\s*\d+\s*(?:,\s*\d+\s*)?\))?)(.*)")

(defn- parse-column-def
  "Parse a single column-definition fragment into a column map, or nil if not a column."
  [s]
  (when-let [[_ col-name col-type rest-str] (re-find col-re (str/trim s))]
    (let [rest-upper (str/upper rest-str)
          not-null?  (boolean (re-find #"\bNOT\s+NULL\b" rest-upper))
          pk?        (boolean (re-find #"\bPRIMARY\s+KEY\b" rest-upper))
          default-m  (re-find #"(?i)\bDEFAULT\s+(\S+)" rest-str)]
      {:ddl/name     col-name
       :ddl/type     (str/trim col-type)
       :ddl/nullable (not not-null?)
       :ddl/pk       pk?
       :ddl/default  (when default-m (second default-m))})))

;; --- table-level constraint parsers ---

(defn- parse-pk-constraint
  "Parse PRIMARY KEY (col, ...) → [\"col\" ...] or nil."
  [s]
  (when-let [[_ cols] (re-find #"(?i)PRIMARY\s+KEY\s*\(([^)]+)\)" s)]
    (mapv str/trim (str/split cols #","))))

(defn- parse-fk-constraint
  "Parse FOREIGN KEY (cols) REFERENCES t (cols) → fk map or nil."
  [s]
  (when-let [[_ cols ref-tbl ref-cols]
             (re-find #"(?i)FOREIGN\s+KEY\s*\(([^)]+)\)\s+REFERENCES\s+(\w+)\s*\(([^)]+)\)" s)]
    {:ddl/columns     (mapv str/trim (str/split cols #","))
     :ddl/ref-table   ref-tbl
     :ddl/ref-columns (mapv str/trim (str/split ref-cols #","))}))

;; --- parse-str ---

(defn parse-str
  "Parse one or more CREATE TABLE SQL statements into a DDL schema map.
  Statements must be ';'-terminated. '--' line comments are stripped."
  [sql]
  (let [sql   (strip-comments sql)
        stmts (str/split sql #";")]
    (reduce
     (fn [schema stmt]
       (let [stmt (str/trim stmt)]
         (if-let [[_ tbl-name] (re-find #"(?i)CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s*\(" stmt)]
           (let [open-idx  (str/index-of stmt "(")
                 close-idx (find-body-end stmt open-idx)]
             (if-not close-idx
               schema
               (let [body       (subs stmt (inc open-idx) close-idx)
                     parts      (split-top-level body)
                     cols       (volatile! [])
                     pk-ovrd    (volatile! nil)
                     fks        (volatile! [])]
                 (doseq [part parts]
                   (let [p  (str/trim part)
                         pu (str/upper p)]
                     (cond
                       (str/starts-with? pu "PRIMARY KEY")
                       (when-let [pk (parse-pk-constraint p)]
                         (vreset! pk-ovrd pk))

                       (str/starts-with? pu "FOREIGN KEY")
                       (when-let [fk (parse-fk-constraint p)]
                         (vswap! fks conj fk))

                       ;; skip CONSTRAINT keyword lines (named constraints)
                       (str/starts-with? pu "CONSTRAINT")
                       nil

                       ;; anything else — attempt column parse
                       :else
                       (when-let [col (parse-column-def p)]
                         (vswap! cols conj col)))))
                 (let [cols-vec @cols
                       ;; If table-level PK constraint, override inline :ddl/pk flags
                       cols-vec (if-let [pk @pk-ovrd]
                                  (let [pk-set (set pk)]
                                    (mapv #(assoc % :ddl/pk (boolean (pk-set (:ddl/name %))))
                                          cols-vec))
                                  cols-vec)
                       pk       (or @pk-ovrd
                                    (vec (keep #(when (:ddl/pk %) (:ddl/name %)) cols-vec)))
                       tbl      {:ddl/name         tbl-name
                                 :ddl/columns      cols-vec
                                 :ddl/primary-key  pk
                                 :ddl/foreign-keys @fks}]
                   (assoc-in schema [:ddl/tables tbl-name] tbl)))))
           schema)))
     {:ddl/tables {}}
     stmts)))

;; --- emit helpers ---

(defn- emit-col-def
  "Emit one column definition line (no leading indent)."
  [col pk-set multi-pk?]
  (str (:ddl/name col)
       " " (:ddl/type col)
       (when (false? (:ddl/nullable col)) " NOT NULL")
       (when (and (not multi-pk?) (contains? pk-set (:ddl/name col))) " PRIMARY KEY")
       (when-let [d (:ddl/default col)] (str " DEFAULT " d))))

(defn emit-table
  "Emit a single CREATE TABLE statement from a table map."
  [tbl]
  (let [pk       (:ddl/primary-key tbl)
        pk-set   (set pk)
        multi?   (> (count pk) 1)
        col-defs (mapv #(str "  " (emit-col-def % pk-set multi?)) (:ddl/columns tbl))
        pk-line  (when multi? (str "  PRIMARY KEY (" (str/join ", " pk) ")"))
        fk-lines (mapv (fn [fk]
                         (str "  FOREIGN KEY ("
                              (str/join ", " (:ddl/columns fk))
                              ") REFERENCES " (:ddl/ref-table fk)
                              " (" (str/join ", " (:ddl/ref-columns fk)) ")"))
                       (:ddl/foreign-keys tbl))
        all-defs (concat col-defs (when pk-line [pk-line]) fk-lines)]
    (str "CREATE TABLE " (:ddl/name tbl) " (\n"
         (str/join ",\n" all-defs)
         "\n);")))

(defn emit-str
  "Emit CREATE TABLE SQL for all tables in a schema (sorted by name)."
  [schema]
  (str/join "\n\n"
            (map emit-table (sort-by :ddl/name (vals (:ddl/tables schema))))))
