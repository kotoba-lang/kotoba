(ns sip.uri
  "SIP/SIPS/tel URI parsing and serialization — RFC 3261 §19.1 (SIP-URI /
  SIPS-URI) and RFC 3966 §3 (tel URI, referenced by RFC 3261's
  `telephone-subscriber` production for backward compatibility).

      sip:alice@atlanta.com
      sip:alice:secretword@atlanta.com;transport=tcp
      sips:alice@atlanta.com?subject=project%20x&priority=urgent
      sip:+1-212-555-0101@gateway.com;user=phone
      tel:+1-212-555-0101

  `%XX` percent-escapes inside `user`/`password`/URI-headers are passed
  through byte-for-byte, not decoded — this codec treats them as opaque
  wire text (the same choice `org-ietf-smtp` and `modbus` make for their
  own opaque fields), which is enough to route and re-serialize a
  request without misinterpreting an escaped reserved character as a
  delimiter. A caller that needs the decoded `user` string for display
  can percent-decode it itself.

  Bracket handling for IPv6 references (`sip:[2001:db8::1]:5060`) is the
  one place this namespace can't reuse `sip.grammar/scan-balanced`
  (which understands `<...>` and quoted strings, not `[...]`) — a
  literal `:` inside `[...]` is part of the address, not the host/port
  separator."
  (:require [kotoba.lang.text :as str]
            [sip.grammar :as g]))

(def schemes #{"sip" "sips" "tel"})

;; ---------------------------------------------------------------------
;; host[:port], respecting IPv6 [::1]-style brackets
;; ---------------------------------------------------------------------

(defn hostport-span-end
  "From `i`, the index of the first character in `stop-chars` (default
  `#{\\; \\?}`, the SIP-URI case) that is not inside `[...]` — the end of
  the `hostport` (or tel `telephone-subscriber`) component. Exposed for
  `sip.headers`'s Via `sent-by`, which has this exact same
  IPv6-bracket-aware grammar but a different stop set (no `?headers`
  component on a Via, so `#{\\;}` alone)."
  ([s i] (hostport-span-end s i #{\; \?}))
  ([s i stop-chars]
   (let [n (count s)]
     (loop [j i bracketed? false]
       (cond
         (>= j n) j
         (= (nth s j) \[) (recur (inc j) true)
         (= (nth s j) \]) (recur (inc j) false)
         (and (not bracketed?) (contains? stop-chars (nth s j))) j
         :else (recur (inc j) bracketed?))))))

(defn parse-hostport
  "`s` is exactly the `host[:port]` substring (no leading/trailing
  parameters). Returns `[host port]`; `port` is `nil` when absent, or
  `[:error :sip/bad-port]` if what follows `:` isn't all digits.
  Exposed for `sip.headers`'s Via `sent-by`."
  [s]
  (if (str/starts-with? s "[")
    (let [close (str/index-of s "]")]
      (if (nil? close)
        [:error :sip/bad-ipv6-host]
        (let [host (subs s 0 (inc close))
              rest-s (subs s (inc close))]
          (if (and (seq rest-s) (= (first rest-s) \:))
            (let [port-str (subs rest-s 1)
                  port (g/parse-uint port-str)]
              (if port [host port] [:error :sip/bad-port]))
            [host nil]))))
    (let [colon (str/index-of s ":")]
      (if (nil? colon)
        [s nil]
        (let [port-str (subs s (inc colon))
              port (g/parse-uint port-str)]
          (if port
            [(subs s 0 colon) port]
            [:error :sip/bad-port]))))))

;; ---------------------------------------------------------------------
;; sip: / sips:
;; ---------------------------------------------------------------------

(defn- parse-sip-like [scheme rest-s]
  (let [at (str/index-of rest-s "@")
        [userinfo hostport-and-tail]
        (if at [(subs rest-s 0 at) (subs rest-s (inc at))] [nil rest-s])
        [user password]
        (if userinfo
          (let [colon (str/index-of userinfo ":")]
            (if colon
              [(subs userinfo 0 colon) (subs userinfo (inc colon))]
              [userinfo nil]))
          [nil nil])
        hp-end (hostport-span-end hostport-and-tail 0)
        hostport-str (subs hostport-and-tail 0 hp-end)]
    (if (empty? hostport-str)
      [:error :sip/empty-host]
      (let [hp (parse-hostport hostport-str)]
        (if (= :error (first hp))
          hp
          (let [[host port] hp
                params (g/parse-params-tail hostport-and-tail hp-end #{\?})
                ;; advance past the params tail to find where '?headers' begins
                params-end (loop [j hp-end]
                             (if (and (< j (count hostport-and-tail))
                                      (= (nth hostport-and-tail j) \;))
                               (recur (g/scan-balanced hostport-and-tail (inc j) #{\; \?}))
                               j))
                headers (if (and (< params-end (count hostport-and-tail))
                                  (= (nth hostport-and-tail params-end) \?))
                          (into {}
                                (map (fn [kv]
                                       (let [eq (str/index-of kv "=")]
                                         (if eq
                                           [(subs kv 0 eq) (subs kv (inc eq))]
                                           [kv ""])))
                                     (g/split-top-level (subs hostport-and-tail (inc params-end)) \&)))
                          {})]
            {:scheme scheme :user user :password password :host host :port port
             :params params :headers headers}))))))

;; ---------------------------------------------------------------------
;; tel:
;; ---------------------------------------------------------------------

(defn- parse-tel [rest-s]
  (let [end (hostport-span-end rest-s 0)
        number (subs rest-s 0 end)]
    (if (empty? number)
      [:error :sip/empty-tel-number]
      {:scheme "tel" :number number :params (g/parse-params-tail rest-s end)})))

;; ---------------------------------------------------------------------
;; public entry points
;; ---------------------------------------------------------------------

(defn parse
  "Parse a `sip:`/`sips:`/`tel:` URI. Returns a map keyed by `:scheme`, or
  `[:error reason]`.

  `sip:`/`sips:` -> `{:scheme :user :password :host :port :params
  :headers}` (`:user`/`:password`/`:port` are `nil` when absent; `:params`
  is the `;name=value` map, `:headers` the `?name=value&...` map).

  `tel:` -> `{:scheme \"tel\" :number :params}`.

  Reasons: `:sip/unknown-uri-scheme` (not `sip:`/`sips:`/`tel:`),
  `:sip/empty-host`/`:sip/empty-tel-number` (nothing between the scheme
  and the first parameter/end), `:sip/bad-ipv6-host` (unterminated `[`),
  `:sip/bad-port` (`:` followed by something other than 1+ digits)."
  [s]
  (let [colon (str/index-of s ":")]
    (if (nil? colon)
      [:error :sip/unknown-uri-scheme]
      (let [scheme (str/lower (subs s 0 colon))
            rest-s (subs s (inc colon))]
        (cond
          (contains? #{"sip" "sips"} scheme) (parse-sip-like scheme rest-s)
          (= scheme "tel") (parse-tel rest-s)
          :else [:error :sip/unknown-uri-scheme])))))

(defn encode
  "Serialize a URI map (as `parse` returns it) back to wire text."
  [{:keys [scheme user password host port params headers number]}]
  (case scheme
    "tel"
    (str "tel:" number (g/encode-params params))

    ("sip" "sips")
    (str scheme ":"
         (when user
           (str user (when password (str ":" password)) "@"))
         host
         (when port (str ":" port))
         (g/encode-params params)
         (when (seq headers)
           (str "?" (str/join "&" (map (fn [[k v]] (str k "=" v)) (sort-by key headers))))))))
