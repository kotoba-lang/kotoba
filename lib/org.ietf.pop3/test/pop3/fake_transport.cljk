(ns pop3.fake-transport
  "A scripted `pop3.transport/Transport` for tests -- no socket, no real
  I/O. `script` is a vector of response lines returned in order by
  successive `read-line!` calls. Captures every `write!`ed command string
  into `written` (an atom), plus a trailing `:closed` once `close!` runs."
  (:require [pop3.transport :as t]))

(defn make [script]
  (let [queue (atom (vec script))
        written (atom [])]
    {:written written
     :transport
     (reify t/Transport
       (write! [_ s] (swap! written conj s))
       (read-line! [_]
         (let [item (first @queue)]
           (swap! queue (comp vec rest))
           item))
       (close! [_] (swap! written conj :closed)))}))
