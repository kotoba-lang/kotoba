(ns auth.cli
  "Command dispatch and rendering for the `authenticator-clj` CLI. Pure logic
  sits in auth.otp / auth.uri / auth.db; this namespace is the IO shell —
  it loads the vault, prints, and saves."
  (:require [auth.db :as db]
            [auth.otp :as otp]
            [auth.uri :as uri]
            [auth.vault :as vault]
            [auth.clock :as clock]
            [auth.base32 :as base32]
            [kotoba.lang.text :as str]))

;; ───────────────────────── rendering helpers ─────────────────────────

(defn- pad-right [s n]
  (let [s (str s)] (str s (apply str (repeat (max 0 (- n (count s))) " ")))))

(defn- spaced
  "Splits a code in the middle for readability: 123456 → \"123 456\"."
  [code]
  (let [mid (quot (count code) 2)]
    (str (subs code 0 mid) " " (subs code mid))))

(defn- account-label [{:account/keys [issuer name]}]
  (if (seq issuer) (str issuer " (" name ")") (str name)))

(defn- render-code [a now]
  (let [code  (otp/account-code a now)
        right (if (= :hotp (:account/type a))
                (str "#" (:account/counter a))
                (str (otp/remaining-seconds now (or (:account/period a) 30)) "s"))]
    (println (str "  " (pad-right (spaced code) 10)
                  "  " (pad-right right 5)
                  "  " (account-label a)))))

