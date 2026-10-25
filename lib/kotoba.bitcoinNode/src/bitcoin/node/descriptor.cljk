(ns bitcoin.node.descriptor
  "Fail-closed policy for Bitcoin Core-canonicalized public descriptors."
  (:require [kotoba.lang.text :as str]))

(def max-descriptor-length 16384)

(defn kind [descriptor]
  (cond
    (and (str/starts-with? descriptor "tr(")
         (str/includes? descriptor "multi_a(")) :taproot-multisig
    (str/starts-with? descriptor "tr(") :taproot
    (and (or (str/starts-with? descriptor "wsh(")
             (str/starts-with? descriptor "sh(wsh("))
         (or (str/includes? descriptor "multi(")
             (str/includes? descriptor "sortedmulti("))) :segwit-multisig
    :else :unsupported))

(defn validate-info
  "Validate getdescriptorinfo output and return normalized public policy.
  This function trusts no browser-side descriptor classification."
  [{:keys [descriptor checksum isrange issolvable hasprivatekeys] :as info}]
  (when-not (and (string? descriptor)
                 (<= 8 (count descriptor) max-descriptor-length)
                 (string? checksum)
                 (re-matches #"[023456789acdefghjklmnpqrstuvwxyz]{8}" checksum))
    (throw (ex-info "Bitcoin Core returned invalid descriptor metadata."
                    {:type :bitcoin.node/invalid-descriptor-metadata})))
  (when hasprivatekeys
    (throw (ex-info "Private descriptors are forbidden."
                    {:type :bitcoin.node/private-descriptor})))
  (when-not issolvable
    (throw (ex-info "Descriptor is not solvable."
                    {:type :bitcoin.node/unsolvable-descriptor})))
  (let [descriptor-kind (kind descriptor)]
    (when (= :unsupported descriptor-kind)
      (throw (ex-info
              "Only Taproot and SegWit multisig vault descriptors are allowed."
              {:type :bitcoin.node/unsupported-descriptor})))
    {:descriptor descriptor
     :checksum checksum
     :kind descriptor-kind
     :ranged? (true? isrange)
     :solvable? true
     :private-keys? false
     :source (dissoc info :descriptor)}))
