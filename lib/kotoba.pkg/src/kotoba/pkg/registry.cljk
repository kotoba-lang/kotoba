(ns kotoba.pkg.registry
  "Package geometry & thermal-model registry — data only, no domain logic,
  no IO, no requires. Portable across JVM / ClojureScript / SCI / GraalVM.

  `default-registry` mirrors resources/kotoba/pkg/registry.edn, which is
  the human-editable EDN authority for these values (kept in sync by
  kotoba.pkg.registry-test on the JVM, where classpath resource IO is
  available).")

(def resource-path "kotoba/pkg/registry.edn")

(def default-registry
  {:qfp   {:body-clearance-mm 2.0
           :body-z-mm 1.4}
   :bga   {:body-clearance-mm 1.0
           :body-z-mm 1.2}
   :csp   {:body-clearance-mm 0.5
           :body-z-mm 0.8}
   :wlcsp {:body-z-mm 0.5}

   :sip          {:die-multiplier-x 2.5
                  :die-multiplier-y 2.5
                  :body-z-mm 2.0
                  :fixed-pin-count 256}
   :chiplet-2-5d {:die-multiplier-x 3.0
                  :die-multiplier-y 2.0
                  :body-z-mm 1.5
                  :fixed-pin-count 512}
   :chiplet-3d   {:die-multiplier-x 1.5
                  :die-multiplier-y 1.5
                  :body-z-mm 2.5
                  :fixed-pin-count 1024}

   :thermal-estimation {:base-theta-jc 0.5
                         :area-coeff-jc 20.0
                         :area-coeff-ca 30.0}

   :airflow-model {:reduction-exponent 0.5}})

(def registry
  "Effective registry used by default across kotoba.pkg.* domain fns."
  default-registry)
