(ns sdp.attrs
  "Parsers for the handful of `a=` attribute values a real media session
  actually depends on to be machine-readable, not just carried as text.

  [RFC 4566] itself defines `attribute = (att-field \":\" att-value) /
  att-field` and stops there — `att-value` is `byte-string`, opaque as
  far as the base grammar is concerned. `rtpmap` and `fmtp` are defined
  *by* 4566 (section 6, as the two attributes SDP itself gives special
  meaning), while `rtcp-fb` ([RFC 4585] section 4.2) and `ssrc`
  ([RFC 5576] section 4.1) are attributes *registered under* the 4566
  extension point by later RFCs. Parsing them here is a deliberate step
  past what 4566 alone requires, because an SDP library that stops at
  \"attribute value is a string\" cannot answer the question codecs and
  payload types actually get negotiated with."
  (:require [kotoba.lang.text]))

(defn parse-rtpmap
  "`a=rtpmap:<payload-type> <encoding-name>/<clock-rate>[/<encoding-parameters>]`
  — [RFC 4566] §6. The payload type is the same integer `m=`'s `fmt`
  list carries as a string; joining the two is the entire point of this
  attribute existing."
  [value]
  (if-let [[_ pt rest] (re-matches #"(\d+) (.+)" value)]
    (let [parts (kotoba.lang.text/split rest #"/" 3)]
      (if (< (count parts) 2)
        [:error :sdp/malformed-rtpmap]
        [:ok (cond-> {:payload-type (parse-long pt)
                      :encoding-name (nth parts 0)
                      :clock-rate (parse-long (nth parts 1))}
               (= 3 (count parts)) (assoc :encoding-parameters (nth parts 2)))]))
    [:error :sdp/malformed-rtpmap]))

(defn parse-fmtp
  "`a=fmtp:<format> <format specific parameters>` — [RFC 4566] §6. The
  parameter string itself (`profile-level-id=42e01f;...`) is defined
  per-codec by the payload format's own RFC, not by 4566, so it is kept
  as opaque text rather than guessed at."
  [value]
  (if-let [[_ fmt params] (re-matches #"(\S+) (.+)" value)]
    [:ok {:format fmt :parameters params}]
    [:error :sdp/malformed-fmtp]))

(defn parse-rtcp-fb
  "`a=rtcp-fb:<payload-type> <feedback-type> [<feedback-parameter>]` —
  [RFC 4585] §4.2. `<payload-type>` may be the literal token `*`,
  meaning \"applies to every payload type in this media section\"."
  [value]
  (if-let [[_ pt rest] (re-matches #"(\S+) (.+)" value)]
    (let [[fb-type param] (kotoba.lang.text/split rest #" " 2)]
      [:ok (cond-> {:payload-type (if (= pt "*") :* (parse-long pt))
                    :feedback-type fb-type}
             param (assoc :feedback-parameter param))])
    [:error :sdp/malformed-rtcp-fb]))

(defn parse-ssrc
  "`a=ssrc:<ssrc-id> <attribute>[:<value>]` — [RFC 5576] §4.1. The SSRC
  is the same 32-bit identifier RTP's own header carries; this is how an
  offer/answer tells a receiver which CNAME/MSID goes with which
  synchronization source before a single packet has arrived."
  [value]
  (if-let [[_ ssrc rest] (re-matches #"(\d+) (.+)" value)]
    (let [colon (kotoba.lang.text/index-of rest \:)]
      [:ok (if colon
             {:ssrc (parse-long ssrc)
              :attribute (subs rest 0 colon)
              :value (subs rest (inc colon))}
             {:ssrc (parse-long ssrc) :attribute rest})])
    [:error :sdp/malformed-ssrc]))

(def known-parsers
  {"rtpmap" parse-rtpmap
   "fmtp" parse-fmtp
   "rtcp-fb" parse-rtcp-fb
   "ssrc" parse-ssrc})

(defn parse-attribute-line
  "Split `att-field[\":\" att-value]` and, for the four attributes above,
  also decode the value. Everything else stays as `{:field .. :value ..}`
  with `value` opaque — this is the correct outcome for e.g. `a=recvonly`
  (no value at all) or `a=charset:...`, not a gap."
  [raw]
  (let [colon (kotoba.lang.text/index-of raw \:)]
    (if (nil? colon)
      {:field raw}
      (let [field (subs raw 0 colon)
            value (subs raw (inc colon))]
        (if-let [parser (get known-parsers field)]
          (let [[status v] (parser value)]
            (if (= status :ok)
              {:field field :value value :parsed v}
              {:field field :value value :parse-error v}))
          {:field field :value value})))))

(defn encode-attribute-line
  "Inverse of `parse-attribute-line`. Only the raw `:field`/`:value` are
  ever used to encode — `:parsed` is a read convenience, never the source
  of truth, so a round trip is never at the mercy of the sub-parser
  re-serializing a value it decoded loosely."
  [{:keys [field value]}]
  (if value (str field ":" value) field))
