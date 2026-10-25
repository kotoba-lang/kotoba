(ns ip-xact.component
  "IP-XACT component catalog and XML export. Restored from kami-ip's
  `ip_xact` module (kami-engine/kami-ip/src/ip_xact.rs, deleted PR #82).")

(def bus-types #{:axi4 :axi4-lite :ahb :apb :wishbone :tile-link :avalon})
(def interface-modes #{:master :slave :system})
(def port-directions #{:in :out :in-out})
(def resolve-types #{:immediate :user :generated})

(defn port-map [logical physical] {:logical logical :physical physical})

(defn bus-interface [name bus-type mode port-maps]
  {:name name :bus-type bus-type :mode mode :port-maps (vec port-maps)})

(defn ip-port [name direction width] {:name name :direction direction :width width})

(defn ip-param [name value resolve] {:name name :value value :resolve resolve})

(defn ip-xact-component
  [{:keys [vendor library name version bus-interfaces ports parameters]}]
  {:vendor vendor :library library :name name :version version
   :bus-interfaces (vec bus-interfaces) :ports (vec ports) :parameters (vec parameters)})

(defn catalog
  "A fresh, empty IP catalog."
  []
  {:components []})

(defn add-component [cat component] (update cat :components conj component))

(defn find-by-bus-type
  "Components that expose `bus-type` on any of their bus interfaces."
  [cat bus-type]
  (vec (filter (fn [c] (some #(= (:bus-type %) bus-type) (:bus-interfaces c))) (:components cat))))

(defn- mode-str [mode] (case mode :master "master" :slave "slave" :system "system"))
(defn- dir-str [dir] (case dir :in "in" :out "out" :in-out "inout"))
(defn- resolve-str [r] (case r :immediate "immediate" :user "user" :generated "generated"))

(defn export-ip-xact-xml
  "Export `component` to IEEE 1685-2014 XML format."
  [component]
  (str "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
       "<ipxact:component xmlns:ipxact=\"http://www.accellera.org/XMLSchema/IPXACT/1685-2014\">\n"
       "  <ipxact:vendor>" (:vendor component) "</ipxact:vendor>\n"
       "  <ipxact:library>" (:library component) "</ipxact:library>\n"
       "  <ipxact:name>" (:name component) "</ipxact:name>\n"
       "  <ipxact:version>" (:version component) "</ipxact:version>\n"

       (when (seq (:bus-interfaces component))
         (str "  <ipxact:busInterfaces>\n"
              (apply str
                     (for [bi (:bus-interfaces component)]
                       (str "    <ipxact:busInterface>\n"
                            "      <ipxact:name>" (:name bi) "</ipxact:name>\n"
                            "      <ipxact:" (mode-str (:mode bi)) "/>\n"
                            (when (seq (:port-maps bi))
                              (str "      <ipxact:portMaps>\n"
                                   (apply str
                                          (for [pm (:port-maps bi)]
                                            (str "        <ipxact:portMap>\n"
                                                 "          <ipxact:logicalPort><ipxact:name>" (:logical pm) "</ipxact:name></ipxact:logicalPort>\n"
                                                 "          <ipxact:physicalPort><ipxact:name>" (:physical pm) "</ipxact:name></ipxact:physicalPort>\n"
                                                 "        </ipxact:portMap>\n")))
                                   "      </ipxact:portMaps>\n"))
                            "    </ipxact:busInterface>\n")))
              "  </ipxact:busInterfaces>\n"))

       (when (seq (:ports component))
         (str "  <ipxact:model>\n    <ipxact:ports>\n"
              (apply str
                     (for [port (:ports component)]
                       (str "      <ipxact:port>\n        <ipxact:name>" (:name port) "</ipxact:name>\n"
                            "        <ipxact:wire><ipxact:direction>" (dir-str (:direction port)) "</ipxact:direction>\n"
                            "          <ipxact:vectors><ipxact:vector><ipxact:left>" (max 0 (dec (:width port)))
                            "</ipxact:left><ipxact:right>0</ipxact:right></ipxact:vector></ipxact:vectors>\n"
                            "        </ipxact:wire>\n      </ipxact:port>\n")))
              "    </ipxact:ports>\n  </ipxact:model>\n"))

       (when (seq (:parameters component))
         (str "  <ipxact:parameters>\n"
              (apply str
                     (for [p (:parameters component)]
                       (str "    <ipxact:parameter resolve=\"" (resolve-str (:resolve p)) "\">\n"
                            "      <ipxact:name>" (:name p) "</ipxact:name>\n"
                            "      <ipxact:value>" (:value p) "</ipxact:value>\n"
                            "    </ipxact:parameter>\n")))
              "  </ipxact:parameters>\n"))

       "</ipxact:component>\n"))
