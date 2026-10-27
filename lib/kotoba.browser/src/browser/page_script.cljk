(ns browser.page-script
  "Script discovery for kotoba browser pages."
  (:require [browser.origin :as origin]
            [kotoba.lang.text :as str]))

(def script-source-storage-key :quickjs.script/source)

(defn- node
  [document id]
  (get-in document [:nodes id]))

(defn- text-content
  [document id]
  (let [n (node document id)]
    (case (:node/type n)
      :text (:text n)
      :element (str/join "" (map #(text-content document %) (:children n)))
      "")))

(defn- truthy-attr? [v]
  (or (= true v)
      (= "true" v)
      (= "" v)
      (and (string? v)
           (not (str/blank? v))
           (not= "false" (str/lower v)))))

(defn script-nodes
  [document]
  (->> (:nodes document)
       vals
       (filter #(and (= :element (:node/type %))
                     (= :script (:tag %))))
       (sort-by :node/id)
       vec))

(def ^:private javascript-mime-types
  ;; WHATWG's "JavaScript MIME type essence match"
  ;; (https://mimesniff.spec.whatwg.org/#javascript-mime-type) -- the
  ;; complete set of `type` attribute values (trimmed, lower-cased) real
  ;; browsers treat as an ordinary classic script.
  #{"application/ecmascript" "application/javascript" "application/x-ecmascript"
    "application/x-javascript" "text/ecmascript" "text/javascript"
    "text/javascript1.0" "text/javascript1.1" "text/javascript1.2"
    "text/javascript1.3" "text/javascript1.4" "text/javascript1.5"
    "text/jscript" "text/livescript" "text/x-ecmascript" "text/x-javascript"})

(defn script-type
  "Classifies a <script> per the HTML spec's own \"prepare the script
   element\" algorithm: absent/empty type, or a real JavaScript MIME-type
   essence match (trimmed, case-insensitive) -> :classic; the exact value
   \"module\" -> :module; anything else (a real, common idiom: JSON-LD
   structured data, framework-embedded state via
   type=\"application/json\", an \"importmap\" -- import maps themselves
   are correctly never executed as script either way, matching real
   browsers, even without this engine implementing import-map
   resolution) -> nil, meaning the script must NOT execute at all.
   Previously every non-\"module\" value fell through to :classic
   unconditionally, so a real, common type=\"application/json\" data
   block had its literal text handed straight to the JS engine as
   executable source -- many JSON payloads (bare objects, arrays,
   numbers, strings) are ALSO syntactically valid JS, so this executed
   silently with no error at all. Confirmed via direct REPL reproduction
   before this fix."
  [script-node]
  (let [type (some-> script-node :attrs :type str str/trim str/lower)]
    (cond
      (str/blank? type) :classic
      (= "module" type) :module
      (contains? javascript-mime-types type) :classic
      :else nil)))

(defn executable-script
  [document page-url script-node]
  (let [attrs (:attrs script-node)
        src (:src attrs)
        type (script-type script-node)
        source (when-not src
                 (str/trim (text-content document (:node/id script-node))))]
    ;; script-type returns nil for a type attribute that isn't classic/
    ;; module (a real, common shape -- JSON-LD, embedded framework
    ;; state, importmap) -- such a node must never become an executable
    ;; script at all, matching real browsers.
    (when (and type (or src (seq source)))
      {:script/type type
       :script/source source
       :script/src src
       :script/url (or src page-url)
       :script/node-id (:node/id script-node)
       :script/attrs attrs})))

(defn executable-scripts
  [page]
  (let [document (:browser/document page)]
    (vec
     (keep #(executable-script document (:browser/url page) %)
           (script-nodes document)))))

(defn async-script?
  "Per the HTML spec, `async` only affects an EXTERNAL script (one with
   a `src`) -- an inline script carrying the `async` attribute is
   spec-defined to still run as an ordinary blocking, document-order
   script, so `:script/src` must be present too. `run-page-scripts!`
   (browser.session) uses this to keep an async script's fetch/execute
   OUT of the document-order blocking chain entirely and to never let
   it delay DOMContentLoaded/load -- previously every script, `async`
   or not, was executed strictly in document order and unconditionally
   blocked both lifecycle events, so a slow- or never-fetching `async`
   script (e.g. denied by policy, or simply large) silently delayed
   DOMContentLoaded/load exactly as if it had no `async` attribute at
   all, a real, observable page-ready-state timing bug."
  [script]
  (boolean (and (:script/src script)
                (truthy-attr? (get (:script/attrs script) :async)))))

