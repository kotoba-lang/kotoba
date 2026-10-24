(ns meta-webhook.handshake
  "The one-time GET verification handshake Meta requires when you register a
  webhook URL (WhatsApp Business Cloud API and Messenger Platform both use
  this identical scheme): `GET ?hub.mode=subscribe&hub.verify_token=X&
  hub.challenge=Y` — respond 200 with the literal `challenge` body if
  `verify-token` matches your app's configured value, otherwise reject.
  Pure, portable `.cljc` (string comparison only, no I/O, no crypto).")

(defn verify-handshake
  "`query` is `{:mode :verify-token :challenge}` (the three `hub.*` query
  params, without the `hub.` prefix — callers strip that from the raw
  request). Returns `challenge` (to echo back as the response body) if
  `mode` is \"subscribe\" and `verify-token` matches `expected-verify-token`,
  else nil (caller should respond 403)."
  [{:keys [mode verify-token challenge]} expected-verify-token]
  (when (and (= mode "subscribe")
             (not-empty expected-verify-token)
             (= verify-token expected-verify-token))
    challenge))
