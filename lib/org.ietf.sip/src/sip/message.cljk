(ns sip.message
  "Whole-message SIP codec — RFC 3261 §7 (message format) and §25 (ABNF).

      INVITE sip:bob@biloxi.com SIP/2.0\\r\\n
      Via: SIP/2.0/UDP pc33.atlanta.com;branch=z9hG4bK776asdhds\\r\\n
      To: Bob <sip:bob@biloxi.com>\\r\\n
      From: Alice <sip:alice@atlanta.com>;tag=1928301774\\r\\n
      Call-ID: a84b4c76e66710@pc33.atlanta.com\\r\\n
      CSeq: 314159 INVITE\\r\\n
      Max-Forwards: 70\\r\\n
      Contact: <sip:alice@pc33.atlanta.com>\\r\\n
      Content-Length: 0\\r\\n
      \\r\\n

  `decode` accepts either CRLF or bare-LF line endings (real captures are
  supposed to be CRLF-only per §7, but treating a lone `\\n` as a line
  terminator too costs nothing and is friendlier to hand-edited test
  fixtures and copy-pasted RFC examples). Header continuation
  (`obs-fold`, §7.3.1: a line whose value spans multiple physical lines
  by starting each continuation with SP/HTAB) is unfolded before any
  header value is parsed, and quoted strings, `;parameter` grammars and
  Via's `sent-by` are handled by real scanners in `sip.grammar`/
  `sip.uri`/`sip.headers`, not `str/split`.

  **Round-trip contract**: `decode`/`encode` assert *semantic* equality
  (the decoded header/URI/body values match), not byte-exact
  reserialization. RFC 3261 explicitly permits reordering most headers,
  folding, extra whitespace around `:`, and combining/splitting
  comma-lists, so two byte-different SIP messages are routinely the same
  message on the wire — a codec that insisted on byte-for-byte
  reconstruction would be asserting something the protocol itself
  doesn't guarantee. `encode` always emits Via in decode order (order is
  semantically load-bearing for Via — RFC 3261 §18.1.1) and always
  recomputes `Content-Length` from the actual body rather than trusting
  whatever was declared coming in, the same way a real UA does."
  (:require [kotoba.lang.text :as str]
            [sip.grammar :as g]
            [sip.headers :as h]
            [sip.uri :as uri]))

;; ---------------------------------------------------------------------
;; utf-8 byte length, for Content-Length — RFC 3261 §7.4.14/20.14: an
;; *octet* count, not a character count. Most SIP bodies (SDP) are ASCII,
;; where the two coincide, but a display-name or a body with non-ASCII
;; text (e.g. UTF-8 SDP session names, RFC 6350 vCard bodies) would
;; silently produce a wrong Content-Length if this just did `(count s)`.
;; ---------------------------------------------------------------------

(defn utf8-byte-count
  [s]
  #?(:clj (count (.getBytes ^String s "UTF-8"))
     :cljs (.-length (.encode (js/TextEncoder.) s))))

;; ---------------------------------------------------------------------
;; header unfolding + line splitting
;; ---------------------------------------------------------------------

