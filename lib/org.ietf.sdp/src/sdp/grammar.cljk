(ns sdp.grammar
  "Line-level lexer and the type=value split — [RFC 4566] section 9's
  ABNF at the granularity of a single line, before any field is
  interpreted.

  Every SDP line has the shape `<type-char>=<value>` where `type-char` is
  exactly one of the fourteen letters the grammar defines
  (`v o s i u e p c b t r z k a m`, %x76/%x6f/%x73/%x69/%x75/%x65/%x70/
  %x63/%x62/%x74/%x72/%x7a/%x6b/%x61/%x6d in the RFC's own notation).
  Splitting on the *first* `=` rather than trimming/tokenising the whole
  line is deliberate: `a=fmtp:97 profile-level-id=42e01f` has a second `=`
  inside the value, and a splitter that isn't anchored to \"first
  occurrence\" corrupts every `fmtp`/`rtpmap` parameter line in the
  session."
  (:require [kotoba.lang.text]))

(def line-types
  "The fourteen type characters SDP defines. Anything else at this
  position is not SDP — not \"an unknown attribute\", because only `a=`
  is the open extension point; the letter itself is closed."
  #{\v \o \s \i \u \e \p \c \b \t \r \z \k \a \m})

(defn split-lines
  "CRLF is what [RFC 4566] mandates on the wire (`text CRLF` throughout
  the grammar), but SDP travels almost exclusively as a SIP/RTSP message
  body, where bodies get normalized by intermediaries and hand-written
  fixtures alike drop the CR. Accepting bare LF on decode and always
  emitting CRLF on encode is the same asymmetric leniency `org-ietf-sip`
  applies to header folding — permissive in, canonical out — not a
  relaxation of the *ordering* or *field* grammar this namespace exists
  to enforce."
  [text]
  (-> text
      (kotoba.lang.text/replace #"\r\n" "\n")
      (kotoba.lang.text/split #"\n" -1)))

(defn parse-line
  "One raw line -> `{:type \\v :value \"0\"}` or a named error. `type`
  must be exactly one of `line-types`; `value` is everything after the
  first `=`, unmodified (so a value-parser sees the real bytes, including
  any inner `=`)."
  [line]
  (let [eq (kotoba.lang.text/index-of line \=)]
    (cond
      (empty? line)
      [:error :sdp/blank-line]

      (nil? eq)
      [:error :sdp/missing-equals]

      (not= eq 1)
      [:error :sdp/type-not-single-char]

      (not (contains? line-types (first line)))
      [:error :sdp/unknown-line-type]

      :else
      [:ok {:type (first line) :value (subs line (inc eq))}])))

(defn tokenize
  "The whole message: strip a trailing blank line (the CRLF-terminated
  form leaves one after `split-lines`), reject an empty message outright,
  and parse every remaining line. Stops at the first line-level error and
  reports which line (1-indexed, matching what a human counts) it was —
  a parser that swallows the line number turns every malformed-SDP bug
  report into a re-parse-by-hand."
  [text]
  (let [raw (split-lines text)
        raw (if (and (seq raw) (empty? (last raw))) (butlast raw) raw)]
    (if (empty? raw)
      [:error :sdp/empty-message]
      (loop [lines raw idx 1 acc []]
        (if (empty? lines)
          [:ok acc]
          (let [[status v] (parse-line (first lines))]
            (if (= status :error)
              [:error v {:line idx :text (first lines)}]
              (recur (rest lines) (inc idx) (conj acc v)))))))))
