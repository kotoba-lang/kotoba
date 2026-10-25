(ns kami-app-isekai.omniverse
  "ISEKAI Omniverse/PhysX/OpenUSD facade config data. Restored from
  kami-app-isekai's `omniverse.rs` (kami-engine/kami-app-isekai,
  deleted PR #82).

  The original module wired kami-usd (USDA parser)/kami-genesis
  (PhysX-shaped physics)/kami-articulated (URDF) into the ISEKAI
  runtime — a deep native FFI facade over multiple not-yet-restored
  (and largely out-of-scope, per ADR-2605261800 §D10.3/§G7's
  'kami-* facade only, no direct PhysX/OmniKit/OpenUSD imports'
  invariant) systems. Only the portable DATA — the default USDA scene
  description text — is ported here; the parse/physics-tick/wasm-
  bindgen orchestration is native substrate and NOT ported.")

(def default-isekai-usda
  "Built-in USDA used when the JS side does not supply a custom one.
  One PhysicsScene + a ground plane + one Cartpole articulation that
  spawns above the demo house at the same world coordinates as the
  v3-demos paper-row so the camera framing matches the existing
  scenes."
  "#usda 1.0
(
    upAxis = \"Y\"
    metersPerUnit = 1.0
)

def PhysicsScene \"physics\"
{
    vector3f physics:gravityDirection = (0, -1, 0)
    float physics:gravityMagnitude = 9.81
}

def Plane \"ground\"
{
    double3 xformOp:translate = (0, 0, 0)
    double width = 32.0
    double length = 32.0
}

def Cartpole \"cart_alpha\"
{
    double3 xformOp:translate = (-11, 33.5, 18)
    custom string urdf = \"@./cartpole.urdf@\"
}
")
