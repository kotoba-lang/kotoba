(ns smtp.client
  "SMTP (RFC 5321) session driver: connect!/ehlo!/auth-login!/send-mail!/
  quit! over an `smtp.transport/Transport`. `smtp.protocol` supplies the
  pure command/response functions; this namespace reads (possibly
  multi-line) responses until the final line and checks status codes."
  (:require [kotoba.lang.text :as str]
            [smtp.protocol :as p]
            [smtp.transport :as t]))

(defn- read-response!
  "Read lines until the final (non-hyphen) line of a possibly multi-line
  SMTP response; returns {:code int :text \"line1\\nline2...\"}."
  [transport]
  (loop [texts []]
    (let [line (t/read-line! transport)]
      (when (nil? line) (throw (ex-info "SMTP connection closed mid-response" {:texts texts})))
      (let [{:keys [code final? text] :as parsed} (p/response-line line)]
        (when-not parsed (throw (ex-info "unparseable SMTP response line" {:line line})))
        (if final?
          {:code code :text (str/join "\n" (conj texts text))}
          (recur (conj texts text)))))))

#?(:clj
(defn connect!
  "Open the transport (real TLS unless `:transport` is given, e.g. a test
  fake) and read the server greeting. Throws if the greeting isn't
  positive (2xx/3xx). Returns a session map."
  ([host] (connect! host {}))
  ([host opts]
   (let [transport (or (:transport opts) (t/tls-connect (assoc opts :host host)))
         session {:transport transport}
         resp (read-response! transport)]
     (when-not (p/positive? (:code resp))
       (t/close! transport)
       (throw (ex-info "SMTP greeting was not positive" resp)))
     session))))

(defn- send-line!
  "Write `line` (already CRLF-terminated) and read its response."
  [{:keys [transport]} line]
  (t/write! transport line)
  (read-response! transport))

(defn- assert-positive! [{:keys [code] :as resp} verb]
  (when-not (p/positive? code)
    (throw (ex-info (str "SMTP " verb " failed: " (:text resp)) (assoc resp :verb verb))))
  resp)

(defn ehlo!
  "EHLO `domain`. Returns `session` with the server's advertised ESMTP
  extensions attached.

  `:capabilities` is the raw line list, as before. `:extensions` is those
  lines parsed into `{\"AUTH\" \"PLAIN LOGIN\" \"SIZE\" \"35882577\"}`,
  `:auth-mechanisms` the SASL set, `:max-size` the SIZE limit — the three
  things a client actually decides on, which callers previously had to
  re-derive by scanning strings themselves."
  [session domain]
  (let [resp (assert-positive! (send-line! session (p/ehlo-line domain)) "EHLO")
        lines (str/split-lines (:text resp))
        extensions (p/parse-extensions lines)]
    (assoc session
           :capabilities lines
           :extensions extensions
           :auth-mechanisms (p/auth-mechanisms extensions)
           :max-size (p/max-size extensions))))

(defn supports?
  "Whether the server advertised an ESMTP extension (case-insensitive)."
  [session extension]
  (contains? (:extensions session {}) (str/upper (str extension))))

#?(:clj
(defn starttls!
  "STARTTLS (RFC 3207), then hand the socket to TLS and re-EHLO.

  For port 587 submission, where the session begins in the clear. This
  library's `tls-connect` covers the other shape — implicit TLS on 465 —
  and a host usually offers one of the two, so both are here rather than
  one being declared the right way.

  `upgrade-fn` takes the current transport and returns a TLS one; injected
  because wrapping a live socket is host-specific and a library reaching
  for `SSLSocketFactory` itself could not be tested without one.

  The re-EHLO is mandatory, not tidiness: RFC 3207 §4.2 requires the
  client to discard what it learned before the upgrade, and servers
  routinely advertise AUTH only *after* TLS. A client that keeps the
  cleartext capability list concludes the server offers no AUTH at all."
  [session domain upgrade-fn]
  (assert-positive! (send-line! session (p/starttls-line)) "STARTTLS")
  (-> session
      (assoc :transport (upgrade-fn (:transport session)))
      (dissoc :capabilities :extensions :auth-mechanisms :max-size)
      (ehlo! domain))))

(defn auth-login!
  "AUTH LOGIN with a plaintext user/pass (an app password for Gmail-style
  accounts, per this library's TLS-only transport). Returns `session`."
  [session user pass]
  (assert-positive! (send-line! session (p/auth-login-line)) "AUTH LOGIN")
  (assert-positive! (send-line! session (p/payload-line (p/base64 user))) "AUTH LOGIN (username)")
  (assert-positive! (send-line! session (p/payload-line (p/base64 pass))) "AUTH LOGIN (password)")
  session)

(defn auth-plain!
  "AUTH PLAIN (RFC 4616) with the credentials on the command line.

  One round trip where LOGIN takes three, and the mechanism LOGIN should
  have been. Sent as an initial response because RFC 4954 §4 permits it
  for PLAIN and every server that advertises PLAIN accepts it."
  [session user pass]
  (assert-positive!
   (send-line! session (p/auth-plain-line
                       (p/base64 (p/plain-credentials user pass))))
   "AUTH PLAIN")
  session)

