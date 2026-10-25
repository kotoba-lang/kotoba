(ns prolific.evidence
  "An action's return value is not evidence that the action happened.

  This namespace exists because of measured failures, not caution. Driving
  the Prolific researcher signup form on 2026-07-30 produced three reports
  of success with nothing behind them:

    type   -> \"Typed\"                 4 characters were silently dropped
    key    -> \"Pressed tab\"           focus never moved, so the next value
                                        was concatenated onto the previous field
    resize -> \"after=622,-1049,...\"   the window had not moved one pixel;
                                        the tool echoed the requested bounds

  Each was indistinguishable from success at the call site. The only thing
  that caught them was reading the target's own state back afterwards. So a
  step is complete when an independent read-back matches the intent — never
  because the actuator said so.

  The verdict taxonomy is not decoration. Each verdict has a DIFFERENT
  repair, and picking the wrong one is how the form got worse instead of
  better: a truncated field looks like it needs the missing suffix typed,
  and typing the suffix is exactly what corrupted it a second time.

  Pure: takes three strings, returns data."
  (:require [kotoba.lang.text :as str]))

(def verdicts
  "Every outcome a verified write can have, with the repair it calls for.

  `:retry-same-channel?` is the field worth reading twice. When a channel
  reports success and changes nothing, repeating the call is superstition —
  the channel is not delivering, and the only useful move is a different
  channel (see `prolific.channel`)."
  {:match      {:ok? true
                :repair nil
                :retry-same-channel? false
                :note "read-back equals intent"}

   :unchanged  {:ok? false
                :repair :change-channel
                :retry-same-channel? false
                :note "the actuator claimed success and the value did not move"}

   :truncated  {:ok? false
                ;; NOT :append-missing-suffix. Typing the tail is what turned
                ;; "Research Operations" into "Research Operat" on the second
                ;; attempt: the field must be written whole, atomically.
                :repair :refill
                :retry-same-channel? true
                :note "observed is a proper prefix of intent — keystrokes were lost"}

   :appended   {:ok? false
                :repair :clear-then-refill
                :retry-same-channel? true
                :note "intent landed on top of the previous value — focus never moved"}

   :absent     {:ok? false
                :repair :re-snapshot
                :retry-same-channel? true
                :note "no such field — the selector or the step is wrong"}

   :mismatch   {:ok? false
                :repair :halt
                :retry-same-channel? false
                :note "observed is neither intent, prior, prefix nor concatenation"}})

(defn verdict
  "Classify one verified write.

  Takes `:intent` (what was asked for), `:before` (the value read BEFORE
  acting) and `:observed` (the value read back AFTER). `:observed` of nil
  means the field could not be read at all.

  `:before` is required for the two verdicts that matter most. Without it
  `:unchanged` and `:appended` are unreachable — a lying channel and a
  swallowed Tab both degrade to `:mismatch`, which halts instead of
  repairing. Callers that cannot read a prior value should pass \"\"
  knowingly, not by omission."
  [{:keys [intent before observed]}]
  (let [intent (str intent)
        before (str before)
        v (cond
            (nil? observed) :absent

            (= observed intent) :match

            ;; Checked before :truncated on purpose. When intent is "" the
            ;; observed prior value is also a prefix of it, and reporting
            ;; that as truncation would send a caller off to refill a field
            ;; through a channel that is not writing at all.
            (and (= observed before) (not= before intent)) :unchanged

            (= observed (str before intent)) :appended

            (and (seq observed)
                 (str/starts-with? intent observed)) :truncated

            :else :mismatch)]
    (assoc (get verdicts v)
           :verdict v
           :intent intent
           :before before
           :observed observed)))

(defn complete?
  "Did this write land exactly as intended?"
  [result]
  (true? (:ok? result)))

(defn navigated?
  "Evidence for a step that SUBMITS rather than types.

  A submit has no field to read back, so the read-back is the location plus
  a marker that only the next screen renders. Both are required: the URL
  fragment alone moved while the form stayed put in early testing, and
  rendered text alone cannot distinguish 'advanced' from 'never left'.

  `expect-marker` is matched case-insensitively against the rendered text."
  [{:keys [url-before url-after text-after expect-marker]}]
  (let [moved? (and url-after (not= url-before url-after))
        marked? (boolean
                 (and expect-marker text-after
                      (str/includes? (str/lower (str text-after))
                                     (str/lower (str expect-marker)))))]
    {:ok? (and moved? marked?)
     :moved? moved?
     :marked? marked?
     :url-before url-before
     :url-after url-after
     :expect-marker expect-marker}))

(defn summarize
  "One line per write, for a human reading the run log.

  Reports the verdict rather than a tick, because \"filled 4 fields\" is the
  shape of report that hid today's failures."
  [results]
  (mapv (fn [{:keys [field verdict intent observed]}]
          {:field field
           :verdict verdict
           :intent intent
           :observed observed})
        results))
