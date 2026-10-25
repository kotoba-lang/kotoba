(ns sip.headers
  "Structured decode/encode for the SIP header fields RFC 3261 leans on
  for routing and dialog identification: Via (§20.42), the address
  headers To/From/Contact (§20.10/§20.20/§20.39, all three sharing the
  `name-addr` / `addr-spec` grammar), CSeq (§20.16), and the compact
  header-name table (§7.3.3 / §20).

  Everything else stays as opaque header text in `sip.message` — the
  point of structuring these particular headers is that routing logic
  needs `Via`'s `branch`, `To`/`From`'s tags, and `CSeq`'s method/number
  as actual values, not substrings a caller has to re-parse."
  (:require [kotoba.lang.text :as str]
            [sip.grammar :as g]
            [sip.uri :as uri]))

;; ---------------------------------------------------------------------
;; compact header forms — RFC 3261 §7.3.3 / §20
;; ---------------------------------------------------------------------

(def compact->full
  {"i" "call-id" "m" "contact" "e" "content-encoding" "l" "content-length"
   "c" "content-type" "f" "from" "s" "subject" "k" "supported" "t" "to"
   "v" "via"})

(def full->compact
  (into {} (map (fn [[k v]] [v k]) compact->full)))

;; The proper wire casing for encode — RFC 3261's own examples use this
;; casing throughout, and while header names are case-insensitive on the
;; wire (§7.3.1), emitting the conventional casing is what makes a capture
;; readable next to a real SIP stack's traffic.
(def canonical-casing
  {"via" "Via" "to" "To" "from" "From" "call-id" "Call-ID" "cseq" "CSeq"
   "contact" "Contact" "max-forwards" "Max-Forwards"
   "content-length" "Content-Length" "content-type" "Content-Type"
   "content-encoding" "Content-Encoding" "subject" "Subject"
   "supported" "Supported" "route" "Route" "record-route" "Record-Route"
   "expires" "Expires" "user-agent" "User-Agent" "allow" "Allow"
   "www-authenticate" "WWW-Authenticate" "authorization" "Authorization"
   "proxy-authenticate" "Proxy-Authenticate"
   "proxy-authorization" "Proxy-Authorization" "date" "Date"
   "organization" "Organization" "priority" "Priority" "server" "Server"
   "require" "Require" "retry-after" "Retry-After"
   "in-reply-to" "In-Reply-To" "unsupported" "Unsupported"
   "warning" "Warning" "min-expires" "Min-Expires"
   "mime-version" "MIME-Version" "accept" "Accept"
   "accept-encoding" "Accept-Encoding" "accept-language" "Accept-Language"
   "alert-info" "Alert-Info" "call-info" "Call-Info"
   "content-disposition" "Content-Disposition"
   "content-language" "Content-Language" "error-info" "Error-Info"
   "reply-to" "Reply-To" "timestamp" "Timestamp"})

(defn- title-case-word [w]
  (if (empty? w) w (str (str/upper (subs w 0 1)) (subs w 1))))

