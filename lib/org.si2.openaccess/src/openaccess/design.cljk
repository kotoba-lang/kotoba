(ns openaccess.design
  "Simplified OpenAccess design (view) contents: shapes plus hierarchical
  instances, and the 2D transform math that places an instance's child
  geometry into its parent's coordinate system.

    design   := {:shapes [shape] :instances [instance]}
    instance := {:cell-ref string? :view-ref keyword? :transform transform}
    transform := {:offset [x y] :orientation orientation}
    orientation := :R0 | :R90 | :R180 | :R270 | :MX | :MY | :MXR90 | :MYR90

  `orientation` is one of the 8 Manhattan (axis-aligned) orientations of
  the dihedral group of the square: the 4 rotations `R0`/`R90`/`R180`/
  `R270` (0/90/180/270 degrees counterclockwise) and the 4 reflections
  `MX`/`MY` (mirror about the X axis / Y axis) and `MXR90`/`MYR90`
  (mirror about the diagonal `y=x` / anti-diagonal `y=-x` — equivalently
  `MX` then `R90`, and `MY` then `R90`, composed about the origin).
  Arbitrary-angle rotation is out of scope for this restoration (as it
  is for LEF/DEF-style Manhattan placement in general).")

(defn instance
  "Construct an instance of the `view-ref` view of the cell named
  `cell-ref`, placed via `offset` (`[x y]`) and `orientation` (one of
  the 8 Manhattan orientations)."
  [cell-ref view-ref offset orientation]
  {:cell-ref cell-ref :view-ref view-ref
   :transform {:offset offset :orientation orientation}})

(defn design
  "Construct a design (view contents) from `shapes` and `instances`."
  [shapes instances]
  {:shapes shapes :instances instances})

(defn- orient-point
  "Apply `orientation` alone (about the origin, no offset) to local point
  `[x y]`. This is the linear (rotation/reflection) part of an instance
  transform; see `instance-transform-point` for the full affine
  transform including translation by the instance's offset."
  [orientation [x y]]
  (case orientation
    :R0    [x y]
    :R90   [(- y) x]
    :R180  [(- x) (- y)]
    :R270  [y (- x)]
    :MX    [x (- y)]
    :MY    [(- x) y]
    :MXR90 [y x]
    :MYR90 [(- y) (- x)]))

(defn instance-transform-point
  "Apply `inst`'s `:transform` (`orient-point` followed by translation by
  `:offset`) to local point `local` (`[x y]`, in the instance's own
  child-view coordinate system), returning the corresponding point in
  the parent design's coordinate system."
  [inst local]
  (let [{:keys [offset orientation]} (:transform inst)
        [ox oy] offset
        [rx ry] (orient-point orientation local)]
    [(+ rx ox) (+ ry oy)]))
