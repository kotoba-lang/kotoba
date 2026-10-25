(ns auth.recovery
  "Recovery codes — the way back in when the second factor is gone.

  A second factor that cannot be recovered from is not a security feature, it
  is a way to lose accounts. The phone is lost, wiped, or upgraded far more
  often than it is stolen by an attacker, so the recovery path is the one most
  people will actually use, and it has to be designed rather than bolted on.

  Pure. Randomness and hashing are the caller's — this namespace decides what
  a code looks like, what counts as the same code typed differently, and when
  one may be spent.

  ## Only digests are stored

  A recovery code is a password that the service handed out. Storing the codes
  themselves means a dump of the store is a dump of working credentials, and
  storing them 'encrypted' with a key in the same system is the same thing
  with extra steps. `verdict` therefore compares digests and never sees a code."
  (:require [kotoba.lang.text :as str]))

(def alphabet
  "Crockford-shaped base32: no I, L, O or U.

  I/L/1 and O/0 are the pairs people mistype from paper, and U is dropped so a
  random code cannot spell something a person would be embarrassed to read
  aloud to support. 32 symbols keeps 5 bits per character, so the arithmetic
  below stays exact."
  "0123456789ABCDEFGHJKMNPQRSTVWXYZ")

(def code-length
  "10 characters = 50 bits. A recovery code is used rarely and typed by hand,
  so it is short enough to transcribe and long enough that guessing it is not
  a strategy even without a rate limit."
  10)

(def default-count
  "How many are issued at once. 10 — enough that losing a few does not force a
  regeneration, few enough to print on one line each."
  10)

(defn code
  "Unsigned bytes -> one recovery code.

  Takes at least `code-length` bytes and uses the low 5 bits of each. The high
  bits are discarded rather than packed: packing would spread one byte across
  two characters, which makes the mapping harder to check by eye and buys
  nothing here — the caller supplies fresh random bytes, so there is no
  entropy to conserve."
  [bytes]
  (when (and (sequential? bytes) (>= (count bytes) code-length))
    (->> (take code-length bytes)
         (map #(nth alphabet (mod % 32)))
         (apply str))))

(defn format-for-display
  "`ABCDE-FGHJK`. Grouped because a 10-character string is transcribed with
  fewer errors in two halves, and hyphenated because that is what people
  expect from a code they were told to write down."
  [c]
  (when (and (string? c) (= code-length (count c)))
    (str (subs c 0 5) "-" (subs c 5))))

(defn normalize
  "What someone typed -> the code they meant, or nil.

  Upper-cases, drops anything outside the alphabet (hyphens, spaces), and maps
  the look-alikes the alphabet deliberately excludes: I and L to 1, O to 0.
  Someone reading a code off paper types what they see, and refusing `O` for
  `0` is refusing a correct code for a handwriting reason."
  [s]
  (when (string? s)
    (let [up (-> s str/upper
                 (str/replace #"[IL]" "1")
                 (str/replace #"O" "0")
                 (str/replace (re-pattern (str "[^" alphabet "]")) ""))]
      (when (= code-length (count up)) up))))

(defn verdict
  "Decide one presented recovery code against the digests still unspent.

  `{:presented-digest  the caller's digest of the NORMALIZED code
    :remaining-digests the digests not yet spent}`

  ->

  `{:ok? true :digest d}`  accept, and the caller must delete `d`
  `{:ok? false :reason :malformed}`  did not normalize to a code at all
  `{:ok? false :reason :no-match}`

  Single-use is not enforced here because it cannot be: deleting the digest is
  a write, and a read-then-write outside a transaction lets two concurrent
  attempts both spend the same code. The caller performs the delete
  atomically and treats a failed delete as a failed sign-in — the same rule
  `onetime.core/verify-once` states for challenges."
  [{:keys [presented-digest remaining-digests]}]
  (cond
    (not (string? presented-digest)) {:ok? false :reason :malformed}
    (contains? (set remaining-digests) presented-digest)
    {:ok? true :digest presented-digest}
    :else {:ok? false :reason :no-match}))

(defn exhausted-warning
  "Whether to tell someone their codes are running out, and how loudly.

  `:none` / `:low` / `:last`. Said at all because the failure this prevents is
  silent: codes are spent one at a time, months apart, and the person finds
  out they have none left at exactly the moment they need one."
  [remaining]
  (cond
    (nil? remaining) :none
    (<= remaining 1) :last
    (<= remaining 3) :low
    :else :none))
