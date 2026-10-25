(ns watchlist.match
  "Name-matching for sanctions/PEP screening — pure functions, no I/O.

   HONESTY NOTE (do not remove): matching a query name against a watchlist
   entity by string similarity is a real, hard problem commercial vendors
   (ComplyAdvantage, Refinitiv World-Check, Dow Jones) spend significant
   ongoing effort tuning. A naive exact-string match has a very high
   false-negative rate (misses real matches from transliteration variants,
   e.g. Arabic/Cyrillic romanization drift, that never look like an exact
   or even Jaro-Winkler-close string). This ns's tiered scoring is a real,
   deterministic, tested algorithm — not a black box — but its bounds are
   explicit and narrower than a production compliance vendor's: anything
   below `low-threshold` is NOT surfaced as a candidate at all. Treat that
   as a documented false-negative risk (README.md), not an implementation
   detail to hide."
  (:require [kotoba.lang.text :as str]))

;; --- script folding -------------------------------------------------------
;; Added 2026-08-26, when :jp-mof brought the first non-Latin names into the
;; index. Until then `normalize`'s [a-z0-9 ] filter was total by accident:
;; every indexed name was Latin, so nothing ever asked what a Japanese name
;; normalizes TO. It answered "" -- and that answer is not merely useless,
;; it is unsafe. `jaro-winkler` of two empty strings is 1.0, so the moment
;; ONE indexed name normalized to empty, EVERY query that also normalized to
;; empty scored :fuzzy-high against it. Measured on the commit before this
;; one: (score-name "山田太郎" "アル・カーイダ") returned
;; {:tier :fuzzy-high :confidence 0.92} -- two unrelated names, reported as
;; a sanctions hit. The fix is two-sided, and both halves are load-bearing:
;; fold the scripts so real Japanese names survive normalization, AND floor
;; `score-name` so a name that STILL cannot be represented matches nothing.

(def ^:private halfwidth-katakana
  "U+FF61-U+FF9D in codepoint order. Index i is the halfwidth form of
   character i of `fullwidth-katakana`."
  "｡｢｣､･ｦｧｨｩｪｫｬｭｮｯｰｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ")

(def ^:private fullwidth-katakana
  "。「」、・ヲァィゥェォャュョッーアイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨラリルレロワン")

(def ^:private hw->fw (zipmap halfwidth-katakana fullwidth-katakana))

(def ^:private voiceable
  "Fullwidth katakana whose dakuten form is the NEXT codepoint (カ -> ガ)."
  (set "カキクケコサシスセソタチツテトハヒフヘホ"))

(def ^:private semi-voiceable
  "Fullwidth katakana whose handakuten form is codepoint + 2 (ハ -> パ)."
  (set "ハヒフヘホ"))