(defn- ->int [s default]
  (if (and s (re-matches #"\d+" (str s)))
    #?(:clj (Long/parseLong s) :cljs (js/parseInt s 10))
    default))

(defn- parse-flags [args]
  (loop [a args, m {}]
    (cond
      (empty? a) m
      (str/starts-with? (str (first a)) "--")
      (let [k (keyword (subs (first a) 2))
            v (second a)]
        ;; a value that is itself a flag (or missing) means this flag had none
        (if (and v (not (str/starts-with? (str v) "--")))
          (recur (drop 2 a) (assoc m k v))
          (recur (rest a) (assoc m k nil))))
      :else (recur (rest a) m))))

;; ───────────────────────── commands ─────────────────────────

(defn- cmd-code [args]
  (let [conn  (vault/load-conn)
        now   (clock/now-seconds)
        q     (first args)
        accts (db/search conn q)]
    (if (empty? accts)
      (println (if q
                 (str "No accounts match: " q)
                 "No accounts yet. Add one:  authenticator-clj add <otpauth-uri>"))
      (do
        (doseq [a accts] (render-code a now))
        ;; HOTP is event-based: viewing a code consumes the counter.
        (when-let [hotps (seq (filter #(= :hotp (:account/type %)) accts))]
          (doseq [a hotps] (db/bump-counter! conn (:account/id a)))
          (vault/save-conn! conn))))
    0))

(defn- cmd-list [_]
  (let [conn  (vault/load-conn)
        accts (db/all conn)]
    (if (empty? accts)
      (println "No accounts yet.")
      (do
        (println (str "  " (pad-right "TYPE" 6) "  " (pad-right "DIGITS" 7) "  ACCOUNT"))
        (doseq [a accts]
          (println (str "  " (pad-right (name (or (:account/type a) :totp)) 6)
                        "  " (pad-right (or (:account/digits a) 6) 7)
                        "  " (account-label a))))))
    0))

(defn- account-from-flags [flags]
  {:account/name      (:name flags)
   :account/issuer    (:issuer flags)
   :account/secret    (some-> (:secret flags) (str/replace #"\s" "") str/upper)
   :account/type      (keyword (or (:type flags) "totp"))
   :account/algorithm (keyword (str/lower (or (:algorithm flags) "sha1")))
   :account/digits    (->int (:digits flags) 6)
   :account/period    (->int (:period flags) 30)
   :account/counter   (->int (:counter flags) 0)})

(defn- cmd-add [args]
  (let [first-arg (first args)
        acct (if (and first-arg (str/starts-with? (str/lower (str first-arg)) "otpauth://"))
               (uri/parse first-arg)
               (account-from-flags (parse-flags args)))
        secret (:account/secret acct)]
    (cond
      (nil? acct)
      (do (println "Could not parse otpauth URI.") 1)

      ;; str/blank? handles nil correctly — don't (str nil) first, that yields "nil"
      (str/blank? (:account/name acct))
      (do (println "An account name is required (--name, or use an otpauth:// URI).") 1)

      (or (str/blank? secret) (empty? (base32/decode secret)))
      (do (println "A valid Base32 --secret is required.") 1)

      (not (contains? #{:totp :hotp} (:account/type acct)))
      (do (println "--type must be totp or hotp.") 1)

      (not (contains? #{:sha1 :sha256 :sha512} (:account/algorithm acct)))
      (do (println "--algorithm must be sha1, sha256 or sha512.") 1)

      (not (<= 6 (or (:account/digits acct) 6) 8))
      (do (println "--digits must be 6, 7 or 8.") 1)

      (and (= :totp (:account/type acct)) (not (pos? (or (:account/period acct) 30))))
      (do (println "--period must be a positive number of seconds.") 1)

      :else
      (let [conn (vault/load-conn)]
        (db/put! conn acct)
        (vault/save-conn! conn)
        (println (str "Added " (account-label acct) "."))
        (render-code (db/get-by-id conn (db/account-id acct)) (clock/now-seconds))
        0))))

(defn- cmd-remove [args]
  (let [q     (first args)
        conn  (vault/load-conn)
        match (db/search conn q)]
    (cond
      (str/blank? (str q)) (do (println "Usage: authenticator-clj remove <query>") 1)
      (empty? match)       (do (println (str "No account matches: " q)) 1)
      (> (count match) 1)
      (do (println (str "Ambiguous — " (count match) " accounts match \"" q "\":"))
          (doseq [a match] (println (str "  " (account-label a))))
          (println "Refine your query.")
          1)
      :else
      (let [a (first match)]
        (db/remove! conn (:account/id a))
        (vault/save-conn! conn)
        (println (str "Removed " (account-label a) "."))
        0))))

(defn- cmd-export [args]
  (let [conn (vault/load-conn)]
    (doseq [a (db/search conn (first args))]
      (println (uri/build a)))
    0))

(defn- cmd-import [args]
  (let [path (first args)]
    (if (str/blank? (str path))
      (do (println "Usage: authenticator-clj import <file-of-otpauth-uris>") 1)
      (let [conn  (vault/load-conn)
            lines (str/split-lines (vault/read-text path))
            uris  (->> lines (map str/trim) (filter #(str/starts-with? (str/lower %) "otpauth://")))
            accts (keep uri/parse uris)]
        (doseq [a accts] (db/put! conn a))
        (vault/save-conn! conn)
        (println (str "Imported " (count accts) " account(s).")) 0))))

(def ^:private help-text
  (str/join "\n"
    ["authenticator-clj — Authy-like TOTP/HOTP manager (ClojureScript + Datomic-API vault)"
     ""
     "USAGE"
     "  authenticator-clj [code] [query]   Show current codes (all, or matching query)"
     "  authenticator-clj list             List stored accounts (no codes)"
     "  authenticator-clj add <otpauth://…>            Add by Key-URI (e.g. scanned QR)"
     "  authenticator-clj add --name N --secret BASE32 [--issuer I] [--type totp|hotp]"
     "                        [--algorithm sha1|sha256|sha512] [--digits 6|8] [--period 30]"
     "  authenticator-clj remove <query>   Remove the single matching account"
     "  authenticator-clj export [query]   Print accounts as otpauth:// URIs"
     "  authenticator-clj import <file>    Add every otpauth:// URI in a file"
     "  authenticator-clj help"
     ""
     (str "Vault: " (vault/default-path) "  (EDN, mode 0600)")]))

(defn- print-help [] (println help-text) 0)

(defn run
  "Dispatches a seq of CLI args. Returns an integer exit code."
  [args]
  (let [[cmd & more] args]
    (case cmd
      (nil "code" "show" "gen") (cmd-code more)
      ("list" "ls")             (cmd-list more)
      "add"                     (cmd-add more)
      ("remove" "rm" "delete")  (cmd-remove more)
      "export"                  (cmd-export more)
      "import"                  (cmd-import more)
      ("help" "-h" "--help")    (print-help)
      (do (println (str "Unknown command: " cmd "\n")) (print-help) 1))))
