(ns browseragent.browser.live
  "Live view of the agent's *own* browser.

  The library performs no I/O: it formats events and hands them to an
  injected `:emit-fn` host capability (an SSE/WebSocket push on the
  JVM, a `core.async` tap, or a host UI event callback). With
  no `:emit-fn` this is a silent no-op, so headless runs stay pure.

  A real provider pairs this with a screencast: pass a `:screenshot-fn`
  that returns the current frame (CDP `Page.screencast`, a periodic
  capture, or an Anthropic image block) and it rides the same stream
  the user watches — and can interrupt (take-over)."
  (:require [kotoba.lang.text :as str]))

(defn event
  "Normalize a browser-side event for the UI stream."
  [kind data]
  (merge {:channel :browser :kind kind} data))

(defn emit!
  "Push an event through the injected host transport, if any."
  [{:keys [emit-fn]} ev]
  (when emit-fn (emit-fn ev))
  ev)

(defn frame
  "Build a screencast frame event using the injected `:screenshot-fn`
  (skipped when absent). `state` is the current IBrowser state map."
  [{:keys [screenshot-fn] :as live} {:keys [url title]}]
  (emit! live (event :frame (cond-> {:url url :title title}
                              screenshot-fn (assoc :image (screenshot-fn))))))

(defn handed-over?
  "Take-over latch. The UI flips an injected atom (`:takeover`) to
  signal the human has grabbed the browser; the agent loop checks this
  before each step and yields via a langgraph interrupt when set."
  [{:keys [takeover]}]
  (boolean (and takeover (deref takeover))))

(defn summary [evs]
  (str/join "\n" (map (fn [{:keys [kind url]}] (str kind " " url)) evs)))
