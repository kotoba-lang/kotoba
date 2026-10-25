(ns rtsp.message
  "RTSP request/response messages — [RFC 2326] §4-§8, §12 — over a
  persistent byte stream.

  RTSP is RFC 2326's *own* profile, not HTTP/1.1 reused wholesale: the
  request/status line and `field-name \":\" field-value` header grammar
  are HTTP-shaped ([H6] is cited throughout), but two framing decisions
  are RTSP-specific and this namespace gets both of them right rather
  than borrowing HTTP's:

  1. **No chunked transfer coding.** §4.3: \"RTSP does not (at present)
     support the HTTP/1.1 'chunked' transfer coding and requires the
     presence of the Content-Length header field.\" A body is exactly
     `Content-Length` bytes, full stop — there is no chunk-size line to
     parse and no trailer to skip.
  2. **Absence of Content-Length means zero, not 'read until the
     connection closes'.** §4.3 rule 2: \"If this header field is not
     present, a value of zero is assumed.\" HTTP/1.0 responses use
     connection-close as an implicit length; RTSP explicitly does not,
     because §4.2 says a message with a payload MUST carry
     Content-Length — closing the connection to delimit a body is not a
     fallback this protocol defines.

  Bytes are `vector<int 0..255>` in and out, the same convention
  `rtp.header` and `modbus.pdu` use. `rtsp.bytes` is the one place the
  octet range is mapped to/from characters for the (ASCII-range)
  start-line and header text; the body is never round-tripped through a
  string at all — it stays exactly the byte slice `Content-Length` says
  it is, so a JPEG or an SDP body with a stray high-bit octet is neither
  interpreted nor mangled by this layer.")

(require '[rtsp.bytes :as rb]
         '[kotoba.lang.text :as str])

(def known-methods
  "[RFC 2326] §6.1's `Method` production. `extension-method = token` is
  also accepted on decode (RTSP allows new methods), just not returned
  as one of these known ones."
  #{"DESCRIBE" "ANNOUNCE" "GET_PARAMETER" "OPTIONS" "PAUSE" "PLAY"
    "RECORD" "REDIRECT" "SETUP" "SET_PARAMETER" "TEARDOWN"})

(defn- err
  ([reason] {:status :error :reason reason})
  ([reason context] {:status :error :reason reason :context context}))

;; ── line splitting ──────────────────────────────────────────────────────

(defn- find-header-end
  "Index just past the CRLFCRLF that ends the header block, or nil.
  [RFC 2326] §4.1 rule 1: \"An empty line ... indicates the end of the
  message headers.\" Bare LFLF is accepted as the same asymmetric
  leniency `sdp.grammar` documents — permissive in, canonical CRLF out."
  [text]
  (let [crlf (str/index-of text "\r\n\r\n")
        lf (str/index-of text "\n\n")]
    (cond
      crlf (+ crlf 4)
      lf (+ lf 2)
      :else nil)))

(defn- split-header-lines
  "The header block (everything before the blank line) split into
  logical lines, with [RFC 2326] §12's line-folding rule applied: `LWS =
  [CRLF] 1*( SP | HT )` means a continuation line — one that begins with
  SP or HTAB — is not a new header, it is more of the previous header's
  value, folded. The fold collapses to a single space, matching what
  `field-value = *( field-content | LWS )` says the *parsed* value is
  (the raw whitespace run's exact width is not semantically part of a
  header value, so preserving it would make two byte-different-but-
  equivalent messages decode to different maps)."
  [block]
  (let [raw (str/split (str/replace block #"\r\n" "\n") #"\n")]
    (reduce (fn [lines line]
              (if (and (seq lines) (seq line) (contains? #{\space \tab} (first line)))
                (conj (pop lines) (str (peek lines) " " (str/triml line)))
                (conj lines line)))
            []
            raw)))

;; ── start line ───────────────────────────────────────────────────────────

(def ^:private request-line-re
  #"([!-~]+) (\S+) RTSP/(\d+)\.(\d+)")

(def ^:private status-line-re
  #"RTSP/(\d+)\.(\d+) (\d\d\d) (.*)")

(defn- parse-start-line
  "Status-Line always begins literally `RTSP/` ([RFC 2326] §7.1); no
  `Method` in §6.1's list is that string, so the prefix alone
  disambiguates which production to try."
  [line]
  (if (str/starts-with? line "RTSP/")
    (if-let [[_ maj min code reason] (re-matches status-line-re line)]
      [:ok {:type :response :version (str maj "." min)
            :status (parse-long code) :reason reason}]
      [:error :rtsp/malformed-status-line])
    (if-let [[_ method uri maj min] (re-matches request-line-re line)]
      [:ok {:type :request :method method :uri uri :version (str maj "." min)}]
      [:error :rtsp/malformed-request-line])))

(defn- encode-start-line [{:keys [type method uri version status reason]}]
  (case type
    :request (str method " " uri " RTSP/" version)
    :response (str "RTSP/" version " " status " " reason)))

;; ── headers ──────────────────────────────────────────────────────────────

(defn- parse-header-line [line]
  (let [colon (str/index-of line \:)]
    (if (nil? colon)
      [:error :rtsp/malformed-header-line]
      [:ok [(subs line 0 colon) (str/triml (subs line (inc colon)))]])))

(defn- header-value
  "Case-insensitive lookup, per [RFC 2326] §12 (header names are HTTP-
  shaped tokens, matched case-insensitively — `Content-Length` and
  `content-length` are the same header)."
  [headers name]
  (some (fn [[k v]] (when (= (str/lower k) (str/lower name)) v)) headers))

;; ── whole message ────────────────────────────────────────────────────────

(defn decode
  "`vector<int 0..255>` -> `[:ok message consumed-byte-count]` or
  `[:error reason next-byte-count-consumed-if-known]`, where `message` is
  `{:type :request :method .. :uri .. :version .. :headers [[k v] ...]
  :body <byte-vector>}` or the `:response` shape. `consumed` is how many
  bytes of `bs` this message used, so a caller reading a persistent
  stream (see `rtsp.stream`) knows where the next message or interleaved
  frame begins."
  [bs]
  (let [text (rb/bytes->str bs)
        header-end (find-header-end text)]
    (if (nil? header-end)
      (err :rtsp/incomplete-headers)
      (let [header-block (subs text 0 header-end)
            lines (split-header-lines header-block)
            start (first lines)
            header-lines (->> (rest lines) (remove empty?))]
        (if (empty? start)
          (err :rtsp/empty-message)
          (let [[st sl] (parse-start-line start)]
            (if (= st :error)
              (err sl {:line start})
              (loop [hs header-lines acc []]
                (if (empty? hs)
                  (let [headers acc
                        cl (header-value headers "Content-Length")
                        body-len (if cl (or (parse-long (str/trim cl)) -1) 0)]
                    (if (neg? body-len)
                      (err :rtsp/malformed-content-length)
                      (let [total (+ header-end body-len)]
                        (if (> total (count bs))
                          (err :rtsp/incomplete-body {:need total :have (count bs)})
                          {:status :ok
                           :message (assoc sl :headers headers
                                           :body (subvec (vec bs) header-end total))
                           :consumed total}))))
                  (let [[st2 hv] (parse-header-line (first hs))]
                    (if (= st2 :error)
                      (err hv {:line (first hs)})
                      (recur (rest hs) (conj acc hv)))))))))))))

(defn encode
  "`{:type :request ...}` or `{:type :response ...}` -> byte vector, or
  `[:error :rtsp/missing-content-length ...]` when a non-empty `:body` is
  present without the caller having put `Content-Length` in `:headers`
  — this namespace will not silently compute one, because §4.2 makes
  Content-Length a MUST for any message carrying a payload and a codec
  that fills it in invisibly would hide a caller bug that RTSP itself
  treats as a protocol violation."
  [{:keys [headers body] :as msg}]
  (let [body (or body [])
        cl (header-value headers "Content-Length")]
    (if (and (seq body) (nil? cl))
      [:error :rtsp/missing-content-length]
      (let [header-text (str (encode-start-line msg) "\r\n"
                              (str/join "" (map (fn [[k v]] (str k ": " v "\r\n")) headers))
                              "\r\n")]
        (into (rb/str->bytes header-text) body)))))