(defn auth-xoauth2!
  "AUTH XOAUTH2 with an OAuth2 access token.

  What lets an account this application already holds a send-capable OAuth
  grant for actually send, instead of being asked for an app password
  covering exactly what the grant covers.

  A rejected token answers `334` with a base64 JSON error rather than a
  failure code, and the protocol requires an empty line to finish the
  exchange before the real status arrives — a client that treats the 334
  as success reports a send that never happened."
  [session user access-token]
  (let [resp (send-line! session
                         (p/auth-xoauth2-line
                          (p/base64 (p/xoauth2-credentials user access-token))))]
    (if (p/xoauth2-continue? (:code resp))
      (let [final (send-line! session (p/empty-line))]
        (assert-positive! final "AUTH XOAUTH2")
        session)
      (do (assert-positive! resp "AUTH XOAUTH2")
          session))))

(defn authenticate!
  "Pick the strongest mechanism the server advertised and use it.

  Order: XOAUTH2 when a token was given, then PLAIN, then LOGIN. A caller
  that knows which one it wants can still call it directly; this exists so
  the ordinary case does not require every caller to re-derive the same
  preference from `:auth-mechanisms`. The pick itself is `smtp.protocol/auth-pick`."
  [session {:keys [user password access-token] :as creds}]
  (let [mechanisms (:auth-mechanisms session #{})
        pick (p/auth-pick-from mechanisms creds)]
    (cond
      (= pick p/auth-xoauth2) (auth-xoauth2! session user access-token)
      (= pick p/auth-plain) (auth-plain! session user password)
      (= pick p/auth-login) (auth-login! session user password)
      (= pick p/auth-none) session
      :else
      (throw (ex-info "この SMTP サーバーが受け付ける認証方式に対応していません。"
                      {:type :smtp/no-supported-mechanism
                       :offered mechanisms})))))

(defn- recipients-of [msg]
  (let [as-list (fn [v] (cond (nil? v) []
                              (string? v) [v]
                              (sequential? v) (vec (remove nil? v))
                              :else [v]))]
    (vec (distinct (concat (as-list (:to msg))
                           (as-list (:cc msg))
                           (as-list (:bcc msg)))))))

(defn send-mail!
  "Send one message: MAIL FROM / RCPT TO… / DATA / dot-stuffed payload.

  `msg`: `{:to :cc :bcc :subject :body :in-reply-to}`. `:to`/`:cc`/`:bcc`
  each take one address or many. `from` comes from `session`'s `:from`,
  set by the caller, since it is the same across every send on one
  connection.

  **Every recipient goes in one transaction.** This used to take a single
  `:to` and send once, which meant a caller with three recipients either
  dropped two or opened three transactions — and three transactions is
  three separate messages, each with only its own recipient in the header,
  so nobody can see who else received it and a reply-all goes to one
  person. RFC 5321 §3.3 is explicit that a mail transaction has one MAIL
  FROM and *one or more* RCPT TO.

  `:raw` sends a prebuilt RFC 5322 message instead of `mime-message`'s
  minimal one — for a caller that has already composed headers this
  library does not model (MIME parts, Content-Transfer-Encoding, RFC 2047
  encoded-words in the subject).

  A recipient the server refuses does not abort the send: RFC 5321 §3.3
  allows some RCPT TO commands to fail while others succeed, and the
  message is delivered to those that were accepted. Returns `session` with
  `:accepted` and `:rejected` so the caller can tell which happened —
  throwing on the first refusal would turn a partial success into a total
  failure and lose the mail that did go out. All recipients refused is a
  genuine failure and does throw."
  [{:keys [from] :as session} msg]
  (let [recipients (recipients-of msg)
        _ (when (empty? recipients)
            (throw (ex-info "SMTP send with no recipient" {:msg (dissoc msg :body)})))
        _ (assert-positive! (send-line! session (p/mail-from-line from))
                            "MAIL FROM")
        results (reduce (fn [acc recipient]
                          (let [resp (send-line! session (p/rcpt-to-line recipient))]
                            (if (p/positive? (:code resp))
                              (update acc :accepted conj recipient)
                              (update acc :rejected conj
                                      {:recipient recipient
                                       :code (:code resp)
                                       :status (p/enhanced-status (:text resp))
                                       :text (:text resp)}))))
                        {:accepted [] :rejected []}
                        recipients)]
    (when (empty? (:accepted results))
      (throw (ex-info (str "SMTP RCPT TO failed for every recipient: "
                           (str/join "; " (map :text (:rejected results))))
                      (assoc results :verb "RCPT TO"))))
    (assert-positive! (send-line! session (p/data-line)) "DATA")
    (assert-positive! (send-line! session
                                  (p/dot-stuff (or (:raw msg)
                                                   (p/mime-message (assoc msg :from from)))))
                      "DATA payload")
    (merge session results)))

(defn rset!
  "RSET — abandon the current transaction (RFC 5321 §4.1.1.5).

  Named for the command rather than as `reset!`, which would shadow
  `clojure.core/reset!` in every namespace that refers this one.

  What to send after a failed one before reusing the connection: a session
  left mid-transaction rejects the next MAIL FROM, and the error names
  sequencing rather than whatever actually went wrong."
  [session]
  (assert-positive! (send-line! session (p/rset-line)) "RSET")
  session)

(defn noop!
  "NOOP — is this connection still alive (RFC 5321 §4.1.1.9)."
  [session]
  (assert-positive! (send-line! session (p/noop-line)) "NOOP")
  session)

(defn quit!
  "QUIT and close the transport. Swallows a failed QUIT response (the
  transport is closed either way) but not a transport-level exception
  raised before that point."
  [{:keys [transport] :as session}]
  (try (send-line! session (p/quit-line)) (catch #?(:clj Exception :cljs :default) _ nil))
  (t/close! transport)
  nil)
