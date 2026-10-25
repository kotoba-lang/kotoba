(ns render-fidelity.measure
  "What one document tells us about the renderer.

  ## The oracle is a second implementation, not a fixture

  `pdf.core/extract-text` collects the strings shown between `BT` and `ET`
  with no matrices and no state machine. It is useless for placing anything,
  which is why `hanmen` exists — and that uselessness is exactly what makes
  it a good witness: it shares no code with the interpreter, so the two
  agreeing about WHICH CHARACTERS are on a page is evidence, and the two
  disagreeing is a defect in one of them.

  Compared with all whitespace removed. Where the characters land is
  `hanmen`'s business and this cannot check it; whether it invented or lost
  any is checkable, and is the failure that actually happened: a coalescer
  once put a space between every pair of letters, and 6,289 characters
  nobody wrote went into the text of 45 documents.

  Only pages whose fonts are all simple are compared. `extract-text` cannot
  read a composite font at all — it has no CMap and no `/ToUnicode` — so on
  those pages `hanmen` legitimately knows more, and demanding agreement
  would be demanding it be as wrong as the witness.

  ## Metrics are counts of things, not scores

  Nothing here produces a number out of ten. Every field is a count of
  something a person can go and look at: marks by kind, regions left
  undrawn by reason, pages where the two readers disagree. A score would
  hide which of those moved."
  (:require [adobe.cmap.core :as acmap]
            [kotoba.lang.text :as str]
            [hanmen.page :as page]
            [hanmen.pdf :as hpdf]
            [pdf.core :as pdf]))

(def encoding->cmap
  "The resolver a real host passes in. Memoised for the same reason a host
  memoises it — every document that uses an encoding uses it on every page."
  (memoize
   (fn [name]
     (when-let [e (acmap/encoding name)]
       {:split #(acmap/split-codes (:codespace e) %)
        :text (acmap/code->unicode name)}))))

(def render-opts
  {:cid->unicode acmap/cid->unicode :encoding->cmap encoding->cmap})

(defn- strip [s] (str/replace (str s) #"\s+" ""))

(defn simple-fonts?
  "Whether every font on the page is a simple one — the condition under
  which the witness can read the page at all."
  [objs page-dict]
  (let [fonts (pdf/resolve-ref objs (:Font (pdf/resolve-ref objs (:Resources page-dict))))]
    (and (map? fonts)
         (seq fonts)
         (not-any? #(= :Type0 (:Subtype (pdf/resolve-ref objs (val %)))) fonts))))

(defn- undrawn
  "Regions the renderer placed and could not draw, by reason. These are the
  renderer's own admissions, and the point of counting them is that they
  should only ever go down."
  [items]
  (frequencies (keep :item/reason items)))

(defn measure-page
  "One page, as counts."
  [parsed index]
  (let [objs (:objects parsed)
        dict (nth (hpdf/page-dicts parsed) index nil)
        p (hpdf/page-at parsed index render-opts)
        items (:page/items p)
        mine (strip (str/join (page/text-of p)))
        comparable? (and dict (simple-fonts? objs dict))
        theirs (when comparable? (strip (str/join (pdf/page-text objs dict))))]
    {:marks (frequencies (map :item/kind items))
     :undrawn (undrawn items)
     :clips (count (:page/clips p))
     :chars (count mine)
     :comparable? (boolean comparable?)
     ;; `:agrees?` is nil rather than false when the page cannot be
     ;; compared. A rate computed over pages that were never checked is a
     ;; rate that improves by adding documents nobody can verify.
     :agrees? (when comparable? (= mine theirs))
     ;; Signed: positive means the renderer has characters the witness does
     ;; not, which is the direction that means invention.
     :drift (when comparable? (- (count mine) (count theirs)))}))

(defn measure-document
  "The first page of `bytes`, or why it could not be measured.

  Page one only, and on purpose: the loop's job is to run over MANY
  documents often, and a hundred-page contract costs a hundred times as
  much to tell us roughly the same thing. Depth is a different tool."
  [bytes]
  (try
    (let [parsed (pdf/parse bytes)
          n (count (hpdf/page-dicts parsed))]
      (if (zero? n)
        {:error :no-pages}
        (assoc (measure-page parsed 0) :pages n)))
    (catch #?(:clj Exception :cljs :default) e
      {:error :threw :message (str #?(:clj (.getMessage ^Exception e) :cljs e))})))

(defn- sum-maps [ms]
  (reduce (fn [acc m] (merge-with + acc m)) {} ms))

(defn summarise
  "Per-document measurements into the row that goes in the ledger."
  [results]
  (let [ok (remove :error results)
        comparable (filter :comparable? ok)]
    {:documents/seen (count results)
     :documents/measured (count ok)
     :documents/errors (frequencies (keep :error results))
     ;; The distinct reasons, counted. Eight documents throwing one message
     ;; is a decoder to write; eight throwing eight is a corpus.
     :documents/messages (frequencies (keep :message results))
     :marks (sum-maps (map :marks ok))
     :undrawn (sum-maps (map :undrawn ok))
     :clips (reduce + 0 (map :clips ok))
     :chars (reduce + 0 (map :chars ok))
     ;; The witness's verdict, and the two numbers that make it meaningful:
     ;; how many pages it could judge, and how far apart the two readers
     ;; were where it could.
     :oracle/comparable (count comparable)
     :oracle/agree (count (filter :agrees? comparable))
     :oracle/drift (reduce + 0 (keep :drift comparable))
     :oracle/invented (reduce + 0 (filter pos? (keep :drift comparable)))
     :oracle/lost (reduce + 0 (map - (filter neg? (keep :drift comparable))))}))