(defn display-name-for
  "The wire-casing to emit for a canonical (lower-case, full-form) header
  name. Known headers use `canonical-casing`'s RFC-conventional spelling;
  an unrecognised header is title-cased word-by-word on `-`
  (`x-custom-header` -> `X-Custom-Header`) rather than left lower-case,
  since an all-lowercase header name in a hand-inspected capture reads as
  a bug, not as 'unrecognised'."
  [canonical]
  (or (get canonical-casing canonical)
      (str/join "-" (map title-case-word (str/split canonical #"-")))))

(defn canonicalize-name
  "Expand a compact form (`v` -> `via`) and lower-case. Header names are
  case-insensitive (RFC 3261 §7.3.1: `Content-Length` and `l` and `L` and
  `CONTENT-LENGTH` all name the same header), so every lookup in this
  library goes through this function first."
  [raw-name]
  (let [lower (str/lower raw-name)]
    (get compact->full lower lower)))

;; ---------------------------------------------------------------------
;; Via — RFC 3261 §20.42
;;
;;   Via = "Via" HCOLON via-parm *(COMMA via-parm)
;;   via-parm = sent-protocol LWS sent-by *( SEMI via-params )
;;   sent-protocol = protocol-name SLASH protocol-version SLASH transport
;; ---------------------------------------------------------------------

(defn decode-via
  "Decode one `via-parm` (already split off a comma-list / separate
  header line by `sip.message`) into `{:protocol-name :protocol-version
  :transport :host :port :params}`. `:params` carries `branch`,
  `received`, and `rport` (present as `true` when the request-side bare
  `;rport` form is used, or a port-number string once a responder fills
  it in per RFC 3581) the same way every other parameter does — there is
  nothing Via-specific about how those three are stored, only about what
  callers do with them.

  Returns `[:error :sip/bad-via]` if the `sent-protocol` isn't
  `name/version/transport` or `sent-by` is empty."
  [s]
  (let [s (str/trim s)
        n (count s)
        proto-end (loop [j 0] (if (and (< j n) (not (contains? #{\space \tab} (nth s j)))) (recur (inc j)) j))
        proto (subs s 0 proto-end)
        parts (str/split proto #"/")]
    (if (not= 3 (count parts))
      [:error :sip/bad-via]
      (let [[pname pver ptransport] parts
            after-proto (g/skip-lws s proto-end)
            hp-end (uri/hostport-span-end s after-proto #{\;})
            hostport (subs s after-proto hp-end)]
        (if (empty? hostport)
          [:error :sip/bad-via]
          (let [hp (uri/parse-hostport hostport)]
            (if (= :error (first hp))
              [:error :sip/bad-via]
              (let [[host port] hp
                    params (g/parse-params-tail s hp-end)]
                {:protocol-name pname :protocol-version pver
                 :transport (str/upper ptransport)
                 :host host :port port :params params}))))))))

(defn encode-via
  [{:keys [protocol-name protocol-version transport host port params]
    :or {protocol-name "SIP" protocol-version "2.0"}}]
  (str protocol-name "/" protocol-version "/" (str/upper transport) " "
       host (when port (str ":" port))
       (g/encode-params params)))

;; ---------------------------------------------------------------------
;; name-addr / addr-spec — shared by To (§20.10), From (§20.20),
;; Contact (§20.39)
;;
;;   name-addr  = [ display-name ] LAQUOT addr-spec RAQUOT
;;   addr-spec  = SIP-URI / SIPS-URI / absoluteURI
;;   (from-spec / to-spec / contact-param) = (name-addr / addr-spec)
;;                                            *(SEMI generic-param)
;; ---------------------------------------------------------------------

(defn decode-addr
  "Decode a To/From/Contact value into `{:display-name :uri :params}`.
  `:display-name` is `nil` when absent. `:params` holds header-level
  parameters (`tag` for To/From, `q`/`expires` for Contact) — only
  reachable when the URI is wrapped in `<...>`; RFC 3261 requires the
  angle brackets whenever a header-level parameter like `tag` is present,
  precisely because without them there's no way to tell a `;tag=...`
  apart from one more URI parameter (see `sip.uri`'s docstring on the
  same ambiguity). A bare `addr-spec` with no brackets is decoded with
  `:params {}` at this level — its own `;name=value`s land in
  `(:params uri)` instead, which is the only place the grammar allows
  them to mean anything in that form.

  Returns `[:error :sip/bad-uri-brackets]` for an unterminated `<`, or
  whatever `sip.uri/parse` returns for a malformed URI inside."
  [s]
  (let [s (str/trim s)
        lt (str/index-of s "<")]
    (if lt
      (let [display-raw (str/trim (subs s 0 lt))
            display-name (cond
                           (empty? display-raw) nil
                           (= (first display-raw) \") (first (g/read-quoted-string display-raw 0))
                           :else display-raw)
            gt (str/index-of s ">" lt)]
        (if (nil? gt)
          [:error :sip/bad-uri-brackets]
          (let [u (uri/parse (subs s (inc lt) gt))]
            (if (and (vector? u) (= :error (first u)))
              u
              {:display-name display-name :uri u
               :params (g/parse-params-tail s (inc gt))}))))
      (let [u (uri/parse s)]
        (if (and (vector? u) (= :error (first u)))
          u
          {:display-name nil :uri u :params {}})))))

(defn- printable-display-name?
  [s]
  (and (seq s) (every? #(or (g/token-char? %) (= % \space)) s)))

(defn encode-addr
  [{:keys [display-name uri params]}]
  (str (when display-name
         (if (printable-display-name? display-name)
           (str display-name " ")
           (str "\"" (g/escape-quoted display-name) "\" ")))
       "<" (uri/encode uri) ">"
       (g/encode-params params)))

;; ---------------------------------------------------------------------
;; CSeq — RFC 3261 §20.16
;;
;;   CSeq = "CSeq" HCOLON 1*DIGIT LWS Method
;; ---------------------------------------------------------------------

(defn decode-cseq
  [s]
  (let [s (str/trim s)
        sp (str/index-of s " ")]
    (if (nil? sp)
      [:error :sip/bad-cseq]
      (let [n (g/parse-uint (subs s 0 sp))
            method (str/trim (subs s (inc sp)))]
        (if (or (nil? n) (empty? method))
          [:error :sip/bad-cseq]
          {:seq n :method method})))))

(defn encode-cseq [{:keys [seq method]}] (str seq " " method))

;; ---------------------------------------------------------------------
;; small scalar headers
;; ---------------------------------------------------------------------

(defn decode-uint-header
  "Shared decoder for the header fields whose entire value is
  `1*DIGIT` — `Max-Forwards` (§20.22) and `Content-Length` (§20.14).
  `reason` is the caller-specific error keyword to return on failure."
  [s reason]
  (let [n (g/parse-uint (str/trim s))]
    (if n n [:error reason])))
