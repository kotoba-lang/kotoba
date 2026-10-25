# kami-engine-cad

Portable CAD geometry engine. The initial stable primitive is a rational Bezier span, the fundamental NURBS-compatible curve evaluator; knots, surfaces, trim, loft, sweep and tessellation extend this EDN contract.

Solids come from two generators: `extrude-polygon` (prismatic, planar cross-section × extrusion vector) and `revolve` (open XZ-plane profile revolved about the Z axis — the axisymmetric sibling, for cylinders, cones, and closed-of-revolution shells). Both return watertight `:cad/kind :solid` values that `solid-mesh` / `solid-volume` consume. The boolean ops below accept only `extrude-polygon` prisms and refuse other solids loudly. Polygon extrusion supports a single convex hole (`extrude-polygon-with-holes`) for tube/annular solids such as a cartridge body pierced by a flow channel.
