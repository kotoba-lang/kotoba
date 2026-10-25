(ns rtsp.transport
  "The `Transport` header — [RFC 2326] §12.39 — the one header whose
  value is its own comma-separated, semicolon-parameterized
  mini-grammar rather than a flat string, and the header that actually
  carries the information SETUP negotiates: which channels a client's
  RTP/RTCP will arrive on, whether that's UDP or the interleaved-in-TCP
  form `rtsp.interleaved` implements.

  ABNF (§12.39, reproduced from the fetched RFC text):

    Transport      = \"Transport\" \":\" 1#transport-spec
    transport-spec = transport-protocol/profile[/lower-transport] *parameter
    parameter      = ( \"unicast\" | \"multicast\" )
                    | \";\" \"destination\" [ \"=\" address ]
                    | \";\" \"interleaved\" \"=\" channel [ \"-\" channel ]
                    | \";\" \"append\"
                    | \";\" \"ttl\" \"=\" ttl
                    | \";\" \"layers\" \"=\" 1*DIGIT
                    | \";\" \"port\" \"=\" port [ \"-\" port ]
                    | \";\" \"client_port\" \"=\" port [ \"-\" port ]
                    | \";\" \"server_port\" \"=\" port [ \"-\" port ]
                    | \";\" \"ssrc\" \"=\" ssrc
                    | \";\" \"mode\" = <\"> 1#mode <\">

  A header value is `1#transport-spec` — one or more specs, comma
  separated, each an independent transport the client/server is willing
  to use (§12.39's own example negotiates multicast *and* unicast in one
  header). Splitting on top-level commas (not commas inside a quoted
  `mode` list) and then on top-level semicolons within each spec is what
  this namespace actually does; it does not try to be a general ABNF
  interpreter for a grammar this small.")

(require '[kotoba.lang.text :as str])

(defn- split-top-level
  "Split `s` on every occurrence of `ch` that is not inside a `\"..\"`
  quoted string — needed because `mode=\"PLAY\"` and, in principle, a
  comma-separated `mode` list inside those quotes must not be mistaken
  for a spec/parameter boundary."
  [s ch]
  (loop [i 0 start 0 in-quote? false acc []]
    (if (>= i (count s))
      (conj acc (subs s start))
      (let [c (nth s i)]
        (cond
          (= c \") (recur (inc i) start (not in-quote?) acc)
          (and (= c ch) (not in-quote?)) (recur (inc i) (inc i) in-quote? (conj acc (subs s start i)))
          :else (recur (inc i) start in-quote? acc))))))

(defn- parse-range [v]
  (let [[a b] (str/split v #"-" 2)]
    (if b {:from (parse-long a) :to (parse-long b)} {:from (parse-long a)})))

(defn- parse-parameter [p]
  (let [p (str/trim p)]
    (cond
      (= p "unicast") [:unicast true]
      (= p "multicast") [:multicast true]
      (= p "append") [:append true]
      :else
      (let [eq (str/index-of p \=)]
        (if (nil? eq)
          [:unknown p]
          (let [k (subs p 0 eq)
                v (subs p (inc eq))]
            (case k
              "destination" [:destination v]
              "interleaved" [:interleaved (parse-range v)]
              "ttl" [:ttl (parse-long v)]
              "layers" [:layers (parse-long v)]
              "port" [:port (parse-range v)]
              "client_port" [:client-port (parse-range v)]
              "server_port" [:server-port (parse-range v)]
              "ssrc" [:ssrc v]
              "mode" [:mode (str/split (str/replace v #"\"" "") #",")]
              [:unknown p])))))))

(defn parse-spec
  "One `transport-spec` -> `{:transport-protocol \"RTP\" :profile \"AVP\"
  :lower-transport \"TCP\" ...parameters}`. `lower-transport` is present
  only if the spec had a third `/`-segment (it is `[optional]` in the
  grammar)."
  [spec]
  (let [parts (str/split spec #";")
        proto-part (first parts)
        proto-segs (str/split proto-part #"/")]
    (if (< (count proto-segs) 2)
      [:error :rtsp/malformed-transport-protocol]
      (let [base {:transport-protocol (nth proto-segs 0) :profile (nth proto-segs 1)}
            base (if (= 3 (count proto-segs)) (assoc base :lower-transport (nth proto-segs 2)) base)
            params (map parse-parameter (rest parts))]
        (if (some #(= :unknown (first %)) params)
          [:error :rtsp/malformed-transport-parameter {:parameter (second (first (filter #(= :unknown (first %)) params)))}]
          [:ok (reduce (fn [m [k v]] (assoc m k v)) base params)])))))

(defn decode
  "`Transport` header value -> `[:ok [spec ...]]` or
  `[:error :rtsp/malformed-transport-protocol]` /
  `[:error :rtsp/malformed-transport-parameter ...]`."
  [value]
  (let [specs (split-top-level value \,)
        parsed (map parse-spec specs)]
    (if-let [failure (first (filter #(= :error (first %)) parsed))]
      failure
      [:ok (mapv second parsed)])))

(defn- encode-range [{:keys [from to]}] (if to (str from "-" to) (str from)))

(defn- encode-parameter [[k v]]
  (case k
    :unicast "unicast"
    :multicast "multicast"
    :append "append"
    :destination (str "destination=" v)
    :interleaved (str "interleaved=" (encode-range v))
    :ttl (str "ttl=" v)
    :layers (str "layers=" v)
    :port (str "port=" (encode-range v))
    :client-port (str "client_port=" (encode-range v))
    :server-port (str "server_port=" (encode-range v))
    :ssrc (str "ssrc=" v)
    :mode (str "mode=\"" (str/join "," v) "\"")))

(defn encode-spec [{:keys [transport-protocol profile lower-transport] :as spec}]
  (str transport-protocol "/" profile (when lower-transport (str "/" lower-transport))
       (str/join "" (for [[k v] spec
                           :when (not (#{:transport-protocol :profile :lower-transport} k))]
                       (str ";" (encode-parameter [k v]))))))

(defn encode [specs] (str/join "," (map encode-spec specs)))
