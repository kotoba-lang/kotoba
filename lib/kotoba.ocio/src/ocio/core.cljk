(ns ocio.core
  "OpenColorIO (OCIO) config as data — 'hiccup for colour management'. An .ocio config is YAML
   describing roles / displays / views / colorspaces and the transforms between them; this lets a
   colour pipeline be composable data you fork and diff like the rest of the kotoba.* world. The colour
   axis, adjacent to kotoba.usd / kotoba.gltf (which reference colorspaces). `.cljc`, serialized via
   kotoba.yaml; its OCIO `!<…>` tags use the historical kotoba.yaml/ytag contract.

   Builders return EDN that `config` serializes to an .ocio YAML string:
     (colorspace {:name \"ACEScg\" :family \"ACES\" :bitdepth \"32f\"
                  :to_reference (xf \"MatrixTransform\" {:matrix […]})})
     (view \"ACES\" \"ACEScg\")          → !<View> {name: ACES, colorspace: ACEScg}
     (display \"sRGB\" view…)
     (config {:version 2 :roles {…} :displays […] :colorspaces […]})"
  (:require [kotoba.yaml :as yaml]))

(defn xf
  "A named OCIO transform, e.g. (xf \"MatrixTransform\" {:matrix [...]})."
  [kind props] (yaml/ytag kind props))

(defn colorspace
  "A !<ColorSpace> entry (a property map)."
  [props] (yaml/ytag "ColorSpace" props))

(defn view
  "A !<View>: a name bound to a colorspace."
  [name colorspace] (yaml/ytag "View" {:name name :colorspace colorspace}))

(defn display
  "A display device name mapped to its ordered views."
  [name & views] {name (vec views)})

(defn config
  "Assemble an OCIO config map and serialize it to an .ocio YAML string. Keys mirror OCIO:
   :version :description :roles :displays :active_displays :active_views :colorspaces."
  [{:keys [version description roles displays active_displays active_views colorspaces]}]
  (yaml/yaml
   (cond-> {}
     version         (assoc :ocio_profile_version version)
     description      (assoc :description description)
     roles            (assoc :roles roles)
     displays         (assoc :displays (apply merge displays))
     active_displays  (assoc :active_displays active_displays)
     active_views     (assoc :active_views active_views)
     colorspaces      (assoc :colorspaces colorspaces))))
