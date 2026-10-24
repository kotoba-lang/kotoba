(ns apn.validate
  "Structural checks over an apn.model topology — never throws, returns a
  vector of problem maps. Pure, no I/O — portable .cljc."
  (:require [apn.model :as m]))

(defn- dangling-link-endpoint-problems
  [sys]
  (for [l (m/links sys)
        end [:apn/a :apn/z]
        :let [node-id (get l end)]
        :when (nil? (m/node-by-id sys node-id))]
    {:apn/error :dangling-link-endpoint :apn/link (:apn/id l)
     :apn/end end :apn/node node-id}))

(defn- dangling-lightpath-node-problems
  [sys]
  (for [lp (m/lightpaths sys)
        end [:apn/src :apn/dst]
        :let [node-id (get lp end)]
        :when (nil? (m/node-by-id sys node-id))]
    {:apn/error :dangling-lightpath-node :apn/lightpath (:apn/id lp)
     :apn/end end :apn/node node-id}))

(defn- dangling-lightpath-link-problems
  [sys]
  (for [lp (m/lightpaths sys)
        link-id (:apn/path lp)
        :when (nil? (m/link-by-id sys link-id))]
    {:apn/error :dangling-lightpath-link :apn/lightpath (:apn/id lp)
     :apn/link link-id}))

(defn- walk-path
  "Walk path from src; returns the node reached, or nil if any hop doesn't
  connect to the current node (a link on the path, or a dangling link, that
  doesn't touch where the walk currently is)."
  [sys path src]
  (reduce (fn [current link-id]
            (if (nil? current)
              (reduced nil)
              (let [l (m/link-by-id sys link-id)]
                (when l (m/other-end l current)))))
          src path))

(defn- path-connectivity-problems
  [sys]
  (for [lp (m/lightpaths sys)
        :when (every? #(m/link-by-id sys %) (:apn/path lp))
        :let [reached (walk-path sys (:apn/path lp) (:apn/src lp))]
        :when (not= reached (:apn/dst lp))]
    {:apn/error :path-not-connected :apn/lightpath (:apn/id lp)
     :apn/expected-dst (:apn/dst lp) :apn/reached reached}))

(defn- wavelength-unavailable-problems
  [sys]
  (for [lp (m/lightpaths sys)
        link-id (:apn/path lp)
        :let [l (m/link-by-id sys link-id)]
        :when (and l (not (contains? (:apn/channels l) (:apn/wavelength lp))))]
    {:apn/error :wavelength-not-in-grid :apn/lightpath (:apn/id lp)
     :apn/link link-id :apn/wavelength (:apn/wavelength lp)}))

(defn- lightpaths-using-link
  [sys link-id]
  (filter #(some #{link-id} (:apn/path %)) (m/lightpaths sys)))

(defn- wavelength-clash-problems
  [sys]
  (for [l (m/links sys)
        :let [by-wavelength (group-by :apn/wavelength
                                       (lightpaths-using-link sys (:apn/id l)))]
        [wavelength holders] by-wavelength
        :when (> (count holders) 1)]
    {:apn/error :wavelength-clash :apn/link (:apn/id l) :apn/wavelength wavelength
     :apn/lightpaths (mapv :apn/id holders)}))

(defn validate
  [sys]
  (vec (concat (dangling-link-endpoint-problems sys)
               (dangling-lightpath-node-problems sys)
               (dangling-lightpath-link-problems sys)
               (path-connectivity-problems sys)
               (wavelength-unavailable-problems sys)
               (wavelength-clash-problems sys))))

(defn valid?
  [sys]
  (empty? (validate sys)))
