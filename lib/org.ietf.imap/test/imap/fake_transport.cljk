(ns imap.fake-transport
  "A scripted `imap.transport/Transport` for tests -- no socket, no real
  I/O. `script` is a vector where each element is either a plain string
  (returned by the next `read-line!`) or `{:literal \"...\"}` (returned by
  the next `read-n!`, regardless of the requested `n` -- tests are expected
  to script a preceding line ending in the matching `{n}` marker, exactly
  like a real IMAP server would send one)."
  (:require [imap.transport :as t]))

(defn make
  "Returns {:written (atom [...]) :transport <Transport>}. `written`
  accumulates every `write!`ed command string, plus a trailing `:closed`
  once `close!` is called, so tests can assert on both the commands sent
  and that the session was actually closed."
  [script]
  (let [queue (atom (vec script))
        written (atom [])]
    {:written written
     :transport
     (reify t/Transport
       (write! [_ s] (swap! written conj s))
       (read-line! [_]
         (let [item (first @queue)]
           (swap! queue (comp vec rest))
           (when (map? item) (throw (ex-info "fake-transport: expected a line, script had a literal" {:item item})))
           item))
       (read-n! [_ _n]
         (let [item (first @queue)]
           (swap! queue (comp vec rest))
           (when-not (map? item) (throw (ex-info "fake-transport: expected a literal, script had a line" {:item item})))
           (:literal item)))
       (close! [_] (swap! written conj :closed)))}))
