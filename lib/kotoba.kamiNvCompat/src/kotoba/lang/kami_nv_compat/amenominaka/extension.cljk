(ns kotoba.lang.kami-nv-compat.amenominaka.extension
  "Clean-room Kit extension model (IExt + extension.toml) — JVM port of
  src/amenominaka/extension.ts. Reproduces the omni.ext.IExt lifecycle and a
  minimal-but-faithful TOML manifest parser (the subset Kit extension.toml
  files actually use). Clean-room: from-spec IExt + a hand-written TOML subset
  parser. No Kit source/binaries. ADR-2605261800 §D6 / D10.4 amenominaka.

  Wave 3 of the kami-nv-compat TS->CLJC port (ADR-2607020130). The parsed root
  keeps STRING keys (TOML keys are strings, may contain dots like dependency
  ids 'omni.usd'); the convenience ExtensionToml map exposes the common
  [package] fields directly.

  Pure data + parsing, no platform seam — portable JVM/cljs."
  (:require [kotoba.lang.text :as str]))

;; ── IExt lifecycle (mirrors omni.ext.IExt) ────────────────────────────────

(defprotocol IExt
  (on-startup [this ext-id] "Called when the Application loads this extension.")
  (on-update  [this dt]     "Called once per app tick (seconds).")
  (on-shutdown [this]       "Called when the Application unloads this extension."))

(defn default-ext
  "A no-op IExt — mirrors `new IExt()` with the abstract class's default hooks."
  []
  (reify IExt
    (on-startup  [_ _])
    (on-update   [_ _])
    (on-shutdown [_])))

;; ── TOML subset parser ────────────────────────────────────────────────────

