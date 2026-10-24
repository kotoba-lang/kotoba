(ns kotoba.lang.http.host.httpkit
  "JVM / Babashka host adapter for HTTP servers via `org.httpkit.server`.

  Consumers depend on `io.github.kotoba-lang/http` and add `http-kit/http-kit`
  only through the `:httpkit-host` alias — not as a top-level shipped dep."
  #?(:clj (:require [org.httpkit.server :as impl])))

#?(:clj (def run-server impl/run-server))
#?(:clj (def send! impl/send!))
#?(:clj (def close impl/close))
#?(:clj (def as-channel impl/as-channel))
#?(:clj (def on-receive impl/on-receive))
#?(:clj (def on-close impl/on-close))
#?(:clj (def on-ping impl/on-ping))
#?(:clj (def open? impl/open?))
#?(:clj (def websocket? impl/websocket?))
#?(:clj (def Channel impl/Channel))
#?(:clj (def as-channel impl/as-channel))

#?(:clj
   (defmacro with-channel
     "Ring async / SSE / WebSocket channel binding. Delegates to http-kit."
     [req channel & body]
     `(impl/with-channel ~req ~channel ~@body)))

#?(:clj
   (defn ring-async-response
     "Ring async handler response channel. `org.httpkit.server` never shipped a
     `ring-async-response` var (measured 2026-08-31 against 2.8.0, 2.8.1 and
     2.9.0-beta4 — none of `ns-publics` carries it, and neither does Babashka's
     bundled copy), so the original `(def ring-async-response
     impl/ring-async-response)` could not LOAD: the namespace itself threw
     `No such var: impl/ring-async-response` on every consumer that merely
     required it, taking murakumo's main CI down for ~36h. The shape an async
     Ring handler must return is a plain channel — `as-channel` is what
     creates one, and `send!` puts the response on it. Keep the name alive as
     a function so existing callers keep working, but build it from vars
     http-kit actually exports."
     ([channel] channel)
     ([channel response]
      (impl/send! channel response)
      channel)))
