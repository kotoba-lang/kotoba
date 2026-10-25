(ns auth.verify
  "Accepting a TOTP code, as a decision.

  `auth.otp` produces codes. This namespace decides whether a code someone
  typed should be accepted — which is a different question, and the one with
  the security content: a generator has no notion of drift, replay, or how
  many guesses a stranger gets.

  Pure. The caller supplies the candidate codes (one per counter in the
  window), because computing them needs an HMAC and on some hosts that is
  asynchronous — see `auth.otp/code-from-hmac`. Everything decided here is
  decided from values.

  ## The three rules, and why each one exists

  **Drift.** Phone clocks are wrong. RFC 6238 §6 says a validator SHOULD
  accept a small number of steps either side, and a validator that accepts
  only the current step rejects real people at a rate that gets the second
  factor switched off. The window is counted in STEPS and never in seconds:
  a window expressed in seconds silently changes width depending on where
  `now` falls inside its own step.

  **Replay.** A TOTP code stays valid for its whole step — 30 seconds is long
  enough to read one over someone's shoulder, or to reuse one captured by a
  phishing page. So a counter that has already been accepted for this secret
  is never accepted again, and the caller persists the last accepted counter.
  Without this the drift window makes it worse, not better: a wider window is
  a longer replay window.

  **Guesses.** Six digits is one in a million per attempt, which is strong
  against a person and weak against a loop. The attempt budget is the caller's
  (`onetime.core/verify-once-limited` already models it); this namespace only
  refuses to pretend a code was right."
  (:require [kotoba.lang.text :as str]))

(def default-window
  "Steps accepted either side of the current one. 1 — so a 30-second step
  admits a clock up to ±30s wrong, and the total window is 90 seconds.

  Not larger by default. Every extra step widens the replay window as well as
  the tolerance, and the counter check below is what keeps that bounded rather
  than free."
  1)

(defn window-counters
  "The counters a code may legitimately have come from, oldest first.

  Oldest first so a caller that computes codes in order and stops at the first
  match spends its HMACs on the likeliest candidates in a predictable order —
  and so the returned sequence reads the same way the window is described."
  ([counter] (window-counters counter default-window))
  ([counter window]
   (let [w (if (and (integer? window) (<= 0 window)) window default-window)]
     (range (- counter w) (+ counter w 1)))))

(defn normalize
  "What someone typed -> the digits they meant.

  Authenticator apps display `123 456`; password managers paste non-breaking
  spaces and hyphens. Rejecting those is rejecting a correct code for a
  formatting reason, which reads to the person as 'this is broken'. Anything
  that is not a digit after this is a real refusal."
  [s]
  (when (string? s)
    (str/replace s #"[^0-9]" "")))

(defn verdict
  "Decide one presented code.

  `{:presented   what the person typed (unnormalised is fine)
    :codes       {counter -> code} for the counters in the window
    :last-used   the highest counter already accepted for this secret, or nil
    :digits      expected length, default 6}`

  ->

  `{:ok? true  :counter n}`                    accept, and persist `n`
  `{:ok? false :reason :malformed}`            not `digits` digits at all
  `{:ok? false :reason :no-match}`             a wrong code
  `{:ok? false :reason :replayed :counter n}`  right code, already spent

  `:replayed` is distinguished from `:no-match` deliberately. To the caller
  they are both refusals and must look identical to the person typing — but
  they are not the same event: a replay is a code that WAS valid, which is a
  signal worth recording, and a caller that cannot tell them apart cannot ever
  notice one."
  [{:keys [presented codes last-used digits] :or {digits 6}}]
  (let [typed (normalize presented)]
    (cond
      (or (nil? typed) (not= digits (count typed)))
      {:ok? false :reason :malformed}

      :else
      (let [hit (some (fn [[counter code]] (when (= code typed) counter))
                      ;; Sorted so a code that somehow matches two counters
                      ;; (possible only with a degenerate secret) resolves to
                      ;; the newest, which is the one a replay check can bound.
                      (sort-by key > codes))]
        (cond
          (nil? hit) {:ok? false :reason :no-match}
          (and (some? last-used) (<= hit last-used)) {:ok? false :reason :replayed :counter hit}
          :else {:ok? true :counter hit})))))
