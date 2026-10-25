(ns prolific.channel
  "Which automation channel may drive a form, decided BEFORE touching it.

  On 2026-07-30 the Prolific signup form was driven through synthetic
  keystrokes because the two better channels turned out to be unavailable —
  but that was discovered one field at a time, by corrupting the form:

    accessibility  Chrome's web content was an AXGroup 500x547 with zero
                   children (renderer accessibility off), so no field could
                   be addressed by label
    coordinate     the window sat on a second display at y=-1049 while the
                   click space was the primary display only
    keystroke      the only channel left — and it dropped characters and
                   swallowed a Tab, concatenating two field values

  The keystroke channel's defect is not flakiness, it is structural: it
  cannot read a field back, so it can never produce the evidence
  `prolific.evidence` requires. A channel that cannot be verified is refused
  even when it is the only one available. Refusing means the run stops with
  the form untouched, which is strictly better than the half-filled form
  that a best-effort attempt actually produced.

  Pure: takes observed capabilities, returns a decision."
  (:require [kotoba.lang.text :as str]))

(def channels
  "Ordered best-first. `reads-back?` is the gate: it is what makes a write
  verifiable, and an unverifiable write is not a write."
  [{:channel :cdp
    :via "agent-browser (Chrome DevTools Protocol)"
    :writes :dom
    :reads-back? true
    :requires [:agent-browser-installed]
    :note "fill + `get value` are DOM-level; no focus, no coordinates, no display"}

   {:channel :extension
    :via "claude-in-chrome (form_input with refs)"
    :writes :dom
    :reads-back? true
    :requires [:extension-connected]
    :note "drives the user's own logged-in profile, which CDP does not"}

   {:channel :ax
    :via "accessibility set_value by label"
    :writes :ax-value
    :reads-back? true
    :requires [:web-content-in-ax-tree]
    :note "needs renderer accessibility, which Chrome leaves off by default"}

   {:channel :keystroke
    :via "synthetic key events to the focused element"
    :writes :synthetic-keys
    :reads-back? false
    :requires [:window-focusable]
    :note "REFUSED: cannot read a field back, so cannot be verified"}

   {:channel :coordinate
    :via "synthetic clicks at screen positions"
    :writes :synthetic-clicks
    :reads-back? false
    :requires [:window-on-clickable-display]
    :note "REFUSED: same, and silently misses when the layout shifts"}])

(defn- unmet [{:keys [requires]} capabilities]
  (vec (remove #(true? (get capabilities %)) requires)))

(defn assess
  "Why each channel is or is not usable, given observed `capabilities`.

  `capabilities` is a map of the probe results, e.g.
  `{:agent-browser-installed true :web-content-in-ax-tree false}`. An absent
  key counts as false: a capability nobody probed is not a capability."
  [capabilities]
  (mapv (fn [c]
          (let [missing (unmet c capabilities)]
            (assoc c
                   :unmet missing
                   :usable? (and (:reads-back? c) (empty? missing))
                   :refused-because (cond
                                      (not (:reads-back? c)) :unverifiable
                                      (seq missing) :unmet-requirement
                                      :else nil))))
        channels))

(defn choose
  "Pick a channel, or refuse.

  Returns `{:channel k}` on success, or `{:channel nil :refusals [...]}`.
  There is deliberately no `:fallback` — falling back to an unverifiable
  channel is the behaviour this namespace exists to prevent."
  [capabilities]
  (let [assessed (assess capabilities)]
    (if-let [pick (first (filter :usable? assessed))]
      {:channel (:channel pick)
       :via (:via pick)
       :assessed assessed}
      {:channel nil
       :refusals (mapv #(select-keys % [:channel :refused-because :unmet])
                       assessed)
       :assessed assessed})))

(defn explain
  "Human-readable refusal, for the message a run prints when it stops.

  Written to name the remedy rather than the failure: the useful thing to
  tell somebody is that installing agent-browser or connecting the
  extension unblocks the run, not that five channels were unavailable."
  [{:keys [channel refusals]}]
  (if channel
    (str "channel: " (name channel))
    (str "no verifiable channel available.\n"
         (str/join "\n"
                   (for [{:keys [channel refused-because unmet]} refusals]
                     (str "  " (name channel) " — " (name refused-because)
                          (when (seq unmet)
                            (str " " (mapv name unmet))))))
         "\n\nremedy: `npm i -g agent-browser && agent-browser install`,"
         " or connect the Chrome extension.")))
