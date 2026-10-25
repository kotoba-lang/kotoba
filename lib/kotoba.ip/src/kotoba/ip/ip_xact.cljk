(ns kotoba.ip.ip-xact
  "IP-XACT component catalog and XML export.

  Ported from kami-engine's `kami-ip` Rust crate (`src/ip_xact.rs`). Pure
  data + string generation — no network, no I/O, no GPU. Portable `.cljc`
  across JVM / ClojureScript.")

;; ---------------------------------------------------------------------------
;; Vocabulary
;; ---------------------------------------------------------------------------

(def bus-types
  "Standard bus protocol types."
  #{:axi4 :axi4-lite :ahb :apb :wishbone :tile-link :avalon})

(def interface-modes
  "Bus interface mode."
  #{:master :slave :system})

(def port-directions
  "Port direction."
  #{:in :out :in-out})

(def resolve-types
  "Parameter resolve type."
  #{:immediate :user :generated})

(def xml-schema
  "IEEE 1685-2014 (IP-XACT) XML export constants."
  {:declaration "<?xml version=\"1.0\" encoding=\"UTF-8\"?>"
   :xmlns "http://www.accellera.org/XMLSchema/IPXACT/1685-2014"})

;; ---------------------------------------------------------------------------
;; Constructors
;; ---------------------------------------------------------------------------

(defn port-map
  "Mapping between logical and physical port names."
  [logical physical]
  {:logical logical :physical physical})

(defn bus-interface
  "Bus interface on a component. `mode` is one of `interface-modes`."
  [interface-name bus-type mode port-maps]
  {:name interface-name :bus-type bus-type :mode mode :port-maps (vec port-maps)})

(defn ip-port
  "A component port. `direction` is one of `port-directions`."
  [port-name direction width]
  {:name port-name :direction direction :width width})

(defn ip-param
  "A configurable parameter on a component. `resolve` is one of
  `resolve-types`; `value` is the parameter value as a string."
  [param-name value resolve]
  {:name param-name :value value :resolve resolve})

(defn ip-xact-component
  "An IP-XACT component description (VLNV: vendor/library/name/version)."
  [{:keys [vendor library name version bus-interfaces ports parameters]}]
  {:vendor vendor
   :library library
   :name name
   :version version
   :bus-interfaces (vec bus-interfaces)
   :ports (vec ports)
   :parameters (vec parameters)})

(defn ip-catalog
  "Catalog of IP components."
  ([] {:components []})
  ([components] {:components (vec components)}))

(defn find-by-bus-type
  "Find components in `catalog` that expose a specific bus type."
  [catalog bus-type]
  (filterv (fn [component]
             (some #(= bus-type (:bus-type %)) (:bus-interfaces component)))
           (:components catalog)))

;; ---------------------------------------------------------------------------
;; IEEE 1685-2014 XML export
;; ---------------------------------------------------------------------------

(defn- mode-str [mode]
  (case mode :master "master" :slave "slave" :system "system"))

(defn- direction-str [direction]
  (case direction :in "in" :out "out" :in-out "inout"))

(defn- resolve-str [resolve]
  (case resolve :immediate "immediate" :user "user" :generated "generated"))

(defn- port-map-xml [{:keys [logical physical]}]
  (str "        <ipxact:portMap>\n"
       "          <ipxact:logicalPort><ipxact:name>" logical "</ipxact:name></ipxact:logicalPort>\n"
       "          <ipxact:physicalPort><ipxact:name>" physical "</ipxact:name></ipxact:physicalPort>\n"
       "        </ipxact:portMap>\n"))

(defn- bus-interface-xml [{:keys [name mode port-maps]}]
  (str "    <ipxact:busInterface>\n"
       "      <ipxact:name>" name "</ipxact:name>\n"
       "      <ipxact:" (mode-str mode) "/>\n"
       (when (seq port-maps)
         (str "      <ipxact:portMaps>\n"
              (apply str (map port-map-xml port-maps))
              "      </ipxact:portMaps>\n"))
       "    </ipxact:busInterface>\n"))

(defn- port-xml [{:keys [name direction width]}]
  (str "      <ipxact:port>\n        <ipxact:name>" name "</ipxact:name>\n"
       "        <ipxact:wire><ipxact:direction>" (direction-str direction) "</ipxact:direction>\n"
       "          <ipxact:vectors><ipxact:vector><ipxact:left>" (max 0 (dec width))
       "</ipxact:left><ipxact:right>0</ipxact:right></ipxact:vector></ipxact:vectors>\n"
       "        </ipxact:wire>\n      </ipxact:port>\n"))

(defn- param-xml [{:keys [name value resolve]}]
  (str "    <ipxact:parameter resolve=\"" (resolve-str resolve) "\">\n"
       "      <ipxact:name>" name "</ipxact:name>\n"
       "      <ipxact:value>" value "</ipxact:value>\n"
       "    </ipxact:parameter>\n"))

(defn export-ip-xact-xml
  "Export an IP-XACT component to IEEE 1685-2014 XML format."
  [{:keys [vendor library name version bus-interfaces ports parameters]}]
  (str (:declaration xml-schema) "\n"
       "<ipxact:component xmlns:ipxact=\"" (:xmlns xml-schema) "\">\n"
       "  <ipxact:vendor>" vendor "</ipxact:vendor>\n"
       "  <ipxact:library>" library "</ipxact:library>\n"
       "  <ipxact:name>" name "</ipxact:name>\n"
       "  <ipxact:version>" version "</ipxact:version>\n"
       (when (seq bus-interfaces)
         (str "  <ipxact:busInterfaces>\n"
              (apply str (map bus-interface-xml bus-interfaces))
              "  </ipxact:busInterfaces>\n"))
       (when (seq ports)
         (str "  <ipxact:model>\n    <ipxact:ports>\n"
              (apply str (map port-xml ports))
              "    </ipxact:ports>\n  </ipxact:model>\n"))
       (when (seq parameters)
         (str "  <ipxact:parameters>\n"
              (apply str (map param-xml parameters))
              "  </ipxact:parameters>\n"))
       "</ipxact:component>\n"))
