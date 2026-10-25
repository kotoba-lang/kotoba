(ns kaigi.invite
  "Meeting codes and the links that carry them — the \"share a URL and people
  join\" half of the product, as pure functions.

  A meeting in kaigi is addressed by an opaque id, and until now the console
  read one from `?meeting=` and fell back to the literal string `lobby` when
  the URL carried none. That fallback is what made a bare link useless as an
  invitation: everyone who opened the site with no query string landed in the
  same room, and there was no way to *get* a link for a new meeting other than
  inventing an id by hand.

  So this namespace owns two decisions and no I/O.

  ## Why the code is letters in three groups

  `abc-defg-hij` — ten lowercase letters, grouped 3-4-3. The grouping is not
  decoration: a code gets read aloud on a phone call and typed by someone who
  is not looking at it, and ungrouped strings of ten characters get
  transcribed wrong. Letters only, with no digits, because the pairs a reader
  confuses (`0`/`O`, `1`/`l`) are exactly the ones a spoken code produces.

  26^10 is about 1.4e14 codes, so guessing one is not a way in. That is the
  only access control a bare link has, which is the same bargain Meet makes —
  and it is why `:approval-required` still exists in `kaigi.model` for
  meetings that want a door as well as a key.

  ## Randomness is supplied, not taken

  `meeting-code` takes the random numbers as an argument. Portable `.cljc`
  with no clock and no `rand` means the same input always produces the same
  code, so this is testable at all — and the caller in the browser can hand it
  `crypto.getRandomValues`, which is what a code that nobody should be able to
  guess actually requires. A `rand-int` here would have been unguessable
  right up until someone needed to test it."
  (:require [kotoba.lang.text :as str]))

(def alphabet
  "The code alphabet: lowercase letters, no digits. See the namespace
  docstring for why."
  "abcdefghijklmnopqrstuvwxyz")

(def groups
  "Letters per hyphen-separated group. 3-4-3, like Meet's, for the same
  reason: it is the shape people can hold in working memory long enough to
  type it."
  [3 4 3])

(def code-length (reduce + groups))

(defn meeting-code
  "A meeting code from `ints`, a seq of at least `code-length` non-negative
  integers.

  Returns nil when there is not enough randomness rather than padding with
  something deterministic: a short read from the entropy source must not
  silently produce a code with a predictable tail."
  [ints]
  (let [xs (take code-length (filter int? ints))]
    (when (= code-length (count xs))
      ;; `mod`, not `rem`: Clojure's `mod` takes the sign of the divisor, so a
      ;; negative int from an entropy source still lands inside the alphabet
      ;; instead of throwing an index error at 3am.
      (let [letters (mapv #(nth alphabet (mod % (count alphabet))) xs)]
        (->> groups
             (reduce (fn [{:keys [i out]} n]
                       {:i (+ i n)
                        :out (conj out (apply str (subvec letters i (+ i n))))})
                     {:i 0 :out []})
             :out
             (str/join "-"))))))

(defn normalize-code
  "The canonical form of a code a human typed, or nil if it is not one.

  Accepts the code with or without its hyphens, in any case, with surrounding
  or interior whitespace — because all four are what people actually paste,
  and refusing `ABC DEFG HIJ` teaches them the field is broken rather than
  that they made a mistake. Anything that is not exactly `code-length`
  letters is nil; this is a validator, not a coercion that guesses."
  [s]
  (let [letters (-> (str s) str/lower (str/replace #"[^a-z]" ""))]
    (when (= code-length (count letters))
      (meeting-code (map #(str/index-of alphabet %) letters)))))

(defn code?
  "Whether `s` is already a canonical meeting code.

  The `some?` is not redundant: `normalize-code` returns nil for anything that
  is not a code, so comparing it to its input alone reports **nil as a valid
  code** — nil normalizes to nil, and the two are equal. A caller asking \"is
  this a code I can show as one?\" about a URL that carried no meeting id would
  have been told yes."
  [s]
  (let [n (normalize-code s)]
    (and (some? n) (= s n))))

(defn join-path
  "The path-and-query half of an invitation for `meeting-id`.

  Every meeting id is legal here, not just generated codes: a meeting called
  from `kaisha` names its own id, and an invitation to it has to be
  expressible. The id is percent-encoded by the caller — this returns the
  pieces, and `join-url` assembles them, so nothing here has to know how a
  particular host encodes."
  [meeting-id]
  (str "/?meeting=" meeting-id))

(defn join-url
  "The full shareable link: what goes in a chat message.

  `origin` is passed in rather than read from anywhere, so the same fn
  produces the link server-side (for a calendar invitation) and in the
  browser (for the copy button)."
  [origin meeting-id]
  (str origin (join-path meeting-id)))
