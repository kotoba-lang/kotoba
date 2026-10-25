(ns kami.ongaku.notation.rational
  "Exact rational arithmetic as a portable {:rational/num :rational/den}
  record (den > 0, gcd(num,den) = 1). Needed because ClojureScript's
  number tower is IEEE-754 doubles only — unlike Clojure, `(/ 1 4)` in
  cljs is 0.25, not an exact ratio. Every duration/time-signature
  computation in kami.ongaku.notation(.duration) goes through this ns
  instead of native `/`/`*`/`+` so \"no floats\" holds on both platforms.

  Values are always kept in normalized form, so equality is just
  structural map `=` — no custom comparator needed.")

(defn- gcd [a b]
  (if (zero? b) (if (neg? a) (- a) a) (recur b (mod a b))))

(defn make
  "Normalize n/d: reduce by gcd, keep the denominator positive."
  [n d]
  (when (zero? d) (throw (ex-info "rational: zero denominator" {:num n :den d})))
  (let [sign (if (neg? d) -1 1)
        n (* sign n)
        d (* sign d)
        g (gcd n d)
        g (if (zero? g) 1 g)]
    {:rational/num (quot n g) :rational/den (quot d g)}))

(defn int->rational [n] (make n 1))

(defn integer-value? [{:rational/keys [den]}] (= den 1))

(defn ->int
  "Extract the integer value; throws if the rational is not exact (den != 1)."
  [{:rational/keys [num] :as r}]
  (when-not (integer-value? r) (throw (ex-info "rational: not an exact integer" {:r r})))
  num)

(defn add
  [{n1 :rational/num d1 :rational/den} {n2 :rational/num d2 :rational/den}]
  (make (+ (* n1 d2) (* n2 d1)) (* d1 d2)))

(defn negate [{:rational/keys [num den]}] (make (- num) den))

(defn sub [a b] (add a (negate b)))

(defn mul
  [{n1 :rational/num d1 :rational/den} {n2 :rational/num d2 :rational/den}]
  (make (* n1 n2) (* d1 d2)))

(defn scale
  "Multiply a rational by a plain integer."
  [r n]
  (mul r (int->rational n)))

(def zero (int->rational 0))
(def one (int->rational 1))
