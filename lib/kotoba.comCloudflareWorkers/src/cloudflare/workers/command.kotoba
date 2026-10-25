(ns cloudflare.workers.command
  "Typed effect commands for the Cloudflare Workers storage bindings
  (KV / D1 / R2).

  A `.kotoba` guest never touches a binding. It *plans*: it returns a vector
  of command values describing what it wants done. The host
  (`cloudflare.workers.admission` then `cloudflare.workers.provider`) decides
  whether each command is admissible and is the only thing that ever holds a
  real `env.<BINDING>` object. That keeps the storage plane out of the guest's
  ambient authority entirely -- there is no capability to leak, because the
  guest is handed none.

  This namespace is the *structural* gate only: shape, types, and bounds that
  hold regardless of policy. Authority questions (is this binding reachable?
  is this key in scope? is this statement registered?) belong to
  `cloudflare.workers.admission`.

  Two structural rules carry most of the safety weight:

  1. **No raw SQL crosses the boundary.** A D1 command names a *statement id*
     that the operator registered in policy; the SQL text lives host-side. A
     command carrying `:sql` is rejected with an explicit `:raw-sql-forbidden`
     rather than a generic shape error, because that is the one denial an
     operator most needs to see by name. Guest-authored SQL injection is
     therefore not mitigated here, it is unrepresentable.

  2. **Unknown keys are rejected, not ignored.** A command map is closed. An
     extra key is a denial (`:unknown-command-key`), so a future provider
     option can never be smuggled in by a guest that learned about it before
     the policy did.

  Everything here is pure `.cljc` with no clock, no I/O, and no randomness --
  `admission` and `provider` take `now` as a parameter for the same reason.")

;; ---------------------------------------------------------------------------
;; Command catalogue
;; ---------------------------------------------------------------------------

(def command-specs
  "Closed catalogue of effect commands.

  `:cap` is the capability kind a command requires, except for D1 where it is
  `:statement-mode`: the requirement is derived from the *registered* mode of
  the named statement, never from anything the guest supplies. A guest cannot
  label a write as a read to slip past a read-only grant."
  {:cf.kv/get    {:binding-kind :kv :cap :cf/kv-read
                  :required #{:binding :key}        :optional #{}}
   :cf.kv/put    {:binding-kind :kv :cap :cf/kv-write
                  :required #{:binding :key :value} :optional #{:ttl}}
   :cf.kv/delete {:binding-kind :kv :cap :cf/kv-write
                  :required #{:binding :key}        :optional #{}}
   :cf.d1/exec   {:binding-kind :d1 :cap :statement-mode
                  :required #{:binding :statement}  :optional #{:params}}
   :cf.r2/get    {:binding-kind :r2 :cap :cf/r2-read
                  :required #{:binding :key}        :optional #{}}
   :cf.r2/put    {:binding-kind :r2 :cap :cf/r2-write
                  :required #{:binding :key :body}  :optional #{:content-type}}
   :cf.r2/delete {:binding-kind :r2 :cap :cf/r2-write
                  :required #{:binding :key}        :optional #{}}})

(def capability-kinds
  "Capability kinds this family can require. Deny-by-default: a policy that
  grants none of these can drive no storage at all."
  #{:cf/kv-read :cf/kv-write :cf/d1-read :cf/d1-write :cf/r2-read :cf/r2-write})

(def read-commands
  "Commands that only observe. Used for quota accounting and for the
  read/write split in receipts."
  #{:cf.kv/get :cf.r2/get})

(def sql-bearing-keys
  "Keys that would carry guest-authored SQL. Their presence is a named denial."
  #{:sql :query :statement-sql :raw})

;; Cloudflare documented limits, used as hard structural ceilings. A policy may
;; be stricter; it may not be looser.
(def ^:const max-key-bytes 512)          ; KV key limit; reused for R2 for uniformity
(def ^:const max-params 32)              ; D1 bound parameters per statement
(def ^:const min-ttl-seconds 60)         ; KV expirationTtl floor
(def ^:const max-content-type-length 128)

(def ^:private binding-name-re #"^[A-Z][A-Z0-9_]{0,63}$")
(def ^:private statement-id-re #"^[a-z][a-z0-9-]{0,63}$")

;; ---------------------------------------------------------------------------
;; Portable helpers
;; ---------------------------------------------------------------------------

(defn- char-code
  [s i]
  #?(:clj  (int (.charAt ^String s i))
     :cljs (.charCodeAt s i)))

(defn utf8-byte-count
  "UTF-8 byte length of S without interop asymmetry between clj and cljs.

  Counts a surrogate pair as the 4 bytes it encodes to (high surrogate 4, low
  surrogate 0) so a key of emoji is measured the way Cloudflare measures it,
  not the way `count` would."
  [s]
  (let [n (count s)]
    (loop [i 0 total 0]
      (if (>= i n)
        total
        (let [c (char-code s i)]
          (recur (inc i)
                 (+ total (cond
                            (< c 0x80) 1
                            (< c 0x800) 2
                            (<= 0xD800 c 0xDBFF) 4   ; high surrogate: whole pair
                            (<= 0xDC00 c 0xDFFF) 0   ; low surrogate: already counted
                            :else 3))))))))

(defn- control-char?
  [s]
  (let [n (count s)]
    (loop [i 0]
      (if (>= i n)
        false
        (let [c (char-code s i)]
          (if (or (< c 0x20) (= c 0x7F))
            true
            (recur (inc i))))))))

(defn- non-empty-string?
  [x]
  (and (string? x) (pos? (count x))))

(defn- scalar-param?
  "D1 binds scalars. Collections are rejected rather than stringified, so a
  guest cannot smuggle structure through a parameter slot."
  [x]
  (or (nil? x)
      (string? x)
      (boolean? x)
      (number? x)))

(defn body-byte-count
  "Byte length of an R2/KV payload value. `{:b64 s}` is measured at its decoded
  length (base64 encodes 3 bytes per 4 chars, minus padding) so a policy's
  `:max-value-bytes` means the same thing for text and binary payloads."
  [body]
  (cond
    (string? body) (utf8-byte-count body)
    (and (map? body) (string? (:b64 body)))
    (let [s (:b64 body)
          n (count s)
          pad (cond
                (and (>= n 2) (= \= (nth s (- n 1))) (= \= (nth s (- n 2)))) 2
                (and (>= n 1) (= \= (nth s (- n 1)))) 1
                :else 0)]
      (max 0 (- (quot (* n 3) 4) pad)))
    :else 0))

(defn- base64-string?
  [s]
  (and (string? s)
       (pos? (count s))
       (zero? (mod (count s) 4))
       (some? (re-matches #"^[A-Za-z0-9+/]+={0,2}$" s))))

(defn- valid-body?
  [body]
  (or (string? body)
      (and (map? body)
           (= #{:b64} (set (keys body)))
           (base64-string? (:b64 body)))))

;; ---------------------------------------------------------------------------
;; Structural validation
;; ---------------------------------------------------------------------------

(defn- field-problem
  "First structural problem with FIELD's value, or nil."
  [field value]
  (case field
    :binding
    (when-not (and (non-empty-string? value)
                   (some? (re-matches binding-name-re value)))
      {:reason :malformed-binding-name :field field})

    :key
    (cond
      (not (non-empty-string? value)) {:reason :malformed-key :field field}
      (control-char? value) {:reason :malformed-key :field field
                             :detail :control-character}
      (> (utf8-byte-count value) max-key-bytes)
      {:reason :key-too-long :field field
       :limit max-key-bytes :actual (utf8-byte-count value)}
      :else nil)

    :value
    (when-not (valid-body? value)
      {:reason :malformed-value :field field})

    :body
    (when-not (valid-body? value)
      {:reason :malformed-value :field field})

    :ttl
    (cond
      (not (integer? value)) {:reason :malformed-ttl :field field}
      (< value min-ttl-seconds) {:reason :ttl-out-of-range :field field
                                 :minimum min-ttl-seconds :actual value}
      :else nil)

    :statement
    (when-not (and (non-empty-string? value)
                   (some? (re-matches statement-id-re value)))
      {:reason :malformed-statement-id :field field})

    :params
    (cond
      (not (vector? value)) {:reason :malformed-params :field field
                             :detail :must-be-vector}
      (> (count value) max-params) {:reason :too-many-params :field field
                                    :limit max-params :actual (count value)}
      (not (every? scalar-param? value)) {:reason :malformed-params :field field
                                          :detail :non-scalar-parameter}
      :else nil)

    :content-type
    (cond
      (not (non-empty-string? value)) {:reason :malformed-content-type :field field}
      (> (count value) max-content-type-length)
      {:reason :malformed-content-type :field field :detail :too-long}
      (control-char? value) {:reason :malformed-content-type :field field
                             :detail :control-character}
      :else nil)

    nil))

(defn problems
  "Vector of structural problems with COMMAND; empty means structurally sound.

  Ordered so the most security-relevant signal wins: a command carrying raw
  SQL reports `:raw-sql-forbidden` even if it is malformed in other ways."
  [command]
  (cond
    (not (map? command))
    [{:reason :malformed-command :detail :not-a-map}]

    (some sql-bearing-keys (keys command))
    [{:reason :raw-sql-forbidden
      :detail (vec (sort (filter sql-bearing-keys (keys command))))}]

    :else
    (let [cmd (:cmd command)
          spec (get command-specs cmd)]
      (if (nil? spec)
        [{:reason :unknown-command :cmd cmd}]
        (let [allowed (into #{:cmd} (concat (:required spec) (:optional spec)))
              present (set (keys command))
              extra (sort (remove allowed present))
              missing (sort (remove present (:required spec)))]
          (vec
           (concat
            (map (fn [k] {:reason :unknown-command-key :field k}) extra)
            (map (fn [k] {:reason :missing-required-field :field k}) missing)
            (keep (fn [k]
                    (when (contains? command k)
                      (field-problem k (get command k))))
                  (sort (concat (:required spec) (:optional spec)))))))))))

(defn valid?
  [command]
  (empty? (problems command)))

(defn spec-for
  [command]
  (get command-specs (:cmd command)))

(defn read-command?
  [command]
  (contains? read-commands (:cmd command)))

(defn payload-byte-count
  "Bytes this command would write. Reads and deletes write nothing."
  [command]
  (case (:cmd command)
    :cf.kv/put (body-byte-count (:value command))
    :cf.r2/put (body-byte-count (:body command))
    0))

(defn resource
  "Stable resource string for receipts and policy scoping.

  `kv:SESSIONS/user:42`, `d1:APP_DB#order-by-id`, `r2:ASSETS/img/logo.png`."
  [command]
  (case (:binding-kind (spec-for command))
    :kv (str "kv:" (:binding command) "/" (:key command))
    :d1 (str "d1:" (:binding command) "#" (:statement command))
    :r2 (str "r2:" (:binding command) "/" (:key command))
    nil))