(defn- split-lines [s] (str/split s #"\r\n|\n" -1))

(defn unfold-lines
  "RFC 3261 §7.3.1's `obs-fold`: a header whose value continues onto
  following physical lines, each of which starts with SP or HTAB. Given
  the header-section's lines (start-line excluded), returns a vector of
  logical lines with every continuation joined onto the header line it
  continues — the CRLF is dropped, the continuation line's own leading
  whitespace is kept exactly as written (this is deliberately *not*
  collapsed to a single space: RFC 2822 §2.2.3's unfolding rule, which
  RFC 3261 inherits, removes only the line break)."
  [lines]
  (reduce (fn [acc line]
            (if (and (seq line) (contains? #{\space \tab} (first line)) (seq acc))
              (conj (pop acc) (str (peek acc) line))
              (conj acc line)))
          []
          lines))

;; ---------------------------------------------------------------------
;; header-section / body split
;; ---------------------------------------------------------------------

(defn- header-body-boundary
  "`[header-end body-start]` around the blank line separating headers
  from body, or `nil` if there is no blank line anywhere in `s`."
  [s]
  (let [crlf2 (str/index-of s "\r\n\r\n")
        lf2 (str/index-of s "\n\n")]
    (cond
      (and crlf2 (or (nil? lf2) (<= crlf2 lf2))) [crlf2 (+ crlf2 4)]
      lf2 [lf2 (+ lf2 2)]
      :else nil)))

;; ---------------------------------------------------------------------
;; start-line
;; ---------------------------------------------------------------------

(def ^:private status-line-re #"^SIP/(\d+\.\d+)\s+(\d{3})\s+(.*)$")
(def ^:private request-line-re #"^(\S+)\s+(\S+)\s+SIP/(\d+\.\d+)$")

(defn- parse-start-line
  [line]
  (if-let [[_ version code reason] (re-matches status-line-re line)]
    {:type :response :version (str "SIP/" version)
     :status (g/parse-uint code) :reason reason}
    (if-let [[_ method request-uri version] (re-matches request-line-re line)]
      (let [u (uri/parse request-uri)]
        (if (and (vector? u) (= :error (first u)))
          [:error :sip/bad-request-uri]
          {:type :request :method method :uri u :version (str "SIP/" version)}))
      [:error :sip/bad-start-line])))

;; ---------------------------------------------------------------------
;; raw header lines -> {canonical-name [value-string ...]}, order-preserving
;; ---------------------------------------------------------------------

(defn- raw-header-map
  "Every header line, unfolded, split at the first `:`, name
  canonicalised (compact form expanded, lower-cased) and value
  comma-split at the top level (RFC 3261 §7.3.1: repeatable header
  fields may be sent as one comma-separated line or as several separate
  lines with the same name — this flattens both forms into one ordered
  list per canonical name, so `sip.headers`/callers never have to care
  which one was on the wire). Returns `[header-map order]` where `order`
  is the sequence of canonical names in first-seen order, for
  `:headers`' generic-header encode order.

  `[:error :sip/bad-header-line]` for a line with no `:` in it at all."
  [lines]
  (loop [lines lines hmap (transient {}) order []]
    (if (empty? lines)
      [(persistent! hmap) order]
      (let [line (first lines)
            colon (str/index-of line ":")]
        (if (nil? colon)
          [:error :sip/bad-header-line]
          (let [raw-name (subs line 0 colon)
                raw-value (str/trim (subs line (inc colon)))
                canonical (h/canonicalize-name raw-name)
                values (g/split-top-level raw-value \,)
                seen? (contains? hmap canonical)]
            (recur (rest lines)
                   (assoc! hmap canonical (into (get hmap canonical []) values))
                   (if seen? order (conj order canonical)))))))))

;; ---------------------------------------------------------------------
;; structured extraction of the headers this codec models directly
;; ---------------------------------------------------------------------

(def ^:private required-always
  ;; RFC 3261 §8.1.1 / §20: mandatory in every request AND every
  ;; response.
  [["via" :sip/missing-via]
   ["to" :sip/missing-to]
   ["from" :sip/missing-from]
   ["call-id" :sip/missing-call-id]
   ["cseq" :sip/missing-cseq]])

(defn- take-single
  "Header fields that must appear exactly once logically (To, From,
  CSeq) even though the wire lets any header be split across lines —
  after `raw-header-map`'s comma-flattening, that means exactly one
  value string. More than one is malformed for these three specifically
  (RFC 3261's grammar defines them as singular, unlike Via/Contact)."
  [hmap canonical]
  (let [vs (get hmap canonical)]
    (cond
      (nil? vs) nil
      (= 1 (count vs)) (first vs)
      :else [:error (keyword "sip" (str "bad-" canonical))])))

(defn- decode-structured
  "Pull Via/To/From/Call-ID/CSeq/Max-Forwards/Contact/Content-Length out
  of `hmap` into their structured forms, checking the always-mandatory
  headers along the way. Returns `[fields error-or-nil]`."
  [hmap]
  (let [missing (some (fn [[canonical reason]]
                         (when-not (contains? hmap canonical) reason))
                       required-always)]
    (if missing
      [nil [:error missing]]
      (let [via-raw (get hmap "via")
            vias (mapv h/decode-via via-raw)
            via-err (some #(when (and (vector? %) (= :error (first %))) %) vias)

            to-raw (take-single hmap "to")
            to (when to-raw (h/decode-addr to-raw))
            from-raw (take-single hmap "from")
            from (when from-raw (h/decode-addr from-raw))

            call-id (take-single hmap "call-id")

            cseq-raw (take-single hmap "cseq")
            cseq (when cseq-raw (h/decode-cseq cseq-raw))

            mf-raw (take-single hmap "max-forwards")
            max-forwards (when mf-raw (h/decode-uint-header mf-raw :sip/bad-max-forwards))

            contact-raw (get hmap "contact")
            contact (cond
                      (nil? contact-raw) nil
                      (= contact-raw ["*"]) "*"
                      :else (mapv h/decode-addr contact-raw))
            contact-err (when (vector? contact)
                          (some #(when (and (vector? %) (= :error (first %))) %) contact))

            cl-raw (take-single hmap "content-length")
            content-length (when cl-raw (h/decode-uint-header cl-raw :sip/bad-content-length))

            first-err (some #(when (and (vector? %) (= :error (first %))) %)
                             [via-err
                              (when (and (vector? to-raw) (= :error (first to-raw))) to-raw)
                              (when (and (vector? to) (= :error (first to))) to)
                              (when (and (vector? from-raw) (= :error (first from-raw))) from-raw)
                              (when (and (vector? from) (= :error (first from))) from)
                              (when (and (vector? call-id) (= :error (first call-id))) call-id)
                              (when (and (vector? cseq-raw) (= :error (first cseq-raw))) cseq-raw)
                              (when (and (vector? cseq) (= :error (first cseq))) cseq)
                              (when (and (vector? max-forwards) (= :error (first max-forwards))) max-forwards)
                              contact-err
                              (when (and (vector? content-length) (= :error (first content-length))) content-length)])]
        (if first-err
          [nil first-err]
          [{:via vias :to to :from from :call-id call-id :cseq cseq
            :max-forwards max-forwards :contact contact
            :content-length content-length}
           nil])))))

;; ---------------------------------------------------------------------
;; decode
;; ---------------------------------------------------------------------

(def structured-names
  #{"via" "to" "from" "call-id" "cseq" "max-forwards" "contact" "content-length"})

(defn decode
  "Decode one full SIP message (request or response) from `s`. Returns a
  map — request fields are `:type :request :method :uri :version`,
  response fields `:type :response :version :status :reason` — plus in
  both cases `:via` (vector) `:to` `:from` `:call-id` `:cseq`
  `:max-forwards` (`nil` if absent) `:contact` (vector, `\"*\"`, or `nil`)
  `:content-length` (`nil` if the header was absent — `decode` does not
  invent one) `:headers` (`{canonical-name [value-string ...]}` for every
  header not listed above, e.g. `Content-Type`, `Subject`, `Route`) and
  `:body` (the raw string after the blank line, truncated to
  `Content-Length` *if present and not larger than what's actually
  there*).

  Reasons include `:sip/missing-header-body-separator`,
  `:sip/bad-start-line`, `:sip/bad-request-uri`, `:sip/bad-header-line`,
  `:sip/missing-via`/`:sip/missing-to`/`:sip/missing-from`/
  `:sip/missing-call-id`/`:sip/missing-cseq` (RFC 3261 §8.1.1's mandatory
  set), `:sip/bad-via`/`:sip/bad-to`/`:sip/bad-from`/`:sip/bad-cseq`/
  `:sip/bad-max-forwards`/`:sip/bad-content-length`/`:sip/bad-contact`,
  `:sip/short-body` (declared `Content-Length` exceeds what's actually in
  `s`)."
  [s]
  (let [boundary (header-body-boundary s)]
    (if (nil? boundary)
      [:error :sip/missing-header-body-separator]
      (let [[header-end body-start] boundary
            header-section (subs s 0 header-end)
            body-raw (subs s body-start)
            all-lines (split-lines header-section)]
        (if (empty? all-lines)
          [:error :sip/bad-start-line]
          (let [start-line (parse-start-line (first all-lines))]
            (if (and (vector? start-line) (= :error (first start-line)))
              start-line
              (let [unfolded (unfold-lines (rest all-lines))
                    hm+order (raw-header-map unfolded)]
                (if (and (vector? hm+order) (= :error (first hm+order)))
                  hm+order
                  (let [[hmap order] hm+order
                        [structured err] (decode-structured hmap)]
                    (if err
                      err
                      (let [generic (into {} (map (fn [k] [k (get hmap k)]))
                                           (remove structured-names order))
                            declared-len (:content-length structured)
                            body (if (and declared-len (<= declared-len (utf8-byte-count body-raw)))
                                   ;; declared length is in octets; body-raw
                                   ;; here is a character string, so for the
                                   ;; (overwhelmingly common) ASCII-body case
                                   ;; char count == byte count and a direct
                                   ;; `subs` is correct. See README for the
                                   ;; documented limit on non-ASCII bodies.
                                   (subs body-raw 0 (min declared-len (count body-raw)))
                                   body-raw)]
                        (if (and declared-len (> declared-len (utf8-byte-count body-raw)))
                          [:error :sip/short-body]
                          (merge start-line structured {:headers generic :body body}))))))))))))))

;; ---------------------------------------------------------------------
;; encode
;; ---------------------------------------------------------------------

(defn- encode-header-line [canonical value]
  (str (h/display-name-for canonical) ": " value "\r\n"))

(defn- encode-structured-headers
  [{:keys [via to from call-id cseq max-forwards contact]}]
  (str
    (apply str (map #(encode-header-line "via" (h/encode-via %)) via))
    (when max-forwards (encode-header-line "max-forwards" (str max-forwards)))
    (when to (encode-header-line "to" (h/encode-addr to)))
    (when from (encode-header-line "from" (h/encode-addr from)))
    (when call-id (encode-header-line "call-id" call-id))
    (when cseq (encode-header-line "cseq" (h/encode-cseq cseq)))
    (cond
      (= contact "*") (encode-header-line "contact" "*")
      (seq contact) (apply str (map #(encode-header-line "contact" (h/encode-addr %)) contact))
      :else nil)))

(defn- encode-generic-headers [headers]
  (apply str
         (for [[canonical values] (sort-by key headers)
               :when (seq values)]
           (encode-header-line canonical (str/join ", " values)))))

(defn encode
  "Encode a decoded (or hand-built) message map back to wire text.
  `Content-Length` is always computed from `(:body msg)`'s actual UTF-8
  byte length — any `:content-length` in `msg` is ignored on encode, the
  same way a real UA never trusts a stale length it happens to be
  carrying around. Missing `:headers`/`:body`/`:max-forwards`/`:contact`
  are all fine (encoded as absent / omitted)."
  [{:keys [type method uri version status reason headers body]
    :or {version "SIP/2.0" headers {} body ""}
    :as msg}]
  (let [start-line (case type
                      :request (str method " " (uri/encode uri) " " version "\r\n")
                      :response (str version " " status " " reason "\r\n")
                      ;; No default would make `case` throw
                      ;; IllegalArgumentException on a map that carries no
                      ;; `:type` -- which is exactly the shape `decode` returns
                      ;; on failure, so `(encode (decode bad-bytes))` would
                      ;; throw rather than report. Every other refusal in this
                      ;; library is a named `[:error kw]` value; an encode that
                      ;; threw instead would be the one path a caller could not
                      ;; handle uniformly.
                      nil)]
    (if (nil? start-line)
      [:error :sip/unknown-message-type]
      (str start-line
           (encode-structured-headers msg)
           (encode-generic-headers headers)
           (encode-header-line "content-length" (str (utf8-byte-count body)))
           "\r\n"
           body))))