(defn absolute-url?
  [url]
  (some? (:scheme (origin/parse-url url))))

(defn directory-url
  [url]
  (let [{:keys [scheme authority path]} (origin/parse-url url)]
    (cond
      authority
      (let [idx (.lastIndexOf ^String path "/")
            dir (if (neg? idx) "/" (subs path 0 (inc idx)))]
        (str scheme "://" authority dir))

      scheme
      (let [idx (.lastIndexOf ^String path "/")
            dir (if (neg? idx) path (subs path 0 (inc idx)))]
        (str scheme ":" dir))

      :else "")))

(defn- strip-fragment
  [url]
  (let [url (str url)
        idx (.indexOf url "#")]
    (if (neg? idx) url (subs url 0 idx))))

(defn- strip-query-and-fragment
  [url]
  (let [url (strip-fragment url)
        idx (.indexOf ^String url "?")]
    (if (neg? idx) url (subs url 0 idx))))

(defn- query-fragment-suffix
  [url]
  (let [url (str url)
        query-idx (.indexOf ^String url "?")
        fragment-idx (.indexOf ^String url "#")
        idx (cond
              (and (not (neg? query-idx)) (not (neg? fragment-idx)))
              (min query-idx fragment-idx)

              (not (neg? query-idx)) query-idx
              (not (neg? fragment-idx)) fragment-idx
              :else -1)]
    (if (neg? idx) "" (subs url idx))))

(defn- normalize-path
  [path]
  (let [absolute? (str/starts-with? (str path) "/")
        trailing-slash? (and (> (count (str path)) 1)
                             (str/ends-with? (str path) "/"))
        segments (str/split (str path) #"/")
        normalized (reduce (fn [result segment]
                             (case segment
                               "" result
                               "." result
                               ".." (if (seq result) (pop result) result)
                               (conj result segment)))
                           []
                           segments)
        path (str/join "/" normalized)
        path (cond-> path
               (and trailing-slash? (seq path)) (str "/"))]
    (cond
      (and absolute? (seq path)) (str "/" path)
      absolute? "/"
      :else path)))

(defn- normalize-dot-segments
  [url]
  (let [{:keys [scheme authority path]} (origin/parse-url url)
        suffix (query-fragment-suffix url)
        path (strip-query-and-fragment path)]
    (cond
      authority
      (str scheme "://" authority (normalize-path path) suffix)

      scheme
      (str scheme ":" (normalize-path path) suffix)

      :else
      url)))

(defn- has-dot-segments?
  [url]
  (boolean (re-find #"(^|/)\.{1,2}(/|$|\?|#)" (str url))))

(defn resolve-src
  [page-url src]
  (let [src (str src)
        ;; RFC 3986 4.2: a relative-path reference whose first segment
        ;; contains a colon (e.g. "video:120/clip.js") is indistinguishable
        ;; from an absolute URI with scheme "video" -- callers must prefix
        ;; it with "./" to force relative-path interpretation. `dot-relative?`
        ;; remembers that the caller did so, so the colon in what's left
        ;; after stripping "./" is never mistaken for a scheme below (an
        ;; earlier version stripped the "./" and then still ran
        ;; `absolute-url?` on the remainder, silently defeating the very
        ;; disambiguation "./" exists to provide).
        dot-relative? (str/starts-with? src "./")
        src (if dot-relative? (subs src 2) src)]
    (cond
      (and (not dot-relative?) (absolute-url? src))
      (if (has-dot-segments? src)
        (normalize-dot-segments src)
        src)
      (str/starts-with? src "#")
      (str (strip-fragment page-url) src)
      (str/starts-with? src "?")
      (str (strip-query-and-fragment page-url) src)
      (str/starts-with? src "//")
      (let [{:keys [scheme]} (origin/parse-url page-url)]
        (normalize-dot-segments (str scheme ":" src)))
      (str/starts-with? src "/")
      (let [{:keys [scheme authority]} (origin/parse-url page-url)]
        (if authority
          (normalize-dot-segments (str scheme "://" authority src))
          (normalize-dot-segments (str scheme ":" src))))
      :else
      (normalize-dot-segments (str (directory-url page-url) src)))))
