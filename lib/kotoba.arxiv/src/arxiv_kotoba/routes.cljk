(ns arxiv-kotoba.routes)

(defn route-supports?
  [op route]
  (contains? (set (:route/capabilities route)) op))

(defn route-available?
  [available route]
  (or (nil? available)
      (contains? (set available) (:route/kind route))
      (contains? (set available) (:route/id route))))

(defn choose-route
  "Select the preferred yorishiro route for an op.

  `ctx` may include `:available-surfaces`, a set of route kinds or ids such as
  `#{:api :browser}` or `#{:browser-dom}`."
  [yorishiro op ctx]
  (->> (:yorishiro/surfaces yorishiro)
       (filter #(route-supports? op %))
       (filter #(route-available? (:available-surfaces ctx) %))
       (sort-by :route/prefer)
       first))

