(ns demo)

#?(:kotoba
   (defn main []
     (+ 100 23))

   :clj
   (defn main []
     (+ 1 2))

   :cljs
   (defn main []
     (+ 10 20)))
