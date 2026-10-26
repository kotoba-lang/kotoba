(ns tls.transport.jvm
  "A TCP transport for `tls.client`, on the JVM.

  Written as `.cljc` with a `:clj` reader conditional rather than as `.clj`:
  this workspace forbids new production `.clj` files (ADR-2608201300), and a
  transport is exactly the sort of file that should have a ClojureScript
  sibling later -- `node:net` implements the same two functions.

  The contract is two functions and nothing else:

      {:send (fn [bytes] ...)}   ; write, flush
      {:recv (fn [] bytes)}      ; block for at least one byte, [] at EOF

  `tls.client` owns all buffering and record framing. That is deliberate: the
  record layer already has to reassemble across TCP segments, and a transport
  that also tried would give two places to get it subtly wrong."
  #?(:clj (:import (java.io InputStream OutputStream)
                   (java.net InetSocketAddress Socket))))

#?(:clj
   (defn socket-transport
     "Connect to `host`:`port` and return `{:send :recv :close :socket}`.

      `:timeout-ms` bounds both the connect and each read. A TLS client with no
      read timeout does not fail on a silent peer -- it hangs, which in a test
      suite is indistinguishable from a slow one and in production is a leaked
      thread."
     ([host port] (socket-transport host port {}))
     ([host port {:keys [timeout-ms buffer-size] :or {timeout-ms 15000 buffer-size 16640}}]
      (let [sock (Socket.)]
        (.connect sock (InetSocketAddress. ^String host (int port)) (int timeout-ms))
        (.setSoTimeout sock (int timeout-ms))
        (.setTcpNoDelay sock true)
        (let [in (.getInputStream sock)
              out (.getOutputStream sock)
              buf (byte-array buffer-size)]
          {:socket sock
           :send (fn [bytes]
                   (.write ^OutputStream out (byte-array (map unchecked-byte bytes)))
                   (.flush ^OutputStream out)
                   (count bytes))
           :recv (fn []
                   (let [n (.read ^InputStream in buf)]
                     ;; -1 is EOF and must become an empty vector, not nil and
                     ;; not an exception: `tls.client` distinguishes "no more
                     ;; bytes" from "no bytes yet" and only the former ends a
                     ;; read loop.
                     (if (neg? n)
                       []
                       (mapv #(bit-and % 0xff) (take n (seq buf))))))
           :close (fn [] (.close sock))})))))

#?(:clj
   (defn with-socket
     "Run `f` against a transport and always close the socket."
     [host port opts f]
     (let [t (socket-transport host port opts)]
       (try (f t) (finally ((:close t)))))))