(defn- strip-comment
  "Drop a trailing `# ...` comment, but keep `#` that appears inside a
  double-quoted string. (An unescaped `\"` toggles in-string.)"
  [line]
  (let [n (count line)]
    (loop [i 0 in-string? false out ""]
      (if (>= i n)
        out
        (let [c    (.charAt line i)
              prev (if (pos? i) (.charAt line (dec i)) \space)
              in-string?' (if (and (= c \") (not= prev \\)) (not in-string?) in-string?)]
          (if (and (= c \#) (not in-string?))
            out
            (recur (inc i) in-string?' (str out c))))))))

(defn- strip-quotes
  "Trim, then strip one leading + trailing double-quote if both present."
  [s]
  (let [s (str/trim s)]
    (if (and (str/starts-with? s "\"") (str/ends-with? s "\"") (> (count s) 1))
      (subs s 1 (dec (count s)))
      s)))

(defn- split-top-level
  "Split `inner` on top-level commas, respecting nested [] / {} depth."
  [inner]
  (loop [chars (seq inner) depth 0 cur "" out []]
    (if-let [ch (first chars)]
      (cond
        (or (= ch \[) (= ch \{)) (recur (rest chars) (inc depth) (str cur ch) out)
        (or (= ch \]) (= ch \})) (recur (rest chars) (dec depth) (str cur ch) out)
        (and (= ch \,) (zero? depth)) (recur (rest chars) depth "" (conj out cur))
        :else (recur (rest chars) depth (str cur ch) out))
      (if (str/blank? cur) out (conj out cur)))))

(declare parse-value)

(defn- parse-num
  "Parse a TOML scalar number; returns nil if `s` is not a number. Integers
  (no '.') become long; decimals stay double — matching TS Number()/Math.trunc.
  (On cljs there is no int/long distinction — every number is a JS double.)"
  [s]
  #?(:clj  (try
             (let [n (Double/parseDouble s)]
               (if (str/includes? s ".") n (long n)))
             (catch Exception _ nil))
     :cljs (let [n (js/parseFloat s)]
             (when-not (js/isNaN n) n))))

(defn- parse-value
  "Parse a TOML scalar / array / inline-table value (string already trimmed)."
  [raw]
  (let [s (str/trim raw)]
    (cond
      (and (str/starts-with? s "\"") (str/ends-with? s "\"") (> (count s) 1))
      (subs s 1 (dec (count s)))

      (and (str/starts-with? s "[") (str/ends-with? s "]"))
      (let [inner (str/trim (subs s 1 (dec (count s))))]
        (if (str/blank? inner) [] (mapv parse-value (split-top-level inner))))

      (and (str/starts-with? s "{") (str/ends-with? s "}"))
      (let [inner (str/trim (subs s 1 (dec (count s))))]
        (if (str/blank? inner)
          {}
          (into {} (for [part (split-top-level inner)
                         :let [eq (str/index-of part "=")]
                         :when (>= eq 0)]
                     [(strip-quotes (subs part 0 eq)) (parse-value (subs part (inc eq)))]))))

      (= s "true")  true
      (= s "false") false
      :else         (or (parse-num s) s))))

(defn- ensure-table-in
  "Ensure the map at `path` (vector of string keys) in m exists and is a map;
  assoc-in creates intermediate levels as maps. Returns updated m."
  [m path]
  (let [p (vec path)]
    (cond-> m
      (and (seq p) (not (map? (get-in m p)))) (assoc-in p {}))))

(defn- ensure-array-of-tables-in
  "Ensure the array-of-tables at `path` exists (appending a fresh {}), and
  return [new-root new-current-path] where current-path includes the new
  element's index."
  [m path]
  (let [p      (vec path)
        parent (vec (butlast p))
        k      (last p)
        m      (if (seq parent) (ensure-table-in m parent) m)
        base   (if (seq parent) (get-in m parent) m)
        arr    (if (seq parent) (get base k) (get m k))
        arr'   (if (vector? arr) arr [])
        idx    (count arr')
        arr''  (conj arr' {})
        m'     (if (seq parent) (assoc-in m (conj parent k) arr'') (assoc m k arr''))]
    [m' (conj p idx)]))

(defn parse-extension-toml
  "Parse the subset of TOML used by Kit extension manifests. Returns a map with
  :title :version :description :category :keywords :authors :repository
  :dependencies :python-modules :raw-tables."
  [text]
  (let [[root _current-path]
        (loop [lines (str/split text #"\n") root {} current-path []]
          (if-let [raw-line (first lines)]
            (let [line (-> raw-line strip-comment str/trim)]
              (if (str/blank? line)
                (recur (rest lines) root current-path)
                (cond
                  (and (str/starts-with? line "[[") (str/includes? line "]]"))
                  (let [name (-> line (subs 2 (str/index-of line "]]")) str/trim)
                        path (str/split name #"\.")
                        [root' new-path] (ensure-array-of-tables-in root path)]
                    (recur (rest lines) root' new-path))

                  (and (str/starts-with? line "[") (str/includes? line "]"))
                  (let [name (-> line (subs 1 (str/index-of line "]")) str/trim)
                        path (str/split name #"\.")]
                    (recur (rest lines) (ensure-table-in root path) path))

                  :else
                  (let [eq (str/index-of line "=")]
                    (if (neg? eq)
                      (recur (rest lines) root current-path)
                      (let [k (strip-quotes (subs line 0 eq))
                            v (parse-value (subs line (inc eq)))]
                        (recur (rest lines)
                               (assoc-in root (conj current-path k) v)
                               current-path)))))))
            [root current-path]))
        pkg (or (get root "package") {})
        py  (get root "python")
        modules (if (vector? (get py "module")) (get py "module") [])]
    {:title          (str (get pkg "title" ""))
     :version        (str (get pkg "version" "0.1.0"))
     :description    (str (get pkg "description" ""))
     :category       (str (get pkg "category" ""))
     :keywords       (or (get pkg "keywords") [])
     :authors        (or (get pkg "authors") [])
     :repository     (str (get pkg "repository" ""))
     :dependencies   (or (get root "dependencies") {})
     :python-modules modules
     :raw-tables     root}))
