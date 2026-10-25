(ns godaddydns.tool
  "The DNS tool vocabulary over an `IDns`, as ordinary langchain tools
  (explicit input_schema, plain {:name :description :schema :fn} maps), so
  they work through langchain.model's Anthropic/OpenAI adapters as-is.

    list_domains   (read)
    list_records   (read)   {domain, type?, name?}
    upsert_record  (write)  {domain, type, name, data, ttl?}
    delete_record  (write)  {domain, type, name}

  Read tools always hit the IDns. Write tools are *gated* by `dry-run?`:
  when true they DO NOT mutate — they append the intended change to
  `plan-atom` and return a `PLANNED: …` string so the model (and the
  caller) can see exactly what would happen. When false they execute and
  return `APPLIED: …`. This is the safety default for a destructive
  surface (DNS): plan first, apply on explicit opt-in."
  (:require [kotoba.lang.text] [godaddydns.dns :as dns]))

(defn- fmt-record [{:keys [type name data ttl]}]
  (str type " " name " → " data " (ttl " (or ttl 600) ")"))

(defn- plan-change!
  "Record an intended write to `plan-atom` and return its PLANNED line."
  [plan-atom change]
  (when plan-atom (swap! plan-atom conj change))
  (str "PLANNED: " (case (:op change)
                     :upsert (str "upsert " (fmt-record change)
                                  " in " (:domain change))
                     :delete (str "delete " (:type change) " " (:name change)
                                  " in " (:domain change)))
       " — not applied (dry-run). Re-run with dry-run disabled to commit."))

;; ───────────────────────────── tools ───────────────────────────────

(defn list-domains-tool [dns]
  {:name "list_domains"
   :description "List all domains on the account."
   :schema {:type "object" :properties {}}
   :fn (fn [_] (pr-str (dns/-list-domains dns)))})

(defn list-records-tool [dns]
  {:name "list_records"
   :description (str "List DNS records in a domain. Optionally filter by "
                     "record type (A/AAAA/CNAME/MX/TXT/…) and/or host name "
                     "('@' is the apex). Always inspect current records "
                     "before changing anything.")
   :schema {:type "object"
            :properties {:domain {:type "string"}
                         :type {:type "string"
                                :description "Record type filter, e.g. A, CNAME, TXT."}
                         :name {:type "string"
                                :description "Host name filter, e.g. blog or @."}}
            :required ["domain"]}
   :fn (fn [{:keys [domain type name]}]
         (pr-str (dns/-list-records dns domain
                                    (cond-> {}
                                      type (assoc :type type)
                                      name (assoc :name name)))))})

(defn upsert-record-tool [dns dry-run? plan-atom]
  {:name "upsert_record"
   :description (str "Create or replace a DNS record. GoDaddy replaces the "
                     "entire set of records for the (type, name) pair, so to "
                     "edit one of several same-name records, read them first "
                     "and re-send the full set as separate calls is not "
                     "supported — this sets a single record for (type,name).")
   :schema {:type "object"
            :properties {:domain {:type "string"}
                         :type {:type "string" :description "A, AAAA, CNAME, MX, TXT, …"}
                         :name {:type "string" :description "Host name, '@' for apex."}
                         :data {:type "string" :description "Record value, e.g. 1.2.3.4."}
                         :ttl {:type "integer" :description "Seconds; default 600."}}
            :required ["domain" "type" "name" "data"]}
   :fn (fn [{:keys [domain type name data ttl]}]
         (let [ttl (or ttl 600)
               change {:op :upsert :domain domain :type (kotoba.lang.text/upper type)
                       :name name :data data :ttl ttl}]
           (if dry-run?
             (plan-change! plan-atom change)
             (do (dns/-upsert-records! dns domain type name [{:data data :ttl ttl}])
                 (str "APPLIED: upsert " (fmt-record change) " in " domain)))))})

(defn delete-record-tool [dns dry-run? plan-atom]
  {:name "delete_record"
   :description "Delete every record of a (type, name) pair in a domain."
   :schema {:type "object"
            :properties {:domain {:type "string"}
                         :type {:type "string"}
                         :name {:type "string"}}
            :required ["domain" "type" "name"]}
   :fn (fn [{:keys [domain type name]}]
         (let [change {:op :delete :domain domain
                       :type (kotoba.lang.text/upper type) :name name}]
           (if dry-run?
             (plan-change! plan-atom change)
             (do (dns/-delete-records! dns domain type name)
                 (str "APPLIED: delete " (kotoba.lang.text/upper type)
                      " " name " in " domain)))))})

(defn dns-tools
  "The four DNS tools over `dns`. Write tools are gated by `dry-run?`;
  planned writes accumulate in `plan-atom` (an atom holding a vector)."
  [dns dry-run? plan-atom]
  [(list-domains-tool dns)
   (list-records-tool dns)
   (upsert-record-tool dns dry-run? plan-atom)
   (delete-record-tool dns dry-run? plan-atom)])

(def write-tools #{"upsert_record" "delete_record"})