(defn- char-code
  "The UTF-16 code unit of a one-character value, on both runtimes.

   NOT `(int c)`. ClojureScript's `int` truncates to a number first, and a
   one-character STRING truncated is NaN, so `(int \"ｶ\")` is 0 -- every
   codepoint comparison below silently tests against zero and every fold
   below becomes a no-op. Measured before this fix: under nbb,
   (normalize \"ｱﾙ･ｶｰｲﾀﾞ\") dropped the voiced ﾀﾞ and
   (normalize \"ＡＬ－ＱＡＩＤＡ\") returned \"\", while the JVM returned the
   right answer for both -- so the tests were green and the nbb scripts that
   consume this namespace were wrong. A .cljc file tested on one runtime is
   tested on one runtime; test/watchlist/cljs_runner.cljs exists because of
   this."
  [c]
  #?(:clj (int c)
     :cljs (.charCodeAt (str c) 0)))

(defn- shift-char [c n] (char (+ (char-code c) n)))

(defn fold-halfwidth
  "Halfwidth katakana -> fullwidth, absorbing a following U+FF9E/U+FF9F
   voicing mark into the single fullwidth codepoint it belongs to.

   A fold, not a character map: ｶﾞ is two codepoints and ガ is one. A
   per-character map leaves the mark stranded, `normalize` then strips it,
   and ガ has silently become カ -- a different name, with no error."
  [s]
  (loop [cs (seq s) out []]
    (if-not cs
      (apply str out)
      (let [c (first cs)
            fw (hw->fw c)
            nxt (second cs)]
        (cond
          (nil? fw) (recur (next cs) (conj out c))
          (and (= nxt \uff9e) (= fw \ウ)) (recur (nnext cs) (conj out \ヴ))
          (and (= nxt \uff9e) (voiceable fw)) (recur (nnext cs) (conj out (shift-char fw 1)))
          (and (= nxt \uff9f) (semi-voiceable fw)) (recur (nnext cs) (conj out (shift-char fw 2)))
          :else (recur (next cs) (conj out fw)))))))

(defn fold-fullwidth-ascii
  "U+FF01-U+FF5E -> ASCII (offset 0xFEE0). Fullwidth Latin is what a
   Japanese input method produces for ASCII, so ＡＢＣ and ABC are one name."
  [s]
  (apply str (map (fn [c]
                    (let [n (char-code c)]
                      (if (and (<= 0xff01 n) (<= n 0xff5e)) (char (- n 0xfee0)) c)))
                  s)))

(defn fold-hiragana
  "Hiragana U+3041-U+3096 -> katakana (+0x60). The MOF list writes names in
   katakana; a caller may type hiragana for the same name."
  [s]
  (apply str (map (fn [c]
                    (let [n (char-code c)]
                      (if (and (<= 0x3041 n) (<= n 0x3096)) (char (+ n 0x60)) c)))
                  s)))

(def ^:private drop-pattern
  ;; Kept: ASCII letters/digits and space; katakana U+30A1-U+30FA (hiragana
  ;; is folded into this range before we get here); the prolonged sound mark
  ;; U+30FC; CJK ideographs U+3400-U+4DBF and U+4E00-U+9FFF.
  ;;
  ;; U+30FB (・) is deliberately NOT kept even though it sits inside the
  ;; katakana block -- it separates parts of a name (アル・カーイダ), so it
  ;; must become a space and yield two tokens, not vanish and yield one.
  #"[^a-z0-9 \u30a1-\u30fa\u30fc\u3400-\u4dbf\u4e00-\u9fff]")

(defn normalize
  "Fold scripts, lowercase, drop every character outside the kept set,
   collapse whitespace, trim.

   Folded first, in this order: halfwidth katakana (with its voicing marks),
   fullwidth ASCII, hiragana -> katakana.

   NOT attempted. Each is a false NEGATIVE -- a name that fails to match --
   rather than a silently wrong answer, because `score-name`'s empty floor
   turns an unrepresentable name into 'no candidate' instead of into a
   1.0 self-match:
     - Latin diacritic stripping (portable .cljc has no Unicode normalizer
       without a dependency) -- the pre-existing gap, unchanged.
     - kanji <-> kana reading: 山田 and ヤマダ are the same name and this
       returns different strings for them. That needs a reading dictionary,
       not a codepoint table.
     - Hangul, Cyrillic, Arabic, Greek, Thai, Devanagari: still normalize
       to \"\". The MOF list romanizes every entry (measured: 0 of 2,866
       rows lack an English name), so its entities remain reachable through
       their Latin primary name -- but a query typed in one of those
       scripts finds nothing and says so."
  [s]
  (-> (str s)
      fold-halfwidth
      fold-fullwidth-ascii
      fold-hiragana
      (str/lower)
      (str/replace drop-pattern " ")
      (str/replace #"\s+" " ")
      str/trim))

(defn tokens [s] (vec (remove str/blank? (str/split (normalize s) #" "))))

;; --- Jaro-Winkler --------------------------------------------------------
;; Standard algorithm (Winkler 1990), verified against the reference
;; vectors from Winkler's own published examples (see match_test.cljc):
;; jaro-winkler("MARTHA","MARHTA") = 0.9611, ("DWAYNE","DUANE") = 0.8400,
;; ("DIXON","DICKSONX") = 0.8133.

(defn- jaro [s1 s2]
  (let [s1 (vec s1) s2 (vec s2)
        len1 (count s1) len2 (count s2)]
    (cond
      (and (zero? len1) (zero? len2)) 1.0
      (or (zero? len1) (zero? len2)) 0.0
      :else
      (let [match-distance (max 0 (dec (quot (max len1 len2) 2)))
            ;; plain persistent vectors of booleans in atoms, not
            ;; boolean-array/aset -- keeps this fully portable .cljc without
            ;; relying on primitive-array mutation semantics matching
            ;; exactly between JVM and cljs.
            s1-matched (atom (vec (repeat len1 false)))
            s2-matched (atom (vec (repeat len2 false)))
            matches (atom 0)]
        (dotimes [i len1]
          (let [lo (max 0 (- i match-distance))
                hi (min (dec len2) (+ i match-distance))]
            (loop [j lo]
              (when (<= j hi)
                (if (and (not (nth @s2-matched j)) (= (s1 i) (s2 j)))
                  (do (swap! s1-matched assoc i true)
                      (swap! s2-matched assoc j true)
                      (swap! matches inc))
                  (recur (inc j)))))))
        (if (zero? @matches)
          0.0
          (let [m (double @matches)
                s1-matched-chars (keep-indexed (fn [i v] (when v (s1 i))) @s1-matched)
                s2-matched-chars (keep-indexed (fn [i v] (when v (s2 i))) @s2-matched)
                transpositions (/ (count (remove true? (map = s1-matched-chars s2-matched-chars))) 2.0)]
            (/ (+ (/ m len1) (/ m len2) (/ (- m transpositions) m)) 3.0)))))))

(defn jaro-winkler
  "Jaro-Winkler similarity in [0.0 1.0]. `prefix-weight` defaults to the
   standard 0.1; `max-prefix` (common-prefix bonus cap) defaults to the
   standard 4."
  ([s1 s2] (jaro-winkler s1 s2 0.1 4))
  ([s1 s2 prefix-weight max-prefix]
   (let [j (jaro s1 s2)
         prefix (count (take-while true? (map = s1 s2)))
         l (min prefix max-prefix)]
     (+ j (* l prefix-weight (- 1.0 j))))))

;; --- tiered candidate scoring ---------------------------------------------

(def high-threshold 0.92)
(def low-threshold 0.80)

(defn- token-set-subset?
  "Every token in `query-tokens` appears somewhere in `candidate-tokens`
   (order-independent) -- catches reordered names (\"Doe John\" vs
   \"John Doe\") a pure Jaro-Winkler full-string comparison would miss."
  [query-tokens candidate-tokens]
  (let [candidate-set (set candidate-tokens)]
    (and (seq query-tokens) (every? candidate-set query-tokens))))

(defn- token-overlap-ratio [query-tokens candidate-tokens]
  (if (empty? query-tokens)
    0.0
    (/ (count (filter (set candidate-tokens) query-tokens)) (double (count query-tokens)))))

(defn score-name
  "Compare normalized `query` against normalized `candidate`. Returns
   {:tier :exact|:fuzzy-high|:fuzzy-low|nil :confidence double
    :jaro-winkler double :token-overlap double}. `:tier` nil means below
   `low-threshold` on every signal -- NOT a candidate (see this ns's
   module doc)."
  [query candidate]
  (let [nq (normalize query) nc (normalize candidate)
        qt (tokens query) ct (tokens candidate)
        jw (jaro-winkler nq nc)
        overlap (token-overlap-ratio qt ct)
        subset? (token-set-subset? qt ct)]
    (cond
      ;; Empty floor. `jaro-winkler` of two empty strings is 1.0, so without
      ;; this clause any pair of names that `normalize` cannot represent --
      ;; two different Cyrillic names, two different Japanese names before
      ;; the script fold above existed -- scores :fuzzy-high at 0.92. A name
      ;; we cannot represent must match NOTHING, not everything.
      (or (str/blank? nq) (str/blank? nc))
      {:tier nil :confidence 0.0 :jaro-winkler 0.0 :token-overlap 0.0}

      (= nq nc)
      {:tier :exact :confidence 1.0 :jaro-winkler jw :token-overlap overlap}

      (or (>= jw high-threshold) subset?)
      {:tier :fuzzy-high
       :confidence (max 0.75 (min 0.92 jw))
       :jaro-winkler jw :token-overlap overlap}

      (or (>= jw low-threshold) (>= overlap 0.6))
      {:tier :fuzzy-low
       :confidence (max 0.55 (min 0.75 jw))
       :jaro-winkler jw :token-overlap overlap}

      :else
      {:tier nil :confidence 0.0 :jaro-winkler jw :token-overlap overlap})))

(defn candidate-names
  "All names a query could match against for one entity: primary name plus
   every alias, each tagged so a hit can say WHICH name matched."
  [entity]
  (into [{:name (:entity/primary-name entity) :kind :primary}]
        (map (fn [a] {:name a :kind :alias}))
        (:entity/aliases entity)))

(defn best-entity-match
  "The single best-scoring name (primary or alias) for `entity` against
   `query`, or nil if every name scored below `low-threshold`. Returns the
   score map plus :matched-name/:matched-name-kind."
  [query entity]
  (let [scored (for [{:keys [name kind]} (candidate-names entity)
                      :when (seq name)
                      :let [s (score-name query name)]
                      :when (:tier s)]
                  (assoc s :matched-name name :matched-name-kind kind))]
    (when (seq scored)
      (apply max-key :confidence scored))))
