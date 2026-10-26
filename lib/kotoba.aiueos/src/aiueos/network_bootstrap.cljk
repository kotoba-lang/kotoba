(ns aiueos.network-bootstrap
  "Which network interface may carry first boot, and which may be recorded as
  the machine's own network. Two questions, deliberately answered separately.

  R0 was wired DHCP only. A phone tethered over USB is the keyboard-free way to
  bootstrap a box that has no ethernet run to it: the phone already holds the
  credential, the cable is already in the box, and nothing is typed. But a
  phone walks away, so admitting it to carry first boot must not also record it
  as the network this machine depends on.

  Hence `bootstrap-decision` (may it carry first boot?) and `durability` (may it
  be persisted as this machine's network?) are different answers, and the
  receipt keeps them apart. A single `:ok?` would collapse them, and the
  collapse is the failure: the box comes up, the phone leaves, and the machine
  is unreachable with nothing in the record explaining why.

  Pure: probe facts in, decisions out. No I/O, no interface enumeration."
  (:require [kotoba.lang.text :as str]))

(def interface-classes
  "How an interface presents, and what that earns it.

  `:bootstrap?` -- may it carry first boot.
  `:durability` -- :durable is a link that belongs to this machine;
                   :ephemeral is a link that belongs to someone who will leave.

  `:unknown` is present on purpose and earns nothing: an interface we cannot
  classify must not fall through to the same answer as one we examined and
  admitted."
  {:pci-ethernet          {:bootstrap? true  :durability :durable   :note "an ethernet port on this machine"}
   :usb-ethernet-adapter  {:bootstrap? true  :durability :ephemeral :note "a USB NIC dongle: a real link, but removable hardware"}
   :usb-cdc-ncm           {:bootstrap? true  :durability :ephemeral :note "USB tether, CDC-NCM (Android, and iPhone over USB-C)"}
   :usb-cdc-ecm           {:bootstrap? true  :durability :ephemeral :note "USB tether, CDC-ECM"}
   :usb-rndis             {:bootstrap? true  :durability :ephemeral :note "USB tether, RNDIS (Android)"}
   :usb-ipheth            {:bootstrap? true  :durability :ephemeral :note "USB tether, Apple ipheth; needs a Trust tap on the phone"}
   :wifi-sta              {:bootstrap? false :durability :durable   :note "no native Wi-Fi driver yet; R0 does not bootstrap over Wi-Fi"}
   :loopback              {:bootstrap? false :durability :ephemeral :note "never a bootstrap path"}
   :unknown               {:bootstrap? false :durability :ephemeral :note "unclassified: refused rather than guessed"}})

(def tether-classes
  "The classes that are a phone sharing its connection."
  #{:usb-cdc-ncm :usb-cdc-ecm :usb-rndis :usb-ipheth})

(defn- addressing-refusal
  "An interface can be up and still not be on a network. These are the states
  that look like success from a distance:

  :link-local-only  a 169.254/16 or fe80::/10 address. The interface has an
                    address, `ip addr` prints it, and nothing routes. This is
                    the shape the workspace keeps meeting -- a check that could
                    not measure returning the value of a check that measured
                    and found nothing wrong.
  :none             no address at all.
  :static           allowed, but only when the caller says it meant it."
  [{:keys [addressing static-allowed?]}]
  (case addressing
    :dhcp nil
    :static (when-not static-allowed? :static-addressing-not-authorised)
    :link-local-only :link-local-only-is-not-a-network
    :none :no-address
    nil :addressing-unknown
    :addressing-unrecognised))

(defn bootstrap-decision
  "May this interface carry first boot? Returns
  {:ok? true :class ... :durability ... :tether? ...} or
  {:ok? false :reason <keyword>}.

  Fail-closed: a class this table does not list is `:unknown-interface-class`,
  not a pass."
  ([iface] (bootstrap-decision iface {}))
  ([{:keys [class carrier?] :as iface} {:keys [static-allowed?] :or {static-allowed? false}}]
   (let [spec (get interface-classes class)]
     (cond
       (nil? class) {:ok? false :reason :no-interface-class}
       (nil? spec) {:ok? false :reason :unknown-interface-class :class class}
       (not (:bootstrap? spec)) {:ok? false :reason :class-not-admitted-for-bootstrap :class class}
       (not (true? carrier?)) {:ok? false :reason :no-carrier :class class}
       :else
       (if-let [r (addressing-refusal (assoc iface :static-allowed? static-allowed?))]
         {:ok? false :reason r :class class}
         {:ok? true
          :class class
          :durability (:durability spec)
          :tether? (contains? tether-classes class)})))))

(defn durable?
  "May this interface be recorded as the machine's own network? Admitting an
  interface to carry first boot does not answer this, and answering it with the
  same value is the mistake this namespace exists to prevent."
  [iface]
  (let [d (bootstrap-decision iface)]
    (and (:ok? d) (= :durable (:durability d)))))

(def ^:private class-rank
  (zipmap [:pci-ethernet :usb-ethernet-adapter :usb-cdc-ncm :usb-cdc-ecm :usb-rndis :usb-ipheth]
          (range)))

(defn select
  "Choose the bootstrap interface from probed candidates.

  Unlike the install target disk, this RANKS rather than refuses when more than
  one candidate qualifies. The asymmetry is deliberate and is about
  reversibility: writing the wrong disk destroys data, so `install-v1` refuses
  ambiguity; choosing the wrong link is corrected by choosing again. Refusing
  here would strand a machine that has two working paths.

  Order: durable before ephemeral, then the class table's order, then interface
  name, so the same probe always yields the same answer.

  Returns {:ok? true :chosen {...} :alternatives [...] :refused [...]} or
  {:ok? false :reason :no-admissible-interface :refused [...]}."
  ([ifaces] (select ifaces {}))
  ([ifaces opts]
   (let [judged (map (fn [i] (assoc i :decision (bootstrap-decision i opts))) ifaces)
         admitted (filter (comp :ok? :decision) judged)
         refused (->> judged
                      (remove (comp :ok? :decision))
                      (mapv (fn [i] {:name (:name i) :reason (get-in i [:decision :reason])})))
         ranked (sort-by (fn [i]
                           [(if (= :durable (get-in i [:decision :durability])) 0 1)
                            (get class-rank (:class i) 99)
                            (str (:name i))])
                         admitted)]
     (if (empty? ranked)
       {:ok? false :reason :no-admissible-interface :refused refused}
       {:ok? true
        :chosen (first ranked)
        :alternatives (vec (rest ranked))
        :refused refused}))))

(defn receipt
  "What first boot records about how it got on the network.

  `:durable?` is stated on its own line rather than implied by the class,
  because the operator reading this later is asking exactly one question: is
  this machine still reachable if the phone leaves? When the answer is no, the
  receipt says what is still owed."
  [selection]
  (if-not (:ok? selection)
    {:aiueos.network-bootstrap/state :refused
     :reason (:reason selection)
     :refused (:refused selection)}
    (let [c (:chosen selection)
          d (:decision c)
          durable? (= :durable (:durability d))]
      (cond-> {:aiueos.network-bootstrap/state :bootstrapped
               :interface (:name c)
               :class (:class c)
               :tether? (:tether? d)
               :durable? durable?
               :alternatives (mapv :name (:alternatives selection))
               :refused (:refused selection)}
        (not durable?)
        (assoc :owed
               [:durable-network-not-yet-established
                :phone-may-disconnect-at-any-time]
               :must-not
               [:record-this-interface-as-the-machine-network])))))

(defn summary
  "One line for the console. Says which of the two questions was answered."
  [r]
  (case (:aiueos.network-bootstrap/state r)
    :refused (str "no bootstrap interface: "
                  (name (:reason r))
                  (when (seq (:refused r))
                    (str " (" (str/join ", " (map #(str (:name %) "=" (name (:reason %)))
                                                  (:refused r)))
                         ")")))
    :bootstrapped (str "bootstrapped on " (:interface r) " (" (name (:class r)) "); "
                       (if (:durable? r)
                         "durable"
                         "EPHEMERAL -- this machine has no network of its own yet"))))
